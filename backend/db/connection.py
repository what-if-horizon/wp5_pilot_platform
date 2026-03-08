"""asyncpg connection pool — module-level singleton.

Initialised once at FastAPI startup via `init_pool()` and torn down via
`close_pool()`.  Every other module obtains a connection with `get_pool()`.
"""
from __future__ import annotations

import asyncpg
from pathlib import Path

_pool: asyncpg.Pool | None = None

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_pool(dsn: str, min_size: int = 5, max_size: int = 20) -> asyncpg.Pool:
    """Create (and store) the global connection pool.

    Also applies the schema DDL so the pool works against a fresh DB.
    """
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    async with _pool.acquire() as conn:
        # Advisory lock prevents multiple workers from applying schema concurrently.
        await conn.execute("SELECT pg_advisory_lock(42)")
        try:
            await conn.execute(SCHEMA_PATH.read_text())
        finally:
            await conn.execute("SELECT pg_advisory_unlock(42)")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() at startup")
    return _pool
