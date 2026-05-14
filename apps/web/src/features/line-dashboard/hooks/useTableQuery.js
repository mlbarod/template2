// 파일 경로: src/features/line-dashboard/hooks/useTableQuery.js
import { useCallback, useEffect, useMemo, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import { buildBackendUrl } from "@/lib/api"
import { lineDashboardQueryKeys } from "../api/queryKeys"

import { composeEqpChamber, normalizeTablePayload } from "../utils"
import {
  DEFAULT_TABLE,
  getDefaultFromValue,
  getDefaultToValue,
} from "../utils/dataTableConstants"
import {
  createRecentHoursRange,
  normalizeRecentHoursRange,
} from "../utils/dataTableQuickFilters"
import {
  DEFAULT_LINE_FILTER_MODE,
  normalizeLineFilterMode,
} from "../utils/lineFilterMode"

/**
 * 테이블 데이터(컬럼/행/날짜 범위) 로딩을 담당하는 훅입니다.
 * - 날짜/최근 시간 범위를 정규화해 쿼리스트링을 만들고,
 *   서버 응답을 normalizeTablePayload로 안전하게 정리합니다.
 * - 오래된 응답이 최신 상태를 덮어쓰지 않도록 요청 id를 비교합니다.
 * - rows가 외부에서 수정될 수 있도록 setRows를 함께 반환합니다.
 */
export function useTableQuery({ lineId }) {
  const [selectedTable, setSelectedTable] = useState(DEFAULT_TABLE)
  const [fromDate, setFromDate] = useState(() => getDefaultFromValue())
  const [toDate, setToDate] = useState(() => getDefaultToValue())
  const [lineFilterMode, setLineFilterModeState] = useState(DEFAULT_LINE_FILTER_MODE)

  const [recentHoursRange, setRecentHoursRangeState] = useState(() => createRecentHoursRange())
  const [hydrationKey, setHydrationKey] = useState(0)
  const queryClient = useQueryClient()

  const setRecentHoursRange = useCallback((nextRange) => {
    setRecentHoursRangeState((previous) => {
      const normalized = normalizeRecentHoursRange(nextRange)
      if (previous && previous.start === normalized.start && previous.end === normalized.end) {
        return previous
      }
      return normalized
    })
  }, [])

  const normalizedRecent = useMemo(
    () => normalizeRecentHoursRange(recentHoursRange),
    [recentHoursRange]
  )

  const { effectiveFrom, effectiveTo } = useMemo(() => {
    let normalizedFrom = fromDate && fromDate.length > 0 ? fromDate : null
    let normalizedTo = toDate && toDate.length > 0 ? toDate : null

    if (normalizedFrom && normalizedTo) {
      const fromTime = new Date(`${normalizedFrom}T00:00:00Z`).getTime()
      const toTime = new Date(`${normalizedTo}T23:59:59Z`).getTime()
      if (Number.isFinite(fromTime) && Number.isFinite(toTime) && fromTime > toTime) {
        ;[normalizedFrom, normalizedTo] = [normalizedTo, normalizedFrom]
      }
    }

    return { effectiveFrom: normalizedFrom, effectiveTo: normalizedTo }
  }, [fromDate, toDate])

  const setLineFilterMode = useCallback((nextValue) => {
    setLineFilterModeState((previous) => {
      const resolved =
        typeof nextValue === "function"
          ? normalizeLineFilterMode(nextValue(previous))
          : normalizeLineFilterMode(nextValue)
      return previous === resolved ? previous : resolved
    })
  }, [])

  const tableParams = useMemo(
    () => ({
      table: selectedTable,
      lineId: lineId ?? null,
      lineFilterMode,
      from: effectiveFrom,
      to: effectiveTo,
      recentHoursStart: normalizedRecent.start,
      recentHoursEnd: normalizedRecent.end,
    }),
    [
      effectiveFrom,
      effectiveTo,
      lineFilterMode,
      lineId,
      normalizedRecent.end,
      normalizedRecent.start,
      selectedTable,
    ]
  )

  const tableQueryKey = useMemo(
    () => lineDashboardQueryKeys.table(tableParams),
    [tableParams]
  )

  const tableQuery = useQuery({
    queryKey: tableQueryKey,
    keepPreviousData: true,
    queryFn: async () => {
      const params = new URLSearchParams({ table: selectedTable })
      if (effectiveFrom) params.set("from", effectiveFrom)
      if (effectiveTo) params.set("to", effectiveTo)
      if (lineId) params.set("lineId", lineId)
      params.set("lineFilterMode", lineFilterMode)

      params.set("recentHoursStart", String(normalizedRecent.start))
      params.set("recentHoursEnd", String(normalizedRecent.end))

      const endpoint = buildBackendUrl("/api/v1/line-dashboard/tables", params)
      const response = await fetch(endpoint, { cache: "no-store", credentials: "include" })

      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        const message =
          payload && typeof payload === "object" && "error" in payload && typeof payload.error === "string"
            ? payload.error
            : `Request failed with status ${response.status}`
        throw new Error(message)
      }

      const defaults = {
        table: DEFAULT_TABLE,
        from: getDefaultFromValue(),
        to: getDefaultToValue(),
      }
      const {
        columns: fetchedColumns,
        rows: fetchedRows,
        rowCount,
        from: appliedFromValue,
        to: appliedToValue,
        table,
      } = normalizeTablePayload(payload, defaults)

      const baseColumns = fetchedColumns.filter((column) => {
        const normalized = column ? column.toLowerCase() : ""
        return (
          normalized !== "id" &&
          normalized !== "sop_key" &&
          normalized !== "defect_png_url" &&
          normalized !== "target_user_sdwt_prod" &&
          normalized !== "messenger_reason" &&
          normalized !== "mail_reason" &&
          normalized !== "jira_reason"
        )
      })

      const composedRows = fetchedRows.map((row) => {
        const eqpId = row?.eqp_id ?? row?.EQP_ID ?? row?.EqpId
        const chamber = row?.chamber_ids ?? row?.CHAMBER_IDS ?? row?.ChamberIds
        return { ...row, EQP_CB: composeEqpChamber(eqpId, chamber) }
      })

      const columnsWithoutOriginals = baseColumns.filter((column) => {
        const normalized = column.toLowerCase()
        return normalized !== "eqp_id" && normalized !== "chamber_ids"
      })

      const nextColumns = columnsWithoutOriginals.includes("EQP_CB")
        ? columnsWithoutOriginals
        : ["EQP_CB", ...columnsWithoutOriginals]

      return {
        columns: nextColumns,
        rows: composedRows,
        rowCount,
        appliedFrom: appliedFromValue ?? null,
        appliedTo: appliedToValue ?? null,
        table: table ?? selectedTable,
      }
    },
    onSuccess: () => {
      setHydrationKey((previous) => previous + 1)
    },
  })

  const setRows = useCallback(
    (updater) => {
      queryClient.setQueryData(tableQueryKey, (previous) => {
        const base = previous ?? {
          columns: [],
          rows: [],
          rowCount: 0,
          appliedFrom: null,
          appliedTo: null,
          table: selectedTable,
        }
        const nextRows = typeof updater === "function" ? updater(base.rows ?? []) : updater ?? []
        return { ...base, rows: nextRows }
      })
    },
    [queryClient, selectedTable, tableQueryKey]
  )

  const appliedFrom = tableQuery.data?.appliedFrom ?? null
  const appliedTo = tableQuery.data?.appliedTo ?? null

  const responseTable = tableQuery.data?.table ?? null

  useEffect(() => {
    if (responseTable && responseTable !== selectedTable) {
      setSelectedTable(responseTable)
    }
  }, [responseTable, selectedTable])

  const fetchRows = useCallback(() => tableQuery.refetch(), [tableQuery])

  return {
    selectedTable,
    setSelectedTable,
    lineFilterMode,
    setLineFilterMode,
    columns: tableQuery.data?.columns ?? [],
    rows: tableQuery.data?.rows ?? [],
    setRows,
    fromDate,
    setFromDate,
    toDate,
    setToDate,
    appliedFrom,
    appliedTo,
    recentHoursRange,
    setRecentHoursRange,
    isLoadingRows: tableQuery.isFetching,
    rowsError: tableQuery.error
      ? tableQuery.error instanceof Error
        ? tableQuery.error.message
        : String(tableQuery.error)
      : null,
    lastFetchedCount: tableQuery.data?.rowCount ?? 0,
    fetchRows,
    hydrationKey,
  }
}
