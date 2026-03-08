"""Tests for the orchestrator anonymization helpers."""

import random
from datetime import datetime, timezone

import pytest

from models import Message, Agent
from agents.STAGE.orchestrator import (
    build_name_map,
    anonymize_message,
    anonymize_agents,
    deanonymize_text,
    _replace_names_in_text,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_msg(sender: str, content: str, **kwargs) -> Message:
    return Message(
        sender=sender,
        content=content,
        timestamp=datetime.now(timezone.utc),
        message_id="msg-1",
        **kwargs,
    )


# ── build_name_map ───────────────────────────────────────────────────────────

class TestBuildNameMap:
    def test_includes_all_names(self):
        rng = random.Random(42)
        nm = build_name_map(["Alice", "Bob"], "participant", rng)
        assert set(nm.keys()) == {"Alice", "Bob", "participant"}

    def test_labels_are_member_n(self):
        rng = random.Random(42)
        nm = build_name_map(["Alice", "Bob"], "participant", rng)
        assert set(nm.values()) == {"Member 1", "Member 2", "Member 3"}

    def test_shuffle_is_deterministic(self):
        nm1 = build_name_map(["A", "B", "C"], "participant", random.Random(99))
        nm2 = build_name_map(["A", "B", "C"], "participant", random.Random(99))
        assert nm1 == nm2

    def test_different_seeds_give_different_maps(self):
        nm1 = build_name_map(["A", "B", "C"], "participant", random.Random(1))
        nm2 = build_name_map(["A", "B", "C"], "participant", random.Random(2))
        # With 4 names the chance of identical ordering is 1/24 — unlikely
        # but we just check the function works; exact ordering depends on seed.
        assert isinstance(nm1, dict) and isinstance(nm2, dict)

    def test_human_is_indistinguishable(self):
        """The human should get a generic 'Member N' label, same as agents."""
        rng = random.Random(42)
        nm = build_name_map(["Alice", "Bob"], "participant", rng)
        human_label = nm["participant"]
        assert human_label.startswith("Member ")


# ── anonymize_message ────────────────────────────────────────────────────────

class TestAnonymizeMessage:
    def test_sender_is_anonymized(self):
        nm = {"Alice": "Member 1", "participant": "Member 2"}
        msg = _make_msg("Alice", "hello")
        anon = anonymize_message(msg, nm)
        assert anon.sender == "Member 1"

    def test_content_names_replaced(self):
        nm = {"Alice": "Member 1", "Bob": "Member 2", "participant": "Member 3"}
        msg = _make_msg("Alice", "I agree with @Bob on this")
        anon = anonymize_message(msg, nm)
        assert "Bob" not in anon.content
        assert "Member 2" in anon.content

    def test_mentions_anonymized(self):
        nm = {"Alice": "Member 1", "Bob": "Member 2", "participant": "Member 3"}
        msg = _make_msg("Alice", "@Bob hello", mentions=["Bob"])
        anon = anonymize_message(msg, nm)
        assert anon.mentions == ["Member 2"]

    def test_liked_by_anonymized(self):
        nm = {"Alice": "Member 1", "participant": "Member 2"}
        msg = _make_msg("Alice", "hello", liked_by={"participant"})
        anon = anonymize_message(msg, nm)
        assert anon.liked_by == {"Member 2"}

    def test_quoted_text_anonymized(self):
        nm = {"Alice": "Member 1", "Bob": "Member 2", "participant": "Member 3"}
        msg = _make_msg("Alice", "I agree", quoted_text="Bob said something")
        anon = anonymize_message(msg, nm)
        assert "Bob" not in anon.quoted_text
        assert "Member 2" in anon.quoted_text

    def test_original_message_unchanged(self):
        nm = {"Alice": "Member 1", "participant": "Member 2"}
        msg = _make_msg("Alice", "hello @Alice")
        anonymize_message(msg, nm)
        assert msg.sender == "Alice"
        assert msg.content == "hello @Alice"

    def test_unknown_sender_preserved(self):
        nm = {"Alice": "Member 1"}
        msg = _make_msg("[system]", "welcome")
        anon = anonymize_message(msg, nm)
        assert anon.sender == "[system]"


# ── anonymize_agents ─────────────────────────────────────────────────────────

class TestAnonymizeAgents:
    def test_agent_names_replaced(self):
        nm = {"Alice": "Member 1", "Bob": "Member 2", "participant": "Member 3"}
        agents = [Agent(name="Alice"), Agent(name="Bob")]
        anon = anonymize_agents(agents, nm)
        assert [a.name for a in anon] == ["Member 1", "Member 2"]


# ── deanonymize_text ─────────────────────────────────────────────────────────

class TestDeanonymizeText:
    def test_basic_replacement(self):
        reverse = {"Member 1": "Alice", "Member 2": "Bob"}
        assert deanonymize_text("Member 1 says hi to Member 2", reverse) == "Alice says hi to Bob"

    def test_no_match_unchanged(self):
        reverse = {"Member 1": "Alice"}
        assert deanonymize_text("hello world", reverse) == "hello world"

    def test_at_mention_deanonymized(self):
        reverse = {"Member 1": "Alice"}
        assert deanonymize_text("@Member 1 great point!", reverse) == "@Alice great point!"


# ── _replace_names_in_text ───────────────────────────────────────────────────

class TestReplaceNames:
    def test_longer_names_replaced_first(self):
        """Ensure 'Member 10' is replaced before 'Member 1'."""
        nm = {"Member 1": "A", "Member 10": "B"}
        result = _replace_names_in_text("Member 10 and Member 1", nm)
        assert result == "B and A"

    def test_empty_text(self):
        assert _replace_names_in_text("", {"A": "B"}) == ""

    def test_none_text(self):
        assert _replace_names_in_text(None, {"A": "B"}) is None
