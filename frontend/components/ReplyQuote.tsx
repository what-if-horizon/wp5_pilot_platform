import { getSenderColor } from "@/lib/constants"

interface ReplyQuoteProps {
  sender: string
  text: string
  isSelfBubble: boolean
}

export default function ReplyQuote({
  sender,
  text,
  isSelfBubble,
}: ReplyQuoteProps) {
  return (
    <div
      className={`rounded-md px-2.5 py-1.5 mb-1 border-l-4 border-quote cursor-pointer ${
        isSelfBubble ? "bg-black/5" : "bg-gray-100"
      }`}
    >
      <p
        className="text-xs font-medium mb-0.5"
        style={{ color: getSenderColor(sender) }}
      >
        {sender}
      </p>
      <p className="text-xs text-secondary truncate">{text}</p>
    </div>
  )
}
