from dataclasses import dataclass
from datetime import datetime
import uuid


@dataclass
class Message:
    """Represents a single message in the chatroom."""
    
    sender: str  # "user" or agent name (e.g., "Alice")
    content: str 
    timestamp: datetime
    message_id: str
    
    @classmethod
    def create(cls, sender: str, content: str) -> "Message":
        """Factory method to create a new message with auto-generated ID and timestamp."""
        return cls(
            sender=sender,
            content=content,
            timestamp=datetime.now(),
            message_id=str(uuid.uuid4())
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id
        }