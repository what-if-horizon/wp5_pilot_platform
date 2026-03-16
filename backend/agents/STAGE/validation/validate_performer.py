"""Validate the Performer + Moderator for each action type in batch.

Bypasses the Director entirely and directly calls the Performer and
Moderator LLMs with controlled inputs. Runs each of the 4 action types
N times, collecting statistics on:
  - Success / failure rates
  - Moderator rejection rates
  - Message word counts
  - Problems: refusals, meta-commentary leakage, prompt language leaks, etc.

This isolates the Performer/Moderator from the Director so you can verify
that message generation works reliably for every action type.

Configuration
─────────────
Edit the constants at the top of this file:

  RUNS_PER_ACTION    How many times to test each action type.
  SIMULATION_CONFIG  LLM provider/model/params for Performer and Moderator.
  CHATROOM_CONTEXT   The chatroom context string.
  INSTRUCTION        The O/M/D instruction to give the Performer.
  AGENT_PROFILE      The accumulated profile text for the acting agent.
  MSG_1, MSG_2       Seed messages used as targets for targeted/reply actions.

Usage
─────
Run inside the app container:

    cat backend/agents/STAGE/validation/validate_performer.py | docker compose exec -T app python
"""
import asyncio
import re

from models import Message
from utils.llm.llm_manager import LLMManager
from agents.STAGE.performer import build_performer_system_prompt, build_performer_user_prompt
from agents.STAGE.moderator import build_moderator_system_prompt, build_moderator_user_prompt, parse_moderator_response


# ── Configuration ─────────────────────────────────────────────────────────
# Edit these to match the experiment and scenario you want to validate.

RUNS_PER_ACTION = 10

SIMULATION_CONFIG = {
    "performer_llm_provider": "anthropic",
    "performer_llm_model": "claude-haiku-4-5",
    "performer_temperature": 0.8,
    "performer_top_p": 0.8,
    "performer_max_tokens": 256,
    "moderator_llm_provider": "anthropic",
    "moderator_llm_model": "claude-haiku-4-5",
    "moderator_temperature": 0.2,
    "moderator_top_p": 1.0,
    "moderator_max_tokens": 256,
}

CHATROOM_CONTEXT = (
    "This is a an english-language telegram chatroom about climate change, set in Australia. "
)

# The O/M/D instruction given to the Performer (same for all action types
# so you can compare how each action type handles the same instruction).
INSTRUCTION = {
    "objective": "Challenge the idea that individual action matters for climate change, provoking a reaction.",
    "motivation": "You're frustrated with performative environmentalism and want to call it out.",
    "directive": "Keep it short, informal, and slightly dismissive. Use Australian slang.",
}

# The acting agent's accumulated profile.
AGENT_PROFILE = (
    "Performer 2 has been skeptical throughout, questioning whether personal "
    "choices make any difference. Tends toward blunt, dismissive remarks."
)

# Seed messages used as targets for message_targeted and reply actions.
MSG_1 = Message.create(
    sender="Performer 4",
    content="G'day everyone! Reckon we should all be doing our bit for the planet hey 🌏",
)
MSG_2 = Message.create(
    sender="Performer 1",
    content="yeah 100%, I switched to an EV last year and it feels good knowing I'm making a difference",
)


# ── Test cases ────────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "label": "message (standalone)",
        "action_type": "message",
        "target_user": None,
        "target_message": None,
    },
    {
        "label": "message_targeted",
        "action_type": "message",  # resolved to message_targeted by build_performer_user_prompt
        "target_user": "Performer 4",
        "target_message": MSG_1,
    },
    {
        "label": "reply",
        "action_type": "reply",
        "target_user": None,
        "target_message": MSG_2,
    },
    {
        "label": "@mention",
        "action_type": "@mention",
        "target_user": "Performer 4",
        "target_message": None,
    },
]


# ── Problem detectors ────────────────────────────────────────────────────
# Patterns that indicate the Performer leaked meta-commentary or refused.

PROBLEM_PATTERNS = [
    (re.compile(r"(?i)\b(performer \d|instruction|objective|motivation|directive)\b"), "leaked_prompt_language"),
    (re.compile(r"(?i)\b(I can't|I cannot|I'm unable|I notice there's no|could you provide)\b"), "refusal"),
    (re.compile(r"(?i)\b(here'?s? (?:a|my|the) (?:message|response|reply))\b"), "meta_preamble"),
    (re.compile(r"^>"), "echoed_quote"),
]


