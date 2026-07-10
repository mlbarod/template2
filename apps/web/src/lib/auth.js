// src/lib/auth.js
// 인증과 관련된 전역 훅/컴포넌트를 lib 경로로 노출해 feature 간 의존성을 줄입니다.
export { AuthProvider, RequireAuth, useAuth, AuthAutoLoginGate, PortalAccessGate } from "@/features/auth"
