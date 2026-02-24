import re
from pathlib import Path
from typing import List, Optional

from models import Message


# Load Performer prompt templates at import time
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_RAW_SYSTEM_TEMPLATE = (_PROMPTS_DIR / "system" / "performer_prompt.md").read_text(encoding="utf-8")
_RAW_USER_TEMPLATE = (_PROMPTS_DIR / "user" / "performer_prompt.md").read_text(encoding="utf-8")


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


# Only the user template needs parsing (action-block selection happens per turn).
# The system template retains all action blocks as-is for reference.
_PARSED_USER_TEMPLATE = _parse_template(_RAW_USER_TEMPLATE)


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
    if "strategy" in instruction:
        parts.append(f"**Strategy**: {instruction['strategy']}")
    return "\n".join(parts)


def build_performer_system_prompt(chatroom_context: str = "") -> str:
    """Build the Performer system prompt with session-static data only.

    The system prompt retains all action-type blocks so the LLM sees
    the full instruction set. Dynamic placeholders (Director's instructions,
    chat log) are left as descriptive notes already in the template.
    """
    prompt = _RAW_SYSTEM_TEMPLATE
    prompt = prompt.replace("{CHATROOM_CONTEXT}", chatroom_context)
    return prompt


def build_performer_user_prompt(
    instruction: dict,
    action_type: str,
    messages: List[Message],
    target_message: Optional[Message] = None,
    target_user: Optional[str] = None,
    chatroom_context: str = "",
) -> str:
    """Build the full Performer user prompt from the Director's output.

    Selects the appropriate action-type block from the parsed template,
    injects dynamic values, and fills the base template placeholders.
    """
    base_template, action_blocks = _PARSED_USER_TEMPLATE

    # Select the action-type block (fall back to 'message' for unknown types)
    # For 'message' with a target_user, use the 'message_targeted' variant
    if action_type == "message" and target_user:
        block_key = "message_targeted"
    else:
        block_key = action_type
    action_block = action_blocks.get(block_key, action_blocks["message"])

    # Substitute dynamic values within the selected block
    if block_key == "message_targeted":
        user = target_user or "(unknown)"
        action_block = action_block.replace("{TARGET_USER}", user)
        # Use the last message in the chat log as the target content
        target_content = "(message not found)"
        if messages:
            last = messages[-1]
            target_content = f"{last.sender}: {last.content}"
        action_block = action_block.replace("`{TARGET MESSAGE CONTENT GOES HERE}`", target_content)
    elif action_type == "reply":
        target_content = "(message not found)"
        if target_message:
            target_content = f"{target_message.sender}: {target_message.content}"
        action_block = action_block.replace("`{TARGET MESSAGE CONTENT GOES HERE}`", target_content)
    elif action_type == "@mention":
        user = target_user or "(unknown)"
        action_block = action_block.replace("{TARGET_USER}", user)

    # Assemble the full prompt from the base template
    prompt = base_template
    prompt = prompt.replace("{CHATROOM_CONTEXT}", chatroom_context)
    prompt = prompt.replace("`{PERFORMER_INSTRUCTION GOES HERE}`", _format_instruction(instruction))
    prompt = prompt.replace("{ACTION_BLOCK}", action_block)
    prompt = prompt.replace("`{CHAT LOG GOES HERE}`", _format_chat_log(messages))

    return prompt


# Backwards compatibility alias
build_performer_prompt = build_performer_user_prompt
