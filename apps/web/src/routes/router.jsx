// 파일 경로: src/routes/router.jsx
import { createBrowserRouter, Outlet, useLocation } from "react-router-dom"

import { PortalGlobalShell } from "@/components/layout"
import { AuthAutoLoginGate, useAuth } from "@/lib/auth"

import { accessStatsRoutes } from "@/features/access-stats"
import { appstoreRoutes } from "@/features/appstore"
import { authRoutes } from "@/features/auth"
import { RouteErrorPage, errorRoutes } from "@/features/errors"
import { fdcTrendRoutes } from "@/features/fdc-trend"
import { homeRoutes } from "@/features/home"
import { lineDashboardRoutes } from "@/features/line-dashboard"
import { l3SpiderRoutes } from "@/features/l3-spider"
import { pmSpiderRoutes } from "@/features/pm-spider"
import { teamstaffRoutes } from "@/features/teamstaff"
import { TkinPreventDashboardRoute, observerRoutes } from "@/features/observer"
import { vocRoutes } from "@/features/voc"
import { ChatWidget, assistantRoutes } from "@/features/assistant"
import { emailsRoutes, useEmailMailboxes } from "@/features/emails"
import { accountRoutes } from "@/features/account"

const esopDashboardRoutes = lineDashboardRoutes.map((route) => {
  if (route?.path !== "ESOP_Dashboard") return route

  return {
    ...route,
    children: [
      ...(Array.isArray(route.children) ? route.children : []),
      {
        path: "tip-status",
        caseSensitive: false,
        element: <TkinPreventDashboardRoute />,
      },
      {
        path: "tip-status/:lineId",
        caseSensitive: false,
        element: <TkinPreventDashboardRoute />,
      },
    ],
  }
})

const protectedFeatureRoutes = [
  ...teamstaffRoutes,
  ...esopDashboardRoutes,
  ...fdcTrendRoutes,
  ...l3SpiderRoutes,
  ...pmSpiderRoutes,
  ...appstoreRoutes,
  ...accessStatsRoutes,
  ...emailsRoutes,
  ...vocRoutes,
  ...accountRoutes,
]

function AssistantWidgetOutlet() {
  const { user } = useAuth()
  const location = useLocation()
  const { data: mailboxesData } = useEmailMailboxes({ enabled: Boolean(user) })
  const availableMailboxes = Array.isArray(mailboxesData?.results)
    ? mailboxesData.results
    : []
  const hideChatWidget = location.pathname === "/l3_spider"

  return (
    <>
      <Outlet context={{ availableMailboxes }} />
      {user && !hideChatWidget ? <ChatWidget availableMailboxes={availableMailboxes} /> : null}
    </>
  )
}

function AssistantMailboxOutlet() {
  const { user } = useAuth()
  const { data: mailboxesData } = useEmailMailboxes({ enabled: Boolean(user) })
  const availableMailboxes = Array.isArray(mailboxesData?.results)
    ? mailboxesData.results
    : []

  return <Outlet context={{ availableMailboxes }} />
}

const assistantWidgetRoutes = {
  element: <AuthAutoLoginGate />,
  children: [
    {
      element: <AssistantWidgetOutlet />,
      children: [
        ...homeRoutes,
        ...protectedFeatureRoutes,
        ...observerRoutes,
      ],
    },
  ],
}

const assistantProtectedRoutes = {
  element: <AuthAutoLoginGate />,
  children: [
    {
      element: <AssistantMailboxOutlet />,
      children: assistantRoutes,
    },
  ],
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <PortalGlobalShell />,
    errorElement: (
      <PortalGlobalShell>
        <RouteErrorPage />
      </PortalGlobalShell>
    ),
    children: [
      ...authRoutes,
      assistantWidgetRoutes,
      assistantProtectedRoutes,
      ...errorRoutes,
    ],
  },
])
