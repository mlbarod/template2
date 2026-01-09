// 파일 경로: src/features/auth/components/AuthProvider.jsx
// 인증 전역 상태를 제공하는 React Context와 Provider입니다.
// - 여기서는 상태/비즈니스 로직만 담당하고,
// - 공용 가드 UI(RequireAuth 등)는 components 폴더, 페이지 전용 UI는 각 page 폴더에 둡니다.

import React, {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"

import { buildBackendUrl } from "@/lib/api"

import { DEFAULT_AUTH_CONFIG } from "../utils/authConfig"
import { fetchJson } from "../utils/fetchJson"
import { appendNextParam, buildNextUrl } from "../utils/url"
import { UserSdwtProdOnboardingDialog } from "./UserSdwtProdOnboardingDialog"
import { UserSdwtProdReconfirmDialog } from "./UserSdwtProdReconfirmDialog"

/**
 * 인증 사용자 타입 정의
 * @typedef {Object} AuthUser
 * @property {string} id
 * @property {string} [email]
 * @property {string} [username]
 * @property {boolean} [is_superuser]
 * @property {boolean} [is_staff]
 * @property {string[]} [roles]
 * @property {string | null} [user_sdwt_prod]
 * @property {string | null} [pending_user_sdwt_prod]
 * @property {boolean} [has_pending_affiliation]
 */

/**
 * 인증 설정 타입 정의
 * @typedef {Object} AuthConfig
 * @property {string} loginUrl
 * @property {string} logoutUrl
 * @property {string} frontendRedirect
 * @property {number | null | undefined} [sessionMaxAgeSeconds]
 * @property {boolean | undefined} [providerConfigured]
 */

/**
 * 인증 컨텍스트 값 타입 정의
 * @typedef {Object} AuthContextValue
 * @property {AuthUser | null} user
 * @property {boolean} isLoading
 * @property {(options?: { next?: string }) => Promise<{ method: "redirect"; url?: string }>} login
 * @property {() => Promise<void>} logout
 * @property {() => Promise<void>} refresh
 * @property {AuthConfig} config
 */

/**
 * 타입: 인증 컨텍스트
 * @type {React.Context<AuthContextValue | undefined>}
 */
export const AuthContext = createContext(undefined)

const POST_LOGIN_ATTENTION_TOOLTIP_KEY = "auth:post-login-attention-tooltip"

function getSessionRefreshIntervalMs(sessionMaxAgeSeconds) {
  const rawSeconds = Number(sessionMaxAgeSeconds)
  if (!Number.isFinite(rawSeconds) || rawSeconds <= 0) {
    return 0
  }
  const halfLifeMs = Math.floor(rawSeconds * 1000 * 0.5)
  return Math.max(60_000, halfLifeMs)
}

function getFocusCooldownMs(sessionRefreshIntervalMs) {
  if (sessionRefreshIntervalMs > 0) {
    return Math.max(30_000, Math.min(sessionRefreshIntervalMs / 2, 300_000))
  }
  return 30_000
}

/**
 * AuthProvider
 * ---------------------------------------------------------------------------
 * - 앱 전역에서 인증 상태를 공유하도록 Context Provider를 제공합니다.
 * - fetchJson, buildNextUrl 등의 유틸은 utils/ 폴더로 분리해 가독성을 높였습니다.
 * - 중요한 포인트마다 한글 주석을 추가해 초보자도 흐름을 따라가기 쉽게 했습니다.
 */
export function AuthProvider({ children }) {
  /**
   * 타입: 사용자 상태
   * @type {[AuthUser|null, React.Dispatch<React.SetStateAction<AuthUser|null>>]}
   */
  const [user, setUser] = useState(null)
  /**
   * 타입: 인증 설정 상태
   * @type {[AuthConfig, React.Dispatch<React.SetStateAction<AuthConfig>>]}
   */
  const [config, setConfig] = useState(DEFAULT_AUTH_CONFIG)
  const [isLoading, setIsLoading] = useState(true)

  const mountedRef = useRef(false)
  const lastRefreshRef = useRef(0)

  // 세션 만료 시간의 절반 정도에 맞춰 자동 새로고침 주기를 계산합니다.
  const sessionRefreshIntervalMs = getSessionRefreshIntervalMs(config.sessionMaxAgeSeconds)

  // 탭에 다시 포커스될 때 너무 자주 호출되지 않도록 쿨다운을 둡니다.
  const focusCooldownMs = getFocusCooldownMs(sessionRefreshIntervalMs)

  // 컴포넌트가 언마운트된 뒤 setState가 호출되지 않도록 플래그를 유지합니다.
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  /** 서버에서 인증 설정을 로드 (/api/v1/auth/config) */
  const loadConfig = useCallback(async () => {
    try {
      const endpoint = buildBackendUrl("/api/v1/auth/config")
      const result = await fetchJson(endpoint, { cache: "no-store" })
      if (result.ok && result.data && mountedRef.current) {
        setConfig((prev) => ({ ...prev, ...(/** 타입: Partial<AuthConfig> @type {Partial<AuthConfig>} */ (result.data)) }))
      }
    } catch {
      // 설정 로드 실패 시 기본값을 그대로 유지합니다.
    }
  }, [])

  /** 현재 사용자 정보를 가져오는 함수 (/api/v1/auth/me) */
  const loadUser = useCallback(async () => {
    if (mountedRef.current) setIsLoading(true)
    try {
      const endpoint = buildBackendUrl("/api/v1/auth/me")
      const result = await fetchJson(endpoint, { cache: "no-store" })
      if (!mountedRef.current) return
      if (result.ok && result.data) {
        setUser(/** 타입: AuthUser @type {AuthUser} */ (result.data))
      } else {
        setUser(null)
      }
    } catch {
      if (mountedRef.current) setUser(null)
    } finally {
      if (mountedRef.current) setIsLoading(false)
      lastRefreshRef.current = Date.now()
    }
  }, [])

  // 최초 마운트 시 설정과 사용자 정보를 순차적으로 로드합니다.
  useEffect(() => {
    loadConfig()
    loadUser()
  }, [loadConfig, loadUser])

  // 창 포커스가 돌아오면 일정 주기마다 사용자 정보를 새로고침합니다.
  useEffect(() => {
    if (typeof window === "undefined") return undefined

    const onFocus = () => {
      const now = Date.now()
      if (now - lastRefreshRef.current < focusCooldownMs) {
        return
      }
      lastRefreshRef.current = now
      loadUser()
    }

    window.addEventListener("focus", onFocus)
    return () => window.removeEventListener("focus", onFocus)
  }, [focusCooldownMs, loadUser])

  // 세션 만료 시간에 맞춰 주기적으로 사용자 정보를 새로고침합니다.
  useEffect(() => {
    if (typeof window === "undefined") return undefined
    if (!sessionRefreshIntervalMs) return undefined

    const timer = window.setInterval(() => {
      loadUser()
    }, sessionRefreshIntervalMs)

    return () => window.clearInterval(timer)
  }, [loadUser, sessionRefreshIntervalMs])

  /** 로그인: next 파라미터를 안전하게 붙여 백엔드 로그인 페이지로 이동 */
  const login = useCallback(
    async (options = {}) => {
      const nextPath = typeof options?.next === "string" ? options.next : undefined
      const nextAbsolute = buildNextUrl(nextPath, config.frontendRedirect)
      const rawLoginUrl = config.loginUrl || "/api/v1/auth/login"
      const absoluteLoginUrl = rawLoginUrl.startsWith("http") ? rawLoginUrl : buildBackendUrl(rawLoginUrl)
      const target = appendNextParam(absoluteLoginUrl, nextAbsolute)

      if (typeof window !== "undefined") {
        try {
          window.sessionStorage.setItem(POST_LOGIN_ATTENTION_TOOLTIP_KEY, "1")
        } catch {
          // storage 접근 실패 시 무시
        }
        window.location.href = target
      }

      return { method: "redirect", url: target }
    },
    [config],
  )

  /** 로그아웃: 서버에 로그아웃을 요청하고, 받은 redirect URL로 이동 */
  const logout = useCallback(async () => {
    let redirectTarget = config.logoutUrl || "/api/v1/auth/logout"
    try {
      const endpoint = buildBackendUrl("/api/v1/auth/logout")
      const result = await fetchJson(endpoint, { method: "POST" })
      if (result?.data && typeof result.data === "object" && typeof result.data.logoutUrl === "string") {
        redirectTarget = result.data.logoutUrl
      }
    } finally {
      if (mountedRef.current) setUser(null)
      if (typeof window !== "undefined") {
        try {
          window.sessionStorage.removeItem(POST_LOGIN_ATTENTION_TOOLTIP_KEY)
        } catch {
          // storage 접근 실패 시 무시
        }
      }
      if (typeof window !== "undefined" && redirectTarget) {
        window.location.href = redirectTarget
      }
    }
  }, [config.logoutUrl])

  // Context에서 제공할 값들을 묶어 한 번에 전달합니다.
  const value = useMemo(
    () => ({
      user,
      isLoading,
      login,
      logout,
      refresh: loadUser,
      config,
    }),
    [user, isLoading, login, logout, loadUser, config],
  )

  return (
    <AuthContext.Provider value={value}>
      {children}
      <UserSdwtProdOnboardingDialog user={user} onCompleted={loadUser} />
      <UserSdwtProdReconfirmDialog user={user} onCompleted={loadUser} />
    </AuthContext.Provider>
  )
}
