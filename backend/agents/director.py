import json
import re
from pathlib import Path
from typing import List

from models import Message, Agent


# Load the Director prompt template once at import time
_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "director_prompt.md"
_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")


def format_chat_log(messages: List[Message]) -> str:
    """Format messages into a chat log string the Director can reason over.

    Each line includes the message_id so the Director can reference it
    for reply/like targets.
    """
    if not messages:
        return "(No messages yet)"

    lines = []
    for m in messages:
        line = f"[{m.message_id}] {m.sender}: {m.content}"
        if m.reply_to:
            line = f"[{m.message_id}] {m.sender} (replying to {m.reply_to}): {m.content}"
        lines.append(line)
    return "\n".join(lines)


def build_director_prompt(treatment: str, messages: List[Message], agents: List[Agent]) -> str:
    """Build the full Director prompt by injecting treatment and chat log."""
    chat_log = format_chat_log(messages)
    agent_names = ", ".join(a.name for a in agents)

    prompt = _TEMPLATE
    prompt = prompt.replace("{TREATMENT GOES HERE}", treatment)
    prompt = prompt.replace("{CHAT LOG GOES HERE}", chat_log)

    # Append the list of available agent names so the Director knows who it can select
    prompt += f"\n\n## Available Agents\n\n{agent_names}\n"

    return prompt


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
