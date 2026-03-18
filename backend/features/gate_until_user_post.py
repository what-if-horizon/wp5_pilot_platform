"""Feature: gate agent participation until the human posts first."""

from __future__ import annotations

from typing import TYPE_CHECKING

from features.base import BaseFeature

if TYPE_CHECKING:
    from models.session import SessionState


class GateUntilUserPost(BaseFeature):
    """Agents only begin after the human participant has posted at least once."""

    def __init__(self, config: dict, logger=None):
        super().__init__(config, logger)
        self._gate_opened = False

    def agents_active(self, state: SessionState) -> bool:
        active = any(m.sender == state.user_name for m in state.messages)
        if active and not self._gate_opened:
            self._gate_opened = True
            if self.logger:
                self.logger.log_event("feature_gate_opened", {
                    "feature": "gate_until_user_post",
                    "message_count_at_open": len(state.messages),
                })
        return active
