// 경로: src/features/line-dashboard/components/CommentCell.jsx
import * as React from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { toast } from "sonner"
import { CheckCircle2, XCircle } from "lucide-react"

import { buildToastOptions } from "../utils/toast"
import { makeCellKey } from "../utils/dataTableCellState"
import { composeComment, splitComment } from "../utils/commentUtils"

/* ============================================================================
 * 초보자용 요약
 * ----------------------------------------------------------------------------
 * - comment 문자열은 "$@$" 마커를 기준으로 앞부분만 화면에 보여주고(visibleText),
 *   뒷부분(suffix)은 보존합니다. 저장 시에는 앞+뒤를 다시 합쳐서 서버에 보냅니다.
 * - 버튼을 누르면 모달이 열리고 텍스트를 편집할 수 있습니다.
 * - Enter 또는 Ctrl/Cmd+Enter → 저장, Shift+Enter → 줄바꿈
 * - 저장 성공하면 0.8초 후 모달이 자동으로 닫힙니다.
 * - meta.*(상위 훅/컨텍스트에서 내려온 API)를 사용해 상태/업데이트를 처리합니다.
 * ========================================================================== */

function showCommentSavedToast() {
  toast.success("저장 성공", {
    description: "Comment가 저장되었습니다.",
    icon: <CheckCircle2 className="h-5 w-5 text-[var(--normal-text)]" />,
    ...buildToastOptions({ intent: "success", duration: 2000 }),
  })
}

function showCommentErrorToast(message) {
  toast.error("저장 실패", {
    description: message || "저장 중 오류가 발생했습니다.",
    icon: <XCircle className="h-5 w-5 text-[var(--normal-text)]" />,
    ...buildToastOptions({ intent: "destructive", duration: 3000 }),
  })
}

/** 인디케이터 상태를 안전하게 읽습니다. (없으면 undefined) */
function getIndicatorStatus(meta, recordId, field) {
  return meta?.cellIndicators?.[makeCellKey(recordId, field)]?.status
}

/**
 * CommentCell
 * - props.meta: 상위에서 주는 업데이트/상태 관리 인터페이스
 * - props.recordId: 현재 행의 고유 ID
 * - props.baseValue: 서버에서 내려온 원본 comment 값
 */
