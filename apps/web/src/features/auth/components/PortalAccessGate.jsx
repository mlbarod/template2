// 파일 경로: src/features/auth/components/PortalAccessGate.jsx
// 로그인 이후 포털 접근 승인 상태에 따라 보호된 화면 렌더링을 제어합니다.

import { useEffect, useState } from "react"
import { useLocation } from "react-router-dom"
import { AlertCircle, Clock3, Send, ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import { getAppAccess } from "@/lib/access/appAccess"
import { resolveAppAccessTarget } from "@/lib/activity/appAccessCatalog"
import { buildBackendUrl } from "@/lib/api"

import { useAuth } from "../hooks/useAuth"
import { fetchJson } from "../utils/fetchJson"

function getGateCopy(portalAccess) {
  const reason = portalAccess?.reason || "access_state_unavailable"
  if (reason === "access_state_unavailable" || reason === "scope_not_found") {
    return {
      icon: AlertCircle,
      title: "포털 접근 상태를 확인할 수 없습니다",
      description: "권한 설정을 불러오지 못했습니다. 잠시 후 다시 확인하거나 관리자에게 문의하세요.",
      actionLabel: "",
    }
  }
  if (reason === "scope_inactive") {
    return {
      icon: AlertCircle,
      title: "포털 접근이 일시 중지되었습니다",
      description: "현재 포털 접근 정책이 비활성 상태입니다. 관리자에게 문의하세요.",
      actionLabel: "",
    }
  }
  if (reason === "pending") {
    return {
      icon: Clock3,
      title: "포털 접근 승인 대기 중",
      description: "관리자 승인 후 접속 가능합니다.",
      actionLabel: "",
    }
  }
  if (reason === "denied") {
    return {
      icon: AlertCircle,
      title: "포털 접근이 제한되었습니다",
      description: "필요한 경우 다시 승인을 요청하세요.",
      actionLabel: "다시 요청",
    }
  }
  return {
    icon: ShieldCheck,
    title: "포털 접근 승인이 필요합니다",
    description: "현재 계정으로 포털을 사용하려면 관리자 승인이 필요합니다.",
    actionLabel: "승인 요청",
  }
}

function normalizePath(path) {
  if (!path || path === "/") return "/"
  return path.endsWith("/") ? path.slice(0, -1) : path
}

function getRequiredAppScopes(target) {
  if (!target || target.requiresAppAccess === false) return []
  const scopes = target.requiredAppScopes || (target.appId ? [target.appId] : [])
  return scopes.filter(Boolean)
}

function getAppScopeLabel(target, scopeKey) {
  const requiredScopes = getRequiredAppScopes(target)
  if (requiredScopes.length <= 1) return target?.appName || scopeKey
  return scopeKey
}

function getAppRequestState(access, hasSubmittedRequest) {
  if (hasSubmittedRequest || access?.explicitStatus === "pending") return "pending"
  if (access?.underlyingAccess?.allowed || access?.explicitStatus === "allowed") return "allowed"
  if (access?.canRequest) return "requestable"
  return "blocked"
}

function getCombinedActionLabel({ canRequestPortal, requestableAppRows, fallbackLabel }) {
  const appCount = requestableAppRows.length
  if (canRequestPortal && appCount === 1) {
    return `포털 + ${requestableAppRows[0].label} 권한 신청`
  }
  if (canRequestPortal && appCount > 1) {
    return "포털 + 앱 권한 신청"
  }
  if (appCount === 1) {
    return `${requestableAppRows[0].label} 권한 신청`
  }
  if (appCount > 1) {
    return "앱 권한 신청"
  }
  return fallbackLabel
}

export function PortalAccessGate({ children, allowUnapprovedPaths = [] }) {
  const { user, refresh, isRefreshing } = useAuth()
  const location = useLocation()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submittedAppScopes, setSubmittedAppScopes] = useState(() => new Set())
  const [errorMessage, setErrorMessage] = useState("")
  const [statusMessage, setStatusMessage] = useState("")
  const [hasSubmittedRequest, setHasSubmittedRequest] = useState(false)
  const [hasObservedPending, setHasObservedPending] = useState(false)
  const portalAccess = user?.portal_access
  const gatePortalAccess = hasSubmittedRequest
    ? { ...portalAccess, reason: "pending", canRequest: false }
    : portalAccess
  const currentPath = normalizePath(location.pathname)
  const canBypassGate = allowUnapprovedPaths.some((path) => normalizePath(path) === currentPath)
  const isPending = gatePortalAccess?.reason === "pending"
  const appTarget = resolveAppAccessTarget(location.pathname)
  const requiredAppScopes = getRequiredAppScopes(appTarget)
  const appRequestRows = requiredAppScopes.map((scopeKey) => {
    const access = getAppAccess(user, scopeKey)
    const requestState = getAppRequestState(access, submittedAppScopes.has(scopeKey))
    return {
      scopeKey,
      access,
      requestState,
      label: getAppScopeLabel(appTarget, scopeKey),
    }
  })

  useEffect(() => {
    if (!hasSubmittedRequest) return
    if (portalAccess?.reason === "pending") {
      if (!hasObservedPending) setHasObservedPending(true)
      return
    }
    if (hasObservedPending) {
      setHasSubmittedRequest(false)
      setHasObservedPending(false)
    }
  }, [hasObservedPending, hasSubmittedRequest, portalAccess?.reason])

  useEffect(() => {
    if (!user || canBypassGate || !isPending) return undefined
    const timer = window.setInterval(() => {
      if (!isRefreshing) refresh({ background: true })
    }, 15_000)
    return () => window.clearInterval(timer)
  }, [canBypassGate, isPending, isRefreshing, refresh, user])

  if (!user) {
    return null
  }

  if (portalAccess?.allowed || canBypassGate) {
    return children
  }

  const copy = getGateCopy(gatePortalAccess)
  const Icon = copy.icon
  const canRequestPortal = Boolean(gatePortalAccess?.canRequest)
  const requestableAppRows = appRequestRows.filter((row) => row.requestState === "requestable")
  const canSubmitRequest = canRequestPortal || requestableAppRows.length > 0
  const actionLabel = getCombinedActionLabel({
    canRequestPortal,
    requestableAppRows,
    fallbackLabel: copy.actionLabel,
  })
  const department = portalAccess?.department || "미지정"
  const rejectionReason = portalAccess?.rejectionReason || ""
  const isBusy = isSubmitting || isRefreshing

  const requestPortalAccess = async () => {
    const result = await fetchJson(buildBackendUrl("/api/v1/account/portal-access"), {
      method: "POST",
    })
    if (!result.ok) {
      throw new Error("portal_request_failed")
    }
    const requestIsPending =
      result.data?.status === "pending" || result.data?.portalAccess?.reason === "pending"
    setHasSubmittedRequest(requestIsPending)
    return requestIsPending
  }

  const requestAppAccess = async (scopeKey) => {
    const result = await fetchJson(buildBackendUrl("/api/v1/account/access/request"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: scopeKey }),
    })
    if (!result.ok) {
      const error = result.data?.error
      throw new Error(error === "not_requestable" ? "app_not_requestable" : "app_request_failed")
    }
    if (result.data?.status === "pending") {
      setSubmittedAppScopes((prev) => {
        const next = new Set(prev)
        next.add(scopeKey)
        return next
      })
    }
  }

  const handleRequest = async () => {
    if (!canSubmitRequest || isBusy) return

    setIsSubmitting(true)
    setErrorMessage("")
    setStatusMessage("")
    try {
      if (canRequestPortal) {
        await requestPortalAccess()
      }
      for (const row of requestableAppRows) {
        await requestAppAccess(row.scopeKey)
      }
      const didRefresh = await refresh()
      const requestedPortal = canRequestPortal
      const requestedApps = requestableAppRows.length > 0
      const successMessage =
        requestedPortal && requestedApps
          ? "포털과 앱 권한 신청을 저장했습니다."
          : requestedApps
            ? "앱 권한 신청을 저장했습니다."
            : "승인 요청을 저장했습니다."
      if (didRefresh) {
        setStatusMessage(successMessage)
      } else {
        setStatusMessage(successMessage)
        setErrorMessage("최신 접근 상태를 불러오지 못했습니다.")
      }
    } catch (error) {
      const message = error?.message
      if (message === "portal_request_failed") {
        setErrorMessage("포털 권한 신청을 저장하지 못했습니다.")
      } else if (message === "app_not_requestable") {
        setErrorMessage("이 앱 권한은 신청할 수 없습니다.")
      } else if (message === "app_request_failed") {
        setErrorMessage("앱 권한 신청을 저장하지 못했습니다.")
      } else {
        setErrorMessage("권한 신청 중 오류가 발생했습니다.")
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 items-center justify-center overflow-y-auto bg-background px-6 py-10">
      <Card className="w-full max-w-md rounded-lg border bg-card shadow-sm" aria-labelledby="portal-access-title">
        <CardHeader className="gap-3">
          <div className="flex size-10 items-center justify-center rounded-md border bg-muted text-muted-foreground">
            <Icon className="size-5" aria-hidden="true" />
          </div>
          <div className="space-y-2">
            <CardTitle id="portal-access-title" className={isPending ? "text-base text-primary" : "text-base"}>
              {copy.title}
            </CardTitle>
            <CardDescription>{copy.description}</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="sr-only" role="status" aria-live="polite">
            {copy.title}
          </p>
          <div className="rounded-md border bg-muted/40 px-3 py-2">
            <div className="text-xs font-medium text-muted-foreground">부서</div>
            <div className="mt-1 text-foreground">{department}</div>
          </div>
          {appRequestRows.length ? (
            <div className="rounded-md border bg-muted/40 px-3 py-2">
              <div className="text-xs font-medium text-muted-foreground">필요한 앱 권한</div>
              <div className="mt-2 space-y-2">
                {appRequestRows.map((row) => {
                  const canRequestApp = row.requestState === "requestable"
                  const statusLabel =
                    row.requestState === "allowed"
                      ? "앱 권한 허용됨"
                      : row.requestState === "pending"
                        ? "승인 대기 중"
                        : canRequestApp
                          ? "신청 가능"
                          : "신청 불가"

                  return (
                    <div key={row.scopeKey} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-foreground">{row.label}</div>
                        <div className="text-xs text-muted-foreground">{statusLabel}</div>
                      </div>
                      {canRequestApp ? <span className="shrink-0 text-xs font-medium text-primary">함께 신청</span> : null}
                    </div>
                  )
                })}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                앱 권한을 먼저 신청해도 포털 승인이 완료되어야 실제 접속할 수 있습니다.
              </p>
            </div>
          ) : null}
          {rejectionReason ? (
            <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-destructive">
              거절 사유: {rejectionReason}
            </p>
          ) : null}
          {statusMessage ? (
            <p className="text-sm text-muted-foreground" role="status" aria-live="polite">
              {statusMessage}
            </p>
          ) : null}
          {errorMessage ? (
            <p className="text-sm text-destructive" role="alert" aria-live="assertive">
              {errorMessage}
            </p>
          ) : null}
        </CardContent>
        {canSubmitRequest ? (
          <CardFooter className="gap-2">
            <Button className="flex-1" onClick={handleRequest} disabled={isBusy}>
              {isSubmitting ? <Spinner className="size-4" /> : <Send className="size-4" aria-hidden="true" />}
              {isSubmitting ? "신청 중" : actionLabel}
            </Button>
          </CardFooter>
        ) : null}
      </Card>
    </div>
  )
}
