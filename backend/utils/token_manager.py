"""Participant token management.

Tokens are seeded into the DB via the admin wizard and consumed atomically
using PostgreSQL transactions (SELECT FOR UPDATE SKIP LOCKED).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import asyncpg

from db.repositories import token_repo


async def seed_tokens(
    pool: asyncpg.Pool,
    experiment_id: str,
    groups: Dict[str, List[str]],
) -> None:
    """Seed tokens into the DB for the given experiment.

    Idempotent — already-seeded tokens are skipped.
    """
    await token_repo.seed_tokens(pool, experiment_id, groups)
    total = sum(len(v) for v in groups.values())
    print(f"Token seeding complete: {total} tokens across {len(groups)} groups "
          f"for experiment '{experiment_id}'.")


async def consume_token(
    pool: asyncpg.Pool,
    token: str,
    session_id: str,
) -> Optional[Tuple[str, str]]:
    """Atomically validate and consume a participant token.

    Returns (treatment_group, experiment_id) on success, or None if the token
    is invalid, not found, or already used.
    """
    return await token_repo.consume_token(pool, token, session_id)
