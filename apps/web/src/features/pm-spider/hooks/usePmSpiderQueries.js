// 파일 경로: src/features/pm-spider/hooks/usePmSpiderQueries.js
// PM SPIDER 서버 데이터 조회 훅입니다.
import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query"

import {
  fetchPmSpiderMeta,
  fetchPmSpiderResult,
  pmSpiderQueryKeys,
} from "../api"
import {
  PM_SPIDER_CATEGORIES,
  buildPmSpiderTypePayloads,
} from "../utils/format"

export function buildPayloadKey(payload) {
  if (!payload) return "empty"
  return JSON.stringify(payload)
}

function withRefPmDates(payload, refPmDates) {
  if (!payload || refPmDates === null || refPmDates === undefined) return payload
  return {
    ...payload,
    refPmDates,
  }
}

export function usePmSpiderMeta(selection = {}) {
  const selectionKey = buildPayloadKey(selection)
  return useQuery({
    queryKey: pmSpiderQueryKeys.meta(selectionKey),
    queryFn: () => fetchPmSpiderMeta(selection),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: false,
  })
}

export function usePmSpiderResult(payload) {
  const payloadKey = buildPayloadKey(payload)
  return useQuery({
    queryKey: pmSpiderQueryKeys.result(payloadKey),
    queryFn: () => fetchPmSpiderResult(payload),
    enabled: Boolean(payload),
    retry: false,
  })
}

export function usePmSpiderCategoryResults(payload, refPmDates = null) {
  const typePayloads = buildPmSpiderTypePayloads(withRefPmDates(payload, refPmDates))
  const queries = useQueries({
    queries: typePayloads.map(({ type, payload: categoryPayload }) => ({
      queryKey: pmSpiderQueryKeys.category(type, buildPayloadKey(categoryPayload)),
      queryFn: () => fetchPmSpiderResult(categoryPayload),
      enabled: Boolean(payload),
      retry: false,
    })),
  })
  const dataByType = Object.fromEntries(
    typePayloads.map(({ type }, index) => [type, queries[index]?.data]),
  )
  const queryByType = Object.fromEntries(
    typePayloads.map(({ type }, index) => [type, queries[index]]),
  )
  const categories = PM_SPIDER_CATEGORIES.map((category) => {
    const data = dataByType[category.type]
    const query = queryByType[category.type]
    const source = category.kind === "trace" ? data?.trace : data?.oes
    const rows = Array.isArray(source?.summaryRows) ? source.summaryRows : []
    const stepRows = Array.isArray(source?.stepRows) ? source.stepRows : []
    return {
      ...category,
      payload: typePayloads.find((item) => item.type === category.type)?.payload,
      data,
      source,
      rows,
      stepRows,
      trendRows: Array.isArray(source?.trendRows) ? source.trendRows : [],
      shapeRows: Array.isArray(source?.shapeRows) ? source.shapeRows : [],
      jitterRows: Array.isArray(source?.jitterRows) ? source.jitterRows : [],
      trajectoryRows: Array.isArray(source?.trajectoryRows) ? source.trajectoryRows : [],
      topRows: rows.slice(0, 5),
      rowCount: Number(source?.rowCount || 0),
      fileCount: Number(source?.fileCount || 0),
      warnings: Array.isArray(data?.warnings) ? data.warnings : [],
      isFetching: Boolean(query?.isFetching),
      isLoading: Boolean(query?.isFetching && !query?.data),
    }
  })

  return {
    categories,
    isFetching: queries.some((query) => query.isFetching),
    isLoading: Boolean(payload) && queries.some((query) => query.isFetching && !query.data),
    error: queries.find((query) => query.error)?.error,
    refetch: () => {
      queries.forEach((query) => query.refetch())
    },
  }
}

function getRowItemKey(category, row) {
  if (!row) return ""
  if (category?.kind === "trace") {
    return row.traceSensor || row.traceParamName || row.itemName || ""
  }
  return `${row.step || ""}:${row.wavelength || ""}`
}

export function usePmSpiderDetailResult(category, row, refPmDates = null, oesCell = null) {
  const itemKey = getRowItemKey(category, row)
  // OES는 히트맵 클릭으로 전달된 step/wavelength를 row 값보다 우선합니다.
  const oesStep = oesCell?.step ?? row?.step ?? ""
  const oesWl   = oesCell?.wavelength != null ? String(oesCell.wavelength) : String(row?.wavelength ?? "")

  let payload = null
  const hasTarget = category?.kind === "trace" ? Boolean(itemKey) : Boolean(oesStep)
  if (category?.payload && hasTarget) {
    payload = {
      ...withRefPmDates(category.payload, refPmDates),
      includeDetails: true,
      traceParamNames: category.kind === "trace" ? [itemKey].filter(Boolean) : [],
      selectedStep: category.kind === "oes" ? oesStep : "",
      selectedWavelength: category.kind === "oes" ? oesWl : "",
      limit: category.kind === "oes" ? 800 : 1200,
      maxPoints: category.kind === "oes" && oesWl ? 3600 : 2400,
      heatmapXBins: 1200,
      heatmapYBins: 100,
    }
  }
  const cellKey = oesCell ? `${oesCell.step}:${oesCell.wavelength}` : "none"
  const payloadKey = buildPayloadKey(payload)

  return useQuery({
    queryKey: pmSpiderQueryKeys.detail(category?.id || "empty", itemKey || cellKey || "empty", payloadKey),
    queryFn: () => fetchPmSpiderResult(payload),
    enabled: Boolean(payload),
    retry: false,
  })
}
