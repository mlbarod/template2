// 파일 경로: src/components/layout/AppLayout.jsx
import { useLocation } from "react-router-dom"

import { SidebarLayout } from "./SidebarLayout"

export function AppLayout({
  children,
  sidebar,
  providerKey,
  defaultOpen,
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
  paddingClassName = "px-4 pb-3",
  innerClassName = "mx-auto flex h-full w-full flex-col gap-4",
  insetClassName,
}) {
  const { pathname } = useLocation()
  const resolvedProviderKey = providerKey ?? pathname
  const resolvedDefaultOpen = defaultOpen ?? pathname !== "/"

  return (
    <SidebarLayout
      providerKey={resolvedProviderKey}
      defaultOpen={resolvedDefaultOpen}
      sidebar={sidebar}
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
      paddingClassName={paddingClassName}
      innerClassName={innerClassName}
      insetClassName={insetClassName}
    >
      {children}
    </SidebarLayout>
  )
}
