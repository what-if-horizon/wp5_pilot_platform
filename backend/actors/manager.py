import asyncio
import random
import re
from typing import Callable, Optional, Dict, List

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
        # Dynamics managed by AgentManager
        self.affinity: Dict[str, Dict[str, float]] = {}
        # Tunable parameters with sensible defaults (can be overridden by initialize_dynamics)
        self.heat_decay: float = 0.9
        self.heat_boost_speak: float = 1.0
        self.heat_boost_address: float = 0.5
        self.min_weight_floor: float = 0.01
        # Local RNG (can be seeded for reproducibility)
        self._rng = random.Random()

    def set_websocket_send(self, websocket_send: Optional[Callable]) -> None:
        self.websocket_send = websocket_send or (lambda *_: None)

    def initialize_dynamics(self, simulation_config: dict) -> None:
        """Initialize chattiness, heat and affinity matrix from simulation_config or random defaults."""
        # Load tunables if provided
        try:
            self.heat_decay = float(simulation_config.get("heat_decay", self.heat_decay))
            self.heat_boost_speak = float(simulation_config.get("heat_boost_speak", self.heat_boost_speak))
            self.heat_boost_address = float(simulation_config.get("heat_boost_address", self.heat_boost_address))
            self.min_weight_floor = float(simulation_config.get("min_weight_floor", self.min_weight_floor))
        except Exception:
            pass

        # Seed local RNG for reproducible initialization if requested
        seed = simulation_config.get("random_seed", None)
        try:
            if seed is not None:
                self._rng = random.Random(int(seed))
            else:
                self._rng = random.Random()
        except Exception:
            self._rng = random.Random()

        # Initialize per-agent chattiness and heat
        # Optional explicit map: simulation_config.get('chattiness_map') -> {name: float}
        chattiness_map = simulation_config.get("chattiness_map", {}) or {}
        for a in self.state.agents:
            if a.name in chattiness_map:
                a.chattiness = float(chattiness_map[a.name])
            else:
                a.chattiness = float(self._rng.random())
            a.heat = 0.0

        # Initialize affinity matrix (ordered pairs). Use provided map or random
        affinity_cfg = simulation_config.get("affinity", {}) or {}
        self.affinity = {}
        names = [a.name for a in self.state.agents]
        for src in names:
            self.affinity[src] = {}
            for tgt in names:
                if src == tgt:
                    self.affinity[src][tgt] = 0.0
                else:
                    if src in affinity_cfg and tgt in affinity_cfg.get(src, {}):
                        try:
                            self.affinity[src][tgt] = float(affinity_cfg[src][tgt])
                        except Exception:
                            self.affinity[src][tgt] = float(self._rng.random())
                    else:
                        self.affinity[src][tgt] = float(self._rng.random())

    async def on_tick(self) -> None:
        """Called once per simulation tick to apply heat decay."""
        try:
            for a in self.state.agents:
                a.heat = a.heat * self.heat_decay
        except Exception:
            # Don't let tick failures crash the session
            try:
                self.logger.log_error("on_tick", "failed to apply heat decay")
            except Exception:
                pass

    def _weighted_choice(self, items: List, weights: List[float]):
        """Return a single item from items using weights (non-negative)."""
        total = sum(weights)
        if total <= 0:
            # fallback to uniform
            return (self._rng.choice(items) if hasattr(self, "_rng") else random.choice(items)) if items else None
        r = (self._rng.random() if hasattr(self, "_rng") else random.random()) * total
        upto = 0.0
        for it, w in zip(items, weights):
            upto += w
            if r <= upto:
                return it
        return items[-1]

    def _get_agent_by_name(self, name: str):
        return next((a for a in self.state.agents if a.name == name), None)

    def select_agent(self, context_type: str):
        """Choose which agent should act for this tick.

        Implements weighted selection per the Bot Selection System.
        """
        if not self.state.agents:
            return None

        # Foreground (user response) respects explicit addressing first
        if context_type == "user_response":
            last_user_msg = None
            for m in reversed(self.state.messages):
                if m.sender == self.state.user_name:
                    last_user_msg = m
                    break

            if last_user_msg:
                # 1) @mentions (ordered)
                if last_user_msg.mentions:
                    agent_name_map = {a.name.lower(): a for a in self.state.agents}
                    for nm in last_user_msg.mentions:
                        if nm and nm.lower() in agent_name_map:
                            target = agent_name_map[nm.lower()]
                            # addressed: boost address heat
                            target.heat = min(1.0, target.heat + self.heat_boost_address)
                            return target

                # 2) reply_to -> referenced message sender
                if last_user_msg.reply_to:
                    ref_id = last_user_msg.reply_to
                    ref_msg = next((x for x in self.state.messages if x.message_id == ref_id), None)
                    if ref_msg and ref_msg.sender and ref_msg.sender != self.state.user_name:
                        target = next((a for a in self.state.agents if a.name == ref_msg.sender), None)
                        if target:
                            target.heat = min(1.0, target.heat + self.heat_boost_address)
                            return target

        # Fallback: weighted choice among agents using chattiness*(1+heat)
        names = [a for a in self.state.agents]
        weights = [max(self.min_weight_floor, a.chattiness * (1.0 + a.heat)) for a in names]
        return self._weighted_choice(names, weights)
    
    def select_target(self, speaker, context_type: str):
        """Select a target agent for a speaker using affinity and target heat.

        For background posts, uses:
            weight(target) = affinity[speaker][target] * (1 + target.heat)
        Excludes speaker from choices. Returns an Agent or None if no valid target.
        """
        if not speaker or not self.state.agents:
            return None

        names = [a for a in self.state.agents if a.name != speaker.name]
        if not names:
            return None

        weights = []
        for tgt in names:
            aff = 0.0
            try:
                aff = float(self.affinity.get(speaker.name, {}).get(tgt.name, 0.0))
            except Exception:
                aff = 0.0
            w = max(self.min_weight_floor, aff * (1.0 + tgt.heat))
            weights.append(w)

        return self._weighted_choice(names, weights)
    
    async def agent_perform_action(self, agent, context_type: str, target=None) -> None:
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

        # Build prompt using provided callback. Accept optional target if prompt_builder supports it.
        try:
            prompt = self.prompt_builder(agent, target, context_type)
        except TypeError:
            # fallback to older signature
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

        # Update heat for addressed targets (mentions)
        if mentions:
            for nm in mentions:
                tgt = next((a for a in self.state.agents if a.name == nm), None)
                if tgt:
                    tgt.heat = min(1.0, tgt.heat + self.heat_boost_address)

        # If a target was selected by the actor logic but the LLM didn't mention them,
        # add the target as an addressed mention so the "to whom" choice is honored.
        if target and isinstance(target, object):
            try:
                target_name = getattr(target, "name", None)
            except Exception:
                target_name = None
            if target_name and target_name not in (mentions or []):
                # Only enforce for background posts (foreground target is user)
                if context_type == "background":
                    if mentions is None:
                        mentions = [target_name]
                    else:
                        mentions.append(target_name)
                    # also boost target heat
                    try:
                        tgt = next((a for a in self.state.agents if a.name == target_name), None)
                        if tgt:
                            tgt.heat = min(1.0, tgt.heat + self.heat_boost_address)
                    except Exception:
                        pass

        # Create and persist message
        message = Message.create(sender=agent.name, content=response_text, mentions=mentions or None)
        self.state.add_message(message)
        self.logger.log_message(message.to_dict())

        # Send to frontend
        try:
            await self.websocket_send(message.to_dict())
        except Exception as e:
            self.logger.log_error("send", str(e))

        # When a bot speaks, set its heat
        try:
            agent.heat = min(1.0, float(self.heat_boost_speak))
        except Exception:
            pass


__all__ = ["AgentManager"]
