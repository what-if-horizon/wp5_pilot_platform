import re
import random
from copy import copy
from dataclasses import dataclass
from typing import Optional, List, Dict

from models import Message, Agent
from utils import Logger
from agents.STAGE.director import build_director_system_prompt, build_director_user_prompt, parse_director_response
from agents.STAGE.performer import build_performer_system_prompt, build_performer_user_prompt
from agents.STAGE.moderator import build_moderator_system_prompt, build_moderator_user_prompt, parse_moderator_response


MAX_PERFORMER_RETRIES = 3


@dataclass
class TurnResult:
    """The result of a single Director->Performer turn.

    For 'like' actions, `message` will be None and `target_message_id`
    identifies the message to like.  For all other action types,
    `message` contains the generated Message ready to be added to state.
    """
    action_type: str
    agent_name: str
    message: Optional[Message] = None
    target_message_id: Optional[str] = None
    target_user: Optional[str] = None
    director_reasoning: Optional[str] = None


# ── Anonymization helpers ────────────────────────────────────────────────────

def build_name_map(agent_names: List[str], user_name: str, rng: random.Random) -> Dict[str, str]:
    """Build a shuffled mapping from real names to anonymous labels.

    All participants (agents + human) are assigned "Member 1", "Member 2", …
    in a random order so the LLM cannot distinguish the human from agents.
    """
    all_names = list(agent_names) + [user_name]
    rng.shuffle(all_names)
    return {name: f"Member {i + 1}" for i, name in enumerate(all_names)}


def anonymize_message(msg: Message, name_map: Dict[str, str]) -> Message:
    """Return a shallow copy of a Message with sender/mentions/content anonymized."""
    anon = copy(msg)
    anon.sender = name_map.get(msg.sender, msg.sender)

    # Anonymize @mentions in metadata
    if msg.mentions:
        anon.mentions = [name_map.get(m, m) for m in msg.mentions]

    # Anonymize names in liked_by
    if msg.liked_by:
        anon.liked_by = {name_map.get(u, u) for u in msg.liked_by}

    # Anonymize names embedded in content (e.g. "@Maria")
    anon.content = _replace_names_in_text(msg.content, name_map)

    # Anonymize quoted text too
    if msg.quoted_text:
        anon.quoted_text = _replace_names_in_text(msg.quoted_text, name_map)

    return anon


def anonymize_agents(agents: List[Agent], name_map: Dict[str, str]) -> List[Agent]:
    """Return a list of Agents with anonymized names."""
    return [Agent(name=name_map.get(a.name, a.name)) for a in agents]


def _replace_names_in_text(text: str, name_map: Dict[str, str]) -> str:
    """Replace all occurrences of real names in text with their anonymous labels."""
    if not text:
        return text
    # Sort by length descending so longer names are replaced first
    for real, anon in sorted(name_map.items(), key=lambda x: -len(x[0])):
        text = text.replace(real, anon)
    return text


def deanonymize_text(text: str, reverse_map: Dict[str, str]) -> str:
    """Replace anonymous labels in text back to real names."""
    return _replace_names_in_text(text, reverse_map)


