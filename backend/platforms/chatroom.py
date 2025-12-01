import asyncio
import random
import re
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime

from models import Message, Agent, SessionState
from utils import Logger
from utils.config_loader import load_config
from utils.llm.llm_manager import LLMManager
from actors.manager import AgentManager


class SimulationSession:
    """Core platform logic for a chatroom session.

    Responsibilities:
    - manages ticking / opportunity structure (the "pull")
    - delegates agent decisions/actions to `AgentManager` (the "push")
    - wiring platform-level config, lifecycle and websocket attachment

    """
    def __init__(self, session_id: str, websocket_send: Callable, treatment_group: str, user_name: str = "user"):
        self.session_id = session_id
        # Wrap provided websocket_send so we can apply per-sender blocking rules
        # (suppress future messages from blocked senders while keeping past messages visible).
        original_send = websocket_send or self._noop_send
        self.websocket_send = self._wrap_send(original_send)
        self.logger = Logger(session_id)

        # Load experimental configs and map this session to a treatment group
        self.experimental_settings_full = load_config("config/experimental_settings.toml")
        if not (isinstance(self.experimental_settings_full, dict) and "groups" in self.experimental_settings_full):
            raise RuntimeError("experimental_settings.toml must define a top-level 'groups' table mapping treatment names to configs")
        group_map = self.experimental_settings_full["groups"]
        if treatment_group not in group_map:
            raise RuntimeError(f"treatment_group '{treatment_group}' not found in experimental_settings.toml groups")
        self.experimental_config = group_map[treatment_group]
        self.treatment_group = treatment_group

        # Load simulation config and initialize LLM manager
        self.simulation_config = load_config("config/simulation_settings.toml")
        self.llm_manager = LLMManager.from_simulation_config(self.simulation_config)

        # Initialize session state with agents
        agent_names = self.simulation_config["agent_names"]
        agents = [Agent(name=name) for name in agent_names]

        # Create session state with all relevant info
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
        self.actor_manager = AgentManager(
            state=self.state,
            llm_manager=self.llm_manager,
            logger=self.logger,
            prompt_builder=self._build_prompt,
            websocket_send=self.websocket_send,
        )

        # Initialize actor dynamics (chattiness, heat, affinity, tunables)
        try:
            self.actor_manager.initialize_dynamics(self.simulation_config)
        except Exception:
            pass

        # Clock task and running flag
        self.clock_task: Optional[asyncio.Task] = None
        self.running = False

    # Start the session
    async def start(self) -> None:
        self.running = True
        self.logger.log_session_start(self.experimental_config, self.simulation_config, self.treatment_group)
        self.clock_task = asyncio.create_task(self._clock_loop())
        print(f"Session {self.session_id} started")

    # Stop the session
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

    # Main simulation loop (tick based) lives here
    async def _clock_loop(self) -> None:
        tick_interval = 1.0
        mpm = self.simulation_config["messages_per_minute"]
        post_probability = mpm / 60.0

        while self.running:
            try: #First, check if session expired (max. duration)
                if self.state.is_expired():
                    await self.stop(reason="duration_expired")
                    break
                # Apply per-tick actor updates (heat decay, etc.)
                try:
                    await self.actor_manager.on_tick()
                except Exception:
                    pass
                #Second, trigger agent action based on user response or background post:
                if self.state.pending_user_response:
                    # Delegate agent selection and action for a user-triggered response
                    agent = self.actor_manager.select_agent(context_type="user_response")
                    if agent:
                        # foreground responses target the user (no agent target)
                        await self.actor_manager.agent_perform_action(agent, context_type="user_response", target=None)
                    self.state.pending_user_response = False

                elif random.random() < post_probability:
                    agent = self.actor_manager.select_agent(context_type="background")
                    if agent:
                        target = self.actor_manager.select_target(agent, context_type="background")
                        await self.actor_manager.agent_perform_action(agent, context_type="background", target=target)

                await asyncio.sleep(tick_interval)

            # Handle cancellation and errors
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.log_error("clock_loop", str(e))
                print(f"Error in clock loop: {e}")

    async def handle_user_message(self, content: str, reply_to: Optional[str] = None, quoted_text: Optional[str] = None, mentions: Optional[list] = None) -> None:
        message = Message.create(sender=self.state.user_name, content=content, reply_to=reply_to, quoted_text=quoted_text, mentions=mentions)
        self.state.add_message(message)
        self.logger.log_message(message.to_dict())

        response_prob = self.simulation_config["user_response_probability"]
        if random.random() < response_prob:
            self.state.pending_user_response = True

    async def _noop_send(self, message: dict) -> None:
        return

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

    async def attach_websocket(self, websocket_send: Callable) -> None:
        # Wrap the provided send function so per-sender blocking is enforced
        self.websocket_send = self._wrap_send(websocket_send)
        # update actor manager's websocket sender to the wrapped sender
        self.actor_manager.set_websocket_send(self.websocket_send)
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

    def detach_websocket(self) -> None:
        self.websocket_send = self._noop_send
        self.actor_manager.set_websocket_send(None)
        # Log websocket detach so reconnections are visible in logs
        try:
            self.logger.log_event("websocket_detach", {})
        except Exception:
            pass

    def _build_prompt(self, agent: Agent) -> str:
        # New signature accepts optional target and context_type when called from AgentManager
        # Keep backward-compatible single-arg usage by allowing `agent` only and ignoring additional args.
        def _inner(agent: Agent, target=None, context_type: str = None) -> str:
            context_size = self.simulation_config["context_window_size"]

            recent_messages = self.state.get_recent_messages(context_size)
            if recent_messages:
                context = "\n".join([f"{m.sender}: {m.content}" for m in recent_messages])
            else:
                context = "(No messages yet)"

            prompt = f"""Your name is {agent.name}. You are a member of this WhatsApp group.

{self.experimental_config['prompt_template']}

Recent messages:
{context}

Respond as {agent.name}. Keep it brief and natural."""

            # If a target agent was provided, encourage addressing them explicitly
            if target is not None:
                try:
                    tname = target.name
                    prompt = f"{prompt}\n\nAddress your response to {tname} (mention them if appropriate)."
                except Exception:
                    pass

            return prompt

        # If called with the old single-arg signature, call inner with no target
        return _inner(agent)
