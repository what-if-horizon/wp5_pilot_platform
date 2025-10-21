import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid

from simulation import SimulationSession


app = FastAPI(title="WP5 Chatroom Backend")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global session storage (for MVP: single session at a time)
active_session: Optional[SimulationSession] = None
active_websocket: Optional[WebSocket] = None


class SessionStartRequest(BaseModel):
    """Request model for starting a session."""
    token: str


class SessionStartResponse(BaseModel):
    """Response model for session start."""
    session_id: str
    message: str


@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest):
    """
    Start a new simulation session.
    
    Requires authentication token (currently hardcoded as '1234').
    """
    global active_session
    
    # Check token
    if request.token != "1234":
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Check if session already active
    if active_session and active_session.running:
        raise HTTPException(status_code=409, detail="Session already active")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    return SessionStartResponse(
        session_id=session_id,
        message="Session created. Connect via WebSocket to start."
    )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time chat communication.
    
    Handles:
    - Receiving user messages
    - Sending agent messages
    - Session lifecycle
    """
    global active_session, active_websocket
    
    await websocket.accept()
    active_websocket = websocket
    
    # Create and start simulation session
    async def send_to_frontend(message_dict: dict):
        """Helper to send messages to frontend via WebSocket."""
        if active_websocket:
            await active_websocket.send_json(message_dict)
    
    active_session = SimulationSession(session_id=session_id, websocket_send=send_to_frontend)
    await active_session.start()
    
    try:
        while True:
            # Receive message from frontend
            data = await websocket.receive_json()
            
            # Expected format: {"type": "user_message", "content": "..."}
            if data.get("type") == "user_message":
                content = data.get("content", "").strip()
                if content:
                    await active_session.handle_user_message(content)
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")
        if active_session:
            await active_session.stop(reason="websocket_disconnect")
        active_session = None
        active_websocket = None
    
    except Exception as e:
        print(f"WebSocket error: {e}")
        if active_session:
            await active_session.stop(reason="error")
        active_session = None
        active_websocket = None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "message": "WP5 Chatroom Backend",
        "version": "0.1.0",
        "endpoints": {
            "POST /session/start": "Start a new session",
            "WS /ws/{session_id}": "WebSocket for chat communication",
            "GET /health": "Health check"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)