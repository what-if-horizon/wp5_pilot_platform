"""Validate the full STAGE pipeline by stepping through N turns.

Runs a real Orchestrator with real LLM clients, but without a live session
or database. Every LLM call (Director Update, Evaluate, Act, Performer,
Moderator) is intercepted and its system prompt, user prompt, and response
are printed so you can inspect the exact inputs and outputs at each stage.

The Director decides everything — who acts, what action type, the O/M/D
instruction. Messages accumulate in state across turns so you can observe
how profiles, validity evaluations, and conversation history evolve.

Configuration
─────────────
Edit the constants at the top of this file to match your experiment:

  NUM_TURNS               How many turns to step through.
  SIMULATION_CONFIG       Must match your experiment's simulation config.
  CHATROOM_CONTEXT        From experimental.chatroom_context.
  ECOLOGICAL_CRITERIA     From experimental.ecological_validity_criteria.
  INTERNAL_VALIDITY_CRITERIA  From the treatment group's internal_validity_criteria.

Usage
─────
Run inside the app container (which has LLM provider keys and dependencies):

    cat backend/agents/STAGE/validation/validate_pipeline.py | docker compose exec -T app python
"""
import asyncio
import random

from models import Agent, SessionState
from utils import Logger
from utils.llm.llm_manager import LLMManager
from agents.STAGE.orchestrator import Orchestrator


# ── Configuration ─────────────────────────────────────────────────────────
# Edit these to match the experiment you want to validate.

NUM_TURNS = 20

EXPERIMENT_ID = "test"
TREATMENT_GROUP = "condition_1"
SESSION_ID = "validate-pipeline-001"

SIMULATION_CONFIG = {
    "num_agents": 5,
    "agent_names": ["Tim", "Sarah", "Diego", "Doug", "Priya"],
    "random_seed": 42,
    "director_top_p": 0.8,
    "action_window_size": 5,
    "moderator_top_p": 1.0,
    "performer_top_p": 0.8,
    "director_llm_model": "claude-haiku-4-5",
    "evaluate_interval": 5,
    "director_max_tokens": 1024,
    "messages_per_minute": 6,
    "moderator_llm_model": "claude-haiku-4-5",
    "performer_llm_model": "mistral-large-latest",
    "director_temperature": 0.8,
    "moderator_max_tokens": 256,
    "performer_max_tokens": 256,
    "director_llm_provider": "anthropic",
    "moderator_temperature": 0.2,
    "performer_temperature": 0.8,
    "moderator_llm_provider": "anthropic",
    "performer_llm_provider": "mistral",
    "performer_memory_size": 3,
    "session_duration_minutes": 3,
}

CHATROOM_CONTEXT = (
    "This is a an english-language telegram chatroom about climate change, based in the UK."
)
ECOLOGICAL_CRITERIA = (
    "The conversation should be dialogic: agents should react to the state of the conversation, "
    "rather than talking past each other. There should be a mix of action types: approx. 30% message, "
    "30% likes, 20% replies, 20% @mentions. Messages must be short (1-2 sentences, under 30 words) "
    "— brief, punchy contributions like in a real group chat. Tone and style should vary, "
    "with some containing emojis or punctuation. Messages should be 'reddit-like': informal, "
    "self-aware, and sometimes include internet humour, slang, and abbreviations."
)
INTERNAL_VALIDITY_CRITERIA = (
    "2 of the 5 performers must be climate SKEPTICS who communicate in an UNCIVIL manner — "
    "dismissive, sarcastic, aggressive, or rude toward climate concern. "
    "The other 3 performers must be climate CONCERNED and communicate CIVILLY — "
    "polite, respectful, and earnest about climate issues. "
    "Each performer must consistently maintain their assigned stance and tone throughout the conversation."
    "Each performer must contribute equally."
)


# ── Logging LLM wrapper ──────────────────────────────────────────────────

CALL_LOG = []


class LoggingLLMClient:
    """Wraps a real LLM client, capturing every call's input and output."""

    def __init__(self, real_client, role_label: str):
        self._client = real_client
        self._role = role_label

    async def generate_response_async(self, prompt, max_retries=1, system_prompt=None):
        response = await self._client.generate_response_async(
            prompt, max_retries=max_retries, system_prompt=system_prompt,
        )
        CALL_LOG.append({
            "role": self._role,
            "system_prompt": system_prompt,
            "user_prompt": prompt,
            "response": response,
        })
        return response

    def generate_response(self, prompt, max_retries=1, system_prompt=None):
        response = self._client.generate_response(
            prompt, max_retries=max_retries, system_prompt=system_prompt,
        )
        CALL_LOG.append({
            "role": self._role,
            "system_prompt": system_prompt,
            "user_prompt": prompt,
            "response": response,
        })
        return response