class Orchestrator:
    """Coordinates the Director->Performer->Moderator pipeline for each simulation turn.

    The Orchestrator is stateless with respect to conversation history; it
    reads the current state each time `execute_turn` is called.

    All names are anonymized before being sent to the LLMs and deanonymized
    in the response, so the models cannot distinguish the human participant
    from the AI agents.
    """

    def __init__(
        self,
        director_llm,
        performer_llm,
        moderator_llm,
        state,
        logger: Logger,
        context_window_size: int = 10,
        chatroom_context: str = "",
        rng: Optional[random.Random] = None,
    ):
        self.director_llm = director_llm
        self.performer_llm = performer_llm
        self.moderator_llm = moderator_llm
        self.state = state
        self.logger = logger
        self.context_window_size = context_window_size
        self.chatroom_context = chatroom_context

        # Build the shuffled name mapping (stable for the session lifetime).
        _rng = rng or random.Random()
        agent_names = [a.name for a in state.agents]
        self._name_map = build_name_map(agent_names, state.user_name, _rng)
        self._reverse_map = {v: k for k, v in self._name_map.items()}
        self._anon_user = self._name_map[state.user_name]

        # System prompts are cached (session-static data only).
        # Performer/Moderator system prompts can be built immediately; Director
        # needs treatment + human_user which arrive with the first execute_turn call.
        self._performer_system_prompt = build_performer_system_prompt(
            chatroom_context=chatroom_context,
        )
        self._moderator_system_prompt = build_moderator_system_prompt(
            chatroom_context=chatroom_context,
        )
        self._director_system_prompt: Optional[str] = None

    def _deanon_name(self, anon_name: str) -> str:
        """Map an anonymous label back to the real name."""
        return self._reverse_map.get(anon_name, anon_name)

    async def execute_turn(self, treatment: str) -> Optional[TurnResult]:
        """Run one full Director->Performer cycle.

        Returns a TurnResult on success, or None if the cycle fails.
        """
        # 1. Gather recent messages and available agents, then anonymize
        recent = self.state.get_recent_messages(self.context_window_size)
        agents = self.state.agents

        anon_recent = [anonymize_message(m, self._name_map) for m in recent]
        anon_agents = anonymize_agents(agents, self._name_map)

        # 2. Build and send the Director prompt (system + user)
        if self._director_system_prompt is None:
            self._director_system_prompt = build_director_system_prompt(
                treatment=treatment,
                human_user=self._anon_user,
                chatroom_context=self.chatroom_context,
            )

        director_user_prompt = build_director_user_prompt(
            treatment, anon_recent, anon_agents,
            human_user=self._anon_user,
            chatroom_context=self.chatroom_context,
        )
        director_raw = None
        try:
            director_raw = await self.director_llm.generate_response(
                director_user_prompt, max_retries=1,
                system_prompt=self._director_system_prompt,
            )
        except Exception as e:
            self.logger.log_error("director_llm_call", str(e))
            return None

        # Log the Director call
        self.logger.log_llm_call(
            agent_name="__director__",
            prompt=f"[SYSTEM]\n{self._director_system_prompt}\n\n[USER]\n{director_user_prompt}",
            response=director_raw,
            error=None if director_raw else "Director LLM returned no response",
        )

        if not director_raw:
            return None

        # 3. Parse the Director's JSON response and deanonymize names
        try:
            director_data = parse_director_response(director_raw)
        except ValueError as e:
            self.logger.log_error("director_parse", str(e))
            return None

        action_type = director_data["action_type"]
        agent_name = self._deanon_name(director_data["next_agent"])
        target_user = director_data.get("target_user")
        if target_user:
            target_user = self._deanon_name(target_user)
        target_message_id = director_data.get("target_message_id")
        reasoning = director_data.get("reasoning")

        # Validate that the chosen agent exists; fall back to a random valid agent.
        if not agents:
            self.logger.log_error("director_agent", "No agents available for this session")
            return None
        if not any(a.name == agent_name for a in agents):
            fallback = random.choice(agents).name
            self.logger.log_error(
                "director_agent",
                f"Director chose unknown agent '{agent_name}'; falling back to '{fallback}'",
            )
            agent_name = fallback

        # 4. Handle 'like' actions (no Performer call needed)
        if action_type == "like":
            return TurnResult(
                action_type="like",
                agent_name=agent_name,
                target_message_id=target_message_id,
                director_reasoning=reasoning,
            )

        # 5. Performer -> Moderator loop (max MAX_PERFORMER_RETRIES attempts)
        performer_instruction = director_data.get("performer_instruction", {})

        # Look up target message if needed (for reply), and prepare an anon copy
        target_message = None
        anon_target_message = None
        if target_message_id:
            target_message = next(
                (m for m in self.state.messages if m.message_id == target_message_id),
                None,
            )
            if target_message:
                anon_target_message = anonymize_message(target_message, self._name_map)

        # Anonymize target_user for the performer prompt
        anon_target_user = self._name_map.get(target_user, target_user) if target_user else None

        performer_user_prompt = build_performer_user_prompt(
            instruction=performer_instruction,
            action_type=action_type,
            messages=anon_recent,
            target_message=anon_target_message,
            target_user=anon_target_user,
            chatroom_context=self.chatroom_context,
        )

        content = None

        for attempt in range(1, MAX_PERFORMER_RETRIES + 1):
            # 5a. Call the Performer
            performer_raw = None
            try:
                performer_raw = await self.performer_llm.generate_response(
                    performer_user_prompt, max_retries=1,
                    system_prompt=self._performer_system_prompt,
                )
            except Exception as e:
                self.logger.log_error("performer_llm_call", str(e))

            self.logger.log_llm_call(
                agent_name=agent_name,
                prompt=f"[SYSTEM]\n{self._performer_system_prompt}\n\n[USER]\n{performer_user_prompt}",
                response=performer_raw,
                error=None if performer_raw else f"Performer LLM returned no response (attempt {attempt}/{MAX_PERFORMER_RETRIES})",
            )

            if not performer_raw:
                continue

            # 5b. Call the Moderator to extract clean content
            moderator_user_prompt = build_moderator_user_prompt(
                performer_output=performer_raw,
                action_type=action_type,
            )

            moderator_raw = None
            try:
                moderator_raw = await self.moderator_llm.generate_response(
                    moderator_user_prompt, max_retries=1,
                    system_prompt=self._moderator_system_prompt,
                )
            except Exception as e:
                self.logger.log_error("moderator_llm_call", str(e))

            self.logger.log_llm_call(
                agent_name="__moderator__",
                prompt=f"[SYSTEM]\n{self._moderator_system_prompt}\n\n[USER]\n{moderator_user_prompt}",
                response=moderator_raw,
                error=None if moderator_raw else f"Moderator LLM returned no response (attempt {attempt}/{MAX_PERFORMER_RETRIES})",
            )

            content = parse_moderator_response(moderator_raw)

            if content is not None:
                break
            else:
                self.logger.log_error(
                    "moderator_no_content",
                    f"Moderator could not extract content from performer output (attempt {attempt}/{MAX_PERFORMER_RETRIES})",
                )

        if content is None:
            self.logger.log_error(
                "performer_retries_exhausted",
                f"Failed to get valid performer content after {MAX_PERFORMER_RETRIES} attempts",
            )
            return None

        # 6. Deanonymize any anonymous labels in the generated content.
        content = deanonymize_text(content, self._reverse_map)

        # 7. Format the output into a Message

        # For @mention actions, prepend the @mention to the message
        mentions = None
        reply_to = None
        quoted_text = None

        if action_type == "@mention" and target_user:
            content = f"@{target_user} {content}"
            mentions = [target_user]
        elif action_type == "reply" and target_message_id:
            reply_to = target_message_id
            if target_message:
                quoted_text = target_message.content

        message = Message.create(
            sender=agent_name,
            content=content,
            reply_to=reply_to,
            quoted_text=quoted_text,
            mentions=mentions,
        )

        return TurnResult(
            action_type=action_type,
            agent_name=agent_name,
            message=message,
            target_message_id=target_message_id,
            target_user=target_user,
            director_reasoning=reasoning,
        )
