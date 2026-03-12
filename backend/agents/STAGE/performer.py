import re
from pathlib import Path
from typing import List, Optional

from models import Message


# Load unified Performer prompt template at import time
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_RAW_UNIFIED_TEMPLATE = (_PROMPTS_DIR / "performer_prompt.md").read_text(encoding="utf-8")

from agents.STAGE.prompts.prompt_renderer import render as _render_prompt


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


# Render the unified template for each mode, then parse the user variant
# (action-block selection happens per turn; system retains all blocks as-is).
_SYSTEM_TEMPLATE = _render_prompt(_RAW_UNIFIED_TEMPLATE, "system")
_PARSED_USER_TEMPLATE = _parse_template(_render_prompt(_RAW_UNIFIED_TEMPLATE, "user"))


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
    if "directive" in instruction:
        parts.append(f"**Directive**: {instruction['directive']}")
    return "\n".join(parts)


def build_performer_system_prompt(chatroom_context: str = "") -> str:
    """Build the Performer system prompt with session-static data only.

    The system prompt retains all action-type blocks so the LLM sees
    the full instruction set. Dynamic placeholders (Director's instructions,
    chat log) are left as descriptive notes already in the template.
    """
    prompt = _SYSTEM_TEMPLATE
    prompt = prompt.replace("{CHATROOM_CONTEXT}", chatroom_context)
    return prompt


def _resolve_action_block(
    action_type: str,
    action_blocks: dict,
    messages: List[Message],
    target_message: Optional[Message],
    target_user: Optional[str],
) -> str:
    """Select and populate the correct action-type block."""
    if action_type == "message" and target_user:
        block_key = "message_targeted"
    else:
        block_key = action_type
    action_block = action_blocks.get(block_key, action_blocks["message"])

    if block_key == "message_targeted":
        user = target_user or "(unknown)"
        action_block = action_block.replace("{TARGET_USER}", user)
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

    return action_block


def build_performer_user_prompt(
    instruction: dict,
    action_type: str,
    messages: List[Message],
    target_message: Optional[Message] = None,
    target_user: Optional[str] = None,
    chatroom_context: str = "",
    duplicate_prompts: bool = False,
) -> str:
    """Build the Performer user prompt from the Director's output.

    When *duplicate_prompts* is True, the full template (instructions + data)
    is sent.  When False (default), only dynamic data is sent.
    """
    base_template, action_blocks = _PARSED_USER_TEMPLATE

    action_block = _resolve_action_block(
        action_type, action_blocks, messages, target_message, target_user,
    )

    if duplicate_prompts:
        prompt = base_template
        prompt = prompt.replace("{CHATROOM_CONTEXT}", chatroom_context)
        prompt = prompt.replace("`{PERFORMER_INSTRUCTION GOES HERE}`", _format_instruction(instruction))
        prompt = prompt.replace("{ACTION_BLOCK}", action_block)
        prompt = prompt.replace("`{CHAT LOG GOES HERE}`", _format_chat_log(messages))
    else:
        chat_log = _format_chat_log(messages)
        prompt = (
            f"## Director's Instructions\n\n"
            f"{_format_instruction(instruction)}\n\n"
            f"---\n\n"
            f"## Action Type Instructions\n\n"
            f"{action_block}\n\n"
            f"## Chat Log\n\n"
            f"{chat_log}\n"
        )

    return prompt


# Backwards compatibility alias
build_performer_prompt = build_performer_user_prompt