# ── Helpers ───────────────────────────────────────────────────────────────

def print_section(title, content, width=80):
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)
    print(content if content else "(empty)")
    print()


# ── Main ──────────────────────────────────────────────────────────────────

async def main():
    # Build real LLM clients wrapped with logging
    director_llm = LLMManager.from_simulation_config(SIMULATION_CONFIG, role="director")
    performer_llm = LLMManager.from_simulation_config(SIMULATION_CONFIG, role="performer")
    moderator_llm = LLMManager.from_simulation_config(SIMULATION_CONFIG, role="moderator")

    director_llm.client = LoggingLLMClient(director_llm.client, "DIRECTOR")
    performer_llm.client = LoggingLLMClient(performer_llm.client, "PERFORMER")
    moderator_llm.client = LoggingLLMClient(moderator_llm.client, "MODERATOR")

    # Build session state (starts empty)
    agents = [Agent(name=n) for n in SIMULATION_CONFIG["agent_names"]]
    state = SessionState(
        session_id=SESSION_ID,
        agents=agents,
        duration_minutes=SIMULATION_CONFIG["session_duration_minutes"],
        experimental_config={"internal_validity_criteria": INTERNAL_VALIDITY_CRITERIA},
        treatment_group=TREATMENT_GROUP,
        simulation_config=SIMULATION_CONFIG,
        user_name="participant",
    )

    rng = random.Random(SIMULATION_CONFIG["random_seed"])
    logger = Logger(SESSION_ID, EXPERIMENT_ID)

    # Create real Orchestrator
    orchestrator = Orchestrator(
        director_llm=director_llm,
        performer_llm=performer_llm,
        moderator_llm=moderator_llm,
        state=state,
        logger=logger,
        evaluate_interval=SIMULATION_CONFIG["evaluate_interval"],
        action_window_size=SIMULATION_CONFIG["action_window_size"],
        performer_memory_size=SIMULATION_CONFIG["performer_memory_size"],
        chatroom_context=CHATROOM_CONTEXT,
        ecological_criteria=ECOLOGICAL_CRITERIA,
        rng=rng,
    )

    # Show the anonymization mapping
    print_section("NAME MAP (real → anonymous)", "\n".join(
        f"  {real:>15s}  →  {anon}"
        for real, anon in orchestrator._name_map.items()
    ))

    # Step through turns
    for turn in range(1, NUM_TURNS + 1):
        CALL_LOG.clear()

        print("#" * 80)
        print(f"  TURN {turn}")
        print("#" * 80)

        print(f"\n>>> State: {len(state.messages)} messages in history")
        print(f">>> Orchestrator: last_agent={orchestrator._last_agent}, "
              f"last_action={orchestrator._last_action_type}, "
              f"turns_since_eval={orchestrator._turns_since_evaluate}, "
              f"first_interval_done={orchestrator._has_completed_first_interval}")
        print()

        result = await orchestrator.execute_turn(INTERNAL_VALIDITY_CRITERIA)

        # Display all captured LLM calls for this turn
        for i, call in enumerate(CALL_LOG, 1):
            print_section(
                f"LLM CALL {i}: {call['role']} — SYSTEM PROMPT",
                call["system_prompt"],
            )
            print_section(
                f"LLM CALL {i}: {call['role']} — USER PROMPT",
                call["user_prompt"],
            )
            print_section(
                f"LLM CALL {i}: {call['role']} — RESPONSE",
                call["response"],
            )

        # Display final TurnResult
        if result:
            print_section(f"TURN {turn} RESULT", "\n".join([
                f"  Agent:       {result.agent_name}",
                f"  Action:      {result.action_type}",
                f"  Target user: {result.target_user}",
                f"  Target msg:  {result.target_message_id}",
                f"  Priority:    {result.priority}",
                f"  Content:     {result.message.content if result.message else '(none)'}",
            ]))

            # Apply the result to state so the next turn sees it
            if result.action_type == "like" and result.target_message_id:
                target_msg = next(
                    (m for m in state.messages if m.message_id == result.target_message_id),
                    None,
                )
                if target_msg:
                    target_msg.toggle_like(result.agent_name)
                    print(f"  [{result.agent_name} liked message {result.target_message_id}]")
            elif result.message:
                state.add_message(result.message)
                print(f"  [Added message to state — now {len(state.messages)} messages]")
        else:
            print_section(f"TURN {turn} RESULT", "(None — turn failed)")

        # Show accumulated profiles
        print_section("AGENT PROFILES (after turn)", "\n".join(
            f"  {name}: {profile or '(empty)'}"
            for name, profile in orchestrator.agent_profiles.items()
        ))


asyncio.run(main())
