from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict
from models.agent import Agent
from models.message import Message

# Represents the state of a simulation session.
# NOTE: concurrent sessions handled via utils/session_manager.py
@dataclass
class SessionState:
    """Holds the complete state of a simulation session."""
    
    session_id: str
    agents: List[Agent]
    messages: List[Message] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    duration_minutes: int = 15
    pending_user_response: bool = False
    # Identifier for the human participant in this session (default 'user')
    user_name: str = "user"
    experimental_config: dict = field(default_factory=dict)
    simulation_config: dict = field(default_factory=dict)
    treatment_group: str = None
    # Map of agent name -> ISO timestamp when the agent was blocked for this session
    # This allows keeping existing messages visible while suppressing new ones
    # created after the block time.
    blocked_agents: Dict[str, str] = field(default_factory=dict)
 
    def add_message(self, message: Message) -> None:
        """Add a message to the session history."""
        self.messages.append(message)
    
    def get_recent_messages(self, n: int) -> List[Message]:
        """Get the last n messages from the history."""
        return self.messages[-n:] if len(self.messages) >= n else self.messages
    
    def is_expired(self) -> bool:
        """Check if the session has exceeded its duration."""
        elapsed = (datetime.now() - self.start_time).total_seconds() / 60
        return elapsed >= self.duration_minutes

    def block_agent(self, agent_name: str, when_iso: str) -> None:
        """Mark an agent as blocked at the given ISO timestamp for this session."""
        self.blocked_agents[agent_name] = when_iso

    def unblock_agent(self, agent_name: str) -> None:
        """Unblock a previously blocked agent."""
        self.blocked_agents.pop(agent_name, None)
