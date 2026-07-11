import { Outlet } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"

export function L0SpiderShell() {
  return (
    <RequireAuth>
      <div className="flex h-full min-h-0 w-full flex-col bg-background">
        <Outlet />
      </div>
    </RequireAuth>
  )
}
