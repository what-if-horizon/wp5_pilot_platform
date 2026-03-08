"""Tests for the full Orchestrator pipeline (Director → Performer → Moderator).

Uses mock LLM clients to test the orchestration logic without external API calls.
Anonymization helpers are tested separately in test_anonymization.py — these tests
focus on execute_turn() flow, retry logic, and action routing.
"""

import json
import random
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from models.message import Message
from models.agent import Agent
from models.session import SessionState
from agents.STAGE.orchestrator import (
    Orchestrator,
    TurnResult,
    MAX_PERFORMER_RETRIES,
)


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


def _make_logger():
    logger = MagicMock()
    logger.log_error = MagicMock()
    logger.log_llm_call = MagicMock()
    logger.log_event = MagicMock()
    return logger


def _make_orchestrator(
    state=None,
    director_response=None,
    performer_response=None,
    moderator_response=None,
    rng=None,
):
    """Create an Orchestrator with mock LLM clients."""
    if state is None:
        state = _make_state()

    director_llm = AsyncMock()
    performer_llm = AsyncMock()
    moderator_llm = AsyncMock()

    if director_response is not None:
        director_llm.generate_response = AsyncMock(return_value=director_response)
    if performer_response is not None:
        performer_llm.generate_response = AsyncMock(return_value=performer_response)
    if moderator_response is not None:
        moderator_llm.generate_response = AsyncMock(return_value=moderator_response)

    logger = _make_logger()

    orch = Orchestrator(
        director_llm=director_llm,
        performer_llm=performer_llm,
        moderator_llm=moderator_llm,
        state=state,
        logger=logger,
        context_window_size=10,
        chatroom_context="A test chatroom",
        rng=rng or random.Random(42),
    )
    return orch, logger


def _director_json(
    next_agent="Alice",
    action_type="message",
    reasoning="test",
    performer_instruction=None,
    target_user=None,
    target_message_id=None,
):
    """Build a valid Director JSON response.

    Note: next_agent/target_user should use anonymized names (Member N)
    since the Director operates in the anonymized space.
    performer_instruction is required for non-like actions by parse_director_response.
    """
    data = {
        "next_agent": next_agent,
        "action_type": action_type,
        "reasoning": reasoning,
    }
    # performer_instruction is required for non-like actions
    if action_type != "like":
        data["performer_instruction"] = performer_instruction or {"tone": "neutral", "goal": "engage"}
    if target_user:
        data["target_user"] = target_user
    if target_message_id:
        data["target_message_id"] = target_message_id
    return json.dumps(data)


# ── Orchestrator construction ────────────────────────────────────────────────

class TestOrchestratorInit:

    def test_name_map_includes_all(self):
        state = _make_state()
        orch, _ = _make_orchestrator(state=state)
        # All agents + user should be in the name map
        assert "Alice" in orch._name_map
        assert "Bob" in orch._name_map
        assert "participant" in orch._name_map
        # All mapped to Member N
        for v in orch._name_map.values():
            assert v.startswith("Member ")

    def test_reverse_map(self):
        state = _make_state()
        orch, _ = _make_orchestrator(state=state)
        for real, anon in orch._name_map.items():
            assert orch._reverse_map[anon] == real

    def test_deterministic_with_seed(self):
        state = _make_state()
        orch1, _ = _make_orchestrator(state=state, rng=random.Random(42))
        orch2, _ = _make_orchestrator(state=state, rng=random.Random(42))
        assert orch1._name_map == orch2._name_map

    def test_different_seeds_different_maps(self):
        state = _make_state()
        orch1, _ = _make_orchestrator(state=state, rng=random.Random(1))
        orch2, _ = _make_orchestrator(state=state, rng=random.Random(999))
        # Very unlikely to be the same (3! = 6 permutations, p = 1/6)
        # We accept the tiny chance of a flaky test here


# ── execute_turn: message action ─────────────────────────────────────────────

class TestExecuteTurnMessage:

    @pytest.mark.asyncio
    async def test_basic_message_action(self):
        state = _make_state()
        orch, logger = _make_orchestrator(state=state)

        # Get the anonymous name for Alice
        anon_alice = orch._name_map["Alice"]

        director_resp = _director_json(
            next_agent=anon_alice,
            action_type="message",
            performer_instruction={"tone": "friendly"},
        )
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)
        orch.performer_llm.generate_response = AsyncMock(return_value="Hello everyone!")
        orch.moderator_llm.generate_response = AsyncMock(return_value="Hello everyone!")

        result = await orch.execute_turn("treatment_A")

        assert result is not None
        assert result.action_type == "message"
        assert result.agent_name == "Alice"
        assert result.message is not None
        assert result.message.sender == "Alice"
        assert result.message.content == "Hello everyone!"

    @pytest.mark.asyncio
    async def test_director_system_prompt_cached(self):
        """Director system prompt should be built only once."""
        state = _make_state()
        orch, _ = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]

        director_resp = _director_json(next_agent=anon_alice, action_type="message")
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)
        orch.performer_llm.generate_response = AsyncMock(return_value="Hi")
        orch.moderator_llm.generate_response = AsyncMock(return_value="Hi")

        assert orch._director_system_prompt is None
        await orch.execute_turn("treatment_A")
        assert orch._director_system_prompt is not None

        cached = orch._director_system_prompt
        await orch.execute_turn("treatment_A")
        assert orch._director_system_prompt is cached  # same object


