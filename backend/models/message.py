from dataclasses import dataclass, field
from datetime import datetime
import uuid
from typing import Optional, List, Set


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
    # Track which participants have liked this message (store user identifiers)
    liked_by: Set[str] = field(default_factory=set)
    # Whether this message has been reported by the (single) human participant
    reported: bool = False
    
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
            # Likes metadata
            "likes_count": len(self.liked_by),
            "liked_by": list(self.liked_by),
            # Reported flag (single human participant model)
            "reported": self.reported,
        }

    # Likes management
    @property
    def likes_count(self) -> int:
        """Return number of likes for this message."""
        return len(self.liked_by)
    
    def toggle_like(self, user_id: str) -> str:
        """Toggle like state for user_id. Returns 'liked' or 'unliked'."""
        if user_id in self.liked_by:
            self.liked_by.remove(user_id)
            return "unliked"
        else:
            self.liked_by.add(user_id)
            return "liked"

    def toggle_report(self) -> str:
        """Toggle the reported flag for this message. Returns 'reported' or 'unreported'."""
        if self.reported:
            self.reported = False
            return "unreported"
        else:
            self.reported = True
            return "reported"