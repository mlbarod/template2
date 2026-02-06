// 파일 경로: src/components/common/NavUser.jsx
import { useNavigate } from "react-router-dom"
import { BadgeCheck, Bell, ChevronsUpDown, LogOut, MessageSquare } from "lucide-react"

import { useAuth } from "@/lib/auth"
import { buildProfileImageUrl, resolveProfileAvatarId } from "@/lib/profileImage"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

/* -----------------------------------------------------------------------------
 * 유틸: 사용자 표기 처리
 * ---------------------------------------------------------------------------*/

/** 이름에서 머리글자 한 글자 추출: '홍길동' -> 'ㅎ', 'LINE-01' -> 'L' 등 */
function getInitial(name) {
  if (!name) return "?" // 이름이 비어있을 때 안전 폴백
  const trimmed = String(name).trim()
  if (!trimmed) return "?"
  const parts = trimmed.split(/[\s-_]+/).filter(Boolean)
  const firstChunk = parts[0] || trimmed
  return firstChunk[0]?.toUpperCase() || "?"
}

/** 다양한 형태의 사용자 입력을 화면 렌더에 필요한 구조로 정규화 */
function normalizeUser(u) {
  if (!u || typeof u !== "object") return null
  const name = u.username ?? u.displayName ?? ""
  const email = u.email ?? ""
  const avatarid = resolveProfileAvatarId(u)
  // name/email 둘 다 없으면 렌더 의미가 낮으므로 null 처리
  if (!name && !email) return null
  return { name, email, avatarid }
}

/* -----------------------------------------------------------------------------
 * 컴포넌트
 * ---------------------------------------------------------------------------*/

/**
 * NavUser
 * - 사이드바 하단(또는 상단)에 표시되는 사용자 아바타 + 사용자 메뉴
 * - 클릭 핸들러는 props 콜백으로 주입 가능 (미제공 시 동작 없음)
 *
 * @param {Object} props
 * @param {Object} props.user               - 사용자 객체 { username, email, avatarid } (느슨히 수용, normalizeUser에서 정규화)
 * @param {Function} [props.onAccount]      - "계정" 클릭 콜백
 * @param {Function} [props.onVoc]          - "VOC" 클릭 콜백
 * @param {Function} [props.onNotifications]- "알림" 클릭 콜백
 * @param {Function} [props.onLogout]       - "로그아웃" 클릭 콜백
 * @param {Function} [props.onBilling]      - (호환성용) 구 설정 핸들러
 */
export function NavUser({
  user,
  onAccount = () => {},
  onVoc,
  onNotifications = () => {},
  onLogout,
  onBilling,
}) {
  const { isMobile } = useSidebar()
  const navigate = useNavigate()
  const { user: sessionUser, isLoading, logout } = useAuth()

  const handleLogout = () => {
    if (typeof onLogout === "function") {
      onLogout()
      return
    }

    logout()
      .catch(() => {})
      .finally(() => {
        navigate("/login")
      })
  }

  const handleVoc = () => {
    if (typeof onVoc === "function") {
      onVoc()
      return
    }
    if (typeof onBilling === "function") {
      onBilling()
      return
    }
    navigate("/voc")
  }

  // 사용자 입력 정규화 (표시 가능한 값이 없으면 숨김)
  const normalized = normalizeUser(sessionUser || user)

  if (isLoading) {
    return null
  }
  if (!normalized) return null

  const { name, email, avatarid } = normalized
  const initial = getInitial(name || email || "U") // 이름 없으면 이메일에서라도 생성
  const avatarSrc = buildProfileImageUrl(avatarid)

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          {/* 트리거: 아바타 + 이름/이메일 표시 */}
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              aria-label="사용자 메뉴 열기"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="h-8 w-8 rounded-full">
                {/* 아바타 이미지 로딩 실패 시 아바타 폴백(AvatarFallback)이 자동으로 노출 */}
                <AvatarImage src={avatarSrc || undefined} alt={name || email || "User avatar"} />
                <AvatarFallback className="rounded-full">{initial}</AvatarFallback>
              </Avatar>

              <div className="grid flex-1 text-left text-sm leading-tight">
                {/* 이름/이메일은 길어질 수 있어 말줄임 처리 */}
                {name ? <span className="truncate font-medium">{name}</span> : null}
                {email ? <span className="truncate text-xs">{email}</span> : null}
              </div>

              <ChevronsUpDown className="ml-auto size-4" aria-hidden="true" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>

          {/* 드롭다운: 사용자 카드 + 메뉴 그룹들 */}
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            {/* 상단 사용자 카드(간단 요약) */}
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="h-8 w-8 rounded-full">
                  <AvatarImage src={avatarSrc || undefined} alt={name || email || "User avatar"} />
                  <AvatarFallback className="rounded-full">{initial}</AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  {name ? <span className="truncate font-medium">{name}</span> : null}
                  {email ? <span className="truncate text-xs">{email}</span> : null}
                </div>
              </div>
            </DropdownMenuLabel>

            <DropdownMenuSeparator />

            {/* 업그레이드 섹션: 필요 없으면 상위에서 onUpgrade를 전달하지 않고 숨기고 싶다면 아래 매핑 방식으로 제어 가능 */}
            {/* 예시: 업그레이드 메뉴 그룹
            <DropdownMenuGroup>
              <DropdownMenuItem onSelect={onUpgrade}>
                <Sparkles className="mr-2 size-4" aria-hidden="true" />
                프로로 업그레이드
              </DropdownMenuItem>
            </DropdownMenuGroup> */}

            <DropdownMenuSeparator />

            {/* 계정 관련 섹션 */}
            <DropdownMenuGroup>
              <DropdownMenuItem onSelect={onAccount}>
                <BadgeCheck className="mr-2 size-4" aria-hidden="true" />
                Account
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={handleVoc}>
                <MessageSquare className="mr-2 size-4" aria-hidden="true" />
                VOC
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={onNotifications}>
                <Bell className="mr-2 size-4" aria-hidden="true" />
                Notifications
              </DropdownMenuItem>
            </DropdownMenuGroup>

            <DropdownMenuSeparator />

            {/* 로그아웃 */}
            <DropdownMenuItem onSelect={handleLogout}>
              <LogOut className="mr-2 size-4" aria-hidden="true" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
