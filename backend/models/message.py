from dataclasses import dataclass
from datetime import datetime
import uuid
from typing import Optional, List


# Represents a single message or post. 
@dataclass
class Message:
    """Represents a single message in the chatroom."""
    
    sender: str  # "user" or agent name (e.g., "Alice")
    content: str 
    timestamp: datetime
    message_id: str
    # Optional reply metadata (for quoted replies)
    reply_to: Optional[str] = None  # message_id being replied to
    quoted_text: Optional[str] = None  # text excerpt of the message being replied to
    # Optional mentions (tags) included in the message, e.g., ["Alice", "Bob"]
    mentions: Optional[List[str]] = None
    
    @classmethod
    def create(
        cls,
        sender: str,
        content: str,
        reply_to: Optional[str] = None,
        quoted_text: Optional[str] = None,
        mentions: Optional[List[str]] = None,
    ) -> "Message":
        """Factory method to create a new message with auto-generated ID and timestamp.

        reply_to and quoted_text are optional metadata used for quoted replies.
        """
        return cls(
            sender=sender,
            content=content,
            timestamp=datetime.now(),
            message_id=str(uuid.uuid4()),
            reply_to=reply_to,
            quoted_text=quoted_text,
            mentions=mentions,
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
            "reply_to": self.reply_to,
            "quoted_text": self.quoted_text,
            "mentions": self.mentions,
        }