import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import uuid
import json
from pathlib import Path

# Import simulation session business logic
from simulation import SimulationSession

# Participant tokens helper
from utils import participant_tokens

# FastAPI app initialization
app = FastAPI(title="WP5 Chatroom Backend")

# CORS middleware for (safe) frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Next.js local dev; change later...
    allow_credentials=False, # We do NOT yet need cookies (maybe later...)
    allow_methods=["GET", "POST", "OPTIONS"], # Permitted HTTP methods...
    allow_headers=["Authorization", "Content-Type"], # Permitted HTTP headers...
)

# Global session storage (MVP: single session at a time)
active_session: Optional[SimulationSession] = None
active_websocket: Optional[WebSocket] = None

# Pending sessions created via POST /session/start but waiting for websocket connection.
# Maps session_id -> dict with keys like 'treatment_group'
pending_sessions: Dict[str, Dict] = {}


# Startup validation: ensure participant tokens reference existing experimental groups
try:
    exp_path = Path(__file__).resolve().parent / "config" / "experimental_settings.json"
    with open(exp_path, "r") as f:
        experimental_settings = json.load(f)
    participant_tokens.validate_against_experiments(experimental_settings)
    print("Participant tokens validated against experimental settings.")
except Exception as e:
    print(f"Startup validation error: {e}")
    raise


#NOTE: Pydantic for validation at HTTP boundary (later: websockets also???)
class SessionStartRequest(BaseModel):
    """Request model for starting a session."""
    token: str #expects '1234'; later: [UID + Tx] token. 

class SessionStartResponse(BaseModel):
    """Response model for session start."""
    session_id: str #from uuid 
    message: str #confirmation message


#ENDPOINT 1 for starting a new session - 
@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest):
    """
    Start a new simulation session.
    
    Requires authentication token (currently hardcoded as '1234').
    """
    global active_session
    
    # Validate and consume participant token (single-use)
    group = participant_tokens.find_group_for_token(request.token)
    if not group:
        # Either invalid or already used
        raise HTTPException(status_code=401, detail="Invalid or already-used token")

    # Check if session already active
    if active_session and active_session.running:
        raise HTTPException(status_code=409, detail="Session already active")

    # Generate session ID and reserve pending session with treatment group
    session_id = str(uuid.uuid4())
    pending_sessions[session_id] = {"treatment_group": group}

    # Mark token as used (logged to logs/used_tokens.jsonl)
    participant_tokens.mark_token_used(request.token, session_id, group)

    # Return session id and confirmation message
    return SessionStartResponse(
        session_id=session_id,
        message=f"Session created with treatment group {group}. Connect via WebSocket to start."
    )


#ENDPOINT 2 for websocket connection - chat communication
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
    # Check for pending session info (treatment group) saved at /session/start
    pending = pending_sessions.pop(session_id, {})
    treatment_group = pending.get("treatment_group")

    active_session = SimulationSession(session_id=session_id, websocket_send=send_to_frontend, treatment_group=treatment_group)
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
        

#ENDPOINT 3: Health check (used by )
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


#ROOT ENDPOINT: API docstring
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

# Run with: uvicorn backend.main:app --reload on port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)