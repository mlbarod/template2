// src/features/auth/components/AuthAutoLoginGate.jsx
// 전역적으로 "로그인되지 않았다면 즉시 SSO 로그인"을 시도하는 가드 레이아웃입니다.
// - 모든 라우트 위에 배치해 어디서 진입해도 동일한 경험을 제공합니다.

import { useEffect, useRef } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { Spinner } from "@/components/ui/spinner"

import { CenteredPage } from "./CenteredPage"
import { useAuth } from "../hooks/useAuth"

export function AuthAutoLoginGate() {
  const { user, isLoading, login, config } = useAuth()
  const location = useLocation()
  const autoLoginTriggeredRef = useRef(false)

  // 현재 경로 + 쿼리를 next 파라미터로 사용해 돌아올 위치를 보존합니다.
  const nextPath = `${location?.pathname || "/"}${location?.search || ""}`

  useEffect(() => {
    if (autoLoginTriggeredRef.current) return
    if (isLoading) return
    if (user) return
    if (config?.providerConfigured === false) return

    autoLoginTriggeredRef.current = true
    login({ next: nextPath })
  }, [config?.providerConfigured, isLoading, login, location.pathname, location.search, nextPath, user])

  if (!user) {
    const statusMessage = config?.providerConfigured === false
      ? "SSO 설정을 확인할 수 없습니다. 관리자에게 문의하세요."
      : "인증 상태를 확인하는 중입니다."

    return (
      <CenteredPage>
        <div className="flex flex-col items-center gap-3 text-center" role="status" aria-live="polite">
          {config?.providerConfigured === false ? null : <Spinner className="size-8 text-primary" />}
          <p className="text-sm text-muted-foreground">{statusMessage}</p>
        </div>
      </CenteredPage>
    )
  }

  return <Outlet />
}
