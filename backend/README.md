# Simulacra - Prototype Platform (WP5)

Platform for integrating AI agents into mock social media environments to support immersive user studies.

NOTE: Currently under development for WP5 pilot study and subject to significant changes.

## Overview

Backend for a prototype chatroom simulation where multiple AI agents interact with single human user in a session. Separation of experimental and simulation parameters via configuration files. Real-time message updates via WebSocket. Logging of all session activity as source documentation. Currently uses Google Gemini API for LLM responses.

## Quickstart
see main project [README.md](./README.md) for setup instructions. 

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
│   └── session.py                   # Session dataclass 
├── agents/
│   ├── __init__.py
│   ├── agent_manager.py             # Manages agents within a session
│   └── actions/        
│       ├── __init__.py
│       └── post_message.py          # Allows agents to post messages
├── platforms/
│   ├── __init__.py
│   └── chatroom.py                  # Chatroom simulation logic (WhatsApp)
├── utils/
│   ├── __init__.py
│   ├── config_loader.py             # helper for validating TOML config files
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── llm_gemini.py            # Gemini LLM interface
│   │   └── llm_manager.py           # Manages LLM interactions via API
│   ├── logger.py                    # Logging utility (universal)
│   ├── session_manager.py           # Manages user-sessions (concurrent)
│   └── token_manager.py             # Manages user tokens (auth/assignment)
├── config/
│   ├── experimental_settings.toml   # experimental configuration
│   ├── participant_tokens.toml      # (participant tokens) 
│   └── simulation_settings.toml     # simulation configuration
├── logs/                            # session logs & used_tokens.jsonl

