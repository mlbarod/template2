// 파일 경로: src/features/line-dashboard/hooks/useDataTable.js
import * as React from "react"

import { buildBackendUrl } from "@/lib/api"
import { instantInformDroneSop } from "../api/instantInform"
import { retryDroneSopChannel } from "../api/retryChannel"
import { useCellIndicators } from "./useCellIndicators"
import { useTableQuery } from "./useTableQuery"

/* ============================================================================
 * 작은 유틸: 객체에서 키 지우기 (불변성 유지)
 *  - deleteKeys(record, ["a","b"]) → a,b 키만 제거된 "새 객체" 반환
 *  - removeKey(record, "a") → 단일 키 제거
 *  - 원본 객체는 건드리지 않습니다(불변성 유지로 리액트 상태 업데이트 안전)
 * ========================================================================== */
function deleteKeys(record, keys) {
  if (!Array.isArray(keys) || keys.length === 0) return record
  let next = null
  for (const key of keys) {
    if (key in record) {
      if (next === null) next = { ...record }
      delete next[key]
    }
  }
  return next ?? record
}
function removeKey(record, key) {
  if (!(key in record)) return record
  const next = { ...record }
  delete next[key]
  return next
}

/* ============================================================================
 * useDataTableState
 * - 테이블 데이터/필터/정렬/편집 상태와, 서버 fetch/update를 관리하는 커스텀 훅
 * - 초보자 포인트:
 *   1) useTableQuery가 fetch/정규화/최근시간 필터를 관리하고, 여기서는 UI 상태/업데이트만 다룹니다.
 *   2) 업데이트 중인 셀(skeleton/indicator)/오류 맵을 키(`${rowId}:${field}`)로 관리합니다.
 * ========================================================================== */
