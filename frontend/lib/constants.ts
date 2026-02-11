export const API_BASE =
  (process.env.NEXT_PUBLIC_BACKEND_BASE as string) || "http://localhost:8000"
export const WS_BASE = API_BASE.replace(/^http/, "ws")

export const LS_SESSION_ID = "wp5_session_id"
export const LS_USERNAME = "wp5_username"
export const LS_BLOCKED = "wp5_blocked_senders"

const SENDER_COLORS = [
  "#1fa855",
  "#cb62d6",
  "#e06e34",
  "#3d7df5",
  "#d4372b",
  "#e8a400",
  "#019bdd",
  "#ff6f61",
]

export function getSenderColor(sender: string): string {
  let hash = 0
  for (let i = 0; i < sender.length; i++) {
    hash = sender.charCodeAt(i) + ((hash << 5) - hash)
  }
  return SENDER_COLORS[Math.abs(hash) % SENDER_COLORS.length]
}
