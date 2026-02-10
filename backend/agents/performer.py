import json
from pathlib import Path
from typing import List, Optional

from models import Message


# Load the Performer prompt template once at import time
_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "performer_prompt.md"
_RAW_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")

# Pre-extract the action-type blocks from the template
_MESSAGE_BLOCK = """### If action_type is `message`

You are posting a new message to the chatroom. It is not directed at anyone in particular.

**Output format:**
```
[Your message here]
```"""

_REPLY_BLOCK_TEMPLATE = """### If action_type is `reply`

You are replying directly to a specific message in the chatroom. The message you are replying to is:

{TARGET_MESSAGE_CONTENT}

Your reply should be responsive to this message. It may agree, disagree, build upon, or redirect — as indicated by your direction.

**Output format:**
```
[Your reply here]
```"""

_MENTION_BLOCK_TEMPLATE = """### If action_type is `@mention`

You are posting a message that directly @mentions another user: **@{TARGET_USER}**

Your message should address this user specifically. The @mention will be automatically prepended to your message, so do not include it yourself.

**Output format:**
```
[Your message here, without the @mention]
```"""


def _format_chat_log(messages: List[Message]) -> str:
    """Format messages into a chat log string for the Performer."""
    if not messages:
        return "(No messages yet)"

    lines = []
    for m in messages:
        lines.append(f"{m.sender}: {m.content}")
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
) -> str:
    """Build the full Performer prompt from the Director's output.

    Assembles the prompt by injecting the Director's instruction, the
    appropriate action-type block, and the chat log.
    """
    # Format the instruction block
    instruction_text = _format_instruction(instruction)

    # Select the appropriate action-type block
    if action_type == "message":
        action_block = _MESSAGE_BLOCK
    elif action_type == "reply":
        target_content = "(message not found)"
        if target_message:
            target_content = f"{target_message.sender}: {target_message.content}"
        action_block = _REPLY_BLOCK_TEMPLATE.replace("{TARGET_MESSAGE_CONTENT}", target_content)
    elif action_type == "@mention":
        user = target_user or "(unknown)"
        action_block = _MENTION_BLOCK_TEMPLATE.replace("{TARGET_USER}", user)
    else:
        action_block = _MESSAGE_BLOCK  # fallback

    # Format chat log
    chat_log = _format_chat_log(messages)

    # Build the final prompt (simplified assembly from the template structure)
    prompt = f"""# Performer Prompt

You are a 'Performer' in a social scientific experiment simulating a realistic online chatroom. A 'Director' has analysed the current state of the chatroom and determined what action should be taken next. Your role is to execute the Director's instructions by generating a single, realistic chatroom message.

## Your Task

The Director has provided you with:
- An **Objective**: What your character wants to achieve
- A **Motivation**: Why they want this — the situational context
- An **Action**: The specific tactic and communicative approach to use

Your job is to produce a message that fulfills this direction while sounding like an authentic chatroom participant. Do not explain your reasoning. Do not add meta-commentary. Output only the message itself.

## Director's Instructions

{instruction_text}

---

## Action Type Instructions

{action_block}

---

## Chat Log

Here are the recent chatroom messages for context:

{chat_log}

---

## Output

Produce only the message content. No preamble, no explanation, no quotation marks unless they are part of the message itself."""

    return prompt
