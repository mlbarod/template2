import { Outlet, useLocation } from "react-router-dom"

import { TeamSwitcher } from "@/components/common"
import { AppShellLayout } from "@/components/layout"
import { RequireAuth, useAuth } from "@/lib/auth"
import { buildNavigationConfig } from "@/lib/config/navigationConfig"

export function AccountSettingsShell() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const normalizedPath = pathname.replace(/\/+$/, "").toLowerCase()
  const isFixedTablePage = ["/settings/members", "/settings/permissions"].includes(normalizedPath)
  const navigation = buildNavigationConfig({
    canManageAccess: Boolean(user?.portal_access?.canManage),
  })

  return (
    <RequireAuth>
      <AppShellLayout
        navItems={navigation.navMain}
        sidebarHeader={<TeamSwitcher disabled />}
        scrollAreaClassName={isFixedTablePage ? "overflow-hidden" : "overflow-y-auto"}
      >
        <Outlet />
      </AppShellLayout>
    </RequireAuth>
  )
}
