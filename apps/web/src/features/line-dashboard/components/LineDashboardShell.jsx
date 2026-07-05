// 파일 경로: src/features/line-dashboard/components/LineDashboardShell.jsx
import { useEffect } from "react"
import { Outlet } from "react-router-dom"

import { TeamSwitcher } from "@/components/common"
import { AppShellLayout } from "@/components/layout"
import { RequireAuth, useAuth } from "@/lib/auth"
import { buildNavigationConfig } from "@/lib/config/navigationConfig"
import {
  ActiveLineProvider,
  DepartmentProvider,
  buildLineSwitcherOptions,
  useLineSwitcher,
} from "@/lib/affiliation"

import { NavProjects } from "./NavProjects"
import { useLineOptionsQuery } from "../hooks/useLineOptionsQuery"

export function LineDashboardShell({
  contentMaxWidthClass = "max-w-10xl",
  scrollAreaClassName = "overflow-y-auto",
}) {
  return (
    <RequireAuth>
      <LineDashboardShellContent
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      />
    </RequireAuth>
  )
}

function LineDashboardShellContent({ contentMaxWidthClass, scrollAreaClassName }) {
  const { user } = useAuth()
  const {
    data: lineOptions = [],
    isError,
    error,
  } = useLineOptionsQuery({
    preferredUserSdwtProd:
      typeof user?.user_sdwt_prod === "string" ? user.user_sdwt_prod.trim() : "",
  })

  useEffect(() => {
    if (isError) {
      console.warn("Failed to load line options", error)
    }
  }, [isError, error])

  const navigation = buildNavigationConfig({ includeSuperuser: Boolean(user?.is_superuser) })

  return (
    <DepartmentProvider>
      <ActiveLineProvider lineOptions={lineOptions}>
        <LineDashboardShellLayout
          navigation={navigation}
          lineOptions={lineOptions}
          contentMaxWidthClass={contentMaxWidthClass}
          scrollAreaClassName={scrollAreaClassName}
        />
      </ActiveLineProvider>
    </DepartmentProvider>
  )
}

function LineDashboardShellLayout({ navigation, lineOptions, contentMaxWidthClass, scrollAreaClassName }) {
  const { activeLineId, onSelect } = useLineSwitcher()
  const lineSwitcherOptions = buildLineSwitcherOptions(lineOptions)

  return (
    <AppShellLayout
      navItems={navigation.navMain}
      sidebarHeader={(
        <TeamSwitcher
          options={lineSwitcherOptions}
          activeId={activeLineId}
          onSelect={onSelect}
        />
      )}
      sidebarSecondary={<NavProjects projects={navigation.projects} />}
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
    >
      <Outlet />
    </AppShellLayout>
  )
}
