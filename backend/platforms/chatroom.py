import asyncio
import random
from typing import Callable, Optional
from datetime import datetime

from models import Message, Agent, SessionState
from utils import Logger
from utils.config_loader import load_config, validate_sim_config
from utils.llm.llm_manager import LLMManager
from agents.agent_manager import AgentManager
from agents.STAGE.orchestrator import Orchestrator
from scenarios import load_scenario


class SimulationSession:
    """Core platform logic for a chatroom session (STAGE framework).

    Responsibilities:
    - manages platform event loop with tick-based pacing
    - delegates all agent decisions to the Director->Performer pipeline
      via the Orchestrator and AgentManager
    - wiring platform-level config, lifecycle and websocket attachment
    """

    def __init__(self, session_id: str, websocket_send: Callable, treatment_group: str, user_name: str = "user"):
        self.session_id = session_id

        # Wrap provided websocket_send so we can apply per-sender blocking rules
        original_send = websocket_send or self._noop_send
        self.websocket_send = self._wrap_send(original_send)
        self.logger = Logger(session_id)

        # Load experimental configs and resolve the treatment string for the Director
        self.experimental_settings_full = load_config("config/experimental_settings.toml")
        if not (isinstance(self.experimental_settings_full, dict) and "groups" in self.experimental_settings_full):
            raise RuntimeError("experimental_settings.toml must define a top-level 'groups' table")
        group_map = self.experimental_settings_full["groups"]
        if treatment_group not in group_map:
            raise RuntimeError(f"treatment_group '{treatment_group}' not found in experimental_settings.toml groups")
        self.experimental_config = group_map[treatment_group]
        self.treatment_group = treatment_group

        # Extract the treatment description string for the Director prompt
        self.treatment = self.experimental_config.get("treatment", "")
        if not self.treatment:
            raise RuntimeError(f"treatment_group '{treatment_group}' has no 'treatment' description")

        # Extract shared chatroom context (platform, locale, language, etc.)
        self.chatroom_context = self.experimental_settings_full.get("chatroom_context", "")

        # Load and validate simulation config
        self.simulation_config = validate_sim_config("config/simulation_settings.toml")

        # Create two LLM managers: one for the Director, one for the Performer
        self.director_llm = LLMManager.from_simulation_config(self.simulation_config, role="director")
        self.performer_llm = LLMManager.from_simulation_config(self.simulation_config, role="performer")

        # Set session RNG seed
        self._rng = random.Random(int(self.simulation_config["random_seed"]))

        # Initialize session state with named agents
        agent_names = self.simulation_config["agent_names"]
        agents = [Agent(name=name) for name in agent_names]

        self.state = SessionState(
            session_id=session_id,
            agents=agents,
            duration_minutes=self.simulation_config["session_duration_minutes"],
            experimental_config=self.experimental_config,
            treatment_group=treatment_group,
            simulation_config=self.simulation_config,
            user_name=user_name,
        )

        # Create the orchestrator (Director->Performer pipeline)
        orchestrator = Orchestrator(
            director_llm=self.director_llm,
            performer_llm=self.performer_llm,
            state=self.state,
            logger=self.logger,
            context_window_size=int(self.simulation_config["context_window_size"]),
            chatroom_context=self.chatroom_context,
        )

        # Load the experiment scenario (defaults to BaseScenario / no-op)
        self.scenario = load_scenario(self.experimental_config)

        # Create the agent manager wired to the orchestrator
        self.agent_manager = AgentManager(
            state=self.state,
            orchestrator=orchestrator,
            logger=self.logger,
            websocket_send=self.websocket_send,
            typing_delay_seconds=self.simulation_config["typing_delay_seconds"],
        )

        # Clock task and running flag
        self.clock_task: Optional[asyncio.Task] = None
        self.running = False

    async def start(self) -> None:
        """Start the session (launch the simulation loop)."""
        self.running = True
        self.logger.log_session_start(self.experimental_config, self.simulation_config, self.treatment_group)
        await self.scenario.seed(self.state, self.websocket_send)
        self.clock_task = asyncio.create_task(self._clock_loop())
        print(f"Session {self.session_id} started")

    async def stop(self, reason: str = "completed") -> None:
        """Stop the session (stop the simulation loop)."""
        self.running = False
        if self.clock_task:
            self.clock_task.cancel()
            try:
                await self.clock_task
            except asyncio.CancelledError:
                pass
        self.logger.log_session_end(reason)
        print(f"Session {self.session_id} stopped: {reason}")

    async def _clock_loop(self) -> None:
        """Main simulation loop.

        Uses tick-based pacing with messages_per_minute probability gate.
        On each triggered tick, the Director decides which agent acts and how,
        then the Performer generates the actual message.
        """
        tick_interval = 1.0
        mpm = self.simulation_config["messages_per_minute"]
        post_probability = mpm / 60.0

        while self.running:
            try:
                # Check if session expired
                if self.state.is_expired():
                    await self.stop(reason="duration_expired")
                    break

                # Scenario gate: check whether agents should be active yet
                if not self.scenario.agents_active(self.state):
                    await asyncio.sleep(tick_interval)
                    continue

                # Probability gate: should we trigger a Director->Performer turn?
                if self._rng.random() < post_probability:
                    await self.agent_manager.execute_turn(self.treatment)

                await asyncio.sleep(tick_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.log_error("clock_loop", str(e))
                print(f"Error in clock loop: {e}")

    async def handle_user_message(self, content: str, reply_to: Optional[str] = None, quoted_text: Optional[str] = None, mentions: Optional[list] = None) -> None:
        """Handle an incoming user message.

        The message is added to the chat log. The Director will see it
        on the next regular loop iteration and decide how to respond.
        """
        message = Message.create(sender=self.state.user_name, content=content, reply_to=reply_to, quoted_text=quoted_text, mentions=mentions)
        self.state.add_message(message)
        self.logger.log_message(message.to_dict())

    async def _noop_send(self, message: dict) -> None:
        return

    def _wrap_send(self, send_callable: Callable):
        """Return an async wrapper that checks blocked_agents before sending."""
        async def wrapper(message_dict: dict):
            try:
                sender = message_dict.get("sender")
                if sender and hasattr(self.state, "blocked_agents") and sender in self.state.blocked_agents:
                    blocked_iso = self.state.blocked_agents.get(sender)
                    if blocked_iso:
                        try:
                            msg_time = datetime.fromisoformat(message_dict.get("timestamp"))
                            blocked_time = datetime.fromisoformat(blocked_iso)
                            if msg_time >= blocked_time:
                                return
                        except Exception:
                            pass
                await send_callable(message_dict)
            except Exception as e:
                try:
                    self.logger.log_error("send", str(e))
                except Exception:
                    pass

        return wrapper

    async def attach_websocket(self, websocket_send: Callable) -> None:
        """Re-attach websocket and replay missed messages."""
        self.websocket_send = self._wrap_send(websocket_send)
        self.agent_manager.set_websocket_send(self.websocket_send)
        replayed = 0
        for m in self.state.messages:
            try:
                await self.websocket_send(m.to_dict())
                replayed += 1
            except Exception:
                continue
        try:
            self.logger.log_event("websocket_attach", {"replayed_messages": replayed})
        except Exception:
            pass

    def detach_websocket(self) -> None:
        """Detach websocket (session keeps running for reconnection)."""
        self.websocket_send = self._noop_send
        self.agent_manager.set_websocket_send(None)
        try:
            self.logger.log_event("websocket_detach", {})
        except Exception:
            pass
