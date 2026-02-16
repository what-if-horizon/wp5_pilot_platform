# What-If - WP5 Pilot Platform

Platform for integrating AI agents into simulated social media environments to support immersive user studies. A single human participant interacts with multiple AI agents in a chatroom, with agent behaviour driven by experimentally controlled treatment conditions.

**Status**: Under active development for WP5 pilot study by https://github.com/Rptkiddle

## STAGE Framework

The platform is powered by **STAGE** (**S**imulated **T**heater for **A**gent-**G**enerated **E**xperiments), a multi-agent coordination framework that separates agent coordination from message generation duties:

- A **Director** (general reasoning model) analyses the chatroom state and decides which agent should act, what action to take, and provides structured instructions.
- A **Performer** (instruction fine-tuned model) generates the actual chatroom message from the Director's instructions

This separation allows the Performer to be fine-tuned for realistic online speech without compromising the Director's capacity for managing experimental conditions and multi-agent coordination. See the [backend documentation](./backend/README.md) for full details.

## Quick Start

### Backend
```bash
cd backend
pip install -e .
# Create backend/.env with API keys (see .env.example):
echo 'ANTHROPIC_API_KEY=your_key_here' > .env
echo 'HF_API_KEY=your_key_here' >> .env
echo 'GEMINI_API_KEY=your_key_here' >> .env
python main.py
```
Which keys you need depends on the providers configured in [simulation_settings.toml](./backend/config/simulation_settings.toml). The defaults use Anthropic (Director) and HuggingFace (Performer). Gemini is available as an alternative provider.

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
├── backend/          # FastAPI server, STAGE framework, simulation logic
├── frontend/         # Next.js chat UI
├── logs/             # Session logs (generated at runtime)
└── README.md
```

## Documentation

- [Backend Documentation](./backend/README.md) 
- [Frontend Documentation](./frontend/README.md)
