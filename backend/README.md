# What-If - WP5 Pilot Platform (Backend)

Backend for the WP5 pilot chatroom simulation. Multiple AI agents interact with a single human participant in real time, with agent behaviour driven by the **STAGE** framework and experimentally controlled treatment conditions.

FastAPI server with REST endpoints for session lifecycle and a WebSocket for real-time chat. 
All session activity is logged for research purposes.

## STAGE Framework

**STAGE** (**S**imulated **T**heater for **A**gent-**G**enerated **E**xperiments) is the multi-agent coordination framework at the core of this platform. It uses a **Director-Performer** architecture to separate strategic reasoning from message generation.

### Director-Performer Architecture

| Component | Model | Role |
|-----------|-------|------|
| **Director** | e.g., Claude Opus 4.5 | Decides which agent acts, selects action type, and provides structured instructions |
| **Performer** | Llama 3.1 8B  | Generates the actual chatroom message from the Director's instructions |

**Why two models?** Fine-tuning the Performer on social media data produces realistic online speech but degrades the general reasoning needed for goal-oriented multi-agent orchestration. By isolating content generation from strategic reasoning, each model can be optimised independently.

### Director Decision Criteria

The Director weighs three criteria when choosing the next action:

1. **Internal validity** -- Is the simulation satisfying the experimental treatment requirements?
2. **Motivational validity** -- Does the selected agent have a plausible reason to act now?
3. **Ecological validity** -- Would the chatroom appear realistic to a human observer?

### Instruction Structure

The Director provides the Performer with structured instructions:

| Element | Description | Example |
|---------|-------------|---------|
| **Objective** | What the agent wants to achieve | "Sam wants to publicly discredit Sally's climate concerns" |
| **Motivation** | Why -- the situational context | "Sam is a committed skeptic; Sally's post challenges views he holds strongly" |
| **Action** | The tactic and communicative approach | "Ridicule her claim; frame her as naive" |

### Action Types

The Director selects one of four action types per turn:

- `message` -- A general post to the chatroom
- `reply` -- A direct reply to a specific prior message
- `@mention` -- A message addressing a specific user
- `like` -- A non-verbal endorsement (no Performer call needed)

### Execution Loop

```
1. Director receives: treatment specification + recent chat log
2. Director outputs: JSON with reasoning, selected agent, action type, target, and Performer instructions
3. Orchestrator: parses Director JSON, assembles Performer prompt with action-type context
4. Performer receives: Director's instructions + chat log + action-type block
5. Performer outputs: single chatroom message
6. Orchestrator: formats message (e.g., prepends @mention), adds to session state, broadcasts via WebSocket
7. Loop repeats on next tick
```

For full prompt specifications, see [director_prompt.md](agents/prompts/director_prompt.md) and [performer_prompt.md](agents/prompts/performer_prompt.md). For a standalone description of the framework, see [framework_overview.md](agents/framework_overview.md).

## Simulation Loop

The simulation uses **tick-based pacing**: a 1-second tick interval combined with a `messages_per_minute` probability gate. On each tick, a random draw determines whether to trigger a Director-Performer turn. This produces variable-rate message pacing.

User messages are folded into the regular loop -- the Director sees them in the chat log on subsequent iterations and decides how (or whether) agents should respond. This may be later tweaked to facilitate more immediate agent responses to user input for the sake of immersion.

## Configuration

### `config/simulation_settings.toml`

Session-level parameters: agent names, message pacing, LLM provider/model settings for both the Director and the Performer, context window size.

### `config/experimental_settings.toml`

Treatment group definitions. Each group defines a `treatment` string that is injected verbatim into the Director prompt. The Director uses this to satisfy the internal validity criterion.

```toml
[groups.civil]
treatment = "All AI agents should adopt civil, polite, and constructive tones..."
```

### `config/participant_tokens.toml`

Single-use login tokens that assign participants to treatment groups. Validated at startup and consumed on session creation.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/session/start` | Start a session (consumes a participant token) |
| `WS` | `/ws/{session_id}` | WebSocket for real-time chat |
| `POST` | `/session/{id}/message/{mid}/like` | Toggle a like on a message |
| `POST` | `/session/{id}/message/{mid}/report` | Report a message (optionally block sender) |
| `GET` | `/health` | Health check |

## Project Structure

```
backend/
├── main.py                          # FastAPI app: REST + WebSocket entrypoint
├── pyproject.toml                   # Dependencies and project metadata
├── agents/
│   ├── agent_manager.py             # Bridges simulation loop to orchestrator
│   ├── orchestrator.py              # Director->Performer pipeline
│   ├── director.py                  # Director prompt builder and response parser
│   ├── performer.py                 # Performer prompt builder
│   ├── framework_overview.md        # STAGE framework description
│   └── prompts/
│       ├── director_prompt.md       # Director prompt template
│       └── performer_prompt.md      # Performer prompt template
├── platforms/
│   └── chatroom.py                  # Simulation session: tick loop, lifecycle, WebSocket wiring
├── models/
│   ├── agent.py                     # Agent dataclass (name)
│   ├── message.py                   # Message dataclass (content, likes, replies, reports)
│   └── session.py                   # SessionState (agents, messages, clock, blocking)
├── utils/
│   ├── config_loader.py             # TOML config loading and validation
│   ├── logger.py                    # Session logging (messages, events, LLM calls)
│   ├── session_manager.py           # Concurrent session management
│   ├── token_manager.py             # Participant token auth and assignment
│   └── llm/
│       ├── llm_manager.py           # LLM client factory (role-aware)
│       ├── llm_anthropic.py         # Anthropic API client (Director)
│       ├── llm_huggingface.py       # HuggingFace Inference client (Performer)
│       └── llm_gemini.py            # Gemini API client (legacy/alternative)
├── config/
│   ├── simulation_settings.toml     # Simulation parameters
│   ├── experimental_settings.toml   # Treatment group definitions
│   └── participant_tokens.toml      # Login tokens -> treatment group mapping
└── logs/                            # Session logs (generated at runtime)
```
