import json
import re
from pathlib import Path
from typing import List

from models import Message, Agent


# Load Director prompt templates for each supported language at import time
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_TEMPLATES = {
    "EN": (_PROMPTS_DIR / "director_prompt.md").read_text(encoding="utf-8"),
    "ES": (_PROMPTS_DIR / "director_prompt_es.md").read_text(encoding="utf-8"),
}


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


def build_director_prompt(treatment: str, messages: List[Message], agents: List[Agent], human_user: str = "user", language: str = "EN") -> str:
    """Build the full Director prompt by injecting treatment, chat log, and human user name."""
    chat_log = format_chat_log(messages)
    agent_names = ", ".join(a.name for a in agents)

    prompt = _TEMPLATES.get(language, _TEMPLATES["EN"])
    prompt = prompt.replace("{TREATMENT GOES HERE}", treatment)
    prompt = prompt.replace("{CHAT LOG GOES HERE}", chat_log)
    prompt = prompt.replace("{HUMAN_USER}", human_user)

    # Append the list of available agent names so the Director knows who it can select
    heading = "Agentes Disponibles" if language == "ES" else "Available Agents"
    prompt += f"\n\n## {heading}\n\n{agent_names}\n"

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
