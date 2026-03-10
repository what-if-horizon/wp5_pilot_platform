"""Experiment configuration repository — DB-backed immutable config storage.

Each experiment's full configuration (simulation settings + experimental
settings) is stored as a single JSONB blob on the ``experiments`` table.
Once saved, the config is immutable.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg


# ── Validation ────────────────────────────────────────────────────────────────

def validate_simulation_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a simulation config dict. Returns the cleaned dict.

    Raises ValueError on invalid input.
    """
    out = dict(cfg)

    # Required keys
    required = [
        "random_seed", "session_duration_minutes", "num_agents", "agent_names",
        "messages_per_minute", "director_llm_provider", "director_llm_model",
        "performer_llm_provider", "performer_llm_model",
        "moderator_llm_provider", "moderator_llm_model",
        "context_window_size",
    ]
    for k in required:
        if k not in out:
            raise ValueError(f"Missing required key: '{k}'")

    out["random_seed"] = int(out["random_seed"])

    sd = int(out["session_duration_minutes"])
    if sd <= 0:
        raise ValueError("'session_duration_minutes' must be > 0")
    out["session_duration_minutes"] = sd

    na = int(out["num_agents"])
    if na < 0:
        raise ValueError("'num_agents' must be >= 0")
    out["num_agents"] = na

    anames = out.get("agent_names", [])
    if not isinstance(anames, list) or not all(isinstance(x, str) for x in anames):
        raise ValueError("'agent_names' must be a list of strings")
    if len(anames) != na:
        raise ValueError("length of 'agent_names' must equal 'num_agents'")
    if na > 0:
        if any(not name.strip() for name in anames):
            raise ValueError("All agent names must be non-empty")
        if len(set(name.strip() for name in anames)) != na:
            raise ValueError("Agent names must be unique")

    mpm = int(out["messages_per_minute"])
    if mpm < 0:
        raise ValueError("'messages_per_minute' must be >= 0")
    out["messages_per_minute"] = mpm

    # Remove legacy max_concurrent_agents if present (turns are now sequential).
    out.pop("max_concurrent_agents", None)

    for key in ["director_llm_provider", "director_llm_model",
                 "performer_llm_provider", "performer_llm_model",
                 "moderator_llm_provider", "moderator_llm_model"]:
        if not isinstance(out.get(key, ""), str) or not out[key].strip():
            raise ValueError(f"'{key}' must be a non-empty string")

    for k in ["director_temperature", "performer_temperature", "moderator_temperature"]:
        v = float(out.get(k, 1.0))
        if not (0.0 <= v <= 2.0):
            raise ValueError(f"'{k}' must be between 0.0 and 2.0")
        out[k] = v

    for k in ["director_top_p", "performer_top_p", "moderator_top_p"]:
        v = float(out.get(k, 1.0))
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"'{k}' must be between 0.0 and 1.0")
        out[k] = v

    defaults = {"director_max_tokens": 1024, "performer_max_tokens": 512, "moderator_max_tokens": 256}
    for k, d in defaults.items():
        v = int(out.get(k, d))
        if v <= 0:
            raise ValueError(f"'{k}' must be > 0")
        out[k] = v

    cws = int(out["context_window_size"])
    if cws <= 0:
        raise ValueError("'context_window_size' must be > 0")
    out["context_window_size"] = cws

    return out


def validate_experimental_config(
    cfg: Dict[str, Any],
    available_features: List[str],
) -> Dict[str, Any]:
    """Validate an experimental config dict. Returns the cleaned dict.

    Raises ValueError on invalid input.
    """
    groups = cfg.get("groups", {})
    if not groups or not isinstance(groups, dict):
        raise ValueError("At least one treatment group is required")

    for name, g in groups.items():
        if not isinstance(g, dict):
            raise ValueError(f"Group '{name}' must be a dict")
        if not g.get("treatment", "").strip():
            raise ValueError(f"Group '{name}' is missing a treatment description")
        for feat in g.get("features", []):
            if feat not in available_features:
                raise ValueError(
                    f"Group '{name}' has unknown feature '{feat}'. "
                    f"Available: {', '.join(available_features)}"
                )

    return cfg


