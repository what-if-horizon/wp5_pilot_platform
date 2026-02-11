"use client"

import { useCallback, useRef } from "react"
import type { Message } from "@/lib/types"
import { getSenderColor } from "@/lib/constants"
import { formatMessageTime } from "@/lib/dates"
import ReplyQuote from "./ReplyQuote"
import DoubleCheck from "./DoubleCheck"

interface MessageBubbleProps {
  message: Message
  isSelf: boolean
  showTail: boolean
  showSender: boolean
  onContextMenu: (msg: Message, x: number, y: number) => void
}

function renderContent(content: string, mentions?: string[]) {
  if (!mentions || mentions.length === 0) {
    return content
  }

  // Build a regex to match all @mentions in the text
  const escaped = mentions.map((m) =>
    m.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
  )
  const pattern = new RegExp(`(@(?:${escaped.join("|")}))`, "gi")
  const parts = content.split(pattern)

  return parts.map((part, i) => {
    if (pattern.test(part)) {
      // Reset lastIndex since we're reusing the regex
      pattern.lastIndex = 0
      return (
        <span key={i} className="text-mention font-medium">
          {part}
        </span>
      )
    }
    pattern.lastIndex = 0
    return part
  })
}

export default function MessageBubble({
  message,
  isSelf,
  showTail,
  showSender,
  onContextMenu,
}: MessageBubbleProps) {
  const longPressTimer = useRef<number | null>(null)

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      onContextMenu(message, e.clientX, e.clientY)
    },
    [message, onContextMenu],
  )

  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      const touch = e.touches[0]
      longPressTimer.current = window.setTimeout(() => {
        onContextMenu(message, touch.clientX, touch.clientY)
      }, 500)
    },
    [message, onContextMenu],
  )

  const handleTouchEnd = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current)
      longPressTimer.current = null
    }
  }, [])

  const handleTouchMove = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current)
      longPressTimer.current = null
    }
  }, [])

  const likesCount = message.likes_count || 0

  // Find the sender of the quoted message for ReplyQuote display
  const quotedSender = message.reply_to ? "Quoted" : ""

  return (
    <div
      className={`flex ${isSelf ? "justify-end" : "justify-start"} ${
        showTail ? "mt-2" : "mt-0.5"
      } ${isSelf ? "pr-2 pl-16" : "pl-2 pr-16"}`}
    >
      <div
        className={`relative max-w-[85%] rounded-lg shadow-sm px-2 pt-1.5 pb-1 ${
          isSelf
            ? `bg-bubble-out ${showTail ? "bubble-tail-right" : ""}`
            : `bg-bubble-in ${showTail ? "bubble-tail-left" : ""}`
        }`}
        onContextMenu={handleContextMenu}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onTouchMove={handleTouchMove}
      >
        {/* Sender name for incoming messages */}
        {showSender && !isSelf && (
          <p
            className="text-[13px] font-medium mb-0.5 leading-tight"
            style={{ color: getSenderColor(message.sender) }}
          >
            {message.sender}
          </p>
        )}

        {/* Reply quote */}
        {message.quoted_text && (
          <ReplyQuote
            sender={quotedSender}
            text={
              message.quoted_text.length > 150
                ? message.quoted_text.slice(0, 150) + "\u2026"
                : message.quoted_text
            }
            isSelfBubble={isSelf}
          />
        )}

        {/* Message content */}
        <p className="text-[14.2px] text-primary leading-[19px] whitespace-pre-wrap break-words pr-12">
          {renderContent(message.content, message.mentions)}
        </p>

        {/* Timestamp + tick row (absolute bottom-right to save space) */}
        <span className="float-right relative -mr-0.5 -mb-1 ml-2 mt-1 flex items-center gap-1">
          <span className="text-[11px] text-secondary leading-none">
            {formatMessageTime(message.timestamp)}
          </span>
          {isSelf && <DoubleCheck />}
        </span>

        {/* Likes indicator */}
        {likesCount > 0 && (
          <div className="absolute -bottom-2.5 right-2 bg-white rounded-full shadow-md px-1.5 py-0.5 flex items-center gap-0.5 text-[11px] border border-gray-100">
            <span className="text-red-500">&#10084;</span>
            <span className="text-secondary">{likesCount}</span>
          </div>
        )}
      </div>
    </div>
  )
}
