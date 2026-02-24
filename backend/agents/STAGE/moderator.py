from pathlib import Path
from typing import Optional


# Sentinel value the Moderator returns when no valid message content is found
NO_CONTENT = "NO_CONTENT"

# Load Moderator prompt templates at import time
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SYSTEM_TEMPLATE = (_PROMPTS_DIR / "system" / "moderator_prompt.md").read_text(encoding="utf-8")
_USER_TEMPLATE = (_PROMPTS_DIR / "user" / "moderator_prompt.md").read_text(encoding="utf-8")


def build_moderator_system_prompt(chatroom_context: str = "") -> str:
    """Build the Moderator system prompt (session-static)."""
    prompt = _SYSTEM_TEMPLATE
    prompt = prompt.replace("{CHATROOM_CONTEXT}", chatroom_context)
    return prompt


def build_moderator_user_prompt(performer_output: str, action_type: str) -> str:
    """Build the per-turn user prompt with the Performer's raw output."""
    prompt = _USER_TEMPLATE
    prompt = prompt.replace("{PERFORMER_OUTPUT}", performer_output)
    prompt = prompt.replace("{ACTION_TYPE}", action_type)
    return prompt


def parse_moderator_response(raw: str) -> Optional[str]:
    """Parse the Moderator's response.

    Returns the extracted message content as a string, or None if the
    Moderator signalled NO_CONTENT (meaning the performer output was unusable).
    """
    if not raw:
        return None

    cleaned = raw.strip()

    if cleaned == NO_CONTENT:
        return None

    if not cleaned:
        return None

    return cleaned
