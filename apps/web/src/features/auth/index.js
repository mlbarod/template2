// 파일 경로: src/features/auth/index.js
// 인증 기능에서 노출할 모듈들을 한 곳에 모았습니다.
// 다른 영역에서는 '@/features/auth' 경로만 기억하면 됩니다.

export { AuthProvider } from "./components/AuthProvider"
export { useAuth } from "./hooks/useAuth"
export { RequireAuth } from "./components/RequireAuth"
export { AuthAutoLoginGate } from "./components/AuthAutoLoginGate"
export { PortalAccessGate } from "./components/PortalAccessGate"
export { authRoutes } from "./routes"
