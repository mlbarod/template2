import { Outlet } from "react-router-dom"

export default function SettingsPage() {
  return (
    <div className="flex min-h-0 min-w-0 flex-col gap-4">
      <Outlet />
    </div>
  )
}
