import { useLocation } from "react-router-dom"

import { AppLayout } from "./AppLayout"
import { AppSidebar } from "./AppSidebar"
import { NavMain } from "./NavMain"

const APP_PREFIXES = ["/esop_dashboard", "/l0_spider", "/fdc_trend", "/emails", "/settings"]

function getNormalizedPath(value) {
  if (typeof value !== "string") return ""
  return value.split("?")[0].toLowerCase()
}

function matchesPrefix(item, prefix) {
  if (!item || !prefix) return false
  const itemUrl = getNormalizedPath(item.url)
  if (itemUrl.startsWith(prefix)) return true
  if (!Array.isArray(item.items)) return false
  return item.items.some((child) => getNormalizedPath(child?.url).startsWith(prefix))
}

export function AppShellLayout({
  children,
  navItems,
  sidebarHeader,
  sidebarSecondary,
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
  paddingClassName,
  innerClassName,
  insetClassName,
  providerKey,
  defaultOpen,
}) {
  const { pathname } = useLocation()
  const safeNavItems = Array.isArray(navItems) ? navItems : []
  const currentPrefix = APP_PREFIXES.find((prefix) => getNormalizedPath(pathname).startsWith(prefix))
  const resolvedNavItems = currentPrefix
    ? safeNavItems.filter((item) => matchesPrefix(item, currentPrefix))
    : safeNavItems
  const nav = <NavMain items={resolvedNavItems} />
  const sidebar = (
    <AppSidebar header={sidebarHeader ?? null} nav={nav} secondary={sidebarSecondary} />
  )

  return (
    <AppLayout
      sidebar={sidebar}
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
      paddingClassName={paddingClassName}
      innerClassName={innerClassName}
      insetClassName={insetClassName}
      providerKey={providerKey}
      defaultOpen={defaultOpen}
    >
      {children}
    </AppLayout>
  )
}
