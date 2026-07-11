// 파일 경로: src/lib/theme/themeProvider.jsx
// 프레임워크 의존을 없앤 커스텀 ThemeProvider (라이트/다크 + 포인트 컬러 모두 관리)

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

const THEME_STORAGE_KEY = "app-theme"
const COLOR_STORAGE_KEY = "app-theme-color"
const DEFAULT_THEME = "system"
const DEFAULT_COLOR = "sky"
const VALID_THEMES = new Set(["light", "dark", "system"])
const VALID_COLORS = new Set([
  "violet",
  "emerald",
  "amber",
  "sky",
  "rose",
  "gray",
  "indigo",
  "teal",
  "lime",
  "cyan",
])

function readStoredTheme(defaultTheme) {
  if (typeof window === "undefined") return defaultTheme
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (stored && VALID_THEMES.has(stored)) {
      return stored
    }
  } catch {
    // storage 접근 실패 시 무시
  }
  return defaultTheme
}

function readStoredColor(defaultColor) {
  if (typeof window === "undefined") return defaultColor
  try {
    const stored = window.localStorage.getItem(COLOR_STORAGE_KEY)
    if (stored && VALID_COLORS.has(stored)) {
      return stored
    }
  } catch {
    // storage 접근 실패 시 무시
  }
  return defaultColor
}

function getSystemTheme() {
  if (typeof window === "undefined") return "light"
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

const ThemeContext = createContext(null)

export function ThemeProvider({ children, defaultTheme = DEFAULT_THEME, defaultColor = DEFAULT_COLOR }) {
  const [systemTheme, setSystemTheme] = useState(() => getSystemTheme())
  const [theme, setThemeState] = useState(() => readStoredTheme(defaultTheme))
  const [colorScheme, setColorSchemeState] = useState(() => readStoredColor(defaultColor))

  // 운영체제 테마 변경 감지
  useEffect(() => {
    if (typeof window === "undefined") return undefined
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    const handler = (event) => {
      setSystemTheme(event.matches ? "dark" : "light")
    }
    handler(media)
    media.addEventListener("change", handler)
    return () => media.removeEventListener("change", handler)
  }, [])

  // HTML root 클래스(light/dark) 동기화
  useEffect(() => {
    if (typeof document === "undefined") return
    const root = document.documentElement
    const resolvedTheme = theme === "system" ? systemTheme : theme
    root.classList.remove("light", "dark")
    root.classList.add(resolvedTheme)
  }, [theme, systemTheme])

  // 포인트 컬러는 data 속성으로 노출해 CSS 토큰을 덮어쓰기 쉽게 만듭니다.
  useEffect(() => {
    if (typeof document === "undefined") return
    document.documentElement.dataset.themeColor = colorScheme || DEFAULT_COLOR
  }, [colorScheme])

  const setTheme = useCallback((nextTheme) => {
    setThemeState((current) => {
      const normalized = VALID_THEMES.has(nextTheme) ? nextTheme : current
      if (typeof window !== "undefined") {
        try {
          window.localStorage.setItem(THEME_STORAGE_KEY, normalized)
        } catch {
          // storage 실패는 무시
        }
      }
      return normalized
    })
  }, [])

  const setColorScheme = useCallback((nextColor) => {
    setColorSchemeState((current) => {
      const normalized = VALID_COLORS.has(nextColor) ? nextColor : current
      if (typeof window !== "undefined") {
        try {
          window.localStorage.setItem(COLOR_STORAGE_KEY, normalized)
        } catch {
          // storage 실패는 무시
        }
      }
      return normalized
    })
  }, [])

  const contextValue = useMemo(
    () => ({
      theme,
      setTheme,
      systemTheme,
      colorScheme,
      setColorScheme,
    }),
    [theme, setTheme, systemTheme, colorScheme, setColorScheme]
  )

  return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider")
  }
  return context
}
