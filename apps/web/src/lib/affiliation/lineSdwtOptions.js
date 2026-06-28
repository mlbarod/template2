import { useQuery } from "@tanstack/react-query"

import { buildBackendUrl } from "@/lib/api"

const LINE_SDWT_OPTIONS_QUERY_KEY = ["affiliation", "line-sdwt-options"]
const LINE_DASHBOARD_LINE_SDWT_OPTIONS_QUERY_KEY = ["line-dashboard", "line-sdwt-options"]

function normalizeLineId(value) {
  if (value === null || value === undefined) return ""
  return typeof value === "string" ? value.trim() : String(value).trim()
}

function normalizeUserSdwtProd(value) {
  if (value === null || value === undefined) return ""
  return typeof value === "string" ? value.trim() : String(value).trim()
}

function normalizeLineRows(rawLines) {
  if (!Array.isArray(rawLines)) return []

  return rawLines
    .map((line) => {
      const lineId = normalizeLineId(line?.lineId)
      if (!lineId) return null

      const rawUserSdwtProds = Array.isArray(line?.userSdwtProds) ? line.userSdwtProds : []
      const userSdwtProds = rawUserSdwtProds
        .map((value) => normalizeUserSdwtProd(value))
        .filter(Boolean)

      if (userSdwtProds.length === 0) return null

      return {
        lineId,
        userSdwtProds: Array.from(new Set(userSdwtProds)).sort(),
      }
    })
    .filter(Boolean)
}

function normalizeUserSdwtProds(rawUserSdwtProds) {
  if (!Array.isArray(rawUserSdwtProds)) return []
  const normalized = rawUserSdwtProds
    .map((value) => normalizeUserSdwtProd(value))
    .filter(Boolean)
  return Array.from(new Set(normalized)).sort()
}

function toLineOptions(payload) {
  const rawLines = Array.isArray(payload?.lines) ? payload.lines : []
  const normalized = rawLines
    .map((line) => (typeof line?.lineId === "string" ? line.lineId.trim() : ""))
    .filter(Boolean)

  return Array.from(new Set(normalized))
}

async function fetchLineSdwtOptions(endpointPath) {
  const endpoint = buildBackendUrl(endpointPath)

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 5_000)

  let response

  try {
    response = await fetch(endpoint, { credentials: "include", signal: controller.signal })
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Timed out while loading line SDWT options")
    }

    throw error
  } finally {
    clearTimeout(timeoutId)
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const message =
      typeof payload?.error === "string"
        ? payload.error
        : `Failed to load line SDWT options (${response.status})`
    throw new Error(message)
  }

  const payload = await response.json().catch(() => ({}))

  return {
    lines: normalizeLineRows(payload?.lines),
    userSdwtProds: normalizeUserSdwtProds(payload?.userSdwtProds),
  }
}

export function getLineSdwtOptions() {
  return fetchLineSdwtOptions("/api/v1/account/line-sdwt-options")
}

export function getLineDashboardLineSdwtOptions() {
  return fetchLineSdwtOptions("/api/v1/line-dashboard/line-sdwt-options")
}

export function useLineSdwtOptionsQuery(options = {}) {
  const { enabled = true } = options

  return useQuery({
    queryKey: LINE_SDWT_OPTIONS_QUERY_KEY,
    queryFn: getLineSdwtOptions,
    refetchOnWindowFocus: false,
    enabled,
  })
}

export function useLineDashboardLineSdwtOptionsQuery(options = {}) {
  const { enabled = true } = options

  return useQuery({
    queryKey: LINE_DASHBOARD_LINE_SDWT_OPTIONS_QUERY_KEY,
    queryFn: getLineDashboardLineSdwtOptions,
    refetchOnWindowFocus: false,
    enabled,
  })
}

export function useLineOptionsQuery(options = {}) {
  const { enabled = true } = options

  return useQuery({
    queryKey: LINE_SDWT_OPTIONS_QUERY_KEY,
    queryFn: getLineSdwtOptions,
    select: toLineOptions,
    refetchOnWindowFocus: false,
    enabled,
  })
}

export function buildLineSwitcherOptions(lineOptions) {
  const options = Array.isArray(lineOptions) ? lineOptions : []

  return options
    .map((lineId) => (typeof lineId === "string" ? lineId.trim() : ""))
    .filter(Boolean)
    .map((lineId) => ({ id: lineId, label: lineId, lineId }))
}
