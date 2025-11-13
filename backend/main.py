import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict
import uuid
import json

#check that tomllib is available (for parsing configs)
try:
    import tomllib  # Python 3.11+ stdlib   
except Exception:
    raise RuntimeError("TOML support required (Python 3.11+). Please run with Python >=3.11")
from pathlib import Path

# Import simulation logic (i.e., platform)
#NOTE: for pilot we only have one simulation type (chatroom)
from platforms import SimulationSession
# Import concurrent session manager: 
from utils.session_manager import session_manager
# Import login token manager and llm client
from utils import token_manager, gemini_client


# Initialize FastAPI app - 
app = FastAPI(title="Simulcra: Prototype Backend")

# CORS middleware for safe cross-origin requests)
# NOTE: minimal settings for local dev (change later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Next.js local dev; change later...
    allow_credentials=False, # We do NOT yet need cookies (maybe later...)
    allow_methods=["GET", "POST", "OPTIONS"], # Permitted HTTP methods...
    allow_headers=["Authorization", "Content-Type"], # Permitted HTTP headers...
)

# Set sentinel state for websocket: 
active_websocket: Optional[WebSocket] = None


# Startup validation: check that participant tokens reference existing experimental groups
#NOTE: researcher pre-configures these in /config/experimental_settings.toml and /config/participant_tokens.toml
try:
    base = Path(__file__).resolve().parent
    exp_toml = base / "config" / "experimental_settings.toml"

    if not exp_toml.exists():
        raise FileNotFoundError("No experimental_settings.toml found in backend/config; please create one.")

    # tomllib requires binary mode
    with open(exp_toml, "rb") as f:
        experimental_settings = tomllib.load(f)

    token_manager.validate_against_experiments(experimental_settings)
    print("Participant tokens validated against experimental settings.")
except Exception as e:
    print(f"Startup validation error: {e}")
    raise


# Pydantic for validation at HTTP boundary
#NOTE: this guards against malformed requests/responses
class SessionStartRequest(BaseModel):
    """Request model for starting a session."""
    token: str  # single-use participant token (validated against config/participant_tokens.toml)

class SessionStartResponse(BaseModel):
    """Response model for session start."""
    session_id: str #from uuid 
    message: str #confirmation message (e.g. treatment group info)


class LikeRequest(BaseModel):
    """Request model for liking/unliking a message.

    Prototype uses a simple toggle-only API. Clients submit their user id
    and the server will flip their like state for the message.
    """
    user: str


class ReportRequest(BaseModel):
    """Request model for reporting a message.

    user: reporter id (prototype uses the client token/display name)
    block: whether to also block the sender (default: False)
    reason: optional free-text reason
    """
    user: str
    block: Optional[bool] = False
    reason: Optional[str] = None


#ENDPOINT 1 for starting a new session - 
#NOTE: at this point we begin asynchronous session management (multiple user-sessions)
@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest):
    """
    Start a new simulation session.
    
    Requires a valid single-use participant token. Tokens are validated and
    consumed using `utils.token_manager` against `backend/config/participant_tokens.toml`.
    """
    global active_session
    
    # Generate session ID up-front and atomically consume the participant token
    # using the same session_id so logs reference the same session identifier.
    session_id = str(uuid.uuid4())
    group = token_manager.consume_token(request.token, session_id=session_id)
    if not group:
        # Either invalid or already used
        raise HTTPException(status_code=401, detail="Invalid or already-used token")

    # Reserve pending session with treatment group
    await session_manager.reserve_pending(session_id, {"treatment_group": group})

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

    # Create a send helper which uses the currently-accepted websocket
    async def send_to_frontend(message_dict: dict):
        """Helper to send messages to frontend via WebSocket."""
        if active_websocket:
            await active_websocket.send_json(message_dict)

    # First, check if a session already exists for this session_id (reconnect case)
    session = await session_manager.get_session(session_id)
    if session:
        # Attach websocket to existing session and continue
        await session.attach_websocket(send_to_frontend)
        active_session = session
    else:
        # No existing session: check for pending session info (treatment group) saved at /session/start
        pending = await session_manager.pop_pending(session_id)
        treatment_group = pending.get("treatment_group")

        # A treatment_group MUST be present for creating a new session (sessions are experimental and require assignment).
        if not treatment_group:
            # Close the websocket with policy violation and stop.
            await websocket.close(code=1008)
            print(f"WebSocket connection for session {session_id} rejected: missing treatment_group")
            return

        # Create and start a new session with the reserved treatment_group
        session = await session_manager.create_session(session_id, send_to_frontend, treatment_group=treatment_group)
        active_session = session
    
    try:
        while True:
            # Receive message from frontend
            data = await websocket.receive_json()

            # Expected format: {"type": "user_message", "content": "..."}
            if data.get("type") == "user_message":
                content = data.get("content", "").strip()
                # Optional reply metadata sent from frontend
                reply_to = data.get("reply_to")
                quoted_text = data.get("quoted_text")
                mentions = data.get("mentions")
                if content:
                    await session.handle_user_message(content, reply_to=reply_to, quoted_text=quoted_text, mentions=mentions)

    # Handle clean disconnects
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")
        # Detach websocket but keep session running so client can reconnect
        if session:
            session.detach_websocket()
        active_websocket = None
    
    # Handle unexpected errors
    except Exception as e:
        print(f"WebSocket error: {e}")
        # On unexpected errors, detach websocket and leave session to be inspected
        if session:
            session.detach_websocket()
        active_websocket = None
        

