import { Outlet, useLocation } from "react-router-dom"

export default function SettingsPage() {
  const { pathname } = useLocation()
  const normalizedPath = pathname.replace(/\/+$/, "").toLowerCase()
  const isFixedHeightPage = ["/settings/account", "/settings/members", "/settings/permissions"].includes(normalizedPath)

  return (
    <div className={isFixedHeightPage ? "h-full min-h-0 w-full overflow-hidden" : "w-full"}>
      <Outlet />
    </div>
  )
}
