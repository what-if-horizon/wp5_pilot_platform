import asyncio
import random
import re
from typing import Callable, Optional, Dict, List

from models import Message

from agents.actions.post_message import post_message_action


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
        simulation_config: dict,
        prompt_builder: Optional[Callable] = None,
        websocket_send: Optional[Callable] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.state = state
        self.llm_manager = llm_manager
        self.logger = logger
        self._rng = rng
        
        # Use provided prompt_builder or leave None so actions can use their own builder
        # Store websocket_send so actions can call `manager.websocket_send(...)`.
        # Use a no-op async-compatible callable if none provided.
        self.websocket_send = websocket_send or (lambda *_: None)
        
        # Keep a reference to the validated simulation config
        self.simulation_config = simulation_config

    #Websocket send for agent actions (backend/agents/actions/*.py)
    def set_websocket_send(self, websocket_send: Optional[Callable]) -> None:
        self.websocket_send = websocket_send or (lambda *_: None)

    # Initialize agent dynamics (gets from from SimulationSession)
    def assign_agent_dynamics(self, simulation_config: dict) -> None:
        """Initialize chattiness and attention from simulation_config or random defaults."""
        self.attention_decay = float(simulation_config["attention_decay"])
        self.attention_boost_speak = float(simulation_config["attention_boost_speak"])
        self.attention_boost_address = float(simulation_config["attention_boost_address"])
        self.min_weight_floor = float(simulation_config["min_weight_floor"])

        # Initialize per-agent chattiness and attention
        for a in self.state.agents:
            try:
                if hasattr(self, "_rng") and isinstance(self._rng, random.Random):
                    a.chattiness = float(self._rng.random())
                else:
                    a.chattiness = float(random.random())
            except Exception:
                a.chattiness = 0.0
            # initialize attention score
            try:
                # preserve existing attribute if present
                setattr(a, "attention", float(getattr(a, "attention", 0.0)))
            except Exception:
                a.attention = 0.0

        # Affinity removed: target selection uses chattiness and attention only.
        # Target selection now uses agent chattiness and attention only.

    async def on_tick(self) -> None:
        """Called once per simulation tick to apply attention decay."""
        try:
            for a in self.state.agents:
                try:
                    a.attention = float(getattr(a, "attention", 0.0)) * self.attention_decay
                except Exception:
                    a.attention = 0.0
        except Exception:
            # Don't let tick failures crash the session
            try:
                self.logger.log_error("on_tick", "failed to apply attention decay")
            except Exception:
                pass

    def assign_agent_prompts(self, experimental_settings_full: dict) -> None:
        """Assign `prompt` attributes to agents in `self.state.agents` based on
        `experimental_settings_full` and this session's `treatment_group`.

        This method is generic: it uses whatever prompt names appear under
        `[prompts]` and whatever keys are listed in a group's `makeup` table.
        If `makeup` is absent the method will fall back to equal distribution
        across available prompt names.
        """
        try:
            if not isinstance(experimental_settings_full, dict):
                return

            # retain a reference to the full experimental settings so the prompt
            # builder can look up prompt templates by key later
            try:
                self.experimental_settings_full = experimental_settings_full or {}
            except Exception:
                self.experimental_settings_full = experimental_settings_full

            prompts_table = experimental_settings_full.get("prompts", {}) or {}
            groups_table = experimental_settings_full.get("groups", {}) or {}

            tg = getattr(self.state, "treatment_group", None)
            group_cfg = groups_table.get(tg, {}) if tg is not None else {}
            # Prefer explicit `makeup` from the group's config, else try state's experimental_config
            makeup = group_cfg.get("makeup") if isinstance(group_cfg, dict) else None
            if not makeup:
                # fallback: maybe chatroom placed an experimental_config on the state
                makeup = getattr(self.state, "experimental_config", {}) or {}
                makeup = makeup.get("makeup") if isinstance(makeup, dict) else None

            # Determine which prompt names to consider
            if isinstance(makeup, dict) and makeup:
                # use keys from makeup (keeps researcher ordering if present)
                prompts = list(makeup.keys())
            else:
                # fall back to all prompts declared in the config
                prompts = list(prompts_table.keys())

            if not prompts:
                return

            N = len(self.state.agents)
            if N <= 0:
                return

            # Build raw proportions
            raw_props = []
            if isinstance(makeup, dict) and makeup:
                for p in prompts:
                    try:
                        raw_props.append(float(makeup.get(p, 0.0) or 0.0))
                    except Exception:
                        raw_props.append(0.0)
            else:
                # equal proportions
                raw_props = [1.0] * len(prompts)

            total = sum(raw_props)
            if total <= 0:
                # fallback: assign the first prompt to all agents
                chosen = prompts[0]
                for a in self.state.agents:
                    try:
                        a.prompt = chosen
                    except Exception:
                        pass
                return

            normalized = [r / total for r in raw_props]
            prods = [normalized[i] * N for i in range(len(prompts))]
            floors = [int(p) for p in prods]
            remainder = N - sum(floors)

            # Distribute remainder by fractional part (largest first)
            fracs = [(i, prods[i] - floors[i]) for i in range(len(prompts))]
            fracs.sort(key=lambda x: x[1], reverse=True)
            for idx in range(remainder):
                floors[fracs[idx % len(fracs)][0]] += 1

            # Build prompts list
            prompts_list = []
            for i, cnt in enumerate(floors):
                prompts_list.extend([prompts[i]] * cnt)

            # Ensure length matches N
            if len(prompts_list) > N:
                prompts_list = prompts_list[:N]
            elif len(prompts_list) < N:
                prompts_list.extend([prompts[0]] * (N - len(prompts_list)))

            # Shuffle assignments using manager RNG if available
            try:
                if hasattr(self, "_rng") and isinstance(self._rng, random.Random):
                    self._rng.shuffle(prompts_list)
                else:
                    random.shuffle(prompts_list)
            except Exception:
                pass

            # Apply to agents in order
            for a, p in zip(self.state.agents, prompts_list):
                try:
                    a.prompt = p
                except Exception:
                    pass

        except Exception:
            try:
                self.logger.log_error("assign_agent_prompts", "failed to assign prompts")
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
        if context_type == "foreground":
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
                            # addressed: boost addressed agent's attention
                            try:
                                target.attention = min(1.0, float(getattr(target, "attention", 0.0)) + self.attention_boost_address)
                            except Exception:
                                target.attention = min(1.0, self.attention_boost_address)
                            return target

                # 2) reply_to -> referenced message sender
                if last_user_msg.reply_to:
                    ref_id = last_user_msg.reply_to
                    ref_msg = next((x for x in self.state.messages if x.message_id == ref_id), None)
                    if ref_msg and ref_msg.sender and ref_msg.sender != self.state.user_name:
                        target = next((a for a in self.state.agents if a.name == ref_msg.sender), None)
                        if target:
                            try:
                                target.attention = min(1.0, float(getattr(target, "attention", 0.0)) + self.attention_boost_address)
                            except Exception:
                                target.attention = min(1.0, self.attention_boost_address)
                            return target

        # Fallback: weighted choice among agents using chattiness*(1+attention)
        names = [a for a in self.state.agents]
        weights = [max(self.min_weight_floor, a.chattiness * (1.0 + float(getattr(a, "attention", 0.0)))) for a in names]
        return self._weighted_choice(names, weights)
    
    def select_target(self, speaker, context_type: str):
        """Select a target agent for a speaker using chattiness and attention.

        For background posts, uses:
            weight(target) = target.chattiness * (1 + target.attention)
        Excludes speaker from choices. Returns an Agent or None if no valid target.
        """
        if not speaker or not self.state.agents:
            return None

        names = [a for a in self.state.agents if a.name != speaker.name]
        if not names:
            return None

        weights = [
            max(
                self.min_weight_floor,
                float(getattr(tgt, "chattiness", 0.0)) * (1.0 + float(getattr(tgt, "attention", 0.0)))
            )
            for tgt in names
        ]

        return self._weighted_choice(names, weights)
    
    async def agent_post_message(self, agent, context_type: str, target=None) -> None:
        """Delegate posting to the actions module (keeps AgentManager focused)."""
        return await post_message_action(self, agent, context_type, target)
