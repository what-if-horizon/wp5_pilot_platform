# WP5 Pilot Platform — Frontend

Chat interface for the WP5 simulation backend. Styled as a generic community chatroom (WhatsApp-like). Built with Next.js 15, React 19, TypeScript, and Tailwind CSS v4.

## Quickstart

```bash
npm install
npm run dev        # http://localhost:3000
```

Backend must be running on `http://localhost:8000` (or set `NEXT_PUBLIC_BACKEND_BASE`).

## Project Structure

```
frontend/
├── app/
│   ├── globals.css          # Tailwind config, theme tokens, bubble tail CSS
│   ├── layout.tsx           # Root layout
│   └── page.tsx             # Page shell
├── components/
│   ├── ChatApp.tsx          # Top-level client component (auth gate)
│   ├── ChatRoom.tsx         # Main chat layout
│   ├── ChatHeader.tsx       # Header bar (group icon, participant count)
│   ├── MessageFeed.tsx      # Scrollable feed with date separators
│   ├── MessageBubble.tsx    # Chat bubble (tails, sender colors, timestamps)
│   ├── InputBar.tsx         # Message composer + send button
│   ├── ContextMenu.tsx      # Right-click / long-press actions
│   ├── LoginScreen.tsx      # Token entry screen
│   ├── NewsArticleCard.tsx  # Scenario seed article card
│   ├── ReplyQuote.tsx       # Quoted reply inside a bubble
│   ├── ReportModal.tsx      # Report / block dialog
│   └── DateSeparator.tsx    # Date pill ("Today", "Yesterday")
├── hooks/
│   ├── useChat.ts           # Core state orchestrator
│   ├── useWebSocket.ts      # WebSocket connection + reconnect
│   └── useLocalStorage.ts   # SSR-safe localStorage hook
├── lib/
│   ├── types.ts             # Message, event, and payload types
│   ├── constants.ts         # API URLs, localStorage keys, sender colors
│   ├── api.ts               # REST helpers (session, like, report)
│   ├── mentions.ts          # @mention detection
│   └── dates.ts             # Date formatting utilities
├── next.config.ts
├── postcss.config.mjs
├── tsconfig.json
└── package.json
```

