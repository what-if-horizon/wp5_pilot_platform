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

    # Required top-level keys (accept some legacy aliases which we'll normalize)
    # Canonical keys we expect
    canonical = [
        "random_seed",
        "session_duration_minutes",
        "num_agents",
        "agent_names",
        "messages_per_minute",
        "user_response_probability",
        "attention_decay",
        "attention_boost_speak",
        "attention_boost_address",
        "min_weight_floor",
        "context_window_size",
        "llm_concurrency_limit",
    ]

    # Normalize legacy aliases
    # e.g., some configs may use 'heat_decay' instead of 'attention_decay'
    aliases = {
        "heat_decay": "attention_decay",
        "heat_boost_speak": "attention_boost_speak",
        "heat_boost_address": "attention_boost_address",
    }
    for old, new in aliases.items():
        if old in cfg and new not in cfg:
            cfg[new] = cfg[old]

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

        # user_response_probability: float 0..1
        urp = float(cfg["user_response_probability"])
        if not (0.0 <= urp <= 1.0):
            raise ValueError("'user_response_probability' must be between 0 and 1")
        cfg["user_response_probability"] = urp

        # attention_decay, attention_boost_speak, attention_boost_address, min_weight_floor: floats in [0,1]
        for key in ["attention_decay", "attention_boost_speak", "attention_boost_address", "min_weight_floor"]:
            val = float(cfg[key])
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"'{key}' must be between 0 and 1")
            cfg[key] = val

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
