from dataclasses import dataclass


@dataclass
class Agent:
    """Represents an AI agent in the simulation."""
    
    name: str
    
    def __repr__(self) -> str:
        return f"Agent(name='{self.name}')"