"""Tests for cache/redis_client.py (using fakeredis — no live Redis needed)."""
from __future__ import annotations

import asyncio
import json
import pytest
from cache import redis_client


async def test_cache_session_stores_and_retrieves(fake_redis):
    await redis_client.cache_session(fake_redis, "sess-1", {"status": "active", "user": "alice"})
    result = await redis_client.get_cached_session(fake_redis, "sess-1")
    assert result["status"] == "active"
    assert result["user"] == "alice"


async def test_get_cached_session_missing_returns_none(fake_redis):
    result = await redis_client.get_cached_session(fake_redis, "nonexistent")
    assert result is None


async def test_invalidate_session_removes_keys(fake_redis):
    await redis_client.cache_session(fake_redis, "sess-2", {"status": "active"})
    await redis_client.push_to_window(fake_redis, "sess-2", {"content": "hello"})
    await redis_client.invalidate_session(fake_redis, "sess-2")

    assert await redis_client.get_cached_session(fake_redis, "sess-2") is None
    assert await redis_client.get_window(fake_redis, "sess-2") == []


async def test_push_and_get_window(fake_redis):
    for i in range(15):
        await redis_client.push_to_window(fake_redis, "sess-3", {"seq": i}, window=10)

    window = await redis_client.get_window(fake_redis, "sess-3")
    assert len(window) == 10
    # Should contain the last 10 messages (seq 5–14).
    seqs = [m["seq"] for m in window]
    assert seqs == list(range(5, 15))


async def test_publish_and_subscribe(fake_redis):
    received = []

    async def listener():
        async for event in redis_client.subscribe_session(fake_redis, "sess-4"):
            received.append(event)
            if len(received) >= 2:
                break

    task = asyncio.create_task(listener())
    # Give the subscriber a moment to subscribe.
    await asyncio.sleep(0.05)

    await redis_client.publish_event(fake_redis, "sess-4", {"msg": "hello"})
    await redis_client.publish_event(fake_redis, "sess-4", {"msg": "world"})

    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 2
    assert received[0]["msg"] == "hello"
    assert received[1]["msg"] == "world"
