import asyncio
import json
import random
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime

from models import Message, Agent, SessionState
from utils import Logger, gemini_client


class SimulationSession:
    """Core simulation logic for a chatroom session."""
    
    def __init__(self, session_id: str, websocket_send: Callable):
        """
        Initialize a simulation session.
        
        Args:
            session_id: Unique identifier for this session
            websocket_send: Async function to send messages to the frontend
        """
        self.session_id = session_id #stores session id as attribute
        self.websocket_send = websocket_send #method to send messages to frontend
        self.logger = Logger(session_id) #logger instance for this session
        
        # Load configurations (experimental and simulation)
        self.experimental_config = self._load_config("config/experimental_settings.json")
        self.simulation_config = self._load_config("config/simulation_settings.json")
        
        # Initialize agents (from simulation config)
        agent_names = self.simulation_config["agent_names"]
        agents = [Agent(name=name) for name in agent_names]
        
        # Initialize session state
        self.state = SessionState(
            session_id=session_id,
            agents=agents,
            duration_minutes=self.simulation_config["session_duration_minutes"],
            experimental_config=self.experimental_config,
            simulation_config=self.simulation_config
        )
        
        # Clock task handle
        self.clock_task: Optional[asyncio.Task] = None
        self.running = False
    
    def _load_config(self, path: str) -> dict:
        """Load a JSON configuration file."""
        with open(Path(path), "r") as f:
            return json.load(f)
    
    async def start(self) -> None:
        """Start the simulation session."""
        self.running = True
        self.logger.log_session_start(self.experimental_config, self.simulation_config)
        
        # Start the clock
        self.clock_task = asyncio.create_task(self._clock_loop())
        
        print(f"Session {self.session_id} started")
    
    async def stop(self, reason: str = "completed") -> None:
        """Stop the simulation session."""
        self.running = False
        
        # Cancel clock task
        if self.clock_task:
            self.clock_task.cancel()
            try:
                await self.clock_task
            except asyncio.CancelledError:
                pass
        
        self.logger.log_session_end(reason)
        print(f"Session {self.session_id} stopped: {reason}")
    
    async def _clock_loop(self) -> None:
        """Main clock loop that drives the simulation."""
        tick_interval = 1.0  # 1 second per tick
        mpm = self.simulation_config["messages_per_minute"]
        post_probability = mpm / 60.0  # Probability per second
        
        while self.running:
            try:
                # Check if session has expired
                if self.state.is_expired():
                    await self.stop(reason="duration_expired")
                    break
                
                # Handle pending user response
                if self.state.pending_user_response:
                    await self._generate_agent_message(context_type="user_response")
                    self.state.pending_user_response = False
                
                # Probabilistic background message
                elif random.random() < post_probability:
                    await self._generate_agent_message(context_type="background")
                
                # Wait for next tick
                await asyncio.sleep(tick_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.log_error("clock_loop", str(e))
                print(f"Error in clock loop: {e}")
    
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
        
        # Roll dice for agent response
        response_prob = self.simulation_config["user_response_probability"]
        if random.random() < response_prob:
            self.state.pending_user_response = True
    
    async def _generate_agent_message(self, context_type: str) -> None:
        """
        Generate and send an agent message.
        
        Args:
            context_type: Either 'background' or 'user_response'
        """
        # Select random agent
        agent = random.choice(self.state.agents)
        
        # Build prompt
        prompt = self._build_prompt(agent)
        
        # Call LLM (with retry)
        response_text = gemini_client.generate_response(prompt, max_retries=1)
        
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
        
        # Send to frontend via WebSocket
        await self.websocket_send(message.to_dict())
    
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
