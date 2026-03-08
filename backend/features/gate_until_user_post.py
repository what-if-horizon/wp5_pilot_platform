"""Feature: gate agent participation until the human posts first."""

from __future__ import annotations

from typing import TYPE_CHECKING

from features.base import BaseFeature

if TYPE_CHECKING:
    from models.session import SessionState


class GateUntilUserPost(BaseFeature):
    """Agents only begin after the human participant has posted at least once."""

    def agents_active(self, state: SessionState) -> bool:
        return any(m.sender == state.user_name for m in state.messages)
