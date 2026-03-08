"""Unit tests for agents/STAGE/director.py — parsing and formatting."""
import json
import pytest
from datetime import datetime, timezone

from models.message import Message
from models.agent import Agent
from agents.STAGE.director import format_chat_log, parse_director_response


# ── helpers ──────────────────────────────────────────────────────────────────

def _msg(sender="Alice", content="Hello", msg_id="msg-1", **kwargs):
    return Message(
        sender=sender,
        content=content,
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        message_id=msg_id,
        **kwargs,
    )


# ── format_chat_log ─────────────────────────────────────────────────────────

class TestFormatChatLog:
    def test_empty_messages(self):
        assert format_chat_log([]) == "(No messages yet)"

    def test_single_message(self):
        result = format_chat_log([_msg()])
        assert "[msg-1] Alice: Hello" in result

    def test_multiple_messages_each_on_own_line(self):
        msgs = [
            _msg(sender="Alice", content="Hi", msg_id="m1"),
            _msg(sender="Bob", content="Hey", msg_id="m2"),
        ]
        result = format_chat_log(msgs)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert "[m1] Alice: Hi" in lines[0]
        assert "[m2] Bob: Hey" in lines[1]

    def test_reply_metadata(self):
        msg = _msg(reply_to="m0")
        result = format_chat_log([msg])
        assert "replying to m0" in result

    def test_mention_metadata(self):
        msg = _msg(mentions=["Bob", "Carol"])
        result = format_chat_log([msg])
        assert "@mentions Bob, Carol" in result

    def test_liked_by_metadata(self):
        msg = _msg(liked_by={"Bob", "Carol"})
        result = format_chat_log([msg])
        assert "liked by" in result
        # Liked_by is sorted
        assert "Bob" in result
        assert "Carol" in result

    def test_multiple_metadata_separated_by_semicolons(self):
        msg = _msg(reply_to="m0", mentions=["Bob"], liked_by={"Carol"})
        result = format_chat_log([msg])
        assert ";" in result  # metadata items separated by semicolons


# ── parse_director_response — valid inputs ───────────────────────────────────

class TestParseDirectorResponseValid:
    def test_plain_json(self):
        raw = json.dumps({
            "next_agent": "Alice",
            "action_type": "message",
            "performer_instruction": {"objective": "say hi"},
        })
        data = parse_director_response(raw)
        assert data["next_agent"] == "Alice"
        assert data["action_type"] == "message"

    def test_json_in_markdown_fence(self):
        raw = '```json\n{"next_agent":"Alice","action_type":"message","performer_instruction":{"objective":"greet"}}\n```'
        data = parse_director_response(raw)
        assert data["next_agent"] == "Alice"

    def test_json_in_bare_fence(self):
        raw = '```\n{"next_agent":"Alice","action_type":"message","performer_instruction":{"objective":"greet"}}\n```'
        data = parse_director_response(raw)
        assert data["next_agent"] == "Alice"

    def test_reply_action(self):
        raw = json.dumps({
            "next_agent": "Bob",
            "action_type": "reply",
            "target_message_id": "msg-42",
            "performer_instruction": {"objective": "agree"},
        })
        data = parse_director_response(raw)
        assert data["action_type"] == "reply"
        assert data["target_message_id"] == "msg-42"

    def test_like_action(self):
        raw = json.dumps({
            "next_agent": "Bob",
            "action_type": "like",
            "target_message_id": "msg-42",
        })
        data = parse_director_response(raw)
        assert data["action_type"] == "like"

    def test_mention_action(self):
        raw = json.dumps({
            "next_agent": "Carol",
            "action_type": "@mention",
            "target_user": "Dave",
            "performer_instruction": {"objective": "ask question"},
        })
        data = parse_director_response(raw)
        assert data["target_user"] == "Dave"

    def test_like_does_not_require_performer_instruction(self):
        raw = json.dumps({
            "next_agent": "Alice",
            "action_type": "like",
            "target_message_id": "msg-1",
        })
        data = parse_director_response(raw)
        assert "performer_instruction" not in data


# ── parse_director_response — invalid inputs ─────────────────────────────────

class TestParseDirectorResponseInvalid:
    def test_not_json(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_director_response("this is not json at all")

    def test_missing_next_agent(self):
        raw = json.dumps({"action_type": "message", "performer_instruction": {}})
        with pytest.raises(ValueError, match="next_agent"):
            parse_director_response(raw)

    def test_missing_action_type(self):
        raw = json.dumps({"next_agent": "Alice", "performer_instruction": {}})
        with pytest.raises(ValueError, match="action_type"):
            parse_director_response(raw)

    def test_invalid_action_type(self):
        raw = json.dumps({
            "next_agent": "Alice",
            "action_type": "shout",
            "performer_instruction": {},
        })
        with pytest.raises(ValueError, match="invalid action_type"):
            parse_director_response(raw)

    def test_reply_missing_target_message_id(self):
        raw = json.dumps({
            "next_agent": "Alice",
            "action_type": "reply",
            "performer_instruction": {"objective": "agree"},
        })
        with pytest.raises(ValueError, match="target_message_id"):
            parse_director_response(raw)

    def test_like_missing_target_message_id(self):
        raw = json.dumps({
            "next_agent": "Alice",
            "action_type": "like",
        })
        with pytest.raises(ValueError, match="target_message_id"):
            parse_director_response(raw)

    def test_mention_missing_target_user(self):
        raw = json.dumps({
            "next_agent": "Alice",
            "action_type": "@mention",
            "performer_instruction": {"objective": "greet"},
        })
        with pytest.raises(ValueError, match="target_user"):
            parse_director_response(raw)

    def test_message_missing_performer_instruction(self):
        raw = json.dumps({
            "next_agent": "Alice",
            "action_type": "message",
        })
        with pytest.raises(ValueError, match="performer_instruction"):
            parse_director_response(raw)

    def test_reply_missing_performer_instruction(self):
        raw = json.dumps({
            "next_agent": "Alice",
            "action_type": "reply",
            "target_message_id": "m1",
        })
        with pytest.raises(ValueError, match="performer_instruction"):
            parse_director_response(raw)

    def test_mention_missing_performer_instruction(self):
        raw = json.dumps({
            "next_agent": "Alice",
            "action_type": "@mention",
            "target_user": "Bob",
        })
        with pytest.raises(ValueError, match="performer_instruction"):
            parse_director_response(raw)
