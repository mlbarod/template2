// 파일 경로: src/lib/config/navigationConfig.js
import {
  Activity,
  BarChart3,
  Mail,
  Send,
  Settings,
  SquareTerminal,
  Users,
} from "lucide-react"

/**
 * 내비게이션 기본 구성.
 * - scope === "line" 인 메뉴는 라인 ID를 앞에 붙여야 하므로 주의.
 * - 실제 데이터 연동 시 이 구조를 그대로 유지하면서 값만 교체하면 된다.
 */
const LINE_DASHBOARD_GROUP = Object.freeze({
  key: "line-dashboard",
  title: "Line Dashboard",
  url: "/ESOP_Dashboard",
  icon: SquareTerminal,
  isActive: true,
  scope: "line",
  items: [
    {
      title: "Status",
      url: "/ESOP_Dashboard/status",
      scope: "line",
    },
    {
      title: "TIP현황",
      url: "/ESOP_Dashboard/tip-status",
      scope: "line",
    },
    {
      title: "History",
      url: "/ESOP_Dashboard/history",
      scope: "line",
    },
    {
      title: "알림 Step설정",
      url: "/ESOP_Dashboard/settings/notification",
      scope: "line",
    },
    {
      title: "수신 설정",
      url: "/ESOP_Dashboard/settings/recipients",
      scope: "line",
    },
    {
      title: "System현황",
      url: "/ESOP_Dashboard/overview",
      icon: BarChart3,
      scope: "global",
    },
  ],
})

const EMAIL_NAV_ITEMS = Object.freeze([
  {
    title: "Inbox",
    url: "/emails/inbox",
    icon: Mail,
    scope: "global",
  },
  {
    title: "Sent",
    url: "/emails/sent",
    icon: Send,
    scope: "global",
  },
  {
    title: "Members",
    url: "/emails/members",
    icon: Users,
    scope: "global",
  },
])

const EMAILS_GROUP_BASE = Object.freeze({
  key: "emails",
  title: "Emails",
  url: "/emails/inbox",
  icon: Mail,
  isActive: true,
  scope: "global",
  items: EMAIL_NAV_ITEMS,
})

const FDC_TREND_GROUP = Object.freeze({
  key: "fdc-trend",
  title: "L0 Spider",
  url: "/fdc_trend",
  icon: Activity,
  isActive: true,
  scope: "global",
  items: [
    {
      title: "이상 FDC Trend",
      url: "/fdc_trend",
      scope: "global",
    },
  ],
})

const SETTINGS_NAV_ITEMS = Object.freeze([
  {
    title: "Account",
    url: "/settings/account",
    scope: "global",
  },
  {
    title: "Members",
    url: "/settings/members",
    scope: "global",
  },
])

const SETTINGS_GROUP = Object.freeze({
  key: "settings",
  title: "Settings",
  url: "/settings/account",
  icon: Settings,
  isActive: true,
  scope: "global",
  items: SETTINGS_NAV_ITEMS,
})

function normalizeMailbox(value) {
  return typeof value === "string" ? value.trim() : ""
}

function buildMailboxUrl(mailbox) {
  const trimmed = normalizeMailbox(mailbox)
  if (!trimmed) return "/emails/inbox"
  return `/emails/inbox?user_sdwt_prod=${encodeURIComponent(trimmed)}`
}

function buildMembersUrl(mailbox) {
  const trimmed = normalizeMailbox(mailbox)
  if (!trimmed) return "/emails/members"
  return `/emails/members?user_sdwt_prod=${encodeURIComponent(trimmed)}`
}

export const NAVIGATION_CONFIG = Object.freeze({
  user: {
    name: "shadcn",
    email: "m@example.com",
    avatar: "/avatars/shadcn.jpg",
  },
  navMain: [LINE_DASHBOARD_GROUP, FDC_TREND_GROUP, EMAILS_GROUP_BASE, SETTINGS_GROUP],
  projects: [
    // 예시: 프로젝트 그룹
    // {
    //   name: "디자인 엔지니어링",
    //   url: "#", // 링크
    //   icon: Frame, // 아이콘
    // },
  ],
})

export function buildNavigationConfig({ mailbox, disableEmailMembers = false } = {}) {
  const trimmedMailbox = normalizeMailbox(mailbox)
  if (!trimmedMailbox) return NAVIGATION_CONFIG

  const inboxUrl = buildMailboxUrl(trimmedMailbox)
  const membersUrl = buildMembersUrl(trimmedMailbox)
  const membersItem = disableEmailMembers
    ? { ...EMAIL_NAV_ITEMS[2], url: membersUrl, disabled: true }
    : { ...EMAIL_NAV_ITEMS[2], url: membersUrl }

  const emailsGroup = {
    ...EMAILS_GROUP_BASE,
    url: inboxUrl,
    items: [
      { ...EMAIL_NAV_ITEMS[0], url: inboxUrl },
      EMAIL_NAV_ITEMS[1],
      membersItem,
    ],
  }

  return {
    ...NAVIGATION_CONFIG,
    navMain: NAVIGATION_CONFIG.navMain.map((item) =>
      item?.key === EMAILS_GROUP_BASE.key ? emailsGroup : item,
    ),
  }
}
