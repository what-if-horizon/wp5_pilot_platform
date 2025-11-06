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
# Add GEMINI_API_KEY to backend/.env
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and use a token in [participant_tokens.toml](./backend/config/participant_tokens.toml) to login. 

## Documentation

- [Backend Documentation](./backend/README.md)
- [Frontend Documentation](./frontend/README.md)
