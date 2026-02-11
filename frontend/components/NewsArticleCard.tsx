import type { Message } from "@/lib/types"
import { formatMessageTime } from "@/lib/dates"

interface NewsArticleCardProps {
  message: Message
}

export default function NewsArticleCard({ message }: NewsArticleCardProps) {
  return (
    <div className="flex justify-center my-2 px-4">
      <div className="bg-white rounded-lg shadow-sm overflow-hidden border border-gray-200 max-w-[85%] w-full">
        <div className="h-1 bg-header" />
        <div className="p-3.5">
          {message.source && (
            <p className="text-[11px] text-secondary uppercase tracking-wider mb-1 font-medium">
              {message.source}
            </p>
          )}
          {message.headline && (
            <h3 className="text-[14px] font-semibold text-primary leading-snug mb-1.5">
              {message.headline}
            </h3>
          )}
          {message.body && (
            <p className="text-[13px] text-secondary leading-relaxed line-clamp-5">
              {message.body}
            </p>
          )}
          <p className="text-[11px] text-secondary mt-2 text-right">
            {formatMessageTime(message.timestamp)}
          </p>
        </div>
      </div>
    </div>
  )
}
