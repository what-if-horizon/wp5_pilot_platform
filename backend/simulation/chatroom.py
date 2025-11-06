import asyncio
import random
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime

from models import Message, Agent, SessionState
from utils import Logger
from utils.config_loader import load_config
from utils.llm_manager import LLMManager

# CHATROOM SIMULATION LOGIC - 
# NOTE: this script contains the core SimulationSession class for chatroom simulations.

class SimulationSession:
    """Core simulation logic for a chatroom session."""
    #initialize simulation session with session id, websocket, and treatment group
    def __init__(self, session_id: str, websocket_send: Callable, treatment_group: str):
        """
        Initialize a chatroom simulation session.
        
        Args:
            session_id: Unique identifier for this session
            websocket_send: Optional async function to send messages to the frontend
        """
        self.session_id = session_id #stores session id as attribute
        # websocket_send is an async callable used to send messages to the frontend.
        # It may be detached when the client disconnects; use a no-op in that case.
        self.websocket_send = websocket_send or self._noop_send
        self.logger = Logger(session_id) #logger instance for this session
        # Load configurations (experimental and simulation) from TOML files
        self.experimental_settings_full = load_config("config/experimental_settings.toml")
        if not (isinstance(self.experimental_settings_full, dict) and "groups" in self.experimental_settings_full):
            raise RuntimeError("experimental_settings.toml must define a top-level 'groups' table mapping treatment names to configs")
        group_map = self.experimental_settings_full["groups"]
        # treatment_group is required and must be present in the groups mapping
        if treatment_group not in group_map: #redundant due to backend startup validation; but safe.
            raise RuntimeError(f"treatment_group '{treatment_group}' not found in experimental_settings.toml groups")
        self.experimental_config = group_map[treatment_group] #store full exp. config for this user-session. 
        self.treatment_group = treatment_group #store treatment group for this user-session.
        self.simulation_config = load_config("config/simulation_settings.toml") #load sim. config.
        # Configure an LLM manager from the simulation settings. The manager
        # encapsulates concurrency limits and delegates to the chosen LLM client.
        self.llm_manager = LLMManager.from_simulation_config(self.simulation_config)
        
        # Initialize agents (from simulation config)
        # NOTE: later create backend/agents/agent_manager.py to handle agent creation and relations.
        agent_names = self.simulation_config["agent_names"]
        agents = [Agent(name=name) for name in agent_names]
        
        # Initialize session state (pass session id, agents, configs)
        self.state = SessionState(
            session_id=session_id,
            agents=agents,
            duration_minutes=self.simulation_config["session_duration_minutes"],
            experimental_config=self.experimental_config,
            treatment_group=treatment_group,
            simulation_config=self.simulation_config
        )
        
        # Set clock task (but do not start it yet)
        self.clock_task: Optional[asyncio.Task] = None
        self.running = False
    
    
    # Start the simulation session (main clock loop)
    async def start(self) -> None:
        """Start the simulation session."""
        self.running = True #indicate session is running
        #log session start
        self.logger.log_session_start(self.experimental_config, self.simulation_config, self.treatment_group)
        #simulation clock loop start
        self.clock_task = asyncio.create_task(self._clock_loop())
        print(f"Session {self.session_id} started")
    
    # Stop the simulation session
    async def stop(self, reason: str = "completed") -> None:
        """Stop the simulation session."""
        self.running = False #indicate session has stopped
        #simulation clock loop stop
        if self.clock_task:
            self.clock_task.cancel()
            try:
                await self.clock_task
            except asyncio.CancelledError:
                pass
        #log reason for session end
        self.logger.log_session_end(reason)
        print(f"Session {self.session_id} stopped: {reason}")
    
    # Main time-based loop driving the simulation
    async def _clock_loop(self) -> None:
        """Main clock loop that drives the chatroom simulation."""
        tick_interval = 1.0  # 1 second per tick
        #probabilistic background message posting
        mpm = self.simulation_config["messages_per_minute"]
        post_probability = mpm / 60.0  # %prob per second
        
        #Main event loop logic - 
        while self.running:
            try:
                # Check if session has expired (configs)
                if self.state.is_expired():
                    await self.stop(reason="duration_expired")
                    break
                
                # Handle pending user response (if any)
                if self.state.pending_user_response:
                    await self._generate_agent_message(context_type="user_response")
                    self.state.pending_user_response = False
                
                # Probabilistic background message activity
                elif random.random() < post_probability:
                    await self._generate_agent_message(context_type="background")
                
                # Wait for next tick
                await asyncio.sleep(tick_interval)
            
            # Handle cancellation and errors
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.log_error("clock_loop", str(e))
                print(f"Error in clock loop: {e}")
    
    # handle user messages from frontend
    async def handle_user_message(self, content: str) -> None:
        """
        Handle a message from the user.
        
        Args:
            content: The message content from the user
        """
        # Create and store message
        message = Message.create(sender="user", content=content)
        self.state.add_message(message)
        # Log the message
        self.logger.log_message(message.to_dict())
        # Roll dice for agent response (configs)
        response_prob = self.simulation_config["user_response_probability"]
        if random.random() < response_prob:
            self.state.pending_user_response = True
    
    # Generate and send an agent message to frontend
    async def _generate_agent_message(self, context_type: str) -> None:
        """
        Generate and send an agent message.

        Args:
            context_type: Either 'background' or 'user_response'
        """
        # Select random agent (for now)
        agent = random.choice(self.state.agents)

        # Build prompt
        prompt = self._build_prompt(agent)

        # Call LLM (with retry) using async client and a semaphore to limit concurrency
        response_text = None
        try:
            # LLMManager handles concurrency and delegating to the chosen LLM client.
            response_text = await self.llm_manager.generate_response(prompt, max_retries=1)
        except Exception as e:
            response_text = None
            self.logger.log_error("llm_call", str(e))

        # Log LLM call
        self.logger.log_llm_call(
            agent_name=agent.name,
            prompt=prompt,
            response=response_text,
            error=None if response_text else "Failed after retries"
        )

        # If LLM failed, skip this turn
        if not response_text:
            return

        # Create message
        message = Message.create(sender=agent.name, content=response_text)
        self.state.add_message(message)

        # Log message
        self.logger.log_message(message.to_dict())

        # Send to frontend via WebSocket (websocket_send may be a no-op)
        try:
            await self.websocket_send(message.to_dict())
        except Exception as e:
            self.logger.log_error("send", str(e))

    # No-op sender for detached websockets
    # NOTE: this allows sessions to continue running without an active client. 
    async def _noop_send(self, message: dict) -> None:
        """Default no-op sender used when no websocket is attached."""
        return

    # Attach a websocket send function and replay recent messages to the newly connected client.
    async def attach_websocket(self, websocket_send: Callable) -> None:
        """Attach a websocket send function and replay recent messages to the newly connected client.

        This is used for reconnects after client reloads. It sets the session's websocket_send to the
        provided callable and replays the current message history.
        """
        self.websocket_send = websocket_send
        # replay history to new client (send all messages recorded so far)
        for m in self.state.messages:
            try:
                await self.websocket_send(m.to_dict())
            except Exception:
                # ignore individual send errors during replay
                continue

    def detach_websocket(self) -> None:
        """Detach the current websocket sender and replace with a no-op. Keeps session running."""
        self.websocket_send = self._noop_send
    
    # Build the prompt for an agent message
    # NOTE: this is generic; later move to backend/agents/prompt_builder.py
    def _build_prompt(self, agent: Agent) -> str:
        """
        Build the prompt for an agent, including identity and conversation context.
        
        Args:
            agent: The agent generating the message
            
        Returns:
            Complete prompt string
        """
        # Get recent messages
        context_size = self.simulation_config["context_window_size"]
        recent_messages = self.state.get_recent_messages(context_size)
        
        # Format message history
        if recent_messages:
            context = "\n".join([f"{m.sender}: {m.content}" for m in recent_messages])
        else:
            context = "(No messages yet)"
        
        # Build prompt with agent identity
        prompt = f"""Your name is {agent.name}. You are a member of this WhatsApp group.

{self.experimental_config['prompt_template']}

Recent messages:
{context}

Respond as {agent.name}. Keep it brief and natural."""
        
        return prompt
