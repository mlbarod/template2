import {
  BookOpenIcon,
  LayoutGridIcon,
  MessageSquareIcon,
} from "lucide-react"

function readEnvValue(key) {
  if (typeof import.meta !== "undefined" && import.meta.env && key in import.meta.env) {
    const value = import.meta.env[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  if (typeof process !== "undefined" && process.env && key in process.env) {
    const value = process.env[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return ""
}

function externalLink(title, envKey) {
  const href = readEnvValue(envKey)
  return href ? { title, href, external: true } : null
}

function compactItems(items) {
  return items.filter(Boolean)
}

export const portalNavigationItems = [
  {
    title: "Apps",
    icon: LayoutGridIcon,
    items: compactItems([
      { title: "Appstore", href: "/appstore", appScope: "appstore" },
      { title: "ESOP Dashboard", href: "/esop_dashboard", appScope: "line-dashboard" },
      { title: "Observer", href: "/observer", appScope: "observer" },
      {
        title: "TIP현황",
        href: "/ESOP_Dashboard/tip-status",
        requiredAppScopes: ["line-dashboard", "observer"],
      },
      { title: "메일함", href: "/emails/inbox", appScope: "emails" },
      {
        title: "Spider",
        href: "/spider",
        anyAppScopes: ["l0-spider", "l1-spider", "l3-spider", "pm-spider", "tttm-spider"],
      },
      { title: "접속 현황", href: "/access-stats", appScope: "access-stats" },
      externalLink("PMx", "VITE_PORTAL_PMX_URL"),
    ]),
  },
  {
    title: "About Us",
    icon: BookOpenIcon,
    items: compactItems([
      { title: "Team", href: "/teamstaff", appScope: "teamstaff" },
      externalLink("Etch MOSAIC", "VITE_PORTAL_MOSAIC_URL"),
      externalLink("Etch Confluence", "VITE_PORTAL_CONFLUENCE_URL"),
    ]),
  },
  {
    title: "Contacts",
    icon: MessageSquareIcon,
    items: [
      { title: "VoE", href: "/voc", appScope: "voc" },
    ],
  },
]
