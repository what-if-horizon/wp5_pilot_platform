"use client"

import { useEffect, useRef, Fragment, useCallback } from "react"
import type { Message } from "@/lib/types"
import { getDateLabel } from "@/lib/dates"
import MessageBubble from "./MessageBubble"
import NewsArticleCard from "./NewsArticleCard"
import DateSeparator from "./DateSeparator"

interface MessageFeedProps {
  messages: Message[]
  currentUser: string | null
  onContextMenu: (msg: Message, x: number, y: number) => void
}

interface DateGroup {
  label: string
  dateKey: string
  messages: Message[]
}

function groupByDate(messages: Message[]): DateGroup[] {
  const groups: DateGroup[] = []
  let current: DateGroup | null = null

  for (const msg of messages) {
    const label = getDateLabel(msg.timestamp)
    if (!current || current.label !== label) {
      current = { label, dateKey: msg.timestamp.slice(0, 10), messages: [] }
      groups.push(current)
    }
    current.messages.push(msg)
  }

  return groups
}

export default function MessageFeed({
  messages,
  currentUser,
  onContextMenu,
}: MessageFeedProps) {
  const endRef = useRef<HTMLDivElement>(null)

  // Auto-scroll on new messages
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleContextMenu = useCallback(
    (msg: Message, x: number, y: number) => {
      onContextMenu(msg, x, y)
    },
    [onContextMenu],
  )

  const dateGroups = groupByDate(messages)

  return (
    <div className="flex-1 overflow-y-auto chat-scrollbar chat-wallpaper px-1.5 py-2">
      {dateGroups.map((group) => (
        <Fragment key={group.dateKey}>
          <DateSeparator label={group.label} />
          {group.messages.map((msg, idx) => {
            const isSelf =
              msg.sender === currentUser || msg.sender === "user"

            if (msg.msg_type === "news_article") {
              return (
                <NewsArticleCard key={msg.message_id} message={msg} />
              )
            }

            // Determine if this message should show a tail and sender name
            const prevMsg = idx > 0 ? group.messages[idx - 1] : null
            const showTail =
              !prevMsg ||
              prevMsg.sender !== msg.sender ||
              prevMsg.msg_type === "news_article"
            const showSender = showTail && !isSelf

            return (
              <MessageBubble
                key={msg.message_id}
                message={msg}
                isSelf={isSelf}
                showTail={showTail}
                showSender={showSender}
                onContextMenu={handleContextMenu}
              />
            )
          })}
        </Fragment>
      ))}
      <div ref={endRef} />
    </div>
  )
}
