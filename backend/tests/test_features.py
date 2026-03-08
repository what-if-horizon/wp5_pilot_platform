"""Tests for the composable features system.

Covers:
- BaseFeature (no-op defaults)
- FeatureRunner (composition: sequential seed, AND-ed agents_active)
- NewsArticleSeed (seed content injection)
- GateUntilUserPost (agent gating until human posts)
- load_features() registry and backward-compat
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from models.message import Message
from models.agent import Agent
from models.session import SessionState
from features.base import BaseFeature
from features.runner import FeatureRunner
from features.news_article import NewsArticleSeed
from features.gate_until_user_post import GateUntilUserPost
from features import load_features, AVAILABLE_FEATURES, _REGISTRY


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_state(**overrides) -> SessionState:
    defaults = dict(
        session_id="test-session",
        agents=[Agent(name="Alice"), Agent(name="Bob")],
        duration_minutes=30,
        experimental_config={},
        treatment_group="control",
        simulation_config={},
        user_name="participant",
    )
    defaults.update(overrides)
    return SessionState(**defaults)


# ── BaseFeature ──────────────────────────────────────────────────────────────

class TestBaseFeature:
    """BaseFeature provides safe no-op defaults."""

    def test_agents_active_returns_true(self):
        feature = BaseFeature(config={})
        state = _make_state()
        assert feature.agents_active(state) is True

    @pytest.mark.asyncio
    async def test_seed_is_noop(self):
        feature = BaseFeature(config={})
        state = _make_state()
        ws = AsyncMock()
        await feature.seed(state, ws)
        # No messages added, no websocket calls
        assert len(state.messages) == 0
        ws.assert_not_called()

    def test_config_stored(self):
        cfg = {"foo": "bar"}
        feature = BaseFeature(config=cfg)
        assert feature.config is cfg


# ── FeatureRunner ────────────────────────────────────────────────────────────

class TestFeatureRunner:
    """FeatureRunner composes multiple features."""

    def test_empty_runner_agents_active(self):
        runner = FeatureRunner([])
        state = _make_state()
        # all() of empty iterable is True
        assert runner.agents_active(state) is True

    @pytest.mark.asyncio
    async def test_empty_runner_seed(self):
        runner = FeatureRunner([])
        state = _make_state()
        ws = AsyncMock()
        await runner.seed(state, ws)
        assert len(state.messages) == 0

    def test_agents_active_all_true(self):
        """When all features say active, runner says active."""
        f1 = BaseFeature(config={})  # always True
        f2 = BaseFeature(config={})
        runner = FeatureRunner([f1, f2])
        state = _make_state()
        assert runner.agents_active(state) is True

    def test_agents_active_one_false(self):
        """When any feature says inactive, runner says inactive (AND logic)."""
        state = _make_state()

        class AlwaysFalse(BaseFeature):
            def agents_active(self, state):
                return False

        runner = FeatureRunner([BaseFeature({}), AlwaysFalse({})])
        assert runner.agents_active(state) is False

    def test_agents_active_all_false(self):
        state = _make_state()

        class AlwaysFalse(BaseFeature):
            def agents_active(self, state):
                return False

        runner = FeatureRunner([AlwaysFalse({}), AlwaysFalse({})])
        assert runner.agents_active(state) is False

    @pytest.mark.asyncio
    async def test_seed_called_sequentially(self):
        """seed() calls each feature's seed in order."""
        call_order = []

        class TrackingFeature(BaseFeature):
            def __init__(self, label, config):
                super().__init__(config)
                self.label = label

            async def seed(self, state, ws):
                call_order.append(self.label)

        runner = FeatureRunner([
            TrackingFeature("first", {}),
            TrackingFeature("second", {}),
            TrackingFeature("third", {}),
        ])
        state = _make_state()
        await runner.seed(state, AsyncMock())
        assert call_order == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_seed_passes_state_and_ws(self):
        """seed() passes state and websocket_send to each feature."""
        received = []

        class CapturingFeature(BaseFeature):
            async def seed(self, state, ws):
                received.append((state, ws))

        state = _make_state()
        ws = AsyncMock()
        runner = FeatureRunner([CapturingFeature({})])
        await runner.seed(state, ws)
        assert len(received) == 1
        assert received[0][0] is state
        assert received[0][1] is ws


