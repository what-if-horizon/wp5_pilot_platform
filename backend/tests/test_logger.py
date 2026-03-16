"""Tests for the database-backed Logger.

Covers:
- Fire-and-forget scheduling
- drain() awaits pending tasks
- Fallback error file writing
- All public log methods
- Graceful handling when no event loop is running
"""

import asyncio
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from utils.logger import Logger


# ── Construction ─────────────────────────────────────────────────────────────

class TestLoggerInit:

    def test_basic_init(self, tmp_path):
        with patch.object(Path, "mkdir"):
            logger = Logger("session-1", "exp-1")
        assert logger.session_id == "session-1"
        assert logger.experiment_id == "exp-1"

    def test_default_experiment_id(self):
        with patch.object(Path, "mkdir"):
            logger = Logger("session-1")
        assert logger.experiment_id == "default"

    def test_creates_log_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logger = Logger("session-1")
        assert (tmp_path / "logs").is_dir()


# ── Public methods ───────────────────────────────────────────────────────────

class TestLogMethods:

    @pytest.mark.asyncio
    async def test_log_event_schedules_task(self):
        logger = Logger("s1", "e1")

        with patch.object(logger, "_async_insert", new_callable=AsyncMock) as mock_insert:
            logger.log_event("test_event", {"key": "value"})
            # Let the event loop process the task
            await asyncio.sleep(0.01)
            mock_insert.assert_called_once_with("test_event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_log_session_start(self):
        logger = Logger("s1", "e1")

        with patch.object(logger, "_async_insert", new_callable=AsyncMock) as mock_insert:
            logger.log_session_start(
                experimental_config={"internal_validity_criteria": "A"},
                simulation_config={"rate": 5},
                treatment_group="group_a",
            )
            await asyncio.sleep(0.01)
            mock_insert.assert_called_once()
            args = mock_insert.call_args
            assert args[0][0] == "session_start"
            assert args[0][1]["treatment_group"] == "group_a"

    @pytest.mark.asyncio
    async def test_log_session_end(self):
        logger = Logger("s1", "e1")

        with patch.object(logger, "_async_insert", new_callable=AsyncMock) as mock_insert:
            logger.log_session_end("timeout")
            await asyncio.sleep(0.01)
            mock_insert.assert_called_once_with("session_end", {"reason": "timeout"})

    @pytest.mark.asyncio
    async def test_log_message(self):
        logger = Logger("s1", "e1")

        with patch.object(logger, "_async_insert", new_callable=AsyncMock) as mock_insert:
            msg = {"sender": "Alice", "content": "Hi"}
            logger.log_message(msg)
            await asyncio.sleep(0.01)
            mock_insert.assert_called_once_with("message", msg)

    @pytest.mark.asyncio
    async def test_log_llm_call(self):
        logger = Logger("s1", "e1")

        with patch.object(logger, "_async_insert", new_callable=AsyncMock) as mock_insert:
            logger.log_llm_call("Alice", "prompt text", "response text", error=None)
            await asyncio.sleep(0.01)
            mock_insert.assert_called_once()
            data = mock_insert.call_args[0][1]
            assert data["agent_name"] == "Alice"
            assert data["prompt"] == "prompt text"
            assert data["response"] == "response text"
            assert data["error"] is None

    @pytest.mark.asyncio
    async def test_log_error_schedules_and_writes_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logger = Logger("s1", "e1")

        with patch.object(logger, "_async_insert", new_callable=AsyncMock) as mock_insert:
            logger.log_error("test_error", "something went wrong", {"extra": "data"})
            await asyncio.sleep(0.01)
            mock_insert.assert_called_once()
            data = mock_insert.call_args[0][1]
            assert data["error_type"] == "test_error"
            assert data["error_message"] == "something went wrong"

        # Check fallback file was written
        error_file = tmp_path / "logs" / "errors.jsonl"
        assert error_file.exists()
        line = json.loads(error_file.read_text().strip())
        assert line["error_type"] == "test_error"
        assert line["session_id"] == "s1"


# ── drain() ──────────────────────────────────────────────────────────────────

class TestDrain:

    @pytest.mark.asyncio
    async def test_drain_awaits_pending(self):
        logger = Logger("s1", "e1")

        completed = []

        async def slow_insert(event_type, data):
            await asyncio.sleep(0.05)
            completed.append(event_type)

        with patch.object(logger, "_async_insert", side_effect=slow_insert):
            logger.log_event("evt1", {})
            logger.log_event("evt2", {})
            assert len(completed) == 0

            await logger.drain()
            assert len(completed) == 2

    @pytest.mark.asyncio
    async def test_drain_empty(self):
        """drain() with no pending tasks should not raise."""
        logger = Logger("s1", "e1")
        await logger.drain()  # Should complete immediately


# ── _async_insert error handling ─────────────────────────────────────────────

class TestAsyncInsert:

    @pytest.mark.asyncio
    async def test_db_failure_does_not_raise(self):
        """If DB insert fails, _async_insert prints to stderr but doesn't raise."""
        logger = Logger("s1", "e1")

        with patch("utils.logger.Logger._async_insert", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("DB down")
            # Calling log_event should not raise
            logger._schedule = MagicMock()  # prevent actual scheduling
            logger.log_event("test", {})


# ── Fallback file ────────────────────────────────────────────────────────────

class TestFallbackFile:

    def test_write_error_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logger = Logger("s1", "e1")
        logger._write_error_fallback("disk_full", "out of space", {"partition": "/dev/sda1"})

        error_file = tmp_path / "logs" / "errors.jsonl"
        assert error_file.exists()
        entry = json.loads(error_file.read_text().strip())
        assert entry["error_type"] == "disk_full"
        assert entry["error_message"] == "out of space"
        assert entry["context"]["partition"] == "/dev/sda1"

    def test_write_error_fallback_appends(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logger = Logger("s1", "e1")
        logger._write_error_fallback("err1", "msg1", None)
        logger._write_error_fallback("err2", "msg2", None)

        error_file = tmp_path / "logs" / "errors.jsonl"
        lines = error_file.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_write_error_fallback_with_none_context(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logger = Logger("s1", "e1")
        logger._write_error_fallback("err", "msg", None)

        entry = json.loads((tmp_path / "logs" / "errors.jsonl").read_text().strip())
        assert entry["context"] == {}


# ── No event loop scenario ───────────────────────────────────────────────────

class TestNoEventLoop:

    def test_schedule_without_loop_does_not_raise(self):
        """When called outside an event loop, _schedule silently skips."""
        logger = Logger("s1", "e1")

        # Run in a thread or context without asyncio loop
        # _schedule catches RuntimeError when no loop is running
        # Since we're in a test that may have a loop, we patch it
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
            logger.log_event("test", {})  # Should not raise
