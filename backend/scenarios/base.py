"""Base scenario defining the hook interface for experiment-specific behaviour.

A scenario customises session lifecycle without modifying the core platform.
Subclasses override hooks; the defaults are no-ops so the base scenario
preserves current behaviour (no seed content, agents start immediately).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from models.session import SessionState


class BaseScenario:
    """Default (no-op) scenario — agents start immediately, no seed content."""

    def __init__(self, config: dict):
        """Receive the experimental_config dict for this treatment group."""
        self.config = config

    async def seed(self, state: SessionState, websocket_send: Callable) -> None:
        """Inject any content that should exist before agents begin.

        Called once, at the start of the session, before the clock loop launches.
        The default implementation does nothing.
        """

    def agents_active(self, state: SessionState) -> bool:
        """Return True when agents should be allowed to act.

        Called on every tick of the clock loop.  The default always returns True,
        preserving the existing behaviour where agents start immediately.
        """
        return True
