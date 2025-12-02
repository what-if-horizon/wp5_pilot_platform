from dataclasses import dataclass
from typing import Optional

# Represents an AI agent in the simulation.
# NOTE: functional placeholder for future expansion
@dataclass
class Agent:
    """Represents an AI agent in the simulation.

    New fields:
    - chattiness: float (0.0-1.0) how often the bot initiates
    - attention: float (dynamic, 0.0-1.0) recent conversational relevance
    """

    name: str
    chattiness: float = 0.0
    attention: float = 0.0
    # 'prompt' defines which prompt template key this agent uses (matches a
    # prompt name in `experimental_settings.toml` under the [prompts] table).
    # It is intentionally generic and may be any string; if unset the
    # platform/actor manager should fall back to group-level defaults.
    prompt: Optional[str] = None

    def __repr__(self) -> str:
        return (
            f"Agent(name='{self.name}', chattiness={self.chattiness:.2f}, "
            f"attention={self.attention:.2f}, prompt={self.prompt!r})"
        )