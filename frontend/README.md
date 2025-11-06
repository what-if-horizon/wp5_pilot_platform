# Simulacra — Prototype Frontend (WP5)

NOTE: this is a small prototype frontend intended for local development and testing of the WP5 backend.

## Overview

A simple chat interface that allows users to:
1. Enter an authentication token (provided by study coordinators / configured in the backend)
2. Connect to a chatroom simulation with AI agents
3. Send messages and see agent responses in real-time

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx           # Root layout with metadata
│   └── page.tsx             # Main chat interface
├── package.json             # Dependencies and scripts
├── next.config.js           # Next.js configuration
├── tsconfig.json            # TypeScript configuration
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## Prerequisites

- Node.js 18+ (or latest LTS version)
- Backend server running on `http://localhost:8000` (default for local dev)

## Setup

### Installation

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

## Running the Frontend

### Development Mode

Start the development server:

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Production Build

Build for production:

```bash
npm run build
npm start
```

## Usage

1. **Start the backend server** (must be running on port 8000)
2. **Open browser** to `http://localhost:3000`
3. **Enter token:** Type a valid participant token (provided by study coordinators) and click "Start Session"
4. **Chat:** Type messages in the input box and click "Post" (or press Enter)
5. **Watch:** AI agents will respond based on the backend configuration



## Configuration

### Backend URL

By default the frontend connects to the local backend endpoints:
- REST API: `http://localhost:8000`
- WebSocket: `ws://localhost:8000`

To change these (for deployment or a remote backend), edit the network URLs in `app/page.tsx` (search for `session/start` and `ws://`). For production use consider using `https://` and `wss://` and setting the URL via an environment variable or runtime config.


## Features

### Token Entry Screen
- Simple authentication using single-use participant tokens validated by the backend (see `backend/config/participant_tokens.toml`)
- Calls backend `/session/start` endpoint
- Receives session_id for WebSocket connection

### Chat Interface
- **Header:** Displays connection status (🟢 Connected / 🔴 Disconnected)
- **Message Feed:** Scrolling list of messages with auto-scroll to bottom
- **Input Area:** Text input with "Post" button
- **Visual distinction:** User messages (blue) vs agent messages (gray)

### WebSocket Communication
- Connects to `ws://localhost:8000/ws/{session_id}` by default
- Sends user messages: `{"type": "user_message", "content": "..."}`
- Receives agent messages: `{"sender": "Alice", "content": "...", "timestamp": "...", "message_id": "..."}`
- Auto-reconnection is not implemented; refresh the page to reconnect.