def detect_problems(text: str) -> list[str]:
    """Return list of problem labels found in text."""
    problems = []
    for pattern, label in PROBLEM_PATTERNS:
        if pattern.search(text):
            problems.append(label)
    return problems


# ── Main ──────────────────────────────────────────────────────────────────

async def main():
    performer_llm = LLMManager.from_simulation_config(SIMULATION_CONFIG, role="performer")
    moderator_llm = LLMManager.from_simulation_config(SIMULATION_CONFIG, role="moderator")

    performer_system = build_performer_system_prompt(chatroom_context=CHATROOM_CONTEXT)
    moderator_system = build_moderator_system_prompt(chatroom_context=CHATROOM_CONTEXT)

    all_results = {}

    for case in TEST_CASES:
        label = case["label"]
        print(f"\n{'#' * 80}")
        print(f"  {label}  ({RUNS_PER_ACTION} runs)")
        print(f"{'#' * 80}")

        user_prompt = build_performer_user_prompt(
            instruction=INSTRUCTION,
            agent_profile=AGENT_PROFILE,
            action_type=case["action_type"],
            target_user=case["target_user"],
            target_message=case["target_message"],
            chatroom_context=CHATROOM_CONTEXT,
        )

        results = []

        for run in range(1, RUNS_PER_ACTION + 1):
            entry = {"run": run, "performer_raw": None, "final": None,
                     "moderator_rejected": False, "problems": [], "word_count": 0}

            # Performer call
            performer_raw = await performer_llm.generate_response(
                user_prompt, max_retries=1, system_prompt=performer_system,
            )
            entry["performer_raw"] = performer_raw

            if not performer_raw:
                entry["problems"].append("performer_returned_none")
                results.append(entry)
                print(f"  [{run:2d}] FAIL — performer returned None")
                continue

            # Check performer raw output for problems
            entry["problems"].extend(detect_problems(performer_raw))

            # Moderator call
            mod_user = build_moderator_user_prompt(performer_output=performer_raw)
            mod_raw = await moderator_llm.generate_response(
                mod_user, max_retries=1, system_prompt=moderator_system,
            )
            content = parse_moderator_response(mod_raw)

            if content is None:
                entry["moderator_rejected"] = True
                entry["problems"].append("moderator_no_content")
                results.append(entry)
                print(f"  [{run:2d}] REJECTED by moderator")
                print(f"         Performer raw: {performer_raw[:120]}...")
                continue

            # Check final content for problems
            entry["problems"].extend(detect_problems(content))
            entry["final"] = content
            entry["word_count"] = len(content.split())

            # For @mention, simulate the Orchestrator's prefix
            display = content
            if case["action_type"] == "@mention" and case["target_user"]:
                display = f"@{case['target_user']} {content}"

            status = "OK" if not entry["problems"] else f"ISSUES: {', '.join(entry['problems'])}"
            print(f"  [{run:2d}] {status} ({entry['word_count']}w) — {display[:100]}{'...' if len(display) > 100 else ''}")

            results.append(entry)

        all_results[label] = results

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n\n{'=' * 80}")
    print(f"  SUMMARY")
    print(f"{'=' * 80}\n")

    for label, results in all_results.items():
        total = len(results)
        successes = sum(1 for r in results if r["final"] is not None)
        mod_rejected = sum(1 for r in results if r["moderator_rejected"])
        performer_none = sum(1 for r in results if "performer_returned_none" in r["problems"])
        word_counts = [r["word_count"] for r in results if r["final"]]

        problem_counts = {}
        for r in results:
            for p in r["problems"]:
                if p != "moderator_no_content":
                    problem_counts[p] = problem_counts.get(p, 0) + 1

        avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
        min_words = min(word_counts) if word_counts else 0
        max_words = max(word_counts) if word_counts else 0

        print(f"  {label}")
        print(f"    Success:          {successes}/{total}")
        print(f"    Moderator reject: {mod_rejected}/{total}")
        print(f"    Performer None:   {performer_none}/{total}")
        print(f"    Word count:       avg={avg_words:.0f}, min={min_words}, max={max_words}")
        if problem_counts:
            print(f"    Problems:")
            for prob, count in sorted(problem_counts.items(), key=lambda x: -x[1]):
                print(f"      {prob}: {count}/{total}")
        else:
            print(f"    Problems:         none")
        print()


asyncio.run(main())
