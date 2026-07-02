import { useMemo } from "react"
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query"

import {
  commitManualAppAccessStats,
  fetchAppAccessStats,
  previewManualAppAccessStats,
  syncExternalAppUsageStats,
} from "../api/accessStatsApi"

export const accessStatsQueryKeys = {
  appAccessStats: (params) => ["access-stats", "app-access", params],
}

const MAX_APP_ACCESS_STATS_QUERY_DAYS = 90
const APP_ACCESS_STATS_STALE_TIME_MS = 5 * 60 * 1000
const APP_ACCESS_STATS_GC_TIME_MS = 30 * 60 * 1000

function parseIsoDate(value) {
  if (typeof value !== "string") return null
  const [year, month, day] = value.split("-").map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function formatIsoDate(value) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const day = String(value.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function addDays(value, days) {
  const next = new Date(value)
  next.setDate(next.getDate() + days)
  return next
}

function diffDays(from, to) {
  const dayMs = 24 * 60 * 60 * 1000
  return Math.round((to.getTime() - from.getTime()) / dayMs) + 1
}

function buildAppAccessStatsQueryChunks(params = {}) {
  const fromDate = parseIsoDate(params.from)
  const toDate = parseIsoDate(params.to)
  if (!fromDate || !toDate || fromDate > toDate) return [params]
  if (diffDays(fromDate, toDate) <= MAX_APP_ACCESS_STATS_QUERY_DAYS) return [params]

  const chunks = []
  let cursorEnd = toDate
  while (cursorEnd >= fromDate) {
    const chunkStart = new Date(Math.max(addDays(cursorEnd, -(MAX_APP_ACCESS_STATS_QUERY_DAYS - 1)).getTime(), fromDate.getTime()))
    chunks.push({
      ...params,
      from: formatIsoDate(chunkStart),
      to: formatIsoDate(cursorEnd),
    })
    cursorEnd = addDays(chunkStart, -1)
  }
  return chunks.reverse()
}

function mergeSourceType(left, right) {
  if (!left) return right || ""
  if (!right || left === right) return left
  return "mixed"
}

function mergeSourceName(left, right) {
  if (!left) return right || ""
  if (!right || left === right) return left
  return "mixed"
}

function mergeLastAccessedAt(left, right) {
  if (!left) return right || null
  if (!right) return left
  return left > right ? left : right
}

function mergeAppRows(payloads) {
  const rows = new Map()
  payloads.forEach((payload) => {
    ;(payload?.apps ?? []).forEach((app) => {
      const key = app.appId || app.appName || "unknown"
      const current = rows.get(key) ?? {
        ...app,
        appId: key,
        accessCount: 0,
        uniqueUserCount: 0,
      }
      current.appName = current.appName || app.appName || key
      current.accessCount += Number(app.accessCount) || 0
      current.uniqueUserCount += Number(app.uniqueUserCount) || 0
      current.lastAccessedAt = mergeLastAccessedAt(current.lastAccessedAt, app.lastAccessedAt)
      current.sourceType = mergeSourceType(current.sourceType, app.sourceType)
      current.sourceName = mergeSourceName(current.sourceName, app.sourceName)
      rows.set(key, current)
    })
  })
  return Array.from(rows.values()).sort((left, right) => {
    const countDiff = Number(right.accessCount || 0) - Number(left.accessCount || 0)
    if (countDiff !== 0) return countDiff
    return String(left.appName || "").localeCompare(String(right.appName || ""), "ko")
  })
}

function mergeSeriesRows(payloads) {
  const rows = new Map()
  payloads.forEach((payload) => {
    ;(payload?.series ?? []).forEach((row) => {
      const key = `${row.date || ""}:${row.appId || row.appName || "unknown"}`
      const current = rows.get(key) ?? {
        ...row,
        appId: row.appId || row.appName || "unknown",
        accessCount: 0,
      }
      current.appName = current.appName || row.appName || current.appId
      current.accessCount += Number(row.accessCount) || 0
      current.sourceType = mergeSourceType(current.sourceType, row.sourceType)
      current.sourceName = mergeSourceName(current.sourceName, row.sourceName)
      rows.set(key, current)
    })
  })
  return Array.from(rows.values()).sort((left, right) => {
    const dateDiff = String(left.date || "").localeCompare(String(right.date || ""))
    if (dateDiff !== 0) return dateDiff
    return String(left.appName || "").localeCompare(String(right.appName || ""), "ko")
  })
}

function mergeAppAccessStatsPayloads(payloads, params) {
  const apps = mergeAppRows(payloads)
  const series = mergeSeriesRows(payloads)
  const totalAccessCount = payloads.reduce(
    (sum, payload) => sum + Number(payload?.summary?.totalAccessCount || 0),
    0
  )
  const uniqueUserCount = payloads.reduce(
    (sum, payload) => sum + Number(payload?.summary?.uniqueUserCount || 0),
    0
  )

  return {
    timezone: payloads[0]?.timezone || "Asia/Seoul",
    period: params.period || payloads[0]?.period || "day",
    range: {
      from: params.from,
      to: params.to,
    },
    summary: {
      totalAccessCount,
      uniqueUserCount,
      activeAppCount: apps.length,
      topApp: apps[0] ?? null,
    },
    externalUsage: payloads.find((payload) => payload?.externalUsage)?.externalUsage,
    apps,
    series,
  }
}

export function useAppAccessStatsQuery(params, options = {}) {
  const { enabled = true, ...queryOptions } = options
  const chunks = useMemo(() => buildAppAccessStatsQueryChunks(params), [params])
  const queries = useQueries({
    queries: chunks.map((chunk) => ({
      queryKey: accessStatsQueryKeys.appAccessStats(chunk),
      queryFn: () => fetchAppAccessStats(chunk),
      enabled,
      staleTime: APP_ACCESS_STATS_STALE_TIME_MS,
      gcTime: APP_ACCESS_STATS_GC_TIME_MS,
      refetchOnWindowFocus: false,
      ...queryOptions,
    })),
  })
  const error = queries.find((query) => query.error)?.error ?? null
  const isLoading = queries.some((query) => query.isLoading)
  const isFetching = queries.some((query) => query.isFetching)
  const payloads = queries.map((query) => query.data).filter(Boolean)
  const hasAllPayloads = enabled && payloads.length === chunks.length
  const data = hasAllPayloads && !error ? mergeAppAccessStatsPayloads(payloads, params) : undefined

  return {
    data,
    error,
    isError: Boolean(error),
    isLoading,
    isFetching,
    refetch: () => Promise.all(queries.map((query) => query.refetch())),
  }
}

export function useManualAppAccessPreviewMutation(options = {}) {
  return useMutation({
    mutationFn: previewManualAppAccessStats,
    ...options,
  })
}

export function useManualAppAccessCommitMutation(options = {}) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: commitManualAppAccessStats,
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["access-stats", "app-access"] })
      options.onSuccess?.(...args)
    },
  })
}

export function useExternalAppUsageSyncMutation(options = {}) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: syncExternalAppUsageStats,
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["access-stats", "app-access"] })
      options.onSuccess?.(...args)
    },
  })
}
