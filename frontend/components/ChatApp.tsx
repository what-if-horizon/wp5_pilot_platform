"use client"

import { useChat } from "@/hooks/useChat"
import LoginScreen from "./LoginScreen"
import ChatRoom from "./ChatRoom"

export default function ChatApp() {
  const chat = useChat()

  if (!chat.sessionId) {
    return (
      <LoginScreen
        initialUsername={chat.username}
        onStart={chat.startSession}
      />
    )
  }

  return (
    <ChatRoom
      visibleMessages={chat.visibleMessages}
      participants={chat.participants}
      currentUser={chat.currentUser}
      isConnected={chat.isConnected}
      inputValue={chat.inputValue}
      setInputValue={chat.setInputValue}
      replyTo={chat.replyTo}
      setReplyTo={chat.setReplyTo}
      sendMessage={chat.sendMessage}
      toggleLike={chat.toggleLike}
      reportModalOpen={chat.reportModalOpen}
      setReportModalOpen={chat.setReportModalOpen}
      reportTarget={chat.reportTarget}
      setReportTarget={chat.setReportTarget}
      reporting={chat.reporting}
      performReport={chat.performReport}
      contextMenu={chat.contextMenu}
      setContextMenu={chat.setContextMenu}
      username={chat.username}
    />
  )
}
