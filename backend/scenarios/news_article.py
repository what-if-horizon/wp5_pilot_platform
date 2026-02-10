"""Scenario: seed a news article and gate agents on first user message.

Experimental config (in experimental_settings.toml) should include:

    [groups.<name>.seed]
    type = "news_article"
    headline = "..."
    source = "..."
    body = "..."
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from models.message import Message
from scenarios.base import BaseScenario

if TYPE_CHECKING:
    from models.session import SessionState


class NewsArticleScenario(BaseScenario):
    """Seed a reposted news article; agents wait for the user's first message."""

    async def seed(self, state: SessionState, websocket_send: Callable) -> None:
        """Inject a news-article message at the top of the chat log."""
        seed_cfg = self.config.get("seed", {})
        headline = seed_cfg.get("headline", "")
        source = seed_cfg.get("source", "")
        body = seed_cfg.get("body", "")

        if not (headline and body):
            return

        # Plain-text content so the Director sees the article in the chat log
        content = headline
        if source:
            content += f" ({source})"
        content += f" — {body}"

        # Structured metadata is persisted on the Message so that to_dict()
        # includes it on both the initial send and websocket-reconnect replays.
        message = Message.create(sender="[news]", content=content)
        message.metadata = {
            "msg_type": "news_article",
            "headline": headline,
            "source": source,
            "body": body,
        }
        state.add_message(message)
        await websocket_send(message.to_dict())

    def agents_active(self, state: SessionState) -> bool:
        """Agents only begin after the human participant has posted at least once."""
        return any(m.sender == state.user_name for m in state.messages)
