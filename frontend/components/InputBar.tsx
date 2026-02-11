"use client"

import { useRef, useCallback } from "react"
import type { Message } from "@/lib/types"
import { getSenderColor } from "@/lib/constants"
import SendIcon from "./SendIcon"

interface InputBarProps {
  inputValue: string
  setInputValue: (v: string) => void
  replyTo: Message | null
  onCancelReply: () => void
  onSend: () => void
  onMentionInsert?: (sender: string) => void
}

export default function InputBar({
  inputValue,
  setInputValue,
  replyTo,
  onCancelReply,
  onSend,
}: InputBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        onSend()
      }
    },
    [onSend],
  )

  return (
    <div className="bg-input-bar border-t border-gray-200">
      {/* Reply preview strip */}
      {replyTo && (
        <div className="mx-3 mt-2 flex items-stretch bg-white rounded-t-lg overflow-hidden border-b border-gray-100">
          <div
            className="w-1 shrink-0"
            style={{ backgroundColor: getSenderColor(replyTo.sender) }}
          />
          <div className="flex-1 min-w-0 px-3 py-2">
            <p
              className="text-xs font-medium mb-0.5"
              style={{ color: getSenderColor(replyTo.sender) }}
            >
              {replyTo.sender}
            </p>
            <p className="text-xs text-secondary truncate">
              {replyTo.content.length > 120
                ? replyTo.content.slice(0, 120) + "\u2026"
                : replyTo.content}
            </p>
          </div>
          <button
            onClick={onCancelReply}
            className="px-3 text-secondary hover:text-primary transition-colors self-center"
            aria-label="Cancel reply"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
            </svg>
          </button>
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2 px-3 py-2">
        <div className="flex-1 bg-white rounded-full px-4 py-2 flex items-center shadow-sm">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message"
            className="flex-1 text-sm bg-transparent outline-none text-primary placeholder:text-secondary/60"
            aria-label="Message input"
          />
        </div>
        <button
          onClick={onSend}
          className="w-10 h-10 rounded-full bg-send-btn hover:bg-send-btn-hover flex items-center justify-center shrink-0 transition-colors shadow-sm"
          aria-label="Send message"
        >
          <SendIcon />
        </button>
      </div>
    </div>
  )
}
