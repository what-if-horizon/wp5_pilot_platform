"use client"

import { useState } from "react"

interface LoginScreenProps {
  initialUsername: string
  onStart: (token: string, username: string) => Promise<void>
}

export default function LoginScreen({
  initialUsername,
  onStart,
}: LoginScreenProps) {
  const [token, setToken] = useState("")
  const [username, setUsername] = useState(initialUsername)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const handleSubmit = async () => {
    if (!token.trim()) {
      setError("Please enter a token")
      return
    }
    setLoading(true)
    setError("")
    try {
      await onStart(token.trim(), username.trim())
    } catch {
      setError("Invalid token. Please try again.")
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex items-center justify-center h-dvh bg-gray-100">
      {/* Header accent */}
      <div className="fixed top-0 left-0 right-0 h-32 bg-header" />

      <div className="relative z-10 bg-white rounded-lg shadow-xl w-full max-w-sm mx-4 overflow-hidden">
        {/* Card header */}
        <div className="bg-header px-6 py-5">
          <h1 className="text-white text-xl font-medium m-0">
            Community Chatroom
          </h1>
          <p className="text-white/70 text-sm mt-1">
            Enter your token to join
          </p>
        </div>

        {/* Form */}
        <div className="px-6 py-5 space-y-3">
          <div>
            <label
              htmlFor="username"
              className="block text-xs font-medium text-secondary mb-1"
            >
              Display name (optional)
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Alice"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm text-primary focus:outline-none focus:border-header focus:ring-1 focus:ring-header/30 transition-colors placeholder:text-secondary/50"
            />
          </div>
          <div>
            <label
              htmlFor="token"
              className="block text-xs font-medium text-secondary mb-1"
            >
              Participant token
            </label>
            <input
              id="token"
              type="text"
              value={token}
              onChange={(e) => {
                setToken(e.target.value)
                if (error) setError("")
              }}
              onKeyDown={handleKeyDown}
              placeholder="e.g. user0002"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm text-primary focus:outline-none focus:border-header focus:ring-1 focus:ring-header/30 transition-colors placeholder:text-secondary/50"
              autoFocus
            />
          </div>

          {error && (
            <p className="text-sm text-danger mt-1">{error}</p>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full py-2.5 bg-header hover:bg-header-dark text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 mt-2"
          >
            {loading ? "Joining..." : "Join Chatroom"}
          </button>
        </div>
      </div>
    </div>
  )
}
