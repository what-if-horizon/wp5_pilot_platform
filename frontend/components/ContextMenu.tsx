"use client"

import { useEffect, useRef } from "react"
import type { Message } from "@/lib/types"

interface ContextMenuProps {
  message: Message
  x: number
  y: number
  isSelf: boolean
  isLiked: boolean
  likesCount: number
  onReply: () => void
  onLike: () => void
  onMention: () => void
  onReport: () => void
  onClose: () => void
}

export default function ContextMenu({
  x,
  y,
  isSelf,
  isLiked,
  likesCount,
  onReply,
  onLike,
  onMention,
  onReport,
  onClose,
}: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)

  // Close on outside click or Escape
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("mousedown", handleClick)
    document.addEventListener("keydown", handleKey)
    return () => {
      document.removeEventListener("mousedown", handleClick)
      document.removeEventListener("keydown", handleKey)
    }
  }, [onClose])

  // Clamp position to stay in viewport
  const style: React.CSSProperties = {
    top: Math.min(y, window.innerHeight - 200),
    left: Math.min(x, window.innerWidth - 180),
  }

  const itemClass =
    "w-full text-left px-4 py-2.5 text-sm text-primary hover:bg-gray-100 transition-colors"

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-white rounded-xl shadow-xl py-1 min-w-[160px] context-menu-enter"
      style={style}
      role="menu"
      aria-label="Message actions"
    >
      <button
        role="menuitem"
        onClick={() => {
          onReply()
          onClose()
        }}
        className={itemClass}
      >
        Reply
      </button>
      <button
        role="menuitem"
        onClick={() => {
          onLike()
          onClose()
        }}
        className={itemClass}
      >
        {isLiked ? "Unlike" : "Like"}
        {likesCount > 0 && ` (${likesCount})`}
      </button>
      {!isSelf && (
        <>
          <button
            role="menuitem"
            onClick={() => {
              onMention()
              onClose()
            }}
            className={itemClass}
          >
            Mention
          </button>
          <div className="border-t border-gray-100 my-0.5" />
          <button
            role="menuitem"
            onClick={() => {
              onReport()
              onClose()
            }}
            className={`${itemClass} text-danger`}
          >
            Report
          </button>
        </>
      )}
    </div>
  )
}