export function useDataTableState({ lineId }) {
  const {
    selectedTable,
    columns,
    rows,
    setRows,
    fromDate,
    setFromDate,
    toDate,
    setToDate,
    appliedFrom,
    appliedTo,
    isLoadingRows,
    rowsError,
    lastFetchedCount,
    fetchRows,
    recentHoursRange,
    setRecentHoursRange,
    hydrationKey,
  } = useTableQuery({ lineId })

  // 전역 검색(퀵필터와 별도)
  const [filter, setFilter] = React.useState("")

  // 정렬 상태(TanStack Table v8 표준 형태)
  const [sorting, setSorting] = React.useState([])

  // 셀 편집: comment
  const [commentDrafts, setCommentDrafts] = React.useState({})   // { [rowId]: "임시 텍스트" } 형태
  const [commentEditing, setCommentEditing] = React.useState({}) // { [rowId]: true } 형태

  // 셀 편집: needtosend
  const [needToSendDrafts, setNeedToSendDrafts] = React.useState({}) // { [rowId]: 숫자 } 형태

  // 셀 편집: instant_inform
  const [instantInformDrafts, setInstantInformDrafts] = React.useState({}) // { [rowId]: 숫자 } 형태

  // 업데이트 진행중/에러 상태: 키 형식은 `${rowId}:${field}`
  const [updatingCells, setUpdatingCells] = React.useState({})  // { ["1:comment"]: true, ... } 형태
  const [updateErrors, setUpdateErrors] = React.useState({})    // { ["1:comment"]: "에러메시지", ... }

  // 셀 하이라이트/토스트 등 시각 피드백 훅
  const { cellIndicators, begin, finalize } = useCellIndicators()

  React.useEffect(() => {
    setCommentDrafts({})
    setCommentEditing({})
    setNeedToSendDrafts({})
    setInstantInformDrafts({})
  }, [hydrationKey])

  /* ────────────────────────────────────────────────────────────────────────
   * 에러 메시지 1건 제거(셀 포커스 시 이전 에러를 치울 때 유용)
   * ──────────────────────────────────────────────────────────────────────── */
  const clearUpdateError = React.useCallback((key) => {
    setUpdateErrors((prev) => removeKey(prev, key))
  }, [])

  /* ────────────────────────────────────────────────────────────────────────
   * handleUpdate: 단일 레코드 부분 업데이트(PATCH)
   *  - updates = { comment: "...", needtosend: true } 식으로 필드 묶음 전달
   *  - updatingCells/indicators로 진행상태 UI 피드백
   *  - 성공 시 로컬 rows 반영 + 드래프트/편집 상태 정리
   * ──────────────────────────────────────────────────────────────────────── */
  const handleUpdate = React.useCallback(
    async (recordId, updates) => {
      const fields = Object.keys(updates)
      if (!recordId || fields.length === 0) return false

      // 셀 키들: ["{id}:comment", "{id}:needtosend", ...]
      const cellKeys = fields.map((field) => `${recordId}:${field}`)

      // 1) "업데이트 중" 표시 on
      setUpdatingCells((prev) => {
        const next = { ...prev }
        for (const key of cellKeys) next[key] = true
        return next
      })

      // 2) 기존 에러 메시지 클리어
      setUpdateErrors((prev) => {
        const next = { ...prev }
        for (const key of cellKeys) {
          if (key in next) delete next[key]
        }
        return next
      })

      // 3) 셀 인디케이터 시작(시각 효과)
      begin(cellKeys)

      let updateSucceeded = false

      try {
        // 4) 서버 PATCH 호출
        const endpoint = buildBackendUrl("/api/v1/tables/update")
        const response = await fetch(endpoint, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ table: selectedTable, id: recordId, updates }),
        })

        // 5) 응답 파싱(에러 메시지 추출 대비)
        let payload = {}
        try {
          payload = await response.json()
        } catch {
          payload = {}
        }

        // 6) HTTP 에러 처리
        if (!response.ok) {
          const message =
            payload && typeof payload === "object" && "error" in payload && typeof payload.error === "string"
              ? payload.error
              : `Failed to update (status ${response.status})`
          throw new Error(message)
        }

        // 7) 로컬 rows 반영(낙관적 업데이트 확정)
        setRows((previousRows) =>
          previousRows.map((row) => {
            const rowId = String(row?.id ?? "")
            return rowId === recordId ? { ...row, ...updates } : row
          })
        )

        // 8) 관련 드래프트/편집 상태 정리
        if ("comment" in updates) {
          setCommentDrafts((prev) => removeKey(prev, recordId))
          setCommentEditing((prev) => removeKey(prev, recordId))
        }
        if ("needtosend" in updates) {
          setNeedToSendDrafts((prev) => removeKey(prev, recordId))
        }
        if ("instant_inform" in updates) {
          setInstantInformDrafts((prev) => removeKey(prev, recordId))
        }

        updateSucceeded = true
        return true
      } catch (error) {
        // 9) 에러 메시지 매핑(셀별로 동일 메시지)
        const message = error instanceof Error ? error.message : "Failed to update"
        setUpdateErrors((prev) => {
          const next = { ...prev }
          for (const key of cellKeys) next[key] = message
          return next
        })
        return false
      } finally {
        // 10) 진행중 off + 인디케이터 종료(성공/실패 상태)
        setUpdatingCells((prev) => deleteKeys(prev, cellKeys))
        finalize(cellKeys, updateSucceeded ? "success" : "error")
      }
    },
    [
      selectedTable,
      begin,
      finalize,
      setRows,
      setCommentDrafts,
      setCommentEditing,
      setNeedToSendDrafts,
      setUpdateErrors,
      setUpdatingCells,
    ]
  )

  /* ────────────────────────────────────────────────────────────────────────
   * handleInstantInform: 단건 즉시인폼 체크 요청
   *  - comment/instant_inform 값을 서버에 저장하고, 배치 처리 대상에 포함합니다.
   * ──────────────────────────────────────────────────────────────────────── */
  const handleInstantInform = React.useCallback(
    async (recordId, { comment }) => {
      if (!recordId) return null

      const cellKeys = [`${recordId}:instant_inform`, `${recordId}:comment`]

      setUpdatingCells((prev) => {
        const next = { ...prev }
        for (const key of cellKeys) next[key] = true
        return next
      })

      setUpdateErrors((prev) => {
        const next = { ...prev }
        for (const key of cellKeys) {
          if (key in next) delete next[key]
        }
        return next
      })

      begin(cellKeys)

      let updateSucceeded = false

      try {
        const payload = await instantInformDroneSop({ id: recordId, comment })
        const updated = payload?.updated
        const nextUpdates =
          updated && typeof updated === "object" && !Array.isArray(updated) ? updated : {}

        setRows((previousRows) =>
          previousRows.map((row) => {
            const rowId = String(row?.id ?? "")
            return rowId === recordId ? { ...row, ...nextUpdates } : row
          })
        )

        setInstantInformDrafts((prev) => removeKey(prev, recordId))

        updateSucceeded = true
        return payload
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to instant-inform"
        setUpdateErrors((prev) => {
          const next = { ...prev }
          for (const key of cellKeys) next[key] = message
          return next
        })
        return null
      } finally {
        setUpdatingCells((prev) => deleteKeys(prev, cellKeys))
        finalize(cellKeys, updateSucceeded ? "success" : "error")
      }
    },
    [
      begin,
      finalize,
      setInstantInformDrafts,
      setRows,
      setUpdateErrors,
      setUpdatingCells,
    ]
  )

  /* ────────────────────────────────────────────────────────────────────────
   * handleRetryChannel: 단건 채널 재시도 요청
   *  - 실패 채널(send_*=-1)을 대기(0)로 되돌리고, 다음 배치 처리 대상에 포함합니다.
   * ──────────────────────────────────────────────────────────────────────── */
  const handleRetryChannel = React.useCallback(
    async (recordId, { channelKey }) => {
      if (!recordId) {
        return { ok: false, message: "recordId is required" }
      }

      const channelByField = {
        send_jira: "jira",
        send_messenger: "messenger",
        send_mail: "mail",
      }
      const normalizedChannelKey = typeof channelKey === "string" ? channelKey.trim() : ""
      const channel = channelByField[normalizedChannelKey]
      if (!channel) {
        return { ok: false, message: "Invalid retry channel" }
      }

      const cellKeys = [`${recordId}:${normalizedChannelKey}`]

      setUpdatingCells((prev) => {
        const next = { ...prev }
        for (const key of cellKeys) next[key] = true
        return next
      })

      setUpdateErrors((prev) => {
        const next = { ...prev }
        for (const key of cellKeys) {
          if (key in next) delete next[key]
        }
        return next
      })

      begin(cellKeys)

      let updateSucceeded = false

      try {
        const payload = await retryDroneSopChannel({ id: recordId, channel })
        const updated = payload?.updated
        const nextUpdates =
          updated && typeof updated === "object" && !Array.isArray(updated) ? updated : {}

        setRows((previousRows) =>
          previousRows.map((row) => {
            const rowId = String(row?.id ?? "")
            return rowId === recordId ? { ...row, ...nextUpdates } : row
          })
        )

        updateSucceeded = true
        return {
          ok: true,
          status: typeof payload?.status === "string" ? payload.status : "",
          payload,
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to retry channel"
        setUpdateErrors((prev) => {
          const next = { ...prev }
          for (const key of cellKeys) next[key] = message
          return next
        })
        return { ok: false, message }
      } finally {
        setUpdatingCells((prev) => deleteKeys(prev, cellKeys))
        finalize(cellKeys, updateSucceeded ? "success" : "error")
      }
    },
    [
      begin,
      finalize,
      setRows,
      setUpdateErrors,
      setUpdatingCells,
    ]
  )

  /* ────────────────────────────────────────────────────────────────────────
   * comment 편집 상태/드래프트 값 컨트롤러 (셀 컴포넌트가 호출)
   * ──────────────────────────────────────────────────────────────────────── */
  const setCommentEditingState = React.useCallback((recordId, editing) => {
    if (!recordId) return
    setCommentEditing((prev) => (editing ? { ...prev, [recordId]: true } : removeKey(prev, recordId)))
  }, [])

  const setCommentDraftValue = React.useCallback((recordId, value) => {
    if (!recordId) return
    setCommentDrafts((prev) => ({ ...prev, [recordId]: value }))
  }, [])

  const removeCommentDraftValue = React.useCallback((recordId) => {
    if (!recordId) return
    setCommentDrafts((prev) => removeKey(prev, recordId))
  }, [])

  /* ────────────────────────────────────────────────────────────────────────
   * needtosend 드래프트 값 컨트롤러
   * ──────────────────────────────────────────────────────────────────────── */
  const setNeedToSendDraftValue = React.useCallback((recordId, value) => {
    if (!recordId) return
    setNeedToSendDrafts((prev) => ({ ...prev, [recordId]: value }))
  }, [])

  const removeNeedToSendDraftValue = React.useCallback((recordId) => {
    if (!recordId) return
    setNeedToSendDrafts((prev) => removeKey(prev, recordId))
  }, [])

  /* ────────────────────────────────────────────────────────────────────────
   * instant_inform 드래프트 값 컨트롤러
   * ──────────────────────────────────────────────────────────────────────── */
  const setInstantInformDraftValue = React.useCallback((recordId, value) => {
    if (!recordId) return
    setInstantInformDrafts((prev) => ({ ...prev, [recordId]: value }))
  }, [])

  const removeInstantInformDraftValue = React.useCallback((recordId) => {
    if (!recordId) return
    setInstantInformDrafts((prev) => removeKey(prev, recordId))
  }, [])

  /* ────────────────────────────────────────────────────────────────────────
   * TanStack Table의 meta로 내려줄 컨트롤/상태 모음
   * - 셀 컴포넌트(CommentCell/NeedToSendCell)가 이 객체의 함수를 직접 호출
   * ──────────────────────────────────────────────────────────────────────── */
  const tableMeta = {
    commentDrafts,
    commentEditing,
    needToSendDrafts,
    instantInformDrafts,
    updatingCells,
    updateErrors,
    cellIndicators,
    clearUpdateError,
    setCommentDraftValue,
    removeCommentDraftValue,
    setCommentEditingState,
    setNeedToSendDraftValue,
    removeNeedToSendDraftValue,
    setInstantInformDraftValue,
    removeInstantInformDraftValue,
    handleUpdate,
    handleInstantInform,
    handleRetryChannel,
  }

  /* ────────────────────────────────────────────────────────────────────────
   * 훅 바깥에서 쓸 값들 반환
   *  - isLoadingRows / rowsError / lastFetchedCount: 로드 상태와 피드백
   *  - fetchRows: 새로고침(리로드) 버튼 등에 연결 가능
   * ──────────────────────────────────────────────────────────────────────── */
  return {
    selectedTable,
    columns,
    rows,
    fromDate,
    setFromDate,
    toDate,
    setToDate,
    appliedFrom,
    appliedTo,
    filter,
    setFilter,
    sorting,
    setSorting,
    isLoadingRows,
    rowsError,
    lastFetchedCount,
    fetchRows,
    tableMeta,
    recentHoursRange,
    setRecentHoursRange,
  }
}
