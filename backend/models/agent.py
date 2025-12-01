from dataclasses import dataclass

# Represents an AI agent in the simulation.
# NOTE: functional placeholder for future expansion
@dataclass
class Agent:
    """Represents an AI agent in the simulation.

    New fields:
    - chattiness: float (0.0-1.0) how often the bot initiates
    - heat: float (dynamic, 0.0-1.0) recent conversational relevance
    """

    name: str
    chattiness: float = 0.0
    heat: float = 0.0
    # 'style' defines which prompt template this agent uses.
    # One of: 'highly_uncivil', 'slightly_uncivil', 'civil'
    style: str = "civil"

    def __repr__(self) -> str:
        return f"Agent(name='{self.name}', chattiness={self.chattiness:.2f}, heat={self.heat:.2f})"