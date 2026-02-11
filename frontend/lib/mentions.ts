export function detectMentions(
  text: string,
  participants: string[],
): string[] {
  const found: string[] = []
  if (!text) return found
  const re = /@([A-Za-z0-9_\-]+)/g
  const map = new Map(participants.map((p) => [p.toLowerCase(), p]))
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    const key = m[1].toLowerCase()
    if (map.has(key)) {
      const canonical = map.get(key)!
      if (!found.includes(canonical)) found.push(canonical)
    }
  }
  return found
}
