// In production (behind Caddy reverse proxy), leave NEXT_PUBLIC_BACKEND_BASE
// empty — requests use same-origin relative paths. For local development
// without a reverse proxy, set it to "http://localhost:8000".
export const API_BASE =
  (process.env.NEXT_PUBLIC_BACKEND_BASE as string) || ""
export const WS_BASE = API_BASE
  ? API_BASE.replace(/^http/, "ws")
  : (typeof window !== "undefined"
      ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`
      : "")

// The canonical sender identity for the human participant (backend never sees real name).
export const PARTICIPANT_SENDER = "participant"

export const LS_SESSION_ID = "wp5_session_id"
export const LS_USERNAME = "wp5_username"
export const LS_BLOCKED = "wp5_blocked_senders"

const SENDER_COLORS = [
  "#6366f1",
  "#8b5cf6",
  "#ec4899",
  "#f97316",
  "#0ea5e9",
  "#14b8a6",
  "#a855f7",
  "#eab308",
]

export function getSenderColor(sender: string): string {
  let hash = 0
  for (let i = 0; i < sender.length; i++) {
    hash = sender.charCodeAt(i) + ((hash << 5) - hash)
  }
  return SENDER_COLORS[Math.abs(hash) % SENDER_COLORS.length]
}
