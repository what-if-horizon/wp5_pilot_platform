import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'WP5 Chatroom',
  description: 'Social scientific chatroom experiment',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0, fontFamily: 'system-ui, sans-serif' }}>
        {children}
      </body>
    </html>
  )
}