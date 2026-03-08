import type { Metadata } from "next"
import AdminPanel from "../../components/admin/AdminPanel"

export const metadata: Metadata = {
  title: "Admin Panel | WP5",
}

export default function AdminPage() {
  return <AdminPanel />
}
