"""FeatureRunner — composes multiple BaseFeature instances.

Delegates lifecycle hooks to each feature:
  - seed()          → called sequentially on each feature
  - agents_active() → AND of all features (agents act only when ALL agree)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Sequence

from features.base import BaseFeature

if TYPE_CHECKING:
    from models.session import SessionState


class FeatureRunner:
    """Compose a list of features into a single interface."""

    def __init__(self, features: Sequence[BaseFeature]):
        self._features = list(features)

    async def seed(self, state: SessionState, websocket_send: Callable) -> None:
        for feature in self._features:
            await feature.seed(state, websocket_send)

    def agents_active(self, state: SessionState) -> bool:
        return all(f.agents_active(state) for f in self._features)