#ENDPOINT 3: Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/session/{session_id}/message/{message_id}/like")
async def like_message(session_id: str, message_id: str, payload: LikeRequest):
    """Toggle/add/remove a like for a message in a session.

    Payload contains a `user` identifier (simple prototype value, e.g. 'user')
    and an `action` which may be 'toggle' (default), 'like' or 'unlike'.
    The endpoint returns the updated message representation and broadcasts
    a `message_like` event over the session websocket so other clients can
    update in real time.
    """
    # Locate session
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Find message in session state
    message = None
    for m in session.state.messages:
        if m.message_id == message_id:
            message = m
            break

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Toggle-only API (simpler prototype contract)
    user_id = payload.user
    result = message.toggle_like(user_id)  # returns 'liked' or 'unliked'

    # Log the like event
    try:
        session.logger.log_event("message_like", {
            "message_id": message_id,
            "user": user_id,
            "action": result,
            "likes_count": message.likes_count,
        })
    except Exception:
        # logging failures shouldn't block the API
        pass

    # Broadcast to connected websocket (best-effort)
    event = {
        "event_type": "message_like",
        "session_id": session_id,
        "message_id": message_id,
        "action": result,
        "likes_count": message.likes_count,
        "liked_by": list(message.liked_by),
        "user": user_id,
        "timestamp": datetime.now().isoformat(),
    }
    try:
        await session.websocket_send(event)
    except Exception:
        # If broadcasting fails, continue — clients will reconcile on subsequent state
        pass

    return {"message": message.to_dict()}


@app.post("/session/{session_id}/message/{message_id}/report")
async def report_message(session_id: str, message_id: str, payload: ReportRequest):
    """Report a message and optionally block the sender for this session's user.

    Because sessions are single-user, we represent reports as a boolean flag on
    the message and store blocked agent names in the session state.
    """
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Find message
    message = None
    for m in session.state.messages:
        if m.message_id == message_id:
            message = m
            break

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    user_id = payload.user
    block = bool(payload.block)

    # Toggle reported flag on the message
    result = message.toggle_report()  # 'reported' or 'unreported'

    # If requested, block the sender (agent) for this session
    blocked = None
    target_sender = message.sender
    if block and target_sender:
        # Only block agent senders (skip blocking if the sender is the human)
        if target_sender != "user":
            when_iso = datetime.now().isoformat()
            session.state.block_agent(target_sender, when_iso)
            # Return the mapping of blocked agents -> ISO time so clients can apply
            # selective suppression of future messages.
            blocked = dict(session.state.blocked_agents)

    # Log the report event
    try:
        session.logger.log_event("message_report", {
            "message_id": message_id,
            "user": user_id,
            "action": result,
            "blocked": blocked,
            "reason": payload.reason,
        })
    except Exception:
        pass

    # Broadcast report and block events to the websocket (best-effort)
    try:
        await session.websocket_send({
            "event_type": "message_report",
            "session_id": session_id,
            "message_id": message_id,
            "action": result,
            "user": user_id,
            "reported": message.reported,
            "timestamp": datetime.now().isoformat(),
        })
        if blocked is not None:
            await session.websocket_send({
                "event_type": "user_block",
                "session_id": session_id,
                "user": user_id,
                "blocked": blocked,
                "timestamp": datetime.now().isoformat(),
            })
    except Exception:
        pass

    return {"message": message.to_dict(), "blocked": blocked}


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

# Cleanup on shutdown (.on_event depricated; fix needed later)
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown (close async LLM client)."""
    try:
        await gemini_client.aclose()
    except Exception as e:
        print(f"Error closing gemini client: {e}")