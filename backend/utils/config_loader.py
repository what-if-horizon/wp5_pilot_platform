from pathlib import Path


def load_config(path: str) -> dict:
    """Load a TOML configuration file.

    The `path` argument is a relative path under the backend package (for example
    "config/experimental_settings.toml"). This function requires Python 3.11+ and
    will raise FileNotFoundError if the expected TOML file is not present.
    """
    p = Path(path)
    base = Path(__file__).resolve().parent.parent

    # Normalize: expect a .toml path under the backend package. Example:
    # callers should pass "config/experimental_settings.toml" which maps to
    # backend/config/experimental_settings.toml.
    candidate = base / path
    candidate_toml = candidate.with_suffix('.toml')

    if candidate_toml.exists():
        use_path = candidate_toml
    else:
        # Also accept a direct .toml path (absolute or relative)
        p_toml = p.with_suffix('.toml')
        if p_toml.exists():
            use_path = p_toml
        else:
            raise FileNotFoundError(f"TOML config not found for {path}; expected {candidate_toml}")

    try:
        import tomllib
    except Exception:
        raise RuntimeError("TOML support required (Python 3.11+). Please run with Python >=3.11")

    with open(use_path, "rb") as f:
        return tomllib.load(f)


def validate_sim_config(path: str) -> dict:
    """Load a simulation config TOML and validate required keys/types/ranges.

    This enforces that callers receive a fully validated, canonical simulation
    config dict. If validation fails a ValueError is raised with a helpful
    message. Some legacy aliases are normalized to canonical keys.
    """
    cfg = load_config(path)
    if not isinstance(cfg, dict):
        raise ValueError("simulation config must be a TOML table/dictionary")

    # Helper validations
    def require_key(k):
        if k not in cfg:
            raise ValueError(f"simulation_settings missing required key: '{k}'")

    # Required top-level keys for the STAGE framework
    canonical = [
        "random_seed",
        "session_duration_minutes",
        "num_agents",
        "agent_names",
        "messages_per_minute",
        "director_llm_provider",
        "director_llm_model",
        "performer_llm_provider",
        "performer_llm_model",
        "context_window_size",
        "llm_concurrency_limit",
    ]

    # Now require canonical keys exist
    for k in canonical:
        if k not in cfg:
            raise ValueError(f"simulation_settings missing required key: '{k}'")

    # Validate types and ranges
    try:
        # random_seed: integer
        cfg["random_seed"] = int(cfg["random_seed"])

        # session_duration_minutes: positive integer
        sd = int(cfg["session_duration_minutes"])
        if sd <= 0:
            raise ValueError("'session_duration_minutes' must be > 0")
        cfg["session_duration_minutes"] = sd

        # num_agents: non-negative int
        na = int(cfg["num_agents"])
        if na < 0:
            raise ValueError("'num_agents' must be >= 0")
        cfg["num_agents"] = na

        # agent_names: list of strings and length == num_agents
        anames = cfg.get("agent_names")
        if not isinstance(anames, list) or not all(isinstance(x, str) for x in anames):
            raise ValueError("'agent_names' must be a list of strings")
        if len(anames) != na:
            raise ValueError("length of 'agent_names' must equal 'num_agents'")

        # messages_per_minute: non-negative int
        mpm = int(cfg["messages_per_minute"])
        if mpm < 0:
            raise ValueError("'messages_per_minute' must be >= 0")
        cfg["messages_per_minute"] = mpm

        # typing_delay_seconds: non-negative float (optional, defaults to 1.0)
        tds = float(cfg.get("typing_delay_seconds", 1.0))
        if tds < 0:
            raise ValueError("'typing_delay_seconds' must be >= 0")
        cfg["typing_delay_seconds"] = tds

        # LLM provider/model: must be non-empty strings
        for key in ["director_llm_provider", "director_llm_model", "performer_llm_provider", "performer_llm_model"]:
            val = cfg[key]
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"'{key}' must be a non-empty string")

        # director_temperature / performer_temperature: float in [0, 2] (optional, default 1.0)
        for tkey in ["director_temperature", "performer_temperature"]:
            tv = float(cfg.get(tkey, 1.0))
            if not (0.0 <= tv <= 2.0):
                raise ValueError(f"'{tkey}' must be between 0.0 and 2.0")
            cfg[tkey] = tv

        # director_top_p / performer_top_p: float in [0, 1] (optional, default 1.0)
        for pkey in ["director_top_p", "performer_top_p"]:
            pv = float(cfg.get(pkey, 1.0))
            if not (0.0 <= pv <= 1.0):
                raise ValueError(f"'{pkey}' must be between 0.0 and 1.0")
            cfg[pkey] = pv

        # context_window_size: positive int
        cws = int(cfg["context_window_size"])
        if cws <= 0:
            raise ValueError("'context_window_size' must be > 0")
        cfg["context_window_size"] = cws

        # llm_concurrency_limit: positive int > 0
        llc = int(cfg["llm_concurrency_limit"])
        if llc <= 0:
            raise ValueError("'llm_concurrency_limit' must be a positive integer (>0)")
        cfg["llm_concurrency_limit"] = llc

    except KeyError as e:
        raise ValueError(f"missing simulation config key: {e}")
    except (TypeError, ValueError) as e:
        # Re-raise with helpful context
        raise ValueError(f"simulation_settings validation error: {e}")

    # Return normalized/validated config
    return cfg


__all__ = ["load_config", "validate_sim_config"]