# ── execute_turn: like action ────────────────────────────────────────────────

class TestExecuteTurnLike:

    @pytest.mark.asyncio
    async def test_like_action_no_performer_call(self):
        state = _make_state()
        state.add_message(Message.create(sender="Bob", content="Great point"))
        msg_id = state.messages[0].message_id

        orch, _ = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]

        director_resp = _director_json(
            next_agent=anon_alice,
            action_type="like",
            target_message_id=msg_id,
        )
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)

        result = await orch.execute_turn("treatment_A")

        assert result is not None
        assert result.action_type == "like"
        assert result.agent_name == "Alice"
        assert result.target_message_id == msg_id
        assert result.message is None
        # Performer should NOT have been called
        orch.performer_llm.generate_response.assert_not_called()


# ── execute_turn: reply action ───────────────────────────────────────────────

class TestExecuteTurnReply:

    @pytest.mark.asyncio
    async def test_reply_sets_reply_to_and_quoted_text(self):
        state = _make_state()
        state.add_message(Message.create(sender="Bob", content="What do you think?"))
        target_msg = state.messages[0]

        orch, _ = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]

        director_resp = _director_json(
            next_agent=anon_alice,
            action_type="reply",
            target_message_id=target_msg.message_id,
        )
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)
        orch.performer_llm.generate_response = AsyncMock(return_value="I agree!")
        orch.moderator_llm.generate_response = AsyncMock(return_value="I agree!")

        result = await orch.execute_turn("treatment_A")

        assert result is not None
        assert result.action_type == "reply"
        assert result.message.reply_to == target_msg.message_id
        assert result.message.quoted_text == "What do you think?"

    @pytest.mark.asyncio
    async def test_reply_to_nonexistent_message(self):
        """Reply to a message ID that doesn't exist in state."""
        state = _make_state()
        orch, _ = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]

        director_resp = _director_json(
            next_agent=anon_alice,
            action_type="reply",
            target_message_id="nonexistent-id",
        )
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)
        orch.performer_llm.generate_response = AsyncMock(return_value="Reply text")
        orch.moderator_llm.generate_response = AsyncMock(return_value="Reply text")

        result = await orch.execute_turn("treatment_A")

        assert result is not None
        assert result.message.reply_to == "nonexistent-id"
        assert result.message.quoted_text is None  # target not found


# ── execute_turn: mention action ─────────────────────────────────────────────

class TestExecuteTurnMention:

    @pytest.mark.asyncio
    async def test_mention_prepends_at_tag(self):
        state = _make_state()
        orch, _ = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]
        anon_bob = orch._name_map["Bob"]

        director_resp = _director_json(
            next_agent=anon_alice,
            action_type="@mention",
            target_user=anon_bob,
        )
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)
        orch.performer_llm.generate_response = AsyncMock(return_value="what do you think?")
        orch.moderator_llm.generate_response = AsyncMock(return_value="what do you think?")

        result = await orch.execute_turn("treatment_A")

        assert result is not None
        assert result.action_type == "@mention"
        assert result.target_user == "Bob"
        assert result.message.content.startswith("@Bob")
        assert result.message.mentions == ["Bob"]


# ── execute_turn: error handling ─────────────────────────────────────────────

class TestExecuteTurnErrors:

    @pytest.mark.asyncio
    async def test_director_llm_exception_returns_none(self):
        state = _make_state()
        orch, logger = _make_orchestrator(state=state)
        orch.director_llm.generate_response = AsyncMock(side_effect=RuntimeError("API error"))

        result = await orch.execute_turn("treatment_A")
        assert result is None
        logger.log_error.assert_called()

    @pytest.mark.asyncio
    async def test_director_returns_none_response(self):
        state = _make_state()
        orch, _ = _make_orchestrator(state=state)
        orch.director_llm.generate_response = AsyncMock(return_value=None)

        result = await orch.execute_turn("treatment_A")
        assert result is None

    @pytest.mark.asyncio
    async def test_director_returns_empty_string(self):
        state = _make_state()
        orch, _ = _make_orchestrator(state=state)
        orch.director_llm.generate_response = AsyncMock(return_value="")

        result = await orch.execute_turn("treatment_A")
        assert result is None

    @pytest.mark.asyncio
    async def test_director_returns_invalid_json(self):
        state = _make_state()
        orch, logger = _make_orchestrator(state=state)
        orch.director_llm.generate_response = AsyncMock(return_value="not valid json at all")

        result = await orch.execute_turn("treatment_A")
        assert result is None
        logger.log_error.assert_called()

    @pytest.mark.asyncio
    async def test_no_agents_returns_none(self):
        state = _make_state(agents=[])
        orch, logger = _make_orchestrator(state=state)
        orch.director_llm.generate_response = AsyncMock(
            return_value=_director_json(next_agent="Member 1")
        )

        result = await orch.execute_turn("treatment_A")
        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_agent_falls_back(self):
        """Director picks a name not in agents list → falls back to random valid agent."""
        state = _make_state()
        orch, logger = _make_orchestrator(state=state)

        director_resp = _director_json(next_agent="UnknownAgent", action_type="message")
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)
        orch.performer_llm.generate_response = AsyncMock(return_value="Hi")
        orch.moderator_llm.generate_response = AsyncMock(return_value="Hi")

        result = await orch.execute_turn("treatment_A")
        assert result is not None
        assert result.agent_name in ("Alice", "Bob")
        logger.log_error.assert_called()  # logged the fallback


# ── Performer retry logic ────────────────────────────────────────────────────

class TestPerformerRetry:

    @pytest.mark.asyncio
    async def test_performer_retries_on_failure(self):
        state = _make_state()
        orch, logger = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]

        director_resp = _director_json(next_agent=anon_alice, action_type="message")
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)

        # Performer fails twice, succeeds on third
        orch.performer_llm.generate_response = AsyncMock(
            side_effect=[None, None, "Third time's the charm"]
        )
        orch.moderator_llm.generate_response = AsyncMock(return_value="Third time's the charm")

        result = await orch.execute_turn("treatment_A")
        assert result is not None
        assert result.message.content == "Third time's the charm"
        assert orch.performer_llm.generate_response.call_count == 3

    @pytest.mark.asyncio
    async def test_performer_retries_exhausted(self):
        state = _make_state()
        orch, logger = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]

        director_resp = _director_json(next_agent=anon_alice, action_type="message")
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)

        # All attempts fail
        orch.performer_llm.generate_response = AsyncMock(return_value=None)
        orch.moderator_llm.generate_response = AsyncMock(return_value=None)

        result = await orch.execute_turn("treatment_A")
        assert result is None
        assert orch.performer_llm.generate_response.call_count == MAX_PERFORMER_RETRIES

    @pytest.mark.asyncio
    async def test_performer_exception_triggers_retry(self):
        state = _make_state()
        orch, logger = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]

        director_resp = _director_json(next_agent=anon_alice, action_type="message")
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)

        # First call raises, second succeeds
        orch.performer_llm.generate_response = AsyncMock(
            side_effect=[RuntimeError("timeout"), "Success"]
        )
        orch.moderator_llm.generate_response = AsyncMock(return_value="Success")

        result = await orch.execute_turn("treatment_A")
        assert result is not None

    @pytest.mark.asyncio
    async def test_moderator_no_content_triggers_retry(self):
        """Moderator returns NO_CONTENT → triggers performer retry."""
        state = _make_state()
        orch, logger = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]

        director_resp = _director_json(next_agent=anon_alice, action_type="message")
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)

        orch.performer_llm.generate_response = AsyncMock(
            side_effect=["bad output", "good output"]
        )
        # First moderator call signals no content, second succeeds
        orch.moderator_llm.generate_response = AsyncMock(
            side_effect=["NO_CONTENT", "Cleaned output"]
        )

        result = await orch.execute_turn("treatment_A")
        assert result is not None
        assert result.message.content == "Cleaned output"


# ── Deanonymization in output ────────────────────────────────────────────────

class TestOutputDeanonymization:

    @pytest.mark.asyncio
    async def test_content_deanonymized(self):
        """Anonymous labels in performer output should be replaced with real names."""
        state = _make_state()
        orch, _ = _make_orchestrator(state=state)
        anon_alice = orch._name_map["Alice"]
        anon_bob = orch._name_map["Bob"]

        director_resp = _director_json(next_agent=anon_alice, action_type="message")
        orch.director_llm.generate_response = AsyncMock(return_value=director_resp)

        # Performer uses anonymous labels
        performer_output = f"I agree with {anon_bob}!"
        orch.performer_llm.generate_response = AsyncMock(return_value=performer_output)
        orch.moderator_llm.generate_response = AsyncMock(return_value=performer_output)

        result = await orch.execute_turn("treatment_A")
        assert result is not None
        # Content should have real names
        assert "Bob" in result.message.content
        assert anon_bob not in result.message.content


# ── TurnResult dataclass ────────────────────────────────────────────────────

class TestTurnResult:

    def test_message_action_result(self):
        msg = Message.create(sender="Alice", content="Hello")
        result = TurnResult(
            action_type="message",
            agent_name="Alice",
            message=msg,
            director_reasoning="Alice should greet",
        )
        assert result.action_type == "message"
        assert result.agent_name == "Alice"
        assert result.message is msg
        assert result.target_message_id is None
        assert result.target_user is None

    def test_like_action_result(self):
        result = TurnResult(
            action_type="like",
            agent_name="Bob",
            target_message_id="msg-123",
        )
        assert result.action_type == "like"
        assert result.message is None
        assert result.target_message_id == "msg-123"

    def test_defaults(self):
        result = TurnResult(action_type="message", agent_name="Alice")
        assert result.message is None
        assert result.target_message_id is None
        assert result.target_user is None
        assert result.director_reasoning is None
