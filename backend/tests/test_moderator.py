"""Unit tests for agents/STAGE/moderator.py — response parsing and prompt building."""
from agents.STAGE.moderator import (
    parse_moderator_response,
    build_moderator_system_prompt,
    build_moderator_user_prompt,
    NO_CONTENT,
)


# ── parse_moderator_response ─────────────────────────────────────────────────

class TestParseModeratorResponse:
    def test_normal_content(self):
        assert parse_moderator_response("Hello world") == "Hello world"

    def test_strips_whitespace(self):
        assert parse_moderator_response("  Hello world  ") == "Hello world"

    def test_no_content_sentinel(self):
        assert parse_moderator_response("NO_CONTENT") is None

    def test_no_content_with_whitespace(self):
        assert parse_moderator_response("  NO_CONTENT  ") is None

    def test_empty_string(self):
        assert parse_moderator_response("") is None

    def test_none_input(self):
        assert parse_moderator_response(None) is None

    def test_whitespace_only(self):
        assert parse_moderator_response("   ") is None

    def test_multiline_content(self):
        raw = "Line one\nLine two"
        result = parse_moderator_response(raw)
        assert result == "Line one\nLine two"

    def test_no_content_case_sensitive(self):
        """NO_CONTENT is case-sensitive; lowercase should pass through."""
        result = parse_moderator_response("no_content")
        assert result == "no_content"

    def test_no_content_as_substring(self):
        """NO_CONTENT embedded in other text should not be treated as sentinel."""
        result = parse_moderator_response("The result was NO_CONTENT but continued")
        assert result is not None


# ── NO_CONTENT sentinel ──────────────────────────────────────────────────────

class TestNoContentSentinel:
    def test_value(self):
        assert NO_CONTENT == "NO_CONTENT"


# ── build_moderator_system_prompt ────────────────────────────────────────────

class TestBuildModeratorSystemPrompt:
    def test_returns_string(self):
        result = build_moderator_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_injects_chatroom_context(self):
        result = build_moderator_system_prompt(chatroom_context="News discussion")
        assert "News discussion" in result


# ── build_moderator_user_prompt ──────────────────────────────────────────────

class TestBuildModeratorUserPrompt:
    def test_injects_performer_output(self):
        result = build_moderator_user_prompt("I think that's a great point!", "message")
        assert "I think that's a great point!" in result

    def test_injects_action_type(self):
        result = build_moderator_user_prompt("some output", "reply")
        assert "reply" in result

    def test_returns_string(self):
        result = build_moderator_user_prompt("output", "message")
        assert isinstance(result, str)
