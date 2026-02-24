import json
import re
from pathlib import Path
from typing import List

from models import Message, Agent


# Load Director prompt templates at import time
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SYSTEM_TEMPLATE = (_PROMPTS_DIR / "system" / "director_prompt.md").read_text(encoding="utf-8")
_USER_TEMPLATE = (_PROMPTS_DIR / "user" / "director_prompt.md").read_text(encoding="utf-8")


def format_chat_log(messages: List[Message]) -> str:
    """Format messages into a chat log string the Director can reason over.

    Each line includes the message_id so the Director can reference it
    for reply/like targets.
    """
    if not messages:
        return "(No messages yet)"

    lines = []
    for m in messages:
        # Build metadata annotations
        meta = []
        if m.reply_to:
            meta.append(f"replying to {m.reply_to}")
        if m.mentions:
            meta.append(f"@mentions {', '.join(m.mentions)}")
        if m.liked_by:
            meta.append(f"liked by {', '.join(sorted(m.liked_by))}")

        meta_str = f" ({'; '.join(meta)})" if meta else ""
        line = f"[{m.message_id}] {m.sender}{meta_str}: {m.content}"
        lines.append(line)
    return "\n".join(lines)


def build_director_system_prompt(treatment: str, human_user: str = "user", chatroom_context: str = "") -> str:
    """Build the Director system prompt with session-static data only.

    Per-turn dynamic data (chat log, available agents) is left as
    placeholder notes — those sections will be filled in the user prompt.
    """
    prompt = _SYSTEM_TEMPLATE
    prompt = prompt.replace("{CHATROOM_CONTEXT}", chatroom_context)
    prompt = prompt.replace("{TREATMENT GOES HERE}", treatment)
    prompt = prompt.replace("{HUMAN_USER}", human_user)
    return prompt


def build_director_user_prompt(treatment: str, messages: List[Message], agents: List[Agent], human_user: str = "user", chatroom_context: str = "") -> str:
    """Build the full Director user prompt by injecting context, treatment, chat log, and human user name."""
    chat_log = format_chat_log(messages)
    agent_names = ", ".join(a.name for a in agents)

    prompt = _USER_TEMPLATE
    prompt = prompt.replace("{CHATROOM_CONTEXT}", chatroom_context)
    prompt = prompt.replace("{TREATMENT GOES HERE}", treatment)
    prompt = prompt.replace("{CHAT LOG GOES HERE}", chat_log)
    prompt = prompt.replace("{HUMAN_USER}", human_user)

    # Append the list of available agent names so the Director knows who it can select
    prompt += f"\n\n## Available Agents\n\n{agent_names}\n"

    return prompt


# Backwards compatibility alias
build_director_prompt = build_director_user_prompt


def parse_director_response(raw: str) -> dict:
    """Extract and validate the JSON object from the Director's response.

    The Director is expected to return a JSON object (possibly wrapped in
    markdown fences). This function extracts and validates the required fields.
    """
    # Try to extract JSON from markdown code fence first
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    json_str = fence_match.group(1).strip() if fence_match else raw.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Director response is not valid JSON: {e}\nRaw: {raw[:500]}")

    # Validate required fields
    if "next_agent" not in data:
        raise ValueError("Director response missing 'next_agent'")
    if "action_type" not in data:
        raise ValueError("Director response missing 'action_type'")

    action_type = data["action_type"]
    valid_types = {"message", "reply", "@mention", "like"}
    if action_type not in valid_types:
        raise ValueError(f"Director returned invalid action_type: '{action_type}'. Must be one of {valid_types}")

    # Validate target fields based on action type
    if action_type == "reply" and not data.get("target_message_id"):
        raise ValueError("Director chose 'reply' but did not provide 'target_message_id'")
    if action_type == "like" and not data.get("target_message_id"):
        raise ValueError("Director chose 'like' but did not provide 'target_message_id'")
    if action_type == "@mention" and not data.get("target_user"):
        raise ValueError("Director chose '@mention' but did not provide 'target_user'")

    # Validate performer_instruction for non-like actions
    if action_type != "like" and not data.get("performer_instruction"):
        raise ValueError(f"Director chose '{action_type}' but did not provide 'performer_instruction'")

    return data
