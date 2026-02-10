from dataclasses import dataclass


@dataclass
class Agent:
    """Represents an AI agent in the simulation.

    In the STAGE framework, agent selection and behaviour are controlled
    by the Director; the Agent model only needs to carry the agent's name.
    """

    name: str

    def __repr__(self) -> str:
        return f"Agent(name='{self.name}')"
