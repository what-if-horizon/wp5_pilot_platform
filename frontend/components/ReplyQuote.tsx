import { getSenderColor } from "@/lib/constants"

interface ReplyQuoteProps {
  sender: string
  text: string
}

export default function ReplyQuote({ sender, text }: ReplyQuoteProps) {
  return (
    <div className="rounded-md px-2.5 py-1.5 mb-1.5 border-l-3 border-quote bg-bg-feed">
      <p
        className="text-xs font-semibold mb-0.5"
        style={{ color: getSenderColor(sender) }}
      >
        {sender}
      </p>
      <p className="text-xs text-secondary truncate">{text}</p>
    </div>
  )
}
