"""Pytest fixtures shared across all test modules.

DB tests
--------
Require a live PostgreSQL instance.  The test fixture automatically creates
an ephemeral ``wp5_test_<pid>`` database, applies the schema, and drops it
when the test run finishes.  Production data is never touched.

Set ``TEST_DATABASE_URL`` to the **server** connection string (pointing at
any existing DB such as ``postgres`` or ``wp5``).  The fixture will create
a temporary database on that server — it will never run tests against the
database in the URL itself.

    TEST_DATABASE_URL=postgresql://wp5user:wp5pass@localhost:5432/postgres

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

# Server connection — used only to CREATE / DROP the ephemeral test DB.
# This should point at any existing database on the server (e.g. postgres).
TEST_SERVER_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://wp5user:wp5pass@localhost:5432/wp5_test",
)

# Ephemeral database name — unique per process to allow parallel runs.
_EPHEMERAL_DB = f"wp5_test_{os.getpid()}"

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def _replace_dbname(dsn: str, new_db: str) -> str:
    """Replace the database name in a PostgreSQL DSN."""
    # Handle both postgresql://user:pass@host:port/dbname and ?query params
    base, _, params = dsn.partition("?")
    parts = base.rsplit("/", 1)
    new_dsn = f"{parts[0]}/{new_db}"
    if params:
        new_dsn += f"?{params}"
    return new_dsn


# ── DB fixtures (not auto-used) ────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_pool():
    """Session-scoped asyncpg pool on an ephemeral test database.

    Creates a fresh database, applies the schema, yields a pool, then
    drops the database entirely on teardown.  Production data is never
    touched — even if TEST_DATABASE_URL is misconfigured.

    Skips the entire test if PostgreSQL is not reachable so that CI
    environments without a DB don't hard-fail.
    """
    if asyncpg is None:
        pytest.skip("asyncpg not installed; skipping DB tests.")
        return

    # Connect to the server to create the ephemeral DB.
    try:
        admin_conn = await asyncpg.connect(TEST_SERVER_URL, timeout=5)
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available ({exc}); skipping DB tests.")
        return

    try:
        # DROP leftover from a previous crashed run, then CREATE fresh.
        await admin_conn.execute(f'DROP DATABASE IF EXISTS "{_EPHEMERAL_DB}"')
        await admin_conn.execute(f'CREATE DATABASE "{_EPHEMERAL_DB}"')
    except Exception as exc:
        await admin_conn.close()
        pytest.skip(f"Could not create test database ({exc}); skipping DB tests.")
        return
    finally:
        await admin_conn.close()

    # Connect to the ephemeral DB and apply schema.
    ephemeral_url = _replace_dbname(TEST_SERVER_URL, _EPHEMERAL_DB)
    pool = await asyncpg.create_pool(ephemeral_url, min_size=2, max_size=10)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_PATH.read_text())

    yield pool

    # Teardown: close the pool, then drop the entire ephemeral DB.
    await pool.close()
    try:
        admin_conn = await asyncpg.connect(TEST_SERVER_URL, timeout=5)
        await admin_conn.execute(f'DROP DATABASE IF EXISTS "{_EPHEMERAL_DB}"')
        await admin_conn.close()
    except Exception:
        pass  # best-effort cleanup


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
