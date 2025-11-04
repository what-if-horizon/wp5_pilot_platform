# WP5 Prototype Backend

Backend for running user experiments in a simulated WhatsApp community chatroom.

NOTE: Currently under development for WP5 pilot study and subject to significant changes.

## Overview

Backend for a chatroom simulation where multiple AI agents interact with single human user in a session. Separation of experimental and simulation parameters via configuration files. Real-time message updates via WebSocket. Logging of all session activity as source documentation. Currently uses Google Gemini API for LLM responses.

## Project Structure

```
backend/
├── main.py                          # FastAPI app, WebSocket, REST endpoints
├── models/                          # Data models
│   ├── __init__.py
│   ├── message.py                   # Message dataclass
│   ├── agent.py                     # Agent dataclass 
│   └── session.py             # SessionState dataclass 
├── simulation/                      # Core simulation logic
│   ├── __init__.py
│   └── chatroom.py                   # SimulationSession class 
├── utils/                           # Utility functions
│   ├── __init__.py
│   ├── llm_gemini.py               # Gemini API client
│   └── logger.py                   # JSON logging
├── config/                          # Configuration files
│   ├── experimental_settings.json
│   └── simulation_settings.json
├── logs/                            # Session logs (auto-generated)
├── .env                             # API keys (not in git)
├── .gitignore
├── pyproject.toml                   # Dependencies
└── README.md                        # This file
```

## Setup

### Prerequisites

- Python 3.12 or higher
- Google Gemini API key

### Installation

1. Clone the repository and navigate to the backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -e .
```

3. Create a `.env` file in the backend directory with your Gemini API key:
```
GEMINI_API_KEY=your_api_key_here
```

## Configuration Files

### `config/experimental_settings.json`

Controls experimental conditions. 

TODO: implement treatment group conditions here, to be associated with (a portion of) user login tokens.

**Parameters:**
- `prompt_template` (string): The system prompt given to all agents.  

**Example:**
```json
{
  "prompt_template": "You are a member of a WhatsApp community group discussing everyday topics. Respond naturally and briefly to the conversation. Keep messages short and casual, like real WhatsApp messages."
}
```

### `config/simulation_settings.json`

Controls simulation parameters. These affect how the chatroom feels but are not considered experimental variables.

**Parameters:**
- `num_agents` (integer): Number of AI agents in the chatroom. Must match the length of `agent_names`.
- `agent_names` (array of strings): Names assigned to each agent. Agents are self-aware of their own name.
- `messages_per_minute` (number): Global activity rate across all agents. Higher values = more active chatroom. Messages are posted probabilistically based on this rate.
- `user_response_probability` (number, 0-1): Probability that an agent will respond when the user posts a message. 0.7 = 70% chance.
- `context_window_size` (integer): Number of recent messages included in agent prompts. Agents see the last N messages when generating responses.
- `session_duration_minutes` (integer): How long the session runs before automatically ending.

**Example:**
```json
{
  "num_agents": 5,
  "agent_names": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
  "messages_per_minute": 6,
  "user_response_probability": 0.7,
  "context_window_size": 10,
  "session_duration_minutes": 15
}
```

## Running the Backend

### First-time Setup

1. **Install dependencies:**
```bash
pip install -e .
```

2. **Set up your API key:**
   - Copy `.env.example` to `.env`
   - Get a Gemini API key from https://aistudio.google.com/app/apikey
   - Add your key to `.env`:
   ```
   GEMINI_API_KEY=your_actual_key_here
   ```

### Starting the Server

From the backend directory, run:

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000`

### API Endpoints

**REST Endpoints:**
- `GET /` - API information and available endpoints
- `GET /health` - Health check
- `POST /session/start` - Start a new session (requires token in request body)

**WebSocket:**
- `WS /ws/{session_id}` - Connect to a simulation session for real-time chat


## Logging

All session activity is logged to `logs/{session_id}.json` in JSON Lines format (one JSON object per line).

**Log event types:**
- `session_start` - Session initialization with config snapshots
- `session_end` - Session termination with reason
- `message` - All chat messages (user and agents)
- `llm_call` - LLM API calls with prompts, responses, and errors
- `error` - System errors with context

**Example log entries:**
```json
{"timestamp": "2025-10-21T14:30:00.123456", "event_type": "session_start", "data": {...}}
{"timestamp": "2025-10-21T14:30:15.234567", "event_type": "message", "data": {"sender": "user", "content": "Hello!", ...}}
{"timestamp": "2025-10-21T14:30:20.345678", "event_type": "llm_call", "data": {"agent_name": "Alice", ...}}
```

## Message Format

**Frontend → Backend (via WebSocket):**
```json
{
  "type": "user_message",
  "content": "Hello everyone!"
}
```

**Backend → Frontend (via WebSocket):**
```json
{
  "sender": "Alice",
  "content": "Hi there!",
  "timestamp": "2025-10-21T14:30:20.123456",
  "message_id": "uuid-here"
}
```

## Session Flow

1. User enters token "1234" in frontend
2. Frontend calls `POST /session/start` with token
3. Backend validates token and returns `session_id`
4. Frontend opens WebSocket connection to `/ws/{session_id}`
5. Backend creates SimulationSession and starts the clock
6. Simulation runs:
   - Clock ticks every second
   - Agents post messages probabilistically based on `messages_per_minute`
   - When user posts, agents may respond based on `user_response_probability`
7. Session ends when:
   - Duration expires (configured in `simulation_settings.json`)
   - WebSocket disconnects
   - Error occurs


## Authentication

For the minimal prototype, authentication uses a hardcoded token: `1234`

Users must provide this token when starting a session via `POST /session/start`. The endpoint will return a `session_id` if the token is valid.

**TODO** Token-based authentication with [UID]+[treatment group] mapping for experiments. 


