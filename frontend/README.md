# WP5 Prototype Frontend

NOTE: this is a THROWAWAY frontend for developing the WP5 prototype backend. 

## Overview

A simple chat interface that allows users to:
1. Enter an authentication token (currently hardcoded as "1234")
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
- Backend server running on `http://localhost:8000`

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
3. **Enter token:** Type "1234" and click "Start Session"
4. **Chat:** Type messages in the input box and click "Post" (or press Enter)
5. **Watch:** AI agents will respond based on the backend configuration



## Configuration

### Backend URL

The frontend is hardcoded to connect to:
- REST API: `http://localhost:8000`
- WebSocket: `ws://localhost:8000`

To change this (e.g., for deployment), update the URLs in `app/page.tsx`:
- Line ~63: `fetch('http://localhost:8000/session/start'`
- Line ~47: `new WebSocket('ws://localhost:8000/ws/${sessionId}'`


## Features

### Token Entry Screen
- Simple authentication using hardcoded token "1234"
- Calls backend `/session/start` endpoint
- Receives session_id for WebSocket connection

### Chat Interface
- **Header:** Displays connection status (🟢 Connected / 🔴 Disconnected)
- **Message Feed:** Scrolling list of messages with auto-scroll to bottom
- **Input Area:** Text input with "Post" button
- **Visual distinction:** User messages (blue) vs agent messages (gray)

### WebSocket Communication
- Connects to `ws://localhost:8000/ws/{session_id}`
- Sends user messages: `{"type": "user_message", "content": "..."}`
- Receives agent messages: `{"sender": "Alice", "content": "...", "timestamp": "...", "message_id": "..."}`
- Auto-reconnection not implemented (refresh page to reconnect)