# ── NewsArticleSeed ──────────────────────────────────────────────────────────

class TestNewsArticleSeed:

    @pytest.mark.asyncio
    async def test_seed_injects_message(self):
        config = {
            "seed": {
                "type": "news_article",
                "headline": "Breaking News",
                "source": "Reuters",
                "body": "Something happened today.",
            }
        }
        feature = NewsArticleSeed(config)
        state = _make_state()
        ws = AsyncMock()
        await feature.seed(state, ws)

        assert len(state.messages) == 1
        msg = state.messages[0]
        assert msg.sender == "[news]"
        assert "Breaking News" in msg.content
        assert "(Reuters)" in msg.content
        assert "Something happened today." in msg.content
        # WebSocket notified
        ws.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_metadata(self):
        config = {
            "seed": {
                "headline": "Test",
                "source": "AP",
                "body": "Details.",
            }
        }
        feature = NewsArticleSeed(config)
        state = _make_state()
        ws = AsyncMock()
        await feature.seed(state, ws)

        msg = state.messages[0]
        assert msg.metadata["msg_type"] == "news_article"
        assert msg.metadata["headline"] == "Test"
        assert msg.metadata["source"] == "AP"
        assert msg.metadata["body"] == "Details."

    @pytest.mark.asyncio
    async def test_seed_without_source(self):
        config = {
            "seed": {
                "headline": "No Source",
                "body": "Body text.",
            }
        }
        feature = NewsArticleSeed(config)
        state = _make_state()
        ws = AsyncMock()
        await feature.seed(state, ws)

        msg = state.messages[0]
        assert "No Source" in msg.content
        assert "Body text." in msg.content
        # No "(source)" portion
        assert "(" not in msg.content

    @pytest.mark.asyncio
    async def test_seed_skips_when_no_headline(self):
        config = {"seed": {"body": "No headline"}}
        feature = NewsArticleSeed(config)
        state = _make_state()
        ws = AsyncMock()
        await feature.seed(state, ws)

        assert len(state.messages) == 0
        ws.assert_not_called()

    @pytest.mark.asyncio
    async def test_seed_skips_when_no_body(self):
        config = {"seed": {"headline": "No body"}}
        feature = NewsArticleSeed(config)
        state = _make_state()
        ws = AsyncMock()
        await feature.seed(state, ws)

        assert len(state.messages) == 0
        ws.assert_not_called()

    @pytest.mark.asyncio
    async def test_seed_skips_when_empty_config(self):
        feature = NewsArticleSeed(config={})
        state = _make_state()
        ws = AsyncMock()
        await feature.seed(state, ws)

        assert len(state.messages) == 0

    def test_agents_active_always_true(self):
        """NewsArticleSeed doesn't gate agents — inherits BaseFeature default."""
        feature = NewsArticleSeed(config={})
        state = _make_state()
        assert feature.agents_active(state) is True


# ── GateUntilUserPost ────────────────────────────────────────────────────────

