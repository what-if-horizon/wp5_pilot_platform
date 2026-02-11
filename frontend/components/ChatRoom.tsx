"use client"

import { useCallback } from "react"
import type { Message } from "@/lib/types"
import ChatHeader from "./ChatHeader"
import MessageFeed from "./MessageFeed"
import InputBar from "./InputBar"
import ReportModal from "./ReportModal"
import ContextMenu from "./ContextMenu"

interface ChatRoomProps {
  // Messages
  visibleMessages: Message[]
  participants: string[]
  currentUser: string | null
  // Connection
  isConnected: boolean
  // Input
  inputValue: string
  setInputValue: (v: string) => void
  // Reply
  replyTo: Message | null
  setReplyTo: (msg: Message | null) => void
  // Send
  sendMessage: () => void
  // Like
  toggleLike: (msg: Message) => void
  // Report
  reportModalOpen: boolean
  setReportModalOpen: (open: boolean) => void
  reportTarget: Message | null
  setReportTarget: (msg: Message | null) => void
  reporting: boolean
  performReport: (block: boolean) => void
  // Context menu
  contextMenu: { message: Message; x: number; y: number } | null
  setContextMenu: (
    cm: { message: Message; x: number; y: number } | null,
  ) => void
  // Username for mention insertion
  username: string
}

export default function ChatRoom({
  visibleMessages,
  participants,
  currentUser,
  isConnected,
  inputValue,
  setInputValue,
  replyTo,
  setReplyTo,
  sendMessage,
  toggleLike,
  reportModalOpen,
  setReportModalOpen,
  reportTarget,
  setReportTarget,
  reporting,
  performReport,
  contextMenu,
  setContextMenu,
}: ChatRoomProps) {
  const handleContextMenu = useCallback(
    (msg: Message, x: number, y: number) => {
      setContextMenu({ message: msg, x, y })
    },
    [setContextMenu],
  )

  const isSelf = (sender: string) =>
    sender === currentUser || sender === "user"

  return (
    <div className="flex flex-col h-dvh max-w-3xl mx-auto bg-white shadow-lg relative">
      <ChatHeader
        participantCount={participants.length}
        isConnected={isConnected}
      />

      <MessageFeed
        messages={visibleMessages}
        currentUser={currentUser}
        onContextMenu={handleContextMenu}
      />

      <InputBar
        inputValue={inputValue}
        setInputValue={setInputValue}
        replyTo={replyTo}
        onCancelReply={() => setReplyTo(null)}
        onSend={sendMessage}
      />

      {/* Context menu */}
      {contextMenu && (
        <ContextMenu
          message={contextMenu.message}
          x={contextMenu.x}
          y={contextMenu.y}
          isSelf={isSelf(contextMenu.message.sender)}
          isLiked={
            (contextMenu.message.liked_by || []).includes(
              currentUser || "user",
            )
          }
          likesCount={contextMenu.message.likes_count || 0}
          onReply={() => setReplyTo(contextMenu.message)}
          onLike={() => toggleLike(contextMenu.message)}
          onMention={() => {
            const mentionText = `@${contextMenu.message.sender} `
            setInputValue(inputValue + mentionText)
          }}
          onReport={() => {
            setReportTarget(contextMenu.message)
            setReportModalOpen(true)
          }}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Report modal */}
      {reportModalOpen && reportTarget && (
        <ReportModal
          senderName={reportTarget.sender}
          reporting={reporting}
          onReport={() => performReport(false)}
          onReportAndBlock={() => performReport(true)}
          onClose={() => {
            setReportModalOpen(false)
            setReportTarget(null)
          }}
        />
      )}
    </div>
  )
}
