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
    <div className="bg-bg-surface border-t border-border">
      {/* Reply preview strip */}
      {replyTo && (
        <div className="mx-3 mt-2 flex items-stretch bg-bg-feed rounded-lg overflow-hidden border border-border">
          <div
            className="w-1 shrink-0 bg-quote"
          />
          <div className="flex-1 min-w-0 px-3 py-2">
            <p
              className="text-xs font-semibold mb-0.5"
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
            className="px-3 text-tertiary hover:text-primary transition-colors self-center"
            aria-label="Cancel reply"
          >
            <svg
              width="16"
              height="16"
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
      <div className="flex items-end gap-2 px-3 py-2.5">
        <div className="flex-1 bg-bg-feed border border-border rounded-lg px-3.5 py-2.5 flex items-center focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/20 transition-all">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Write a message..."
            className="flex-1 text-sm bg-transparent outline-none text-primary placeholder:text-tertiary"
            aria-label="Message input"
          />
        </div>
        <button
          onClick={onSend}
          className="px-4 h-[42px] rounded-lg bg-accent hover:bg-accent-hover flex items-center justify-center shrink-0 transition-colors text-white"
          aria-label="Send message"
        >
          <SendIcon />
        </button>
      </div>
    </div>
  )
}
