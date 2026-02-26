// 파일 경로: src/features/line-dashboard/hooks/useLineOptionsQuery.js
// 라인 선택 드롭다운에서 사용할 옵션을 React Query로 관리합니다.
// - account/lineSdwtOptions 응답을 기반으로 line 목록만 추출합니다.
// - drone_sop_user_sdwt_channel에 존재하는 target_user_sdwt_prod가 속한 line만 노출합니다.

import { useQuery } from "@tanstack/react-query"

import { lineDashboardQueryKeys } from "../api/queryKeys"
import { getJiraUserSdwtProds } from "../api/getJiraUserSdwtProds"
import { getLineSdwtOptions } from "../api/getLineSdwtOptions"

function toLineOptions(rawLines) {
  const source = Array.isArray(rawLines) ? rawLines : []
  const normalized = source
    .map((line) => (typeof line?.lineId === "string" ? line.lineId.trim() : ""))
    .filter(Boolean)

  return Array.from(new Set(normalized))
}

function normalizeUserSdwtProd(value) {
  if (value === null || value === undefined) return ""
  return typeof value === "string" ? value.trim() : String(value).trim()
}

function normalizeUserSdwtProds(values) {
  if (!Array.isArray(values)) return []
  const normalized = values.map((value) => normalizeUserSdwtProd(value)).filter(Boolean)
  return Array.from(new Set(normalized))
}

function buildPreferredLineIds(rawLines, preferredUserSdwtProd) {
  const normalizedUserSdwt = normalizeUserSdwtProd(preferredUserSdwtProd)
  if (!normalizedUserSdwt) return []

  return rawLines
    .filter((line) => {
      if (!Array.isArray(line?.userSdwtProds)) return false
      return line.userSdwtProds.some((value) => normalizeUserSdwtProd(value) === normalizedUserSdwt)
    })
    .map((line) => (typeof line?.lineId === "string" ? line.lineId.trim() : ""))
    .filter(Boolean)
}

function filterLinesByUserSdwtProds(rawLines, allowedUserSdwtProds) {
  const allowedSet = new Set(normalizeUserSdwtProds(allowedUserSdwtProds))
  if (allowedSet.size === 0) return []

  return rawLines.filter((line) => {
    const userSdwtValues = Array.isArray(line?.userSdwtProds) ? line.userSdwtProds : []
    return userSdwtValues.some((value) => allowedSet.has(normalizeUserSdwtProd(value)))
  })
}

function toPreferredLineOptions(payload, preferredUserSdwtProd, allowedUserSdwtProds) {
  const rawLines = Array.isArray(payload?.lines) ? payload.lines : []
  const filteredLines = filterLinesByUserSdwtProds(rawLines, allowedUserSdwtProds)
  const allLineIds = toLineOptions(filteredLines)
  const preferredLineIds = buildPreferredLineIds(filteredLines, preferredUserSdwtProd)

  const seen = new Set()
  const ordered = []

  preferredLineIds.forEach((lineId) => {
    if (!seen.has(lineId)) {
      seen.add(lineId)
      ordered.push(lineId)
    }
  })

  allLineIds.forEach((lineId) => {
    if (!seen.has(lineId)) {
      seen.add(lineId)
      ordered.push(lineId)
    }
  })

  return ordered
}

export function useLineOptionsQuery(options = {}) {
  const { enabled = true, preferredUserSdwtProd } = options

  const lineSdwtQuery = useQuery({
    queryKey: lineDashboardQueryKeys.lineSdwtOptions(),
    queryFn: getLineSdwtOptions,
    // 탭으로 돌아올 때 홈 진입 페이지가 "새로고침"처럼 보이지 않도록
    // 포커스 시 자동 refetch를 비활성화합니다.
    refetchOnWindowFocus: false,
    enabled,
  })

  const jiraUserSdwtQuery = useQuery({
    queryKey: lineDashboardQueryKeys.jiraUserSdwtProds(),
    queryFn: getJiraUserSdwtProds,
    refetchOnWindowFocus: false,
    enabled,
  })

  const lineOptions =
    lineSdwtQuery.data && jiraUserSdwtQuery.data
      ? toPreferredLineOptions(
        lineSdwtQuery.data,
        preferredUserSdwtProd,
        jiraUserSdwtQuery.data,
      )
      : []

  const refetch = () => Promise.all([lineSdwtQuery.refetch(), jiraUserSdwtQuery.refetch()])

  const isLoading = lineSdwtQuery.isLoading || jiraUserSdwtQuery.isLoading
  const isFetching = lineSdwtQuery.isFetching || jiraUserSdwtQuery.isFetching
  const isError = lineSdwtQuery.isError || jiraUserSdwtQuery.isError
  const error = lineSdwtQuery.error ?? jiraUserSdwtQuery.error

  return {
    ...lineSdwtQuery,
    data: lineOptions,
    isLoading,
    isFetching,
    isError,
    error,
    refetch,
  }
}
