from dataclasses import dataclass

# Represents an AI agent in the simulation.
# NOTE: functional placeholder for future expansion
@dataclass
class Agent:
    """Represents an AI agent in the simulation."""
    
    name: str
    
    def __repr__(self) -> str:
        return f"Agent(name='{self.name}')"