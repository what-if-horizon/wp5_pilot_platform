from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from models.agent import Agent
from models.message import Message


@dataclass
class SessionState:
    """Holds the complete state of a simulation session."""
    
    session_id: str
    agents: List[Agent]
    messages: List[Message] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    duration_minutes: int = 15
    pending_user_response: bool = False
    experimental_config: dict = field(default_factory=dict)
    simulation_config: dict = field(default_factory=dict)
    
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
