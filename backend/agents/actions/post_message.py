import asyncio
import re

from models import Message


async def post_message_action(manager, agent, context_type: str) -> None:
    """Action: produce and send a message on behalf of `agent`.

    This function is intentionally written to be minimal in terms of required
    arguments: it receives the `AgentManager` instance as `manager` so it can
    access state, llm_manager, logger, prompt_builder, and websocket_send.
    """
    if not agent:
        return

    # NOTE: Delay is applied after the agent's response is generated
    # so we can base the typing delay on the actual message length.

    # Build prompt (deterministic): always use the local builder moved
    # here from AgentManager. No fallbacks or manager-provided builders.
    def _local_build_prompt(manager, agent, context_type: str = None) -> str:
        # Use the validated simulation_config attached to the manager
        simulation_config = getattr(manager, "simulation_config", {}) or {}
        try:
            context_size = int(simulation_config["context_window_size"])
        except Exception:
            context_size = 20

        recent_messages = getattr(manager.state, "get_recent_messages", lambda n: [])(context_size)
        if recent_messages:
            context = "\n".join([f"{m.sender}: {m.content}" for m in recent_messages])
        else:
            context = "(No messages yet)"

        # Resolve prompt template: prefer agent.prompt key in the full prompts table
        prompt_template = ""
        try:
            prompt_key = getattr(agent, "prompt", None)
            prompt_template = (
                (getattr(manager, "experimental_settings_full", {}).get("prompts", {}) or {}).get(prompt_key, {}).get("prompt_template")
                if prompt_key
                else None
            )
        except Exception:
            prompt_template = None

        # Backward-compatible fallback: group-level prompt_template on state
        if not prompt_template:
            try:
                prompt_template = getattr(manager.state, "experimental_config", {}).get("prompt_template", "")
            except Exception:
                prompt_template = ""

        # Replace @name placeholder with the agent's actual name
        if prompt_template:
            prompt_template = prompt_template.replace("@name", agent.name)

        prompt = f"{prompt_template}\n\nRecent messages:\n{context}"

        # For foreground (user response), instruct agent to address the user
        if context_type == "foreground":
            try:
                user_name = getattr(manager.state, "user_name", "user")
                prompt = f"{prompt}\n\nAddress your response to {user_name}."
            except Exception:
                pass

        return prompt

    prompt = _local_build_prompt(manager, agent, context_type)

    response_text = None
    try:
        response_text = await manager.llm_manager.generate_response(prompt, max_retries=1)
    except Exception as e:
        response_text = None
        try:
            manager.logger.log_error("llm_call", str(e))
        except Exception:
            pass

    # Log LLM call
    try:
        manager.logger.log_llm_call(
            agent_name=agent.name,
            prompt=prompt,
            response=response_text,
            error=None if response_text else "Failed after retries",
        )
    except Exception:
        pass

    if not response_text:
        return

    # Apply a typing-like delay based on the generated response length so
    # the bot appears to 'type' the message. This works for both foreground
    # and background posts.
    try:
        try:
            wpm = 100.0
            chars_per_word = 5.0
            per_char = 60.0 / (wpm * chars_per_word)
            min_delay = 0.5
            max_delay = 15.0
            content_len = len(response_text or "")
            delay = min(max(min_delay, content_len * per_char), max_delay)
        except Exception:
            delay = 0.5

        if delay and delay > 0:
            await asyncio.sleep(delay)
    except Exception:
        pass

    # Parse mentions marker [[MENTIONS:...]] or inline @name
    mentions = []
    m = re.search(r"\[\[MENTIONS:(.*?)\]\]\s*$", response_text)
    if m:
        raw = m.group(1)
        mentions = [s.strip() for s in raw.split(",") if s.strip()]
        response_text = re.sub(r"\s*\[\[MENTIONS:.*?\]\]\s*$", "", response_text)
    else:
        found = re.findall(r"@([A-Za-z0-9_\-]+)", response_text)
        if found:
            agent_name_map = {a.name.lower(): a.name for a in manager.state.agents}
            for nm in found:
                key = nm.lower()
                if key in agent_name_map and agent_name_map[key] not in mentions:
                    mentions.append(agent_name_map[key])

    # Boost attention for mentioned agents
    if mentions:
        for nm in mentions:
            tgt = next((a for a in manager.state.agents if a.name == nm), None)
            if tgt:
                try:
                    tgt.attention = min(1.0, float(getattr(tgt, "attention", 0.0)) + manager.attention_boost_address)
                except Exception:
                    tgt.attention = min(1.0, manager.attention_boost_address)

    # Persist message
    message = Message.create(sender=agent.name, content=response_text, mentions=mentions or None)
    try:
        manager.state.add_message(message)
    except Exception:
        pass

    try:
        manager.logger.log_message(message.to_dict())
    except Exception:
        pass

    # Send to frontend
    try:
        await manager.websocket_send(message.to_dict())
    except Exception as e:
        try:
            manager.logger.log_error("send", str(e))
        except Exception:
            pass

    # When a bot speaks, set its attention
    try:
        agent.attention = min(1.0, float(manager.attention_boost_speak))
    except Exception:
        pass
