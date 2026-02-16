import re
from pathlib import Path
from typing import List, Optional

from models import Message


# Load Performer prompt templates for each supported language at import time
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_RAW_TEMPLATES = {
    "EN": (_PROMPTS_DIR / "performer_prompt.md").read_text(encoding="utf-8"),
    "ES": (_PROMPTS_DIR / "performer_prompt_es.md").read_text(encoding="utf-8"),
}


def _parse_template(raw: str):
    """Parse the performer prompt template into a base template and action-type blocks.

    The .md template marks each action-type block with:
        `{ACTION_TYPE_BLOCK: <name>}`  — starts a block
        `{END_ACTION_TYPE_BLOCKS}`     — ends the last block

    This extracts them into a dict keyed by action type name, and builds a
    base template with a single {ACTION_BLOCK} placeholder where the selected
    block will be injected at runtime.
    """
    # Extract each block: content between `{ACTION_TYPE_BLOCK: X}` markers
    blocks = {}
    block_re = re.compile(
        r"`\{ACTION_TYPE_BLOCK:\s*([^}]+)\}`\s*\n(.*?)(?=`\{ACTION_TYPE_BLOCK:|`\{END_ACTION_TYPE_BLOCKS\}`)",
        re.DOTALL,
    )
    for m in block_re.finditer(raw):
        blocks[m.group(1).strip()] = m.group(2).strip()

    # Replace everything from the first ACTION_TYPE_BLOCK marker through
    # END_ACTION_TYPE_BLOCKS with a single placeholder
    base = re.sub(
        r"`\{ACTION_TYPE_BLOCK:.*?`\{END_ACTION_TYPE_BLOCKS\}`",
        "{ACTION_BLOCK}",
        raw,
        flags=re.DOTALL,
    )

    return base, blocks


# Parse each language template into base + action blocks
_PARSED_TEMPLATES = {
    lang: _parse_template(raw) for lang, raw in _RAW_TEMPLATES.items()
}


def _format_chat_log(messages: List[Message]) -> str:
    """Format messages into a chat log string for the Performer."""
    if not messages:
        return "(No messages yet)"

    lines = []
    for m in messages:
        line = f"{m.sender}: {m.content}"
        if m.liked_by:
            line += f" [liked by {', '.join(sorted(m.liked_by))}]"
        lines.append(line)
    return "\n".join(lines)


def _format_instruction(instruction: dict) -> str:
    """Format the Director's performer_instruction dict as readable text."""
    parts = []
    if "objective" in instruction:
        parts.append(f"**Objective**: {instruction['objective']}")
    if "motivation" in instruction:
        parts.append(f"**Motivation**: {instruction['motivation']}")
    if "action" in instruction:
        parts.append(f"**Action**: {instruction['action']}")
    return "\n".join(parts)


def build_performer_prompt(
    instruction: dict,
    action_type: str,
    messages: List[Message],
    target_message: Optional[Message] = None,
    target_user: Optional[str] = None,
    language: str = "EN",
) -> str:
    """Build the full Performer prompt from the Director's output.

    Selects the appropriate action-type block from the parsed template,
    injects dynamic values, and fills the base template placeholders.
    """
    base_template, action_blocks = _PARSED_TEMPLATES.get(language, _PARSED_TEMPLATES["EN"])

    # Select the action-type block (fall back to 'message' for unknown types)
    action_block = action_blocks.get(action_type, action_blocks["message"])

    # Substitute dynamic values within the selected block
    if action_type == "reply":
        target_content = "(message not found)"
        if target_message:
            target_content = f"{target_message.sender}: {target_message.content}"
        action_block = action_block.replace("`{TARGET MESSAGE CONTENT GOES HERE}`", target_content)
    elif action_type == "@mention":
        user = target_user or "(unknown)"
        action_block = action_block.replace("{TARGET_USER}", user)

    # Assemble the full prompt from the base template
    prompt = base_template
    prompt = prompt.replace("`{PERFORMER_INSTRUCTION GOES HERE}`", _format_instruction(instruction))
    prompt = prompt.replace("{ACTION_BLOCK}", action_block)
    prompt = prompt.replace("`{CHAT LOG GOES HERE}`", _format_chat_log(messages))

    return prompt
