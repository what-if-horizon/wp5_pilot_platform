import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

try:
    import tomllib
except Exception:
    raise RuntimeError("TOML support required (Python 3.11+). Please run with Python >=3.11")

BASE_DIR = Path(__file__).resolve().parent.parent
TOKENS_PATH_TOML = BASE_DIR / "config" / "participant_tokens.toml"
USED_TOKENS_LOG = BASE_DIR / "logs" / "used_tokens.jsonl"

# In-process lock to avoid race conditions when validating/consuming tokens.
# Note: this only protects within a single process. For multi-replica deployments
# use a centralized store (DB/redis) to enforce single-use across replicas.
_lock = threading.Lock()


def _load_tokens_file() -> Dict[str, List[str]]:
    """Return the mapping group -> [tokens]. Only TOML is supported.

    Returns a dict with key 'groups' mapping to group -> [tokens]. Raises when file missing.
    """
    # Allow tests or overrides to set TOKENS_PATH (e.g., tests set a JSON path).
    override = globals().get("TOKENS_PATH", None)
    if override:
        p = Path(override)
        if not p.exists():
            return {"groups": {}}
        if p.suffix == ".toml":
            with open(p, "rb") as f:
                data = tomllib.load(f)
        else:
            # Accept JSON when explicitly pointed at by an override (tests rely on this).
            with open(p, "r") as f:
                data = json.load(f)
        return data.get("groups", {})

    # Default runtime behavior: require TOML file at the config location.
    if not TOKENS_PATH_TOML.exists():
        raise FileNotFoundError("participant_tokens.toml not found in backend/config; please create one.")
    with open(TOKENS_PATH_TOML, "rb") as f:
        data = tomllib.load(f)
    return data.get("groups", {})


def _load_used_tokens() -> List[str]:
    """Read the used tokens log (one JSON object per line) and return tokens seen."""
    if not USED_TOKENS_LOG.exists():
        return []
    used = []
    with open(USED_TOKENS_LOG, "r") as f:
        for line in f:
            try:
                obj = json.loads(line)
                token = obj.get("token")
                if token:
                    used.append(token)
            except Exception:
                # ignore malformed lines
                continue
    return used


def validate_against_experiments(experimental_settings: dict) -> None:
    """
    Validate that every group referenced in participant_tokens exists in experimental_settings.
    Raises RuntimeError on validation failure.
    """
    groups = _load_tokens_file()
    if not groups:
        raise RuntimeError("No participant tokens defined in backend/config/participant_tokens.toml")

    # Require experimental_settings to be a dict with a top-level 'groups' mapping.
    if not isinstance(experimental_settings, dict) or "groups" not in experimental_settings:
        raise RuntimeError("experimental_settings.toml must define a top-level 'groups' table mapping treatment names to configs")
    exp_group_names = set(experimental_settings["groups"].keys())

    missing = set(groups.keys()) - exp_group_names
    if missing:
        raise RuntimeError(f"participant_tokens references undefined groups: {missing}")


def find_group_for_token(token: str) -> Optional[str]:
    """Return the group name for the given token, or None if not found or already used.

    This is a read-only helper; it does not mark the token as used. For atomic
    consume-and-mark semantics use `consume_token` below.
    """
    groups = _load_tokens_file()
    used = set(_load_used_tokens())

    for group, tokens in groups.items():
        if token in tokens and token not in used:
            return group
    return None


def mark_token_used(token: str, session_id: str, group: Optional[str] = None) -> None:
    """Append a record of the used token to logs/used_tokens.jsonl (single-use enforcement is by reading this file)."""
    USED_TOKENS_LOG.parent.mkdir(exist_ok=True)
    event = {
        "timestamp": datetime.now().isoformat(),
        "token": token,
        "session_id": session_id,
        "group": group,
    }
    with open(USED_TOKENS_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


def consume_token(token: str, session_id: str) -> Optional[str]:
    """Atomically validate the token is unused and mark it used.

    Returns the group name if the token was valid and marked used, otherwise None.
    This is safe against concurrent calls within a single process via a threading lock.
    """
    with _lock:
        groups = _load_tokens_file()
        used = set(_load_used_tokens())

        for group, tokens in groups.items():
            if token in tokens and token not in used:
                # mark used and return group
                mark_token_used(token, session_id, group)
                return group
    return None


def list_all_tokens() -> Dict[str, List[str]]:
    return _load_tokens_file()
