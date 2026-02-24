# What-If - WP5 Pilot Platform

Platform for integrating AI agents into simulated social media environments to support immersive user studies. A single human participant interacts with multiple AI agents in a chatroom, with agent behaviour driven by experimentally controlled treatment conditions.

**Status**: Under active development for WP5 pilot study by https://github.com/Rptkiddle

## STAGE Framework

The platform is powered by **STAGE** (**S**imulated **T**heater for **A**gent-**G**enerated **E**xperiments), a multi-agent framework that separates agent coordination from message generation duties:

- A **Director** (large general reasoning model) analyses the chatroom state and decides which agent should act, what action to take, and provides structured instructions.
- A **Performer** (smaller instruction fine-tuned model) generates the actual chatroom message from the Director's instructions.
- A **Moderator** (smaller general reasoning model) extracts clean message content from the Performer's raw output, handling cases where smaller Performer models include extraneous commentary or formatting. If extraction fails, the Performer is retried (up to 3 attempts).

This separation allows the Performer to be (instruction) fine-tuned for realistic online speech without compromising the Director's capacity for managing experimental conditions and multi-agent coordination. See the [backend documentation](./backend/README.md) for full details.

## Quick Start

### Backend
```bash
cd backend
pip install -e .
```

Then install the package(s) for the LLM provider(s) you want to use:

| Provider | Install command |
|---|---|
| Anthropic | `pip install anthropic` |
| Gemini | `pip install google-genai` |
| HuggingFace | `pip install huggingface_hub` |
| Mistral | `pip install mistralai` |
| Konstanz (vLLM) | `pip install openai` |
| Local model | `pip install torch transformers` |

Configure your chosen providers in [simulation_settings.toml](./backend/config/simulation_settings.toml), then copy [.env.example](./backend/.env.example) to `backend/.env` and fill in the API keys for the providers you are using.

Setup your experimental conditions in [experimental_settings.toml](./backend/config/experimental_settings.toml). See the file for detailed comments on each setting. Configure participant tokens (linked to treatment groups) in [participant_tokens.toml](./backend/config/participant_tokens.toml).

Setup the simulation settings in [simulation_settings.toml](./backend/config/simulation_settings.toml). See the file for detailed comments on each setting.

```bash
cp .env.example .env   # then edit .env with your keys
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:300x (see reported link when starting front end) and use a token from [participant_tokens.toml](./backend/config/participant_tokens.toml) to log in. Tokens are configured by the researcher and can only be used once. Delete used_tokens.jsonl to reset tokens.

## Project Structure

```
wp5_pilot_platform/
├── backend/          # FastAPI server
├── frontend/         # Next.js chat UI
└── README.md
```

## Documentation

- [Backend Documentation](./backend/README.md) 
- [Frontend Documentation](./frontend/README.md)