def validate_token_groups(
    token_groups: Dict[str, List[str]],
    experiment_groups: Dict[str, Any],
) -> None:
    """Validate that token groups match the experimental groups.

    Raises ValueError on mismatch.
    """
    if not token_groups:
        raise ValueError("No tokens provided")
    missing = set(token_groups.keys()) - set(experiment_groups.keys())
    if missing:
        raise ValueError(f"Token groups reference undefined treatment groups: {missing}")
    missing_tokens = set(experiment_groups.keys()) - set(token_groups.keys())
    if missing_tokens:
        raise ValueError(f"Treatment groups missing tokens: {missing_tokens}")


async def save_experiment_config(
    pool: asyncpg.Pool,
    experiment_id: str,
    config: Dict[str, Any],
    description: str = "",
    starts_at: Optional[datetime] = None,
    ends_at: Optional[datetime] = None,
) -> None:
    """Insert a new experiment with its config. Raises on duplicate."""
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT 1 FROM experiments WHERE experiment_id = $1",
            experiment_id,
        )
        if existing:
            raise ValueError(
                f"Experiment '{experiment_id}' already exists. "
                "Experiment configurations are immutable once saved."
            )
        await conn.execute(
            """
            INSERT INTO experiments(experiment_id, description, config, starts_at, ends_at)
            VALUES($1, $2, $3::jsonb, $4, $5)
            """,
            experiment_id,
            description,
            json.dumps(config),
            starts_at,
            ends_at,
        )


async def get_experiment_config(
    pool: asyncpg.Pool,
    experiment_id: str,
) -> Optional[Dict[str, Any]]:
    """Return the config JSONB for an experiment, or None if not found."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT config FROM experiments WHERE experiment_id = $1",
            experiment_id,
        )
    if row is None:
        return None
    cfg = row["config"]
    # asyncpg returns JSONB as a string or dict depending on version
    if isinstance(cfg, str):
        return json.loads(cfg)
    return dict(cfg) if cfg else None


async def get_experiment(
    pool: asyncpg.Pool,
    experiment_id: str,
) -> Optional[Dict[str, Any]]:
    """Return full experiment row as dict, or None."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT experiment_id, description, config, starts_at, ends_at, paused, created_at "
            "FROM experiments WHERE experiment_id = $1",
            experiment_id,
        )
    if row is None:
        return None
    result = dict(row)
    cfg = result.get("config")
    if isinstance(cfg, str):
        result["config"] = json.loads(cfg)
    return result


async def set_paused(
    pool: asyncpg.Pool,
    experiment_id: str,
    paused: bool,
) -> None:
    """Set the paused flag on an experiment."""
    async with pool.acquire() as conn:
        updated = await conn.execute(
            "UPDATE experiments SET paused = $1 WHERE experiment_id = $2",
            paused,
            experiment_id,
        )
        if updated == "UPDATE 0":
            raise ValueError(f"Experiment '{experiment_id}' not found")


async def check_experiment_availability(
    pool: asyncpg.Pool,
    experiment_id: str,
) -> Optional[str]:
    """Check if an experiment is currently available for participation.

    Returns None if available, or an error message string if not.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT starts_at, ends_at, paused FROM experiments WHERE experiment_id = $1",
            experiment_id,
        )
    if row is None:
        return "Experiment not found"

    if row["paused"]:
        return "This study is temporarily paused. Please try again later."

    now = datetime.now(timezone.utc)
    if row["starts_at"] and now < row["starts_at"]:
        return "This study has not started yet. Please try again later."
    if row["ends_at"] and now > row["ends_at"]:
        return "This study has ended and is no longer accepting participants."

    return None
