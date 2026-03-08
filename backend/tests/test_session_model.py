"""Unit tests for models/session.py — SessionState dataclass."""
from datetime import datetime, timezone, timedelta

from models.agent import Agent
from models.message import Message
from models.session import SessionState


def _make_session(**kwargs):
    defaults = dict(
        session_id="sess-1",
        agents=[Agent(name="Alice"), Agent(name="Bob")],
    )
    defaults.update(kwargs)
    return SessionState(**defaults)


def _make_msg(sender="Alice", content="hi", msg_id="m1"):
    return Message(
        sender=sender,
        content=content,
        timestamp=datetime.now(timezone.utc),
        message_id=msg_id,
    )


# ── add_message ──────────────────────────────────────────────────────────────

class TestAddMessage:
    def test_appends_to_list(self):
        s = _make_session()
        m = _make_msg()
        s.add_message(m)
        assert len(s.messages) == 1
        assert s.messages[0] is m

    def test_preserves_order(self):
        s = _make_session()
        m1 = _make_msg(msg_id="m1")
        m2 = _make_msg(msg_id="m2")
        s.add_message(m1)
        s.add_message(m2)
        assert s.messages[0].message_id == "m1"
        assert s.messages[1].message_id == "m2"


# ── get_recent_messages ──────────────────────────────────────────────────────

class TestGetRecentMessages:
    def test_returns_last_n(self):
        s = _make_session()
        for i in range(5):
            s.add_message(_make_msg(msg_id=f"m{i}"))
        recent = s.get_recent_messages(3)
        assert len(recent) == 3
        assert [m.message_id for m in recent] == ["m2", "m3", "m4"]

    def test_returns_all_when_fewer_than_n(self):
        s = _make_session()
        s.add_message(_make_msg(msg_id="only"))
        recent = s.get_recent_messages(10)
        assert len(recent) == 1
        assert recent[0].message_id == "only"

    def test_empty_messages(self):
        s = _make_session()
        assert s.get_recent_messages(5) == []

    def test_n_equals_length(self):
        s = _make_session()
        for i in range(3):
            s.add_message(_make_msg(msg_id=f"m{i}"))
        recent = s.get_recent_messages(3)
        assert len(recent) == 3


# ── is_expired ───────────────────────────────────────────────────────────────

class TestIsExpired:
    def test_fresh_session_not_expired(self):
        s = _make_session(duration_minutes=15)
        assert s.is_expired() is False

    def test_expired_session(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=20)
        s = _make_session(start_time=past, duration_minutes=15)
        assert s.is_expired() is True

    def test_exactly_at_boundary(self):
        """A session at exactly duration_minutes should be expired (>=)."""
        past = datetime.now(timezone.utc) - timedelta(minutes=15)
        s = _make_session(start_time=past, duration_minutes=15)
        assert s.is_expired() is True

    def test_just_before_boundary(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=14, seconds=59)
        s = _make_session(start_time=past, duration_minutes=15)
        assert s.is_expired() is False


# ── block_agent / unblock_agent ──────────────────────────────────────────────

class TestAgentBlocking:
    def test_block_agent(self):
        s = _make_session()
        s.block_agent("Alice", "2025-01-01T00:00:00Z")
        assert "Alice" in s.blocked_agents
        assert s.blocked_agents["Alice"] == "2025-01-01T00:00:00Z"

    def test_block_overwrites_previous(self):
        s = _make_session()
        s.block_agent("Alice", "2025-01-01T00:00:00Z")
        s.block_agent("Alice", "2025-06-01T00:00:00Z")
        assert s.blocked_agents["Alice"] == "2025-06-01T00:00:00Z"

    def test_unblock_agent(self):
        s = _make_session()
        s.block_agent("Alice", "2025-01-01T00:00:00Z")
        s.unblock_agent("Alice")
        assert "Alice" not in s.blocked_agents

    def test_unblock_nonexistent_agent_is_noop(self):
        s = _make_session()
        s.unblock_agent("Nobody")  # should not raise
        assert s.blocked_agents == {}

    def test_multiple_blocks(self):
        s = _make_session()
        s.block_agent("Alice", "2025-01-01T00:00:00Z")
        s.block_agent("Bob", "2025-01-02T00:00:00Z")
        assert len(s.blocked_agents) == 2
        s.unblock_agent("Alice")
        assert len(s.blocked_agents) == 1
        assert "Bob" in s.blocked_agents


# ── defaults ─────────────────────────────────────────────────────────────────

class TestDefaults:
    def test_default_user_name(self):
        s = _make_session()
        assert s.user_name == "participant"

    def test_default_duration(self):
        s = _make_session()
        assert s.duration_minutes == 15

    def test_default_empty_collections(self):
        s = _make_session()
        assert s.messages == []
        assert s.blocked_agents == {}
        assert s.experimental_config == {}
        assert s.simulation_config == {}
