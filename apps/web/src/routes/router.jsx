// 파일 경로: src/routes/router.jsx
import { createBrowserRouter } from "react-router-dom"

import { AuthAutoLoginGate } from "@/lib/auth"

import { appstoreRoutes } from "@/features/appstore"
import { authRoutes } from "@/features/auth"
import { RouteErrorPage, errorRoutes } from "@/features/errors"
import { GlobalNavbarShell, homeRoutes } from "@/features/home"
import { lineDashboardRoutes } from "@/features/line-dashboard"
import { teamstaffRoutes } from "@/features/teamstaff"
import { timelineRoutes } from "@/features/timeline"
import { vocRoutes } from "@/features/voc"
import { assistantRoutes } from "@/features/assistant"
import { emailsRoutes } from "@/features/emails"
import { accountRoutes } from "@/features/account"

const protectedFeatureRoutes = [
  ...teamstaffRoutes,
  ...lineDashboardRoutes,
  ...appstoreRoutes,
  ...emailsRoutes,
  ...vocRoutes,
  ...accountRoutes,
]

const protectedAppRoutes = {
  element: <AuthAutoLoginGate />,
  children: protectedFeatureRoutes,
}

const timelineProtectedRoutes = {
  element: <AuthAutoLoginGate />,
  children: timelineRoutes,
}

const assistantProtectedRoutes = {
  element: <AuthAutoLoginGate />,
  children: assistantRoutes,
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <GlobalNavbarShell />,
    errorElement: (
      <GlobalNavbarShell>
        <RouteErrorPage />
      </GlobalNavbarShell>
    ),
    children: [
      ...homeRoutes,
      ...authRoutes,
      protectedAppRoutes,
      timelineProtectedRoutes,
      assistantProtectedRoutes,
      ...errorRoutes,
    ],
  },
])
