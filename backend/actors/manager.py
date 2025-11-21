import asyncio
import random
import re
from typing import Callable, Optional

from models import Message


class AgentManager:
    """Encapsulates agent selection and action logic.

    Minimal responsibilities (expandable):
    - decide which agent should act in a given context
    - build or request a prompt via a provided prompt_builder
    - ask the LLM manager for a response
    - create Message objects, add to state, log and send via websocket

    The implementation below mirrors the previous inlined logic but centralises it
    so platform code focuses on the ticking / opportunity structure.
    """

    def __init__(
        self,
        state,
        llm_manager,
        logger,
        prompt_builder: Callable,
        websocket_send: Optional[Callable] = None,
    ) -> None:
        self.state = state
        self.llm_manager = llm_manager
        self.logger = logger
        self.prompt_builder = prompt_builder
        self.websocket_send = websocket_send or (lambda *_: None)

    def set_websocket_send(self, websocket_send: Optional[Callable]) -> None:
        self.websocket_send = websocket_send or (lambda *_: None)

    async def decide_and_act(self, context_type: str) -> None:
        """Decide which agent acts and perform the action for this tick.

        This is intentionally minimal: selection is random for now. Behaviour can
        be extended (e.g., weighting, stateful turn-taking, attention models).
        """
        # Select agent
        if not self.state.agents:
            return

        agent = None
        # If this was triggered by a user message, prefer an explicitly targeted agent
        # (either via message.mentions or by quote-replying to an agent's message).
        if context_type == "user_response":
            # Find the most recent user message
            last_user_msg = None
            for m in reversed(self.state.messages):
                if m.sender == self.state.user_name:
                    last_user_msg = m
                    break

            if last_user_msg:
                # 1) Check explicit mentions on the user message (ordered)
                if last_user_msg.mentions:
                    # Map agent names lower->Agent for case-insensitive matching
                    agent_name_map = {a.name.lower(): a for a in self.state.agents}
                    for nm in last_user_msg.mentions:
                        if nm and nm.lower() in agent_name_map:
                            agent = agent_name_map[nm.lower()]
                            break

                # 2) If no mention matched, check reply_to -> find referenced message
                if not agent and last_user_msg.reply_to:
                    ref_id = last_user_msg.reply_to
                    ref_msg = next((x for x in self.state.messages if x.message_id == ref_id), None)
                    if ref_msg and ref_msg.sender and ref_msg.sender != self.state.user_name:
                        # If the referenced sender matches an agent name, choose that agent
                        agent = next((a for a in self.state.agents if a.name == ref_msg.sender), None)

        # Fallback: uniform random choice if no targeted agent found
        if not agent:
            agent = random.choice(self.state.agents)

        # Introduce a small, variable delay for user-triggered responses so replies
        # don't feel instantaneous. Delay is based on the last user message length.
        if context_type == "user_response":
            last_user_msg = None
            for m in reversed(self.state.messages):
                if m.sender == self.state.user_name:
                    last_user_msg = m
                    break

            if last_user_msg:
                content_len = len(last_user_msg.content or "")
                # Estimate per-character delay from a standard typing speed.
                # Default typing speed: 40 words per minute, assume 5 chars/word.
                # per_char = 60 seconds / (wpm * chars_per_word)
                wpm = 40.0
                chars_per_word = 5.0
                per_char = 60.0 / (wpm * chars_per_word)
                # Minimum 0.5s, maximum 30s to avoid long stalls
                delay = min(max(0.5, content_len * per_char), 30.0)
            else:
                delay = 0.5

            try:
                await asyncio.sleep(delay)
            except Exception:
                # Don't let sleep-related errors stop the flow
                pass

        # Build prompt using provided callback
        prompt = self.prompt_builder(agent)

        response_text = None
        try:
            response_text = await self.llm_manager.generate_response(prompt, max_retries=1)
        except Exception as e:
            response_text = None
            self.logger.log_error("llm_call", str(e))

        # Log LLM call
        self.logger.log_llm_call(
            agent_name=agent.name,
            prompt=prompt,
            response=response_text,
            error=None if response_text else "Failed after retries",
        )

        if not response_text:
            return

        # Extract mentions marker if present
        mentions = []
        m = re.search(r"\[\[MENTIONS:(.*?)\]\]\s*$", response_text)
        if m:
            raw = m.group(1)
            mentions = [s.strip() for s in raw.split(",") if s.strip()]
            response_text = re.sub(r"\s*\[\[MENTIONS:.*?\]\]\s*$", "", response_text)
        else:
            # fallback: @name tokens
            found = re.findall(r"@([A-Za-z0-9_\-]+)", response_text)
            if found:
                agent_name_map = {a.name.lower(): a.name for a in self.state.agents}
                for nm in found:
                    key = nm.lower()
                    if key in agent_name_map and agent_name_map[key] not in mentions:
                        mentions.append(agent_name_map[key])

        # Create and persist message
        message = Message.create(sender=agent.name, content=response_text, mentions=mentions or None)
        self.state.add_message(message)
        self.logger.log_message(message.to_dict())

        # Send to frontend
        try:
            await self.websocket_send(message.to_dict())
        except Exception as e:
            self.logger.log_error("send", str(e))


__all__ = ["AgentManager"]
