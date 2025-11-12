import asyncio
from typing import Dict, Optional

from platforms import SimulationSession


class SessionManager:
    """Singleton manager for simulation sessions.

    Provides async-safe create/get/remove operations and pending reservation support.
    """

    _instance = None

    def __init__(self):
        self._sessions: Dict[str, SimulationSession] = {}
        self._pending: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> "SessionManager":
        if cls._instance is None:
            cls._instance = SessionManager()
        return cls._instance

    async def reserve_pending(self, session_id: str, info: Dict) -> None:
        async with self._lock:
            self._pending[session_id] = info

    async def pop_pending(self, session_id: str) -> Dict:
        async with self._lock:
            return self._pending.pop(session_id, {})

    async def create_session(self, session_id: str, websocket_send, treatment_group: str) -> SimulationSession:
        """Create and start a SimulationSession if not present; return the session.

        `treatment_group` is required — sessions must always be created with a treatment.
        """
        async with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            session = SimulationSession(session_id=session_id, websocket_send=websocket_send, treatment_group=treatment_group)
            self._sessions[session_id] = session

        # start outside the lock since it may await
        await session.start()
        return session

    async def get_session(self, session_id: str) -> Optional[SimulationSession]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def attach_or_create(self, session_id: str, websocket_send, treatment_group: Optional[str] = None) -> SimulationSession:
        """Attach websocket to existing session or create/start a new one."""
        session = await self.get_session(session_id)
        if session:
            await session.attach_websocket(websocket_send)
            return session
        # create and start
        # Pass through treatment_group (required by create_session)
        if treatment_group is None:
            raise RuntimeError("attach_or_create requires a treatment_group when creating a new session")
        return await self.create_session(session_id, websocket_send, treatment_group=treatment_group)

    async def detach_websocket(self, session_id: str) -> None:
        session = await self.get_session(session_id)
        if session:
            session.detach_websocket()

    async def remove_session(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            await session.stop(reason="removed")

    async def list_sessions(self) -> Dict[str, SimulationSession]:
        async with self._lock:
            return dict(self._sessions)


session_manager = SessionManager.get()