export function CommentCell({ meta, recordId, baseValue }) {
  // 원본 값에서 보이는 텍스트와 suffix(마커 포함)를 분리
  const { visibleText: baseVisibleText, suffixWithMarker } = splitComment(baseValue)

  // 편집 중 여부 / 드래프트 값(입력값)
  const isEditing = Boolean(meta.commentEditing[recordId])
  const draftValue = meta.commentDrafts[recordId]

  // 실제 에디터에 보여줄 값(편집 중이면 드래프트, 아니면 원본 보이는 텍스트)
  const editorValue = isEditing ? (draftValue ?? baseVisibleText) : baseVisibleText

  // 저장중/오류/인디케이터 상태
  const field = "comment"
  const cellKey = makeCellKey(recordId, field)
  const isSaving = Boolean(meta.updatingCells[cellKey])
  const errorMessage = meta.updateErrors[cellKey]
  const indicatorStatus = getIndicatorStatus(meta, recordId, field)

  // "저장됨" 뱃지 잠깐 보여주기 위한 로컬 상태/타이머
  const [showSaved, setShowSaved] = React.useState(false)
  const timerRef = React.useRef(null)

  /** 타이머 정리(컴포넌트 언마운트/의존 변경 시 안전하게) */
  const clearTimer = React.useCallback(() => {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  /** 에디팅 종료 시 공통 리셋 로직 (드래프트/에러/로컬표시 제거) */
  const resetEditingState = React.useCallback(() => {
    clearTimer()
    setShowSaved(false)
    meta.setCommentEditingState(recordId, false)
    meta.removeCommentDraftValue(recordId)
    meta.clearUpdateError(cellKey)
  }, [cellKey, clearTimer, meta, recordId])

  /** 저장 성공 감지 → 800ms 후 자동 닫기 */
  React.useEffect(() => {
    // 편집 중이 아니면 저장표시도 끔
    if (!isEditing) {
      setShowSaved(false)
      clearTimer()
      return
    }
    // 저장 중이면 "Saved" 숨김
    if (indicatorStatus === "saving") {
      setShowSaved(false)
      clearTimer()
      return
    }
    // 저장 완료 표시 후 800ms 뒤 자동 닫기
    if (indicatorStatus === "saved") {
      setShowSaved(true)
      clearTimer()
      timerRef.current = window.setTimeout(() => {
        resetEditingState()
      }, 800)
    }
    // 클린업
    return clearTimer
  }, [indicatorStatus, isEditing, clearTimer, resetEditingState])

  /** 💾 저장(보이는 텍스트 + suffix 재조합) */
  const handleSave = async () => {
    const nextVisible = draftValue ?? baseVisibleText
    const composed = composeComment(nextVisible, suffixWithMarker)

    // 값이 실제로 바뀌지 않았다면 서버 호출 없이 그냥 닫기
    const original = typeof baseValue === "string" ? baseValue : ""
    if (composed === original) {
      resetEditingState()
      return
    }

    // 서버 업데이트(상위 meta가 수행)
    try {
      const success = await meta.handleUpdate(recordId, { comment: composed })
      if (success) {
        showCommentSavedToast()
        return true
      }

      const message = meta.updateErrors?.[cellKey]
      showCommentErrorToast(message)
      return false
    } catch (error) {
      showCommentErrorToast(error?.message)
      return false
    }
  }

  /** ❌ 취소(에디팅 상태/에러/로컬표시 전부 리셋) */
  const handleCancel = () => {
    resetEditingState()
  }

  /** ⌨️ 키보드: Enter 저장 / Shift+Enter 줄바꿈 / Ctrl|Cmd+Enter 저장 */
  const handleEditorKeyDown = (e) => {
    if (e.key !== "Enter") return
    const isCtrlOrCmd = e.ctrlKey || e.metaKey
    const isShift = e.shiftKey

    // Ctrl/Cmd+Enter 또는 단독 Enter → 저장
    if (isCtrlOrCmd || !isShift) {
      e.preventDefault()
      if (!isSaving) void handleSave()
    }
    // Shift+Enter는 기본 동작(줄바꿈) 허용
  }

  /** 모달 하단 상태 메시지 렌더 */
  const renderDialogStatusMessage = () => {
    if (errorMessage) return <div className="text-xs text-destructive">{errorMessage}</div>
    if (indicatorStatus === "saving") return <div className="text-xs text-muted-foreground">Saving…</div>
    if (indicatorStatus === "saved" && showSaved) return <div className="text-xs text-emerald-600">Saved</div>
    return null
  }

  return (
    <div className="flex flex-col gap-1">
      <Dialog
        open={isEditing}
        onOpenChange={(nextOpen) => {
          // 열기: 현재 보이는 텍스트로 드래프트 채우기
          if (nextOpen) {
            meta.setCommentDraftValue(recordId, baseVisibleText)
            meta.setCommentEditingState(recordId, true)
          } else {
            // 닫기: 편집 상태/드래프트/에러 정리
            resetEditingState()
          }
        }}
      >
        <DialogTrigger asChild>
          {/* 
            - title로 전체 내용 호버 표시
            - truncate로 기본은 한 줄만 보여줌
            - cursor-pointer로 편집 가능 UI 피드백
          */}
          <button
            type="button"
            title="Comment 수정시 수정된 내용으로 발송됩니다."
            className="block w-full cursor-pointer truncate rounded-md border px-2 py-1 text-left text-sm transition-colors hover:border-border hover:bg-muted focus:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Open comment editor"
          >
            {baseVisibleText.length > 0 ? (
              <span className="block truncate">{baseVisibleText}</span>
            ) : (
              <span className="block min-h-[1.25rem] text-muted-foreground" aria-hidden="true" />
            )}
          </button>
        </DialogTrigger>

        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit comment</DialogTitle>
            <DialogDescription className="sr-only">코멘트를 편집합니다.</DialogDescription>
          </DialogHeader>

          {/* 📝 에디터: Enter 저장 / Shift+Enter 줄바꿈 / Ctrl|Cmd+Enter 저장 */}
          <textarea
            value={editorValue}
            disabled={isSaving}
            onChange={(e) => {
              meta.setCommentDraftValue(recordId, e.target.value)
              meta.clearUpdateError(cellKey)
            }}
            onKeyDown={handleEditorKeyDown}
            className="min-h-[6rem] resize-y rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed"
            aria-label="Edit comment"
            placeholder="Shift+Enter : 줄바꿈  |  Enter : 저장"
            autoFocus
          />

          {renderDialogStatusMessage()}

          <DialogFooter className="flex items-center gap-2">
            <span className="mr-auto text-[11px] text-muted-foreground">
              Enter: 저장  |  Shift+Enter: 줄바꿈
            </span>
            <Button onClick={() => void handleSave()} disabled={isSaving}>
              Save
            </Button>
            <Button variant="outline" onClick={handleCancel} disabled={isSaving}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
