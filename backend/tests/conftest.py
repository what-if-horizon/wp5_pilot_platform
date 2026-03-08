"""Pytest fixtures shared across all test modules.

DB tests
--------
Require a live PostgreSQL instance.  Set ``TEST_DATABASE_URL`` in the
environment to point at a throw-away DB:

    TEST_DATABASE_URL=postgresql://wp5user:wp5pass@localhost:5432/wp5_test

DB test files request ``db_pool`` and ``clean_tables`` explicitly — they are
NOT auto-used, so Redis-only tests never attempt a DB connection.

Redis tests
-----------
Use ``fakeredis`` — no live Redis instance required.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest
import pytest_asyncio

try:
    import asyncpg
except ModuleNotFoundError:  # allow unit tests to run without asyncpg
    asyncpg = None

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://wp5user:wp5pass@localhost:5432/wp5_test",
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


# ── DB fixtures (not auto-used) ────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_pool():
    """Session-scoped asyncpg pool.  Applies the schema on first use.

    Skips the entire test if PostgreSQL is not reachable so that CI
    environments without a DB don't hard-fail.  Run with a live Postgres
    (e.g. via ``docker compose up db``) to execute DB tests.
    """
    if asyncpg is None:
        pytest.skip("asyncpg not installed; skipping DB tests.")
        return
    try:
        pool = await asyncpg.create_pool(TEST_DB_URL, min_size=2, max_size=10,
                                         timeout=5)
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available ({exc}); skipping DB tests.")
        return
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_PATH.read_text())
    yield pool
    async with pool.acquire() as conn:
        await conn.execute("""
            DROP TABLE IF EXISTS agent_blocks  CASCADE;
            DROP TABLE IF EXISTS events        CASCADE;
            DROP TABLE IF EXISTS messages      CASCADE;
            DROP TABLE IF EXISTS sessions      CASCADE;
            DROP TABLE IF EXISTS tokens        CASCADE;
            DROP TABLE IF EXISTS experiments   CASCADE;
        """)
    await pool.close()


@pytest_asyncio.fixture(loop_scope="session")
async def clean_tables(db_pool):
    """Truncate all tables before each DB test for full isolation."""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            TRUNCATE agent_blocks, events, messages, sessions, tokens, experiments
            RESTART IDENTITY CASCADE
        """)
    yield


@pytest.fixture
def experiment_id() -> str:
    return "test_experiment"


@pytest_asyncio.fixture(loop_scope="session")
async def ensure_experiment(db_pool):
    """Insert experiment row (needed because seed_tokens no longer creates it)."""
    import json
    async def _ensure(experiment_id: str):
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO experiments(experiment_id, config) VALUES($1, $2::jsonb) ON CONFLICT DO NOTHING",
                experiment_id,
                json.dumps({"simulation": {}, "experimental": {}}),
            )
    return _ensure


# ── Redis fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
async def fake_redis():
    """In-memory Redis substitute via fakeredis (no live Redis required)."""
    import fakeredis.aioredis as fakeredis
    r = fakeredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()
