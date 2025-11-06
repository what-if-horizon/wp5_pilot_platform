# Simulacra - Prototype Platform (WP5)

Platform for integrating AI agents into mock social media environments to support immersive user studies.

**Status**: ongoing backend development; +minimal frontend for testing.

## Quick Start

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  
pip install -e .
# Create `backend/.env` and add GEMINI_API_KEY if you plan to use LLM features:
echo 'GEMINI_API_KEY=your_actual_key_here' > .env
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and use a token in [participant_tokens.toml](./backend/config/participant_tokens.toml) to login.

Participant tokens are configured in `backend/config/participant_tokens.toml` and validated server-side. Provide a valid participant token when starting a session (tokens are single-use in the current prototype implementation).

## Documentation

- [Backend Documentation](./backend/README.md)
- [Frontend Documentation](./frontend/README.md)
