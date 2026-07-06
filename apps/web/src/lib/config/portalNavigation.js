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
      { title: "Appstore", href: "/appstore" },
      { title: "ESOP Dashboard", href: "/esop_dashboard" },
      { title: "Observer", href: "/observer" },
      { title: "TIP현황", href: "/ESOP_Dashboard/tip-status" },
      { title: "메일함", href: "/emails/inbox" },
      { title: "L0 Spider", href: "http://mem-etch-spider.samsungds.net:32603", external: true },
      { title: "L1 Spider", href: "https://atlas.samsungds.net/d/spider?mode=full", external: true },
      { title: "Defect Spider", href: "http://10.173.129.168:32600", external: true },
      { title: "L3 Spider(개발중)", href: "/l3_spider" },
      { title: "PM Spider(개발중)", href: "/pm_spider" },
      { title: "접속 현황", href: "/access-stats" },
      externalLink("PMx", "VITE_PORTAL_PMX_URL"),
    ]),
  },
  {
    title: "About Us",
    icon: BookOpenIcon,
    items: compactItems([
      { title: "Team", href: "/teamstaff" },
      externalLink("Etch MOSAIC", "VITE_PORTAL_MOSAIC_URL"),
      externalLink("Etch Confluence", "VITE_PORTAL_CONFLUENCE_URL"),
    ]),
  },
  {
    title: "Contacts",
    icon: MessageSquareIcon,
    items: [
      { title: "VoE", href: "/voc" },
    ],
  },
]
