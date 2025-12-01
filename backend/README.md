# Simulacra - Prototype Platform (WP5)

Platform for integrating AI agents into mock social media environments to support immersive user studies.

NOTE: Currently under development for WP5 pilot study and subject to significant changes.

## Overview

Backend for a prototype chatroom simulation where multiple AI agents interact with single human user in a session. Separation of experimental and simulation parameters via configuration files. Real-time message updates via WebSocket. Logging of all session activity as source documentation. Currently uses Google Gemini API for LLM responses.

## Project Structure

```
backend/
├── main.py                          # FastAPI app w/ REST + WebSocket (entrypoint)
├── pyproject.toml                   # Project metadata & dependencies
├── README.md                        # (you are here)
├── models/
│   ├── __init__.py
│   ├── agent.py                     # Agent dataclass
│   ├── message.py                   # Message dataclass
│   └── session.py                   # Session dataclass / state
├── simulation/
│   ├── __init__.py
│   └── chatroom.py                  # Chatroom simulation logic
├── utils/
│   ├── __init__.py
│   ├── config_loader.py             # small helpers to load TOML configs
│   ├── llm/llm_gemini.py            # Gemini API client wrapper
│   ├── llm/llm_manager.py           # LLM call orchestration / retries
│   ├── logger.py                    # JSON logging helpers
│   ├── session_manager.py           # manage concurrent sessions
│   └── token_manager.py             # token consumption / locking logic
├── config/
│   ├── experimental_settings.toml   # experimental parameters
│   ├── participant_tokens.toml      # participant tokens (single-use)
│   └── simulation_settings.toml     # simulation parameters
├── logs/                            # session logs & used_tokens.jsonl
```

## Setup

### Prerequisites
- Python 3.12+
- Google Gemini API key

### Installation

1. Clone the repository and navigate to the backend directory:
```bash
cd backend
```

2. Create and activate a virtual environment, install dependencies:
```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

3. Create a `.env` file in the backend directory with your Gemini API key:
   - If you are using LLM features, create a file named `.env` in the `backend/` directory and add your key:
```
GEMINI_API_KEY=your_actual_key_here
```
- There is no `.env.example` in this prototype; create the file manually as shown above.
```
GEMINI_API_KEY=your_actual_key_here
```

## Configuration Files

### `config/experimental_settings.toml`

Defines experimental treatment groups. Each treatment is a `[groups.<name>]` table and should include a `prompt_template` used for agents in that treatment (more conditions to be added).

Note: `backend/config/participant_tokens.toml` maps single-use tokens to treatments; when a token is consumed at session start the backend assigns the matching treatment for that user session.


### `config/simulation_settings.toml`

Controls simulation parameters. These affect how the chatroom feels (immersion).

**Parameters:**
- `num_agents` (integer): Number of AI agents in the chatroom. Must match the length of `agent_names`.
- `agent_names` (array of strings): Names assigned to each agent. Agents are self-aware of their own name.
- `messages_per_minute` (number): Global activity rate across all agents. Higher values = more active chatroom. Messages are posted probabilistically based on this rate.
- `user_response_probability` (number, 0-1): Probability that any agent will respond when the user posts a message. 0.7 = 70% chance.
- `context_window_size` (integer): Number of recent messages included in agent prompts. Agents see the last N messages when generating responses.
- `session_duration_minutes` (integer): How long the session runs before automatically ending.
- `llm_concurrency_limit` (integer): Maximum number of concurrent LLM requests per session (must be a positive integer > 0).


## Running the Backend


### Starting the Server

From the backend directory, run:

```bash
python main.py
```

Or with uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
e.g., the server will start on `http://localhost:8000`



## Session Flow

1. User enters a participant token (from the study tokens) in the frontend
2. Frontend calls `POST /session/start` with token
3. Backend validates token and returns `session_id`
4. Frontend opens WebSocket connection to `/ws/{session_id}`
5. Backend creates SimulationSession and starts the clock
6. Simulation runs:
   - Clock ticks every second
   - Agents post messages probabilistically based on `messages_per_minute`
   - When user posts, agents may respond based on `user_response_probability`
7. Session ends when:
  - Duration expires (configured in `simulation_settings.toml`)
   - WebSocket disconnects
   - Error occurs


## Participant Tokens
Authentication is token-based using single-use participant tokens defined in `backend/config/participant_tokens.toml`.

When a client calls `POST /session/start` it must include a participant token in the request body. The backend will validate and consume the token (single-use) and return a `session_id` if the token is valid. For multi-replica deployments, replace the file-backed token store with a centralized atomic store (Redis/DB) to enforce single-use across replicas.

- Tokens configured in `backend/config/participant_tokens.toml` are consumed (marked used) when a session is created. The current implementation enforces single-use tokens within a single server process by appending entries to `backend/logs/used_tokens.jsonl` and using an in-process lock during consumption.

### Multi-session behavior
- The backend supports multiple concurrent sessions. Each session represents an independent chatroom simulation with exactly one human participant connected via WebSocket. Sessions are managed by an in-memory `SessionManager` and run as asyncio background tasks so they can progress concurrently.
- Start a session by calling `POST /session/start` with a valid participant token. The endpoint returns a `session_id`. Then open a WebSocket to `/ws/{session_id}`.
- Sessions log all activity to `backend/logs/{session_id}.json` (JSON Lines). Each log entry includes `session_id` at the top level to make filtering easier.


### API Endpoints

**REST Endpoints:**
- `GET /` - API information and available endpoints
- `GET /health` - Health check
- `POST /session/start` - Start a new session (requires token in request body)

**WebSocket:**
- `WS /ws/{session_id}` - Connect to a simulation session for real-time chat



### Logging 
- Session logs: `backend/logs/{session_id}.json` (JSON Lines). Events include `session_start`, `message`, `llm_call`, `session_end`, and `error`. Each event includes a `session_id` field.



