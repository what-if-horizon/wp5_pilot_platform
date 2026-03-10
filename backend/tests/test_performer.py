"""Unit tests for agents/STAGE/performer.py — template parsing and prompt building."""
from datetime import datetime, timezone

from models.message import Message
from agents.STAGE.performer import (
    _parse_template,
    _format_chat_log,
    _format_instruction,
    build_performer_user_prompt,
    build_performer_system_prompt,
)


def _msg(sender="Alice", content="Hello", msg_id="m1", **kwargs):
    return Message(
        sender=sender,
        content=content,
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        message_id=msg_id,
        **kwargs,
    )


# ── _parse_template ──────────────────────────────────────────────────────────

class TestParseTemplate:
    SAMPLE = (
        "Preamble text\n\n"
        "`{ACTION_TYPE_BLOCK: message}`\n"
        "Message instructions here\n\n"
        "`{ACTION_TYPE_BLOCK: reply}`\n"
        "Reply instructions here\n\n"
        "`{ACTION_TYPE_BLOCK: @mention}`\n"
        "Mention instructions here\n\n"
        "`{END_ACTION_TYPE_BLOCKS}`\n"
        "\nPostamble text"
    )

    def test_extracts_all_blocks(self):
        _, blocks = _parse_template(self.SAMPLE)
        assert "message" in blocks
        assert "reply" in blocks
        assert "@mention" in blocks

    def test_block_content_correct(self):
        _, blocks = _parse_template(self.SAMPLE)
        assert "Message instructions" in blocks["message"]
        assert "Reply instructions" in blocks["reply"]
        assert "Mention instructions" in blocks["@mention"]

    def test_base_template_has_placeholder(self):
        base, _ = _parse_template(self.SAMPLE)
        assert "{ACTION_BLOCK}" in base
        # Original block markers should be gone
        assert "ACTION_TYPE_BLOCK" not in base

    def test_preserves_surrounding_text(self):
        base, _ = _parse_template(self.SAMPLE)
        assert "Preamble text" in base
        assert "Postamble text" in base


# ── _format_chat_log ─────────────────────────────────────────────────────────

class TestFormatChatLog:
    def test_empty(self):
        assert _format_chat_log([]) == "(No messages yet)"

    def test_single_message(self):
        result = _format_chat_log([_msg()])
        assert "Alice: Hello" in result

    def test_liked_by_annotation(self):
        msg = _msg(liked_by={"Bob"})
        result = _format_chat_log([msg])
        assert "[liked by Bob]" in result

    def test_multiple_messages(self):
        msgs = [_msg(sender="A", content="x"), _msg(sender="B", content="y")]
        result = _format_chat_log(msgs)
        lines = result.strip().split("\n")
        assert len(lines) == 2


# ── _format_instruction ─────────────────────────────────────────────────────

class TestFormatInstruction:
    def test_all_keys(self):
        result = _format_instruction({
            "objective": "say hi",
            "motivation": "be friendly",
            "directive": "casual tone",
        })
        assert "**Objective**: say hi" in result
        assert "**Motivation**: be friendly" in result
        assert "**Directive**: casual tone" in result

    def test_partial_keys(self):
        result = _format_instruction({"objective": "say hi"})
        assert "**Objective**: say hi" in result
        assert "Motivation" not in result

    def test_empty_instruction(self):
        result = _format_instruction({})
        assert result == ""


# ── build_performer_system_prompt ────────────────────────────────────────────

class TestBuildPerformerSystemPrompt:
    def test_injects_chatroom_context(self):
        result = build_performer_system_prompt(chatroom_context="Climate debate")
        assert "Climate debate" in result

    def test_returns_string(self):
        result = build_performer_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0


# ── build_performer_user_prompt ──────────────────────────────────────────────

class TestBuildPerformerUserPrompt:
    def _instruction(self):
        return {"objective": "greet everyone", "motivation": "warmth"}

    def test_message_action(self):
        result = build_performer_user_prompt(
            instruction=self._instruction(),
            action_type="message",
            messages=[_msg()],
        )
        # Should contain the instruction
        assert "greet everyone" in result
        # Should contain the chat log
        assert "Alice: Hello" in result

    def test_reply_action_injects_target(self):
        target = _msg(sender="Bob", content="What do you think?", msg_id="target-1")
        result = build_performer_user_prompt(
            instruction=self._instruction(),
            action_type="reply",
            messages=[target],
            target_message=target,
        )
        assert "Bob: What do you think?" in result

    def test_reply_without_target_shows_not_found(self):
        result = build_performer_user_prompt(
            instruction=self._instruction(),
            action_type="reply",
            messages=[_msg()],
            target_message=None,
        )
        assert "(message not found)" in result

    def test_mention_action_injects_target_user(self):
        result = build_performer_user_prompt(
            instruction=self._instruction(),
            action_type="@mention",
            messages=[_msg()],
            target_user="Dave",
        )
        assert "Dave" in result

    def test_mention_without_target_user_shows_unknown(self):
        result = build_performer_user_prompt(
            instruction=self._instruction(),
            action_type="@mention",
            messages=[_msg()],
            target_user=None,
        )
        assert "(unknown)" in result

    def test_message_targeted_uses_target_user(self):
        msgs = [_msg(sender="Bob", content="I disagree")]
        result = build_performer_user_prompt(
            instruction=self._instruction(),
            action_type="message",
            messages=msgs,
            target_user="Bob",
        )
        assert "Bob" in result

    def test_unknown_action_falls_back_to_message(self):
        """Unknown action types fall back to the 'message' block."""
        result = build_performer_user_prompt(
            instruction=self._instruction(),
            action_type="nonexistent_action",
            messages=[_msg()],
        )
        # Should still produce a valid prompt (fell back to message block)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_chatroom_context_injected(self):
        result = build_performer_user_prompt(
            instruction=self._instruction(),
            action_type="message",
            messages=[],
            chatroom_context="Climate debate",
        )
        assert "Climate debate" in result

    def test_empty_messages(self):
        result = build_performer_user_prompt(
            instruction=self._instruction(),
            action_type="message",
            messages=[],
        )
        assert "(No messages yet)" in result
