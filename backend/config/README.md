participant_tokens.json
=======================

Purpose
-------
This file maps experimental treatment groups to researcher-provided login tokens.

Schema (group -> list-of-tokens)
--------------------------------
File: `backend/config/participant_tokens.json`

{
  "groups": {
    "Tx1": ["token-a", "token-b"],
    "Tx2": ["token-c"]
  }
}

Notes
-----
- We use the group -> tokens layout because it's easier for researchers to see which tokens belong to which group.
- Tokens are single-use: when a token is used to start a session it will be logged to `logs/used_tokens.jsonl` and subsequent attempts to use it will be rejected.
- Tokens do not need to be secret for this prototype; they are identifiers. But treat them as study materials and avoid committing real participant identifiers.

Operational behaviour
---------------------
- On backend startup we validate that every group defined in `participant_tokens.json` exists in `backend/config/experimental_settings.json`.
- When `POST /session/start` is called with a token, the token is matched to its group (if unused). If valid, a session id is returned and the token is logged in `logs/used_tokens.jsonl`.
- The frontend should then connect to `WS /ws/{session_id}`. The server will instantiate the session with the selected treatment group's experimental settings.

Token rotation / reuse
----------------------
- Single-use enforcement is implemented by logging used tokens. If you want strict atomicity or multi-process safety, consider moving token state into a small database.
