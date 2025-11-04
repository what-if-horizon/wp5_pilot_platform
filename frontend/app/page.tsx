'use client'

import { useState, useEffect, useRef } from 'react'

interface Message {
  sender: string
  content: string
  timestamp: string
  message_id: string
}

export default function ChatPage() {
  // State
  const [token, setToken] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  
  // Refs
  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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

      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setIsConnected(false)
        // Simple reconnect logic: try a few times with delay
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

    const message = {
      type: 'user_message',
      content: inputValue.trim(),
    }

    wsRef.current.send(JSON.stringify(message))
    
    // Add user message to display immediately
    const userMessage: Message = {
      sender: 'user',
      content: inputValue.trim(),
      timestamp: new Date().toISOString(),
      message_id: `user-${Date.now()}`,
    }
    setMessages((prev) => [...prev, userMessage])
    
    setInputValue('')
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
            <div style={styles.messageContent}>{msg.content}</div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div style={styles.inputArea}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
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