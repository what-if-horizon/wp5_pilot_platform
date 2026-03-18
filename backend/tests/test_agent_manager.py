"""Tests for AgentManager — message persistence, like handling, Redis pub/sub.

All external dependencies (DB, Redis) are mocked so tests run without infrastructure.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from models.message import Message
from models.agent import Agent
from models.session import SessionState
from agents.agent_manager import AgentManager
from agents.STAGE.orchestrator import TurnResult


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


def _make_agent_manager(state=None) -> AgentManager:
    if state is None:
        state = _make_state()
    orchestrator = MagicMock()
    logger = MagicMock()
    logger.log_error = MagicMock()
    logger.log_event = MagicMock()
    return AgentManager(
        state=state,
        orchestrator=orchestrator,
        logger=logger,
        session_id="test-session",
        experiment_id="test-experiment",
    )


# ── _handle_message ──────────────────────────────────────────────────────────

class TestHandleMessage:

    @pytest.mark.asyncio
    async def test_adds_message_to_state(self):
        state = _make_state()
        am = _make_agent_manager(state)
        msg = Message.create(sender="Alice", content="Hello")
        result = TurnResult(action_type="message", agent_name="Alice", message=msg)

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.insert_message = AsyncMock()
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.push_to_window = AsyncMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_message(result)

        assert len(state.messages) == 1
        assert state.messages[0] is msg

    @pytest.mark.asyncio
    async def test_persists_to_db(self):
        am = _make_agent_manager()
        msg = Message.create(sender="Alice", content="Hello")
        result = TurnResult(action_type="message", agent_name="Alice", message=msg)

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_pool = MagicMock()
            mock_db.get_pool.return_value = mock_pool
            mock_msg_repo.insert_message = AsyncMock()
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.push_to_window = AsyncMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_message(result)

            mock_msg_repo.insert_message.assert_called_once()
            call_kwargs = mock_msg_repo.insert_message.call_args
            assert call_kwargs.kwargs["session_id"] == "test-session"
            assert call_kwargs.kwargs["sender"] == "Alice"
            assert call_kwargs.kwargs["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_pushes_to_redis_window(self):
        am = _make_agent_manager()
        msg = Message.create(sender="Alice", content="Hello")
        result = TurnResult(action_type="message", agent_name="Alice", message=msg)

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.insert_message = AsyncMock()
            fake_r = MagicMock()
            mock_redis.get_redis.return_value = fake_r
            mock_redis.push_to_window = AsyncMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_message(result)

            mock_redis.push_to_window.assert_called_once()

    @pytest.mark.asyncio
    async def test_publishes_via_pubsub(self):
        am = _make_agent_manager()
        msg = Message.create(sender="Alice", content="Hello")
        result = TurnResult(action_type="message", agent_name="Alice", message=msg)

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.insert_message = AsyncMock()
            fake_r = MagicMock()
            mock_redis.get_redis.return_value = fake_r
            mock_redis.push_to_window = AsyncMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_message(result)

            mock_redis.publish_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_message_event(self):
        am = _make_agent_manager()
        msg = Message.create(sender="Alice", content="Hello")
        result = TurnResult(action_type="message", agent_name="Alice", message=msg)

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.insert_message = AsyncMock()
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.push_to_window = AsyncMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_message(result)

            mock_msg_repo.insert_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_message_is_noop(self):
        am = _make_agent_manager()
        result = TurnResult(action_type="message", agent_name="Alice", message=None)

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_msg_repo.insert_message = AsyncMock()

            await am._handle_message(result)

            mock_msg_repo.insert_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_logged_not_raised(self):
        am = _make_agent_manager()
        msg = Message.create(sender="Alice", content="Hello")
        result = TurnResult(action_type="message", agent_name="Alice", message=msg)

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.insert_message = AsyncMock(side_effect=RuntimeError("DB down"))
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.push_to_window = AsyncMock()
            mock_redis.publish_event = AsyncMock()

            # Should not raise
            await am._handle_message(result)

            am.logger.log_error.assert_called()

    @pytest.mark.asyncio
    async def test_redis_error_logged_not_raised(self):
        am = _make_agent_manager()
        msg = Message.create(sender="Alice", content="Hello")
        result = TurnResult(action_type="message", agent_name="Alice", message=msg)

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.insert_message = AsyncMock()
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.push_to_window = AsyncMock(side_effect=RuntimeError("Redis down"))
            mock_redis.publish_event = AsyncMock()

            await am._handle_message(result)

            am.logger.log_error.assert_called()


# ── _handle_like ─────────────────────────────────────────────────────────────

class TestHandleLike:

    @pytest.mark.asyncio
    async def test_toggles_like_on_target(self):
        state = _make_state()
        msg = Message.create(sender="Bob", content="Great point")
        state.add_message(msg)

        am = _make_agent_manager(state)
        result = TurnResult(
            action_type="like",
            agent_name="Alice",
            target_message_id=msg.message_id,
        )

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.update_message_likes = AsyncMock()
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_like(result)

        assert "Alice" in msg.liked_by

    @pytest.mark.asyncio
    async def test_persists_likes_to_db(self):
        state = _make_state()
        msg = Message.create(sender="Bob", content="Great point")
        state.add_message(msg)

        am = _make_agent_manager(state)
        result = TurnResult(
            action_type="like",
            agent_name="Alice",
            target_message_id=msg.message_id,
        )

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.update_message_likes = AsyncMock()
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_like(result)

            mock_msg_repo.update_message_likes.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcasts_like_event(self):
        state = _make_state()
        msg = Message.create(sender="Bob", content="Great point")
        state.add_message(msg)

        am = _make_agent_manager(state)
        result = TurnResult(
            action_type="like",
            agent_name="Alice",
            target_message_id=msg.message_id,
        )

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.update_message_likes = AsyncMock()
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_like(result)

            mock_redis.publish_event.assert_called_once()
            event = mock_redis.publish_event.call_args[0][2]
            assert event["event_type"] == "message_like"
            assert event["message_id"] == msg.message_id

    @pytest.mark.asyncio
    async def test_no_target_id_is_noop(self):
        am = _make_agent_manager()
        result = TurnResult(
            action_type="like",
            agent_name="Alice",
            target_message_id=None,
        )

        with patch("agents.agent_manager.db_conn"), \
             patch("agents.agent_manager.redis_client"), \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_msg_repo.update_message_likes = AsyncMock()

            await am._handle_like(result)

            mock_msg_repo.update_message_likes.assert_not_called()

    @pytest.mark.asyncio
    async def test_target_not_found_logs_error(self):
        state = _make_state()
        am = _make_agent_manager(state)
        result = TurnResult(
            action_type="like",
            agent_name="Alice",
            target_message_id="nonexistent-id",
        )

        with patch("agents.agent_manager.db_conn"), \
             patch("agents.agent_manager.redis_client"), \
             patch("agents.agent_manager.message_repo"):

            await am._handle_like(result)

            am.logger.log_error.assert_called_once()
            assert "not found" in am.logger.log_error.call_args[0][1]

    @pytest.mark.asyncio
    async def test_db_error_on_like_logged(self):
        state = _make_state()
        msg = Message.create(sender="Bob", content="Test")
        state.add_message(msg)

        am = _make_agent_manager(state)
        result = TurnResult(
            action_type="like",
            agent_name="Alice",
            target_message_id=msg.message_id,
        )

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.update_message_likes = AsyncMock(
                side_effect=RuntimeError("DB error")
            )
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_like(result)

            am.logger.log_error.assert_called()

    @pytest.mark.asyncio
    async def test_logs_like_event(self):
        state = _make_state()
        msg = Message.create(sender="Bob", content="Test")
        state.add_message(msg)

        am = _make_agent_manager(state)
        result = TurnResult(
            action_type="like",
            agent_name="Alice",
            target_message_id=msg.message_id,
        )

        with patch("agents.agent_manager.db_conn") as mock_db, \
             patch("agents.agent_manager.redis_client") as mock_redis, \
             patch("agents.agent_manager.message_repo") as mock_msg_repo:
            mock_db.get_pool.return_value = MagicMock()
            mock_msg_repo.update_message_likes = AsyncMock()
            mock_redis.get_redis.return_value = MagicMock()
            mock_redis.publish_event = AsyncMock()

            await am._handle_like(result)

            am.logger.log_event.assert_called_once()
            call_args = am.logger.log_event.call_args[0]
            assert call_args[0] == "agent_like"
            assert call_args[1]["agent_name"] == "Alice"
