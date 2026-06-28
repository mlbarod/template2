const APP_ACCESS_RULES = [
  {
    appId: "home",
    appName: "Portal Home",
    matches: (pathname) => pathname === "/",
  },
  {
    appId: "appstore",
    appName: "Appstore",
    prefixes: ["/appstore"],
  },
  {
    appId: "line-dashboard",
    appName: "ESOP Dashboard",
    prefixes: ["/ESOP_Dashboard", "/esop_dashboard"],
  },
  {
    appId: "l3-spider",
    appName: "L3 Spider",
    prefixes: ["/l3_spider"],
  },
  {
    appId: "fdc-trend",
    appName: "FDC Trend",
    prefixes: ["/fdc_trend"],
  },
  {
    appId: "pm-spider",
    appName: "PM Spider",
    prefixes: ["/pm_spider"],
  },
  {
    appId: "teamstaff",
    appName: "Teamstaff",
    prefixes: ["/teamstaff"],
  },
  {
    appId: "observer",
    appName: "Observer",
    prefixes: ["/observer"],
  },
  {
    appId: "emails",
    appName: "Emails",
    prefixes: ["/emails"],
  },
  {
    appId: "voc",
    appName: "VoE",
    prefixes: ["/voc"],
  },
  {
    appId: "settings",
    appName: "Settings",
    prefixes: ["/settings"],
  },
  {
    appId: "assistant",
    appName: "Assistant",
    prefixes: ["/assistant"],
  },
  {
    appId: "access-stats",
    appName: "접속 현황",
    prefixes: ["/access-stats"],
  },
]

function normalizePathname(pathname) {
  return typeof pathname === "string" && pathname ? pathname : "/"
}

export function resolveAppAccessTarget(pathname) {
  const normalizedPathname = normalizePathname(pathname)
  return APP_ACCESS_RULES.find((rule) => {
    if (rule.matches?.(normalizedPathname)) return true
    return rule.prefixes?.some((prefix) =>
      normalizedPathname.toLowerCase().startsWith(prefix.toLowerCase()),
    )
  }) ?? null
}
