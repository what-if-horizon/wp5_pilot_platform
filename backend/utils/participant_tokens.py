import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
TOKENS_PATH = BASE_DIR / "config" / "participant_tokens.json"
USED_TOKENS_LOG = BASE_DIR / "logs" / "used_tokens.jsonl"


def _load_tokens_file() -> Dict[str, List[str]]:
    """Return the mapping group -> [tokens]."""
    if not TOKENS_PATH.exists():
        return {"groups": {}}
    with open(TOKENS_PATH, "r") as f:
        data = json.load(f)
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
        raise RuntimeError("No participant tokens defined in backend/config/participant_tokens.json")

    # experimental_settings may have a top-level 'groups' mapping or be flat
    exp_groups = experimental_settings.get("groups") if isinstance(experimental_settings, dict) else None
    if exp_groups is None:
        # If experimental_settings is flat, treat it as a single default group 'default'
        exp_group_names = {"default"}
    else:
        exp_group_names = set(exp_groups.keys())

    missing = set(groups.keys()) - exp_group_names
    if missing:
        raise RuntimeError(f"participant_tokens.json references undefined groups: {missing}")


def find_group_for_token(token: str) -> Optional[str]:
    """Return the group name for the given token, or None if not found or already used."""
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


def list_all_tokens() -> Dict[str, List[str]]:
    return _load_tokens_file()
