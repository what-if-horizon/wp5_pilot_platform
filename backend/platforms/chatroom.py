import asyncio #for async operations
import random #for RNG
import re #for regex 
#from pathlib import Path 
from typing import Callable, Optional #for type hints
from datetime import datetime #for datetime operations

from models import Message, Agent, SessionState #required data models for this platform
from utils import Logger #logging utility
from utils.config_loader import load_config, validate_sim_config #for TOML handling
from utils.llm.llm_manager import LLMManager #LLM manager for handling LLM business
from agents.agent_manager import AgentManager #Agent manager for handling agent business


class SimulationSession:
    """Core platform logic for a chatroom session.

    Responsibilities:
    - manages platform event loop / opportunity structure (the "pull")
    - delegates agent decisions/actions to `AgentManager` (the "push")
    - wiring platform-level config, lifecycle and websocket attachment

    """
    def __init__(self, session_id: str, websocket_send: Callable, treatment_group: str, user_name: str = "user"):
        self.session_id = session_id  #this user-session identifier string

        # Wrap provided websocket_send so we can apply per-sender blocking rules
        # (suppress future messages from blocked senders while keeping past messages visible).
        # NOTE: this allows for the 'block_agent' user feature to work correctly.
        original_send = websocket_send or self._noop_send
        self.websocket_send = self._wrap_send(original_send)
        self.logger = Logger(session_id)

        # Load experimental configs and map this user-session to a specified treatment group (validate).
        self.experimental_settings_full = load_config("config/experimental_settings.toml")
        if not (isinstance(self.experimental_settings_full, dict) and "groups" in self.experimental_settings_full):
            raise RuntimeError("experimental_settings.toml must define a top-level 'groups' table mapping treatment names to configs")
        group_map = self.experimental_settings_full["groups"]
        if treatment_group not in group_map:
            raise RuntimeError(f"treatment_group '{treatment_group}' not found in experimental_settings.toml groups")
        self.experimental_config = group_map[treatment_group]
        self.treatment_group = treatment_group

        # Load and validate simulation config (strict; no fallbacks!)
        self.simulation_config = validate_sim_config("config/simulation_settings.toml")

        # Create LLM manager from validated simulation config
        self.llm_manager = LLMManager.from_simulation_config(self.simulation_config)

        # Set session RNG seed from the validated simulation config
        self._rng = random.Random(int(self.simulation_config["random_seed"]))

        # Initialize session state with named agents 
        agent_names = self.simulation_config["agent_names"]
        agents = [Agent(name=name) for name in agent_names]

        # Create session state with all components so far
        self.state = SessionState(
            session_id=session_id,
            agents=agents,
            duration_minutes=self.simulation_config["session_duration_minutes"],
            experimental_config=self.experimental_config,
            treatment_group=treatment_group,
            simulation_config=self.simulation_config,
            user_name=user_name,
        )

        # Create the agent manager to handle agent selection/action when called up by simulation ticks
        self.agent_manager = AgentManager(
            state=self.state,
            llm_manager=self.llm_manager,
            logger=self.logger,
            websocket_send=self.websocket_send,
            simulation_config=self.simulation_config,
            rng=self._rng,
        )

        # Initialize agent dynamics based on experimental configs 
        # e.g., chattiness and attention
        self.agent_manager.assign_agent_dynamics(self.simulation_config)
   
        # Assign agent prompt keys/makeup based on experimental configs.
        self.agent_manager.assign_agent_prompts(self.experimental_settings_full)

        # Clock task and running flag
        self.clock_task: Optional[asyncio.Task] = None
        self.running = False

    # Start the session (launch the simulation loop)
    async def start(self) -> None:
        self.running = True
        self.logger.log_session_start(self.experimental_config, self.simulation_config, self.treatment_group)
        self.clock_task = asyncio.create_task(self._clock_loop())
        print(f"Session {self.session_id} started")

    # Stop the session (stop the simulation loop)
    async def stop(self, reason: str = "completed") -> None:
        self.running = False
        if self.clock_task:
            self.clock_task.cancel()
            try:
                await self.clock_task
            except asyncio.CancelledError:
                pass
        self.logger.log_session_end(reason)
        print(f"Session {self.session_id} stopped: {reason}")

    # Main simulation loop logic lives here - 
    async def _clock_loop(self) -> None:
        tick_interval = 1.0
        mpm = self.simulation_config["messages_per_minute"]
        post_probability = mpm / 60.0

        while self.running:
            try: #First, check if session expired (max. duration)
                if self.state.is_expired():
                    await self.stop(reason="duration_expired")
                    break
                # Second, apply per-tick agent updates (attention decay, etc.)
                try:
                    await self.agent_manager.on_tick()
                except Exception:
                    pass
                # Third, if user response is pending, handle that with priority:
                if self.state.pending_user_response:
                    # Delegate agent selection and action for a user-triggered (foreground) response
                    agent = self.agent_manager.select_agent(context_type="foreground")
                    if agent:
                        await self.agent_manager.agent_post_message(agent, context_type="foreground")
                    self.state.pending_user_response = False

                # Fourth, create background posts based on post_probability:
                elif self._rng.random() < post_probability:
                    agent = self.agent_manager.select_agent(context_type="background")
                    if agent:
                        await self.agent_manager.agent_post_message(agent, context_type="background")

                await asyncio.sleep(tick_interval)

            # Handle cancellation and errors
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.log_error("clock_loop", str(e))
                print(f"Error in clock loop: {e}")

    # Handle (incoming) user message sent via websocket
    async def handle_user_message(self, content: str, reply_to: Optional[str] = None, quoted_text: Optional[str] = None, mentions: Optional[list] = None) -> None:
        message = Message.create(sender=self.state.user_name, content=content, reply_to=reply_to, quoted_text=quoted_text, mentions=mentions)
        self.state.add_message(message) #add to session state
        self.logger.log_message(message.to_dict()) #log the message

        #trigger an agent response based on user_response_probability
        response_prob = self.simulation_config["user_response_probability"]
        if self._rng.random() < response_prob:
            self.state.pending_user_response = True
    # A no-op send function for detached websockets
    async def _noop_send(self, message: dict) -> None:
        return

    # Wrapper that checks blocked_agents before sending a message.
    # This allows for the 'block_agent' user feature to work correctly.
    def _wrap_send(self, send_callable: Callable):
        """Return an async wrapper that checks blocked_agents before sending a message.

        send_callable is expected to be an async function accepting a message dict.
        """
        async def wrapper(message_dict: dict):
            try:
                sender = message_dict.get("sender")
                # If sender is blocked, and the message timestamp is >= blocked time, suppress it
                if sender and hasattr(self.state, "blocked_agents") and sender in self.state.blocked_agents:
                    blocked_iso = self.state.blocked_agents.get(sender)
                    if blocked_iso:
                        try:
                            msg_time = datetime.fromisoformat(message_dict.get("timestamp"))
                            blocked_time = datetime.fromisoformat(blocked_iso)
                            if msg_time >= blocked_time:
                                # Suppress sending this message to the client
                                return
                        except Exception:
                            # If parsing fails, fall back to sending (safer)
                            pass
                await send_callable(message_dict)
            except Exception as e:
                # don't let send failures crash the session
                try:
                    self.logger.log_error("send", str(e))
                except Exception:
                    pass

        return wrapper

    #function to re-attach websocket and replay missed messages
    async def attach_websocket(self, websocket_send: Callable) -> None:
        # Wrap the provided send function so per-sender blocking is enforced
        self.websocket_send = self._wrap_send(websocket_send)
        # update actor manager's websocket sender to the wrapped sender
        self.agent_manager.set_websocket_send(self.websocket_send)
        # Replay existing messages to the client (best-effort)
        replayed = 0
        for m in self.state.messages:
            try:
                await self.websocket_send(m.to_dict())
                replayed += 1
            except Exception:
                continue
        # Log websocket attach with the number of replayed messages for auditability
        try:
            self.logger.log_event("websocket_attach", {"replayed_messages": replayed})
        except Exception:
            pass
    
    #corresponding detach function
    def detach_websocket(self) -> None:
        self.websocket_send = self._noop_send
        self.agent_manager.set_websocket_send(None)
        # Log websocket detach so reconnections are visible in logs
        try:
            self.logger.log_event("websocket_detach", {})
        except Exception:
            pass

    
