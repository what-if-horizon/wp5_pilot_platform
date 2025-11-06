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


__all__ = ["load_config"]
