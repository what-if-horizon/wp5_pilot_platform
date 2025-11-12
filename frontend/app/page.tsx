'use client'

import { useState, useEffect, useRef } from 'react'

interface Message {
  sender: string
  content: string
  timestamp: string
  message_id: string
  reply_to?: string
  quoted_text?: string
  mentions?: string[]
}

export default function ChatPage() {
  // State
  const [token, setToken] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [replyTo, setReplyTo] = useState<Message | null>(null)
  const [mentions, setMentions] = useState<string[]>([])
  const [participants, setParticipants] = useState<string[]>([])
  const inputRef = useRef<HTMLInputElement | null>(null)
  
  // Refs
  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Keep participants list (known senders) up-to-date from observed messages
  useEffect(() => {
    const set = new Set(messages.map((m) => m.sender))
    setParticipants([...set])
  }, [messages])

  // Helper: detect mentions in free text using @name tokens and match to known participants
  const detectMentions = (text: string) => {
    const found: string[] = []
    if (!text) return found
    const re = /@([A-Za-z0-9_\-]+)/g
    // build lookup map for case-insensitive matching
    const map = new Map(participants.map((p) => [p.toLowerCase(), p]))
    let m
    // eslint-disable-next-line no-cond-assign
    while ((m = re.exec(text)) !== null) {
      const raw = m[1]
      const key = raw.toLowerCase()
      if (map.has(key)) {
        const canonical = map.get(key) as string
        if (!found.includes(canonical)) found.push(canonical)
      }
    }
    return found
  }

  // WebSocket connection
  useEffect(() => {
    if (!sessionId) return
    let mounted = true
    let reconnectAttempts = 0
    let reconnectTimer: number | null = null

    const connect = () => {
      if (!mounted) return
      const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        reconnectAttempts = 0
      }

      ws.onmessage = (event) => {
        const message: Message = JSON.parse(event.data)
        setMessages((prev) => [...prev, message])
      }

      ws.onclose = (event: CloseEvent) => {
        console.log('WebSocket disconnected', event)
        setIsConnected(false)

        // If server closed with policy violation (1008) we assume the session
        // is invalid/stale. Clear stored session id and return user to token entry.
        if (event && event.code === 1008) {
          try {
            localStorage.removeItem('wp5_session_id')
          } catch (e) {
            // ignore localStorage errors
          }
          setSessionId(null)
          // Inform the user so they understand why they were disconnected.
          // Keep this simple (alert) to avoid adding new UI components.
          alert('Session invalid or expired. Please enter your token to start a new session.')
          return
        }

        // Simple reconnect logic: try a few times with delay for transient disconnects
        if (reconnectAttempts < 5) {
          reconnectAttempts += 1
          reconnectTimer = window.setTimeout(() => {
            connect()
          }, 2000 * reconnectAttempts)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
    }

    connect()

    // Cleanup on unmount
    return () => {
      mounted = false
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (wsRef.current) wsRef.current.close()
    }
  }, [sessionId])

  // Start session
  const handleStartSession = async () => {
    try {
      const response = await fetch('http://localhost:8000/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      })

      if (!response.ok) {
        alert('Invalid token')
        return
      }

      const data = await response.json()
      setSessionId(data.session_id)
      // persist session id so reloads reconnect automatically
      try {
        localStorage.setItem('wp5_session_id', data.session_id)
      } catch (e) {
        // ignore localStorage errors
      }
    } catch (error) {
      console.error('Error starting session:', error)
      alert('Failed to start session')
    }
  }

  // On mount, restore session_id from localStorage to persist across reloads
  useEffect(() => {
    try {
      const saved = localStorage.getItem('wp5_session_id')
      if (saved) setSessionId(saved)
    } catch (e) {
      // ignore
    }
  }, [])

  // Send message
  const handleSendMessage = () => {
    if (!inputValue.trim() || !wsRef.current) return
    const payload: any = {
      type: 'user_message',
      content: inputValue.trim(),
    }

    // If replying to a message, include reply metadata
    if (replyTo) {
      payload.reply_to = replyTo.message_id
      payload.quoted_text = replyTo.content
    }

    // Include mentions if any (detect from typed text to allow multiple mentions)
    const detected = detectMentions(inputValue)
    if (detected.length > 0) payload.mentions = detected

    wsRef.current.send(JSON.stringify(payload))

    // Add user message to display immediately (include reply metadata so UI is consistent)
    const userMessage: Message = {
      sender: 'user',
      content: inputValue.trim(),
      timestamp: new Date().toISOString(),
      message_id: `user-${Date.now()}`,
      reply_to: replyTo ? replyTo.message_id : undefined,
      quoted_text: replyTo ? replyTo.content : undefined,
      mentions: detected.length ? detected : undefined,
    }
    setMessages((prev) => [...prev, userMessage])

    setInputValue('')
    setReplyTo(null)
    setMentions([])
  }

  // Handle Enter key
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Token entry screen
  if (!sessionId) {
    return (
      <div style={styles.container}>
        <div style={styles.tokenBox}>
          <h1 style={styles.title}>Enter Token</h1>
          <input
            type="text"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleStartSession()}
            placeholder="Enter token (1234)"
            style={styles.input}
          />
          <button onClick={handleStartSession} style={styles.button}>
            Start Session
          </button>
        </div>
      </div>
    )
  }

  // Chat interface
  return (
    <div style={styles.chatContainer}>
      {/* Header */}
      <div style={styles.header}>
        <h2 style={styles.headerTitle}>Chatroom</h2>
        <div style={styles.status}>
          {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
        </div>
      </div>

      {/* Message feed */}
      <div style={styles.messagesFeed}>
        {messages.map((msg) => (
          <div
            key={msg.message_id}
            style={{
              ...styles.message,
              backgroundColor: msg.sender === 'user' ? '#e3f2fd' : '#f5f5f5',
            }}
          >
            <div style={styles.messageSender}>{msg.sender}</div>
            {/* Render quoted block when present */}
            {msg.quoted_text ? (
              <div style={styles.quotedBlock}>
                <div style={styles.quotedSender}>Quoted</div>
                <div style={styles.quotedText}>{msg.quoted_text}</div>
              </div>
            ) : null}
            {/* Render mentions if present */}
            {msg.mentions && msg.mentions.length ? (
              <div style={styles.mentionsRow}>
                {msg.mentions.map((m) => (
                  <span key={m} style={styles.mentionTag}>@{m}</span>
                ))}
              </div>
            ) : null}
            <div style={styles.messageContent}>{msg.content}</div>

            {/* Reply button */}
            <div>
              <button
                onClick={() => setReplyTo(msg)}
                style={styles.replyButton}
                aria-label={`Reply to message ${msg.message_id}`}
              >
                Reply
              </button>
              <button
                onClick={() => {
                  // Insert mention at the current cursor position (or prepend if input not focused)
                  const mentionText = `@${msg.sender} `
                  const el = inputRef.current
                  if (el) {
                    const start = el.selectionStart ?? 0
                    const end = el.selectionEnd ?? 0
                    const newVal = inputValue.slice(0, start) + mentionText + inputValue.slice(end)
                    setInputValue(newVal)
                    // update detected mentions immediately
                    setMentions(detectMentions(newVal))
                    // place caret after inserted mention
                    setTimeout(() => {
                      el.focus()
                      const pos = start + mentionText.length
                      el.setSelectionRange(pos, pos)
                    }, 0)
                  } else {
                    // fallback: prepend
                    const newVal = `${mentionText}${inputValue}`
                    setInputValue(newVal)
                    setMentions(detectMentions(newVal))
                  }
                }}
                style={{ ...styles.replyButton, marginLeft: '0.5rem' }}
                aria-label={`Mention ${msg.sender}`}
              >
                @{msg.sender}
              </button>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div style={styles.inputArea}>
        {/* Composer: show replying-to box when replying */}
        {replyTo ? (
          <div style={styles.replyingBox}>
            <div style={styles.replyingLabel}>Replying to {replyTo.sender}</div>
            <div style={styles.replyingPreview}>{replyTo.content.length > 120 ? replyTo.content.slice(0, 120) + '…' : replyTo.content}</div>
            <button onClick={() => setReplyTo(null)} style={styles.cancelReplyButton}>Cancel</button>
          </div>
        ) : null}
        {/* Composer: show mention tags if any */}
        {mentions && mentions.length ? (
          <div style={styles.mentionsBox}>
            {mentions.map((m) => (
              <span key={m} style={styles.mentionTag}>{`@${m}`}</span>
            ))}
            <button onClick={() => setMentions([])} style={styles.cancelReplyButton}>Clear</button>
          </div>
        ) : null}
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => {
            const v = e.target.value
            setInputValue(v)
            setMentions(detectMentions(v))
          }}
          onKeyPress={handleKeyPress}
          placeholder="Type a message..."
          style={styles.messageInput}
        />
        <button onClick={handleSendMessage} style={styles.sendButton}>
          Post
        </button>
      </div>
    </div>
  )
}

// Inline styles
const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    backgroundColor: '#f0f0f0',
  },
  tokenBox: {
    backgroundColor: 'white',
    padding: '2rem',
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
    width: '300px',
  },
  title: {
    margin: '0 0 1rem 0',
    fontSize: '1.5rem',
    textAlign: 'center' as const,
  },
  input: {
    width: '100%',
    padding: '0.5rem',
    marginBottom: '1rem',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '1rem',
    boxSizing: 'border-box' as const,
  },
  button: {
    width: '100%',
    padding: '0.5rem',
    backgroundColor: '#0070f3',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    fontSize: '1rem',
    cursor: 'pointer',
  },
  chatContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    height: '100vh',
    maxWidth: '800px',
    margin: '0 auto',
    backgroundColor: 'white',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '1rem',
    borderBottom: '1px solid #ddd',
    backgroundColor: '#f8f8f8',
  },
  headerTitle: {
    margin: 0,
    fontSize: '1.25rem',
  },
  status: {
    fontSize: '0.875rem',
  },
  messagesFeed: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '1rem',
    backgroundColor: '#fafafa',
  },
  message: {
    marginBottom: '0.75rem',
    padding: '0.75rem',
    borderRadius: '8px',
  },
  messageSender: {
    fontWeight: 'bold' as const,
    fontSize: '0.875rem',
    marginBottom: '0.25rem',
    color: '#555',
  },
  messageContent: {
    fontSize: '1rem',
  },
  quotedBlock: {
    padding: '0.5rem',
    marginBottom: '0.5rem',
    backgroundColor: '#ffffff',
    borderLeft: '3px solid #ddd',
    borderRadius: '4px',
  },
  quotedSender: {
    fontSize: '0.75rem',
    color: '#666',
    marginBottom: '0.25rem',
  },
  quotedText: {
    fontSize: '0.9rem',
    color: '#333',
  },
  replyButton: {
    marginTop: '0.5rem',
    padding: '0.25rem 0.5rem',
    fontSize: '0.8rem',
    backgroundColor: 'transparent',
    border: '1px solid #ddd',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  replyingBox: {
    display: 'flex',
    flexDirection: 'column' as const,
    padding: '0.5rem',
    marginRight: '0.5rem',
    border: '1px solid #ddd',
    borderRadius: '6px',
    backgroundColor: '#fff8e1',
    maxWidth: '50%',
  },
  replyingLabel: {
    fontSize: '0.8rem',
    color: '#333',
    marginBottom: '0.25rem',
  },
  replyingPreview: {
    fontSize: '0.9rem',
    color: '#555',
    marginBottom: '0.25rem',
  },
  cancelReplyButton: {
    alignSelf: 'flex-end' as const,
    padding: '0.25rem 0.5rem',
    fontSize: '0.8rem',
    backgroundColor: '#f44336',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  mentionsRow: {
    marginBottom: '0.5rem',
    display: 'flex',
    gap: '0.5rem',
    alignItems: 'center',
  },
  mentionTag: {
    padding: '0.25rem 0.5rem',
    backgroundColor: '#e8f0fe',
    border: '1px solid #d0e0ff',
    borderRadius: '4px',
    fontSize: '0.85rem',
    color: '#0366d6',
  },
  mentionsBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    marginRight: '0.5rem',
  },
  inputArea: {
    display: 'flex',
    padding: '1rem',
    borderTop: '1px solid #ddd',
    backgroundColor: 'white',
  },
  messageInput: {
    flex: 1,
    padding: '0.5rem',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '1rem',
    marginRight: '0.5rem',
  },
  sendButton: {
    padding: '0.5rem 1.5rem',
    backgroundColor: '#0070f3',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    fontSize: '1rem',
    cursor: 'pointer',
  },
}