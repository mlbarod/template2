import { useEffect, useRef } from "react"
import { useLocation } from "react-router-dom"

import { recordAppAccess } from "@/features/access-stats"
import { getAppAccess } from "@/lib/access/appAccess"
import { useAuth } from "@/lib/auth"

import { resolveAppAccessTarget } from "./appAccessCatalog"

export function AppAccessTracker() {
  const { user } = useAuth()
  const location = useLocation()
  const lastTrackedKeyRef = useRef("")

  useEffect(() => {
    if (!user) return

    const target = resolveAppAccessTarget(location.pathname)
    if (!target) return
    const access = getAppAccess(user, target.appId)
    if (access && !access.allowed) return

    const path = `${location.pathname}${location.search || ""}`
    const trackedKey = `${user.id || user.usr_id || "user"}:${path}`
    if (lastTrackedKeyRef.current === trackedKey) return
    lastTrackedKeyRef.current = trackedKey

    recordAppAccess({
      appId: target.appId,
      appName: target.appName,
      path,
    }).catch(() => {})
  }, [location.pathname, location.search, user])

  return null
}