class TestGateUntilUserPost:

    def test_inactive_when_no_messages(self):
        feature = GateUntilUserPost(config={})
        state = _make_state()
        assert feature.agents_active(state) is False

    def test_inactive_when_only_agent_messages(self):
        feature = GateUntilUserPost(config={})
        state = _make_state()
        state.add_message(Message.create(sender="Alice", content="Hello"))
        state.add_message(Message.create(sender="Bob", content="Hi"))
        assert feature.agents_active(state) is False

    def test_active_after_user_post(self):
        feature = GateUntilUserPost(config={})
        state = _make_state(user_name="participant")
        state.add_message(Message.create(sender="participant", content="I'm here"))
        assert feature.agents_active(state) is True

    def test_active_after_user_post_with_agent_messages(self):
        feature = GateUntilUserPost(config={})
        state = _make_state(user_name="participant")
        state.add_message(Message.create(sender="Alice", content="Waiting"))
        state.add_message(Message.create(sender="participant", content="Hello"))
        state.add_message(Message.create(sender="Bob", content="Welcome"))
        assert feature.agents_active(state) is True

    def test_custom_user_name(self):
        feature = GateUntilUserPost(config={})
        state = _make_state(user_name="custom_user")
        state.add_message(Message.create(sender="participant", content="not me"))
        assert feature.agents_active(state) is False

        state.add_message(Message.create(sender="custom_user", content="it's me"))
        assert feature.agents_active(state) is True

    def test_news_message_does_not_activate(self):
        """A [news] seed message should not count as user post."""
        feature = GateUntilUserPost(config={})
        state = _make_state()
        state.add_message(Message.create(sender="[news]", content="Article"))
        assert feature.agents_active(state) is False


# ── Combined feature composition ─────────────────────────────────────────────

class TestFeatureComposition:
    """Test realistic combinations of features."""

    @pytest.mark.asyncio
    async def test_news_plus_gate(self):
        """news_article + gate_until_user_post: seed fires, agents gated."""
        config = {
            "seed": {
                "headline": "Breaking",
                "source": "AP",
                "body": "Story body.",
            },
            "features": ["news_article", "gate_until_user_post"],
        }
        news = NewsArticleSeed(config)
        gate = GateUntilUserPost(config)
        runner = FeatureRunner([news, gate])

        state = _make_state(user_name="participant")
        ws = AsyncMock()

        await runner.seed(state, ws)
        # News injected
        assert len(state.messages) == 1
        assert state.messages[0].sender == "[news]"

        # But agents still gated (news msg sender != user_name)
        assert runner.agents_active(state) is False

        # User posts → agents unblocked
        state.add_message(Message.create(sender="participant", content="Hello"))
        assert runner.agents_active(state) is True


# ── load_features() registry ─────────────────────────────────────────────────

class TestLoadFeatures:

    def test_load_empty_features(self):
        runner = load_features({"features": []})
        assert isinstance(runner, FeatureRunner)
        state = _make_state()
        assert runner.agents_active(state) is True

    def test_load_no_features_key(self):
        runner = load_features({})
        assert isinstance(runner, FeatureRunner)

    def test_load_news_article(self):
        runner = load_features({"features": ["news_article"]})
        assert len(runner._features) == 1
        assert isinstance(runner._features[0], NewsArticleSeed)

    def test_load_gate_until_user_post(self):
        runner = load_features({"features": ["gate_until_user_post"]})
        assert len(runner._features) == 1
        assert isinstance(runner._features[0], GateUntilUserPost)

    def test_load_multiple_features(self):
        runner = load_features({"features": ["news_article", "gate_until_user_post"]})
        assert len(runner._features) == 2

    def test_unknown_feature_raises(self):
        with pytest.raises(RuntimeError, match="Unknown feature 'nonexistent'"):
            load_features({"features": ["nonexistent"]})

    def test_legacy_scenario_base(self):
        runner = load_features({"scenario": "base"})
        assert len(runner._features) == 0

    def test_legacy_scenario_news_article(self):
        runner = load_features({"scenario": "news_article"})
        assert len(runner._features) == 2

    def test_legacy_unknown_scenario_raises(self):
        with pytest.raises(RuntimeError, match="Unknown legacy scenario"):
            load_features({"scenario": "unknown_scenario"})

    def test_features_key_takes_precedence_over_scenario(self):
        """When both keys present, 'features' wins."""
        runner = load_features({
            "features": ["news_article"],
            "scenario": "base",
        })
        assert len(runner._features) == 1

    def test_config_passed_to_features(self):
        config = {"features": ["news_article"], "seed": {"headline": "H", "body": "B"}}
        runner = load_features(config)
        assert runner._features[0].config is config

    def test_available_features_sorted(self):
        assert AVAILABLE_FEATURES == sorted(_REGISTRY.keys())
