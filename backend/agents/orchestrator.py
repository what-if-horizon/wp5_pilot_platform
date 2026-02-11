from dataclasses import dataclass
from typing import Optional, List

from models import Message, Agent
from utils import Logger
from agents.director import build_director_prompt, parse_director_response
from agents.performer import build_performer_prompt


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


class Orchestrator:
    """Coordinates the Director->Performer pipeline for each simulation turn.

    The Orchestrator is stateless with respect to conversation history; it
    reads the current state each time `execute_turn` is called.
    """

    def __init__(
        self,
        director_llm,
        performer_llm,
        state,
        logger: Logger,
        context_window_size: int = 10,
    ):
        self.director_llm = director_llm
        self.performer_llm = performer_llm
        self.state = state
        self.logger = logger
        self.context_window_size = context_window_size

    async def execute_turn(self, treatment: str) -> Optional[TurnResult]:
        """Run one full Director->Performer cycle.

        Returns a TurnResult on success, or None if the cycle fails.
        """
        # 1. Gather recent messages and available agents
        recent = self.state.get_recent_messages(self.context_window_size)
        agents = self.state.agents

        # 2. Build and send the Director prompt
        director_prompt = build_director_prompt(treatment, recent, agents, human_user=self.state.user_name)
        director_raw = None
        try:
            director_raw = await self.director_llm.generate_response(director_prompt, max_retries=1)
        except Exception as e:
            self.logger.log_error("director_llm_call", str(e))
            return None

        # Log the Director call
        self.logger.log_llm_call(
            agent_name="__director__",
            prompt=director_prompt,
            response=director_raw,
            error=None if director_raw else "Director LLM returned no response",
        )

        if not director_raw:
            return None

        # 3. Parse the Director's JSON response
        try:
            director_data = parse_director_response(director_raw)
        except ValueError as e:
            self.logger.log_error("director_parse", str(e))
            return None

        action_type = director_data["action_type"]
        agent_name = director_data["next_agent"]
        target_user = director_data.get("target_user")
        target_message_id = director_data.get("target_message_id")
        reasoning = director_data.get("reasoning")

        # Validate that the chosen agent exists
        if not any(a.name == agent_name for a in agents):
            self.logger.log_error("director_agent", f"Director chose unknown agent: '{agent_name}'")
            return None

        # 4. Handle 'like' actions (no Performer call needed)
        if action_type == "like":
            return TurnResult(
                action_type="like",
                agent_name=agent_name,
                target_message_id=target_message_id,
                director_reasoning=reasoning,
            )

        # 5. Build and send the Performer prompt
        performer_instruction = director_data.get("performer_instruction", {})

        # Look up target message if needed (for reply)
        target_message = None
        if target_message_id:
            target_message = next(
                (m for m in self.state.messages if m.message_id == target_message_id),
                None,
            )

        performer_prompt = build_performer_prompt(
            instruction=performer_instruction,
            action_type=action_type,
            messages=recent,
            target_message=target_message,
            target_user=target_user,
        )

        performer_raw = None
        try:
            performer_raw = await self.performer_llm.generate_response(performer_prompt, max_retries=1)
        except Exception as e:
            self.logger.log_error("performer_llm_call", str(e))
            return None

        # Log the Performer call
        self.logger.log_llm_call(
            agent_name=agent_name,
            prompt=performer_prompt,
            response=performer_raw,
            error=None if performer_raw else "Performer LLM returned no response",
        )

        if not performer_raw:
            return None

        # 6. Format the output into a Message
        content = performer_raw.strip()

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
