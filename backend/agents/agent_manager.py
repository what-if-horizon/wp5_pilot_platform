import asyncio
from typing import Callable, Optional
from datetime import datetime

from models import Message
from agents.STAGE.orchestrator import Orchestrator, TurnResult


class AgentManager:
    """Bridges the simulation loop and the STAGE framework orchestrator.

    Responsibilities:
    - hold references to state, logger, websocket, and orchestrator
    - execute a Director->Performer turn via the orchestrator
    - handle the result (persist message, broadcast via websocket, handle likes)
    - apply typing delay for realism
    """

    def __init__(
        self,
        state,
        orchestrator: Orchestrator,
        logger,
        websocket_send: Optional[Callable] = None,
        typing_delay_seconds: float = 1.0,
    ) -> None:
        self.state = state
        self.orchestrator = orchestrator
        self.logger = logger
        self.websocket_send = websocket_send or (lambda *_: None)
        self.typing_delay_seconds = typing_delay_seconds

    def set_websocket_send(self, websocket_send: Optional[Callable]) -> None:
        self.websocket_send = websocket_send or (lambda *_: None)

    async def execute_turn(self, treatment: str) -> Optional[TurnResult]:
        """Run one Director->Performer turn and handle the result.

        Returns the TurnResult on success, or None on failure.
        """
        result = await self.orchestrator.execute_turn(treatment)
        if result is None:
            return None

        if result.action_type == "like":
            await self._handle_like(result)
        else:
            await self._handle_message(result)

        return result

    async def _handle_message(self, result: TurnResult) -> None:
        """Persist and broadcast a generated message."""
        message = result.message
        if not message:
            return

        # Apply a configurable typing delay
        if self.typing_delay_seconds > 0:
            await asyncio.sleep(self.typing_delay_seconds)

        # Persist to session state
        try:
            self.state.add_message(message)
        except Exception:
            pass

        # Log the message
        try:
            self.logger.log_message(message.to_dict())
        except Exception:
            pass

        # Send to frontend via websocket
        try:
            await self.websocket_send(message.to_dict())
        except Exception as e:
            try:
                self.logger.log_error("send", str(e))
            except Exception:
                pass

    async def _handle_like(self, result: TurnResult) -> None:
        """Process a 'like' action from the Director."""
        target_id = result.target_message_id
        agent_name = result.agent_name
        if not target_id:
            return

        # Find the target message and toggle like
        target_msg = next(
            (m for m in self.state.messages if m.message_id == target_id),
            None,
        )
        if not target_msg:
            self.logger.log_error("like_action", f"Target message {target_id} not found")
            return

        target_msg.toggle_like(agent_name)

        # Log the like event
        try:
            self.logger.log_event("agent_like", {
                "agent_name": agent_name,
                "message_id": target_id,
                "likes_count": target_msg.likes_count,
            })
        except Exception:
            pass

        # Broadcast the like event to websocket
        try:
            await self.websocket_send({
                "event_type": "message_like",
                "message_id": target_id,
                "action": "liked",
                "likes_count": target_msg.likes_count,
                "liked_by": list(target_msg.liked_by),
                "user": agent_name,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            try:
                self.logger.log_error("send_like", str(e))
            except Exception:
                pass
