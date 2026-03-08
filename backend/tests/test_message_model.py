"""Unit tests for models/message.py — Message dataclass."""
from datetime import datetime, timezone

from models.message import Message


def _make_msg(**kwargs):
    """Create a Message with sensible defaults for tests."""
    defaults = dict(
        sender="Alice",
        content="Hello world",
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        message_id="msg-1",
    )
    defaults.update(kwargs)
    return Message(**defaults)


# ── create() factory ─────────────────────────────────────────────────────────

class TestCreate:
    def test_basic_fields(self):
        msg = Message.create(sender="Alice", content="hi")
        assert msg.sender == "Alice"
        assert msg.content == "hi"

    def test_auto_id_is_uuid(self):
        msg = Message.create(sender="Alice", content="hi")
        assert len(msg.message_id) == 36  # UUID4 string

    def test_auto_timestamp_is_utc(self):
        msg = Message.create(sender="Alice", content="hi")
        assert msg.timestamp.tzinfo is not None

    def test_unique_ids(self):
        a = Message.create(sender="A", content="x")
        b = Message.create(sender="B", content="y")
        assert a.message_id != b.message_id

    def test_optional_reply_fields(self):
        msg = Message.create(
            sender="Alice",
            content="yes",
            reply_to="msg-0",
            quoted_text="original text",
        )
        assert msg.reply_to == "msg-0"
        assert msg.quoted_text == "original text"

    def test_optional_mentions(self):
        msg = Message.create(sender="Alice", content="hey @Bob", mentions=["Bob"])
        assert msg.mentions == ["Bob"]

    def test_defaults_empty(self):
        msg = Message.create(sender="Alice", content="hi")
        assert msg.reply_to is None
        assert msg.quoted_text is None
        assert msg.mentions is None
        assert msg.liked_by == set()
        assert msg.reported is False
        assert msg.metadata == {}


# ── to_dict() serialization ──────────────────────────────────────────────────

class TestToDict:
    def test_required_keys(self):
        d = _make_msg().to_dict()
        for key in ["sender", "content", "timestamp", "message_id",
                     "reply_to", "quoted_text", "mentions",
                     "likes_count", "liked_by", "reported"]:
            assert key in d

    def test_timestamp_is_iso_string(self):
        d = _make_msg().to_dict()
        assert isinstance(d["timestamp"], str)
        # Should parse back
        datetime.fromisoformat(d["timestamp"])

    def test_likes_count_matches_liked_by(self):
        msg = _make_msg(liked_by={"Bob", "Carol"})
        d = msg.to_dict()
        assert d["likes_count"] == 2
        assert set(d["liked_by"]) == {"Bob", "Carol"}

    def test_liked_by_is_list(self):
        """liked_by set is serialized as a list."""
        d = _make_msg(liked_by={"X"}).to_dict()
        assert isinstance(d["liked_by"], list)

    def test_metadata_merged_into_dict(self):
        msg = _make_msg(metadata={"scenario": "news", "headline": "Breaking"})
        d = msg.to_dict()
        assert d["scenario"] == "news"
        assert d["headline"] == "Breaking"

    def test_empty_metadata_does_not_add_keys(self):
        d = _make_msg(metadata={}).to_dict()
        assert "scenario" not in d


# ── likes_count property ─────────────────────────────────────────────────────

class TestLikesCount:
    def test_zero_by_default(self):
        assert _make_msg().likes_count == 0

    def test_reflects_liked_by_size(self):
        msg = _make_msg(liked_by={"A", "B", "C"})
        assert msg.likes_count == 3


# ── toggle_like() ────────────────────────────────────────────────────────────

class TestToggleLike:
    def test_like_new_user(self):
        msg = _make_msg()
        result = msg.toggle_like("Bob")
        assert result == "liked"
        assert "Bob" in msg.liked_by
        assert msg.likes_count == 1

    def test_unlike_existing_user(self):
        msg = _make_msg(liked_by={"Bob"})
        result = msg.toggle_like("Bob")
        assert result == "unliked"
        assert "Bob" not in msg.liked_by
        assert msg.likes_count == 0

    def test_toggle_cycle(self):
        msg = _make_msg()
        assert msg.toggle_like("X") == "liked"
        assert msg.toggle_like("X") == "unliked"
        assert msg.toggle_like("X") == "liked"
        assert msg.likes_count == 1

    def test_multiple_users(self):
        msg = _make_msg()
        msg.toggle_like("A")
        msg.toggle_like("B")
        msg.toggle_like("C")
        assert msg.likes_count == 3
        msg.toggle_like("B")  # unlike
        assert msg.likes_count == 2
        assert "B" not in msg.liked_by


# ── toggle_report() ──────────────────────────────────────────────────────────

class TestToggleReport:
    def test_report_unreported_message(self):
        msg = _make_msg()
        result = msg.toggle_report()
        assert result == "reported"
        assert msg.reported is True

    def test_unreport_reported_message(self):
        msg = _make_msg(reported=True)
        result = msg.toggle_report()
        assert result == "unreported"
        assert msg.reported is False

    def test_toggle_cycle(self):
        msg = _make_msg()
        assert msg.toggle_report() == "reported"
        assert msg.toggle_report() == "unreported"
        assert msg.toggle_report() == "reported"
        assert msg.reported is True
