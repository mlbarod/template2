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

export function PortalAccessGate({ children, allowUnapprovedPaths = [] }) {
  const { user, refresh, isRefreshing } = useAuth()
  const location = useLocation()
  const [isSubmitting, setIsSubmitting] = useState(false)
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

  if (!user || portalAccess?.allowed || canBypassGate) {
    return children
  }

  const copy = getGateCopy(gatePortalAccess)
  const Icon = copy.icon
  const canRequest = Boolean(gatePortalAccess?.canRequest)
  const department = portalAccess?.department || "미지정"
  const rejectionReason = portalAccess?.rejectionReason || ""
  const isBusy = isSubmitting || isRefreshing

  const handleRequest = async () => {
    if (!canRequest || isBusy) return

    setIsSubmitting(true)
    setErrorMessage("")
    setStatusMessage("")
    try {
      const result = await fetchJson(buildBackendUrl("/api/v1/account/portal-access"), {
        method: "POST",
      })
      if (!result.ok) {
        setErrorMessage("승인 요청을 저장하지 못했습니다.")
        return
      }
      const requestIsPending =
        result.data?.status === "pending" || result.data?.portalAccess?.reason === "pending"
      setHasSubmittedRequest(requestIsPending)
      const didRefresh = await refresh()
      if (didRefresh) {
        setStatusMessage("승인 요청을 저장했습니다.")
      } else {
        setStatusMessage("승인 요청은 저장했습니다.")
        setErrorMessage("최신 접근 상태를 불러오지 못했습니다.")
      }
    } catch {
      setErrorMessage("승인 요청 중 오류가 발생했습니다.")
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
        {canRequest ? (
          <CardFooter className="gap-2">
            <Button className="flex-1" onClick={handleRequest} disabled={isBusy}>
              {isSubmitting ? <Spinner className="size-4" /> : <Send className="size-4" aria-hidden="true" />}
              {isSubmitting ? "요청 중" : copy.actionLabel}
            </Button>
          </CardFooter>
        ) : null}
      </Card>
    </div>
  )
}
