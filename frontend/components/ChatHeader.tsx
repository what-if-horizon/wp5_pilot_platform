import GroupIcon from "./GroupIcon"

interface ChatHeaderProps {
  participantCount: number
  isConnected: boolean
}

export default function ChatHeader({
  participantCount,
  isConnected,
}: ChatHeaderProps) {
  return (
    <header className="flex items-center gap-3 px-4 py-2.5 bg-header text-white shrink-0">
      <GroupIcon />
      <div className="flex-1 min-w-0">
        <h1 className="text-base font-medium leading-tight m-0">
          Community Chatroom
        </h1>
        <p className="text-xs opacity-75 leading-tight mt-0.5">
          {participantCount} participant{participantCount !== 1 ? "s" : ""}
        </p>
      </div>
      <div className="flex items-center gap-1.5">
        <div
          className={`w-2 h-2 rounded-full ${
            isConnected ? "bg-green-300 animate-pulse" : "bg-red-400"
          }`}
        />
        <span className="text-[11px] opacity-75">
          {isConnected ? "Online" : "Offline"}
        </span>
      </div>
    </header>
  )
}
