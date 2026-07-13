import { Link } from "react-router-dom"
import { Clock3, Home, Send, ShieldX } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import { getAppAccess } from "@/lib/access/appAccess"
import { buildBackendUrl } from "@/lib/api"

import { useAuth } from "../hooks/useAuth"
import { fetchJson } from "../utils/fetchJson"

function getAccessCopy(access, appName) {
  const reason = access?.reason || "not_requested"
  if (reason === "pending") {
    return {
      icon: Clock3,
      title: `${appName} 접근 승인 대기 중`,
      description: "관리자 승인 후 접속 가능합니다.",
      actionLabel: "",
    }
  }
  if (reason === "denied") {
    return {
      icon: ShieldX,
      title: `${appName} 접근이 제한되었습니다`,
      description: "필요한 경우 다시 권한을 신청하세요.",
      actionLabel: "다시 신청",
    }
  }
  return {
    icon: ShieldX,
    title: `${appName} 접근 권한이 없습니다`,
    description: "앱 사용이 필요한 경우 권한을 신청하세요.",
    actionLabel: "권한 신청",
  }
}

export function AppAccessGate({ children, scopeKey, appName }) {
  const { user, refresh, isRefreshing } = useAuth()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")
  const [statusMessage, setStatusMessage] = useState("")
  const [hasSubmittedRequest, setHasSubmittedRequest] = useState(false)
  const access = getAppAccess(user, scopeKey)
  const gateAccess = hasSubmittedRequest ? { ...access, reason: "pending", canRequest: false } : access

  if (!user) return null
  if (user.portal_access?.allowed && access?.allowed) return children

  const copy = getAccessCopy(gateAccess, appName)
  const Icon = copy.icon
  const canRequest = Boolean(gateAccess?.canRequest)
  const isBusy = isSubmitting || isRefreshing

  const handleRequest = async () => {
    if (!canRequest || isBusy) return

    setIsSubmitting(true)
    setErrorMessage("")
    setStatusMessage("")
    try {
      const result = await fetchJson(buildBackendUrl("/api/v1/account/access/request"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: scopeKey }),
      })
      if (!result.ok) {
        const error = result.data?.error
        setErrorMessage(error === "not_requestable" ? "이 권한은 신청할 수 없습니다." : "권한 신청을 저장하지 못했습니다.")
        return
      }
      setHasSubmittedRequest(result.data?.status === "pending")
      const didRefresh = await refresh()
      if (didRefresh) {
        setStatusMessage("권한 신청을 저장했습니다.")
      } else {
        setStatusMessage("권한 신청은 저장했습니다.")
        setErrorMessage("최신 접근 상태를 불러오지 못했습니다.")
      }
    } catch {
      setErrorMessage("권한 신청 중 오류가 발생했습니다.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 items-center justify-center overflow-y-auto bg-background px-6 py-10">
      <Card className="w-full max-w-md rounded-lg border bg-card shadow-sm" aria-labelledby="app-access-title">
        <CardHeader className="gap-3">
          <div className="flex size-10 items-center justify-center rounded-md border bg-muted text-muted-foreground">
            <Icon className="size-5" aria-hidden="true" />
          </div>
          <div className="space-y-2">
            <CardTitle id="app-access-title" className={gateAccess?.reason === "pending" ? "text-base text-primary" : "text-base"}>
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
            <div className="text-xs font-medium text-muted-foreground">권한 범위</div>
            <div className="mt-1 text-foreground">{scopeKey}</div>
          </div>
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
        <CardFooter className="gap-2">
          {canRequest ? (
            <Button className="flex-1" onClick={handleRequest} disabled={isBusy}>
              {isSubmitting ? <Spinner className="size-4" /> : <Send className="size-4" aria-hidden="true" />}
              {isSubmitting ? "신청 중" : copy.actionLabel}
            </Button>
          ) : null}
          <Button asChild variant={canRequest ? "outline" : "default"} className={canRequest ? "" : "flex-1"}>
            <Link to="/">
              <Home className="size-4" />
              홈으로 이동
            </Link>
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
