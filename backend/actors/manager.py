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
    - ask the LLM manager for a response (routed to correct LLM)
    - create Message objects, add to state, log and send via websocket
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

    def select_agent(self, context_type: str):
        """Choose which agent should act for this tick.

        Returns an Agent instance (or None if no agents are configured).
        Selection policy:
        - If `context_type == 'user_response'`, and if the user @mentioned or replied to an agent, select that agent.
        - (@mentions are treated as higher priority than quote-replies in agent selection)
        - Else, fall back to a uniform random choice among agents.
        """
        if not self.state.agents:
            return None

        agent = None
        if context_type == "user_response":
            # Find the most recent user message
            last_user_msg = None
            for m in reversed(self.state.messages):
                if m.sender == self.state.user_name:
                    last_user_msg = m
                    break

            if last_user_msg:
                # 1) Check @mentions on the user message (ordered)
                if last_user_msg.mentions:
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
                        agent = next((a for a in self.state.agents if a.name == ref_msg.sender), None)

        # Fallback: uniform random choice if no targeted agent found
        if not agent:
            agent = random.choice(self.state.agents)

        return agent
    
    async def agent_perform_action(self, agent, context_type: str) -> None:
        """Perform the action for the chosen `agent`.

        This includes optional delay (for user-triggered responses), building the
        prompt, requesting an LLM response, parsing mentions, persisting the
        Message and sending it via websocket.
        """
        if not agent:
            return

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
                wpm = 40.0
                chars_per_word = 5.0
                per_char = 60.0 / (wpm * chars_per_word)
                delay = min(max(0.5, content_len * per_char), 30.0)
            else:
                delay = 0.5

            try:
                await asyncio.sleep(delay)
            except Exception:
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
