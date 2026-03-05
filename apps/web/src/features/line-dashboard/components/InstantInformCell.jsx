import * as React from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { Check, XCircle } from "lucide-react"

import { buildToastOptions } from "../utils/toast"
import { makeCellKey } from "../utils/dataTableCellState"
import { composeComment, splitComment } from "../utils/commentUtils"
import { deriveFlagState } from "../utils/dataTableFlagState"

function showInstantInformQueuedToast() {
  toast.info("즉시 인폼 체크 완료", {
    description: "다음 배치 실행 시 Jira 이슈가 생성됩니다.",
    ...buildToastOptions({ intent: "info", duration: 2200 }),
  })
}

function showInstantInformErrorToast(message) {
  toast.error("즉시 인폼 실패", {
    description: message || "즉시 인폼 처리 중 오류가 발생했습니다.",
    icon: <XCircle className="h-5 w-5 text-[var(--normal-text)]" />,
    ...buildToastOptions({ intent: "destructive", duration: 3000 }),
  })
}

function showAlreadyInformedToast() {
  toast.info("이미 Jira 전송 완료되었습니다.", {
    ...buildToastOptions({ intent: "info", duration: 2400 }),
  })
}

function showJiraFailedLockedToast(reason) {
  const detail = typeof reason === "string" && reason.trim() ? reason.trim() : "send_failed"
  toast.info("JIRA 실패 상태입니다.", {
    description: `즉시인폼으로는 재시도되지 않습니다. (reason: ${detail})`,
    ...buildToastOptions({ intent: "info", duration: 3200 }),
  })
}

export function InstantInformCell({
  meta,
  recordId,
  baseValue,
  rowOriginal,
  disabled = false,
  disabledReason = "이미 JIRA 전송됨 (즉시인폼 불가)",
}) {
  const { visibleText: baseVisibleText, suffixWithMarker } = splitComment(rowOriginal?.comment)

  const baseState = deriveFlagState(baseValue, 0)
  const sendJiraState = deriveFlagState(rowOriginal?.send_jira, 0)
  const jiraReason =
    typeof rowOriginal?.jira_reason === "string" && rowOriginal.jira_reason.trim()
      ? rowOriginal.jira_reason.trim()
      : null
  const isLocked = disabled || sendJiraState.isOn || sendJiraState.isError
  const draftValue = meta?.instantInformDrafts?.[recordId]
  const effectiveState = draftValue === undefined ? baseState : deriveFlagState(draftValue, baseState.numericValue)
  const { isOn, isError } = effectiveState
  const isChecked = isOn

  const [isDialogOpen, setIsDialogOpen] = React.useState(false)
  const [commentDraft, setCommentDraft] = React.useState(baseVisibleText)

  React.useEffect(() => {
    if (isDialogOpen) {
      setCommentDraft(baseVisibleText)
    }
  }, [baseVisibleText, isDialogOpen])

  const instantInformKey = makeCellKey(recordId, "instant_inform")
  const commentKey = makeCellKey(recordId, "comment")

  const isSaving =
    Boolean(meta?.updatingCells?.[instantInformKey]) ||
    Boolean(meta?.updatingCells?.[commentKey])

  const errorMessage = meta?.updateErrors?.[instantInformKey] ?? meta?.updateErrors?.[commentKey]

  const resetDraftState = () => {
    meta?.removeInstantInformDraftValue?.(recordId)
    meta?.clearUpdateError?.(instantInformKey)
    meta?.clearUpdateError?.(commentKey)
  }

  const openDialog = () => {
    if (isSaving) return
    if (sendJiraState.isOn) {
      showAlreadyInformedToast()
      return
    }
    if (sendJiraState.isError) {
      showJiraFailedLockedToast(jiraReason)
      return
    }
    if (isLocked) {
      toast.info(disabledReason, {
        ...buildToastOptions({ intent: "info", duration: 2400 }),
      })
      return
    }
    resetDraftState()
    setIsDialogOpen(true)
  }

  const handleConfirm = async () => {
    if (!recordId || typeof meta?.handleInstantInform !== "function") return

    meta?.setInstantInformDraftValue?.(recordId, 1)
    meta?.clearUpdateError?.(instantInformKey)
    meta?.clearUpdateError?.(commentKey)

    const composedComment = composeComment(commentDraft ?? baseVisibleText, suffixWithMarker)

    try {
      const result = await meta.handleInstantInform(recordId, { comment: composedComment })
      if (result) {
        if (result?.alreadyInformed) {
          showAlreadyInformedToast()
          setIsDialogOpen(false)
          return
        }
        showInstantInformQueuedToast()
        setIsDialogOpen(false)
        return
      }

      const message = meta?.updateErrors?.[instantInformKey] ?? meta?.updateErrors?.[commentKey]
      showInstantInformErrorToast(message)
    } catch (error) {
      showInstantInformErrorToast(error?.message)
    } finally {
      meta?.removeInstantInformDraftValue?.(recordId)
    }
  }

  const handleDialogClose = (nextOpen) => {
    if (!nextOpen) {
      resetDraftState()
    }
    setIsDialogOpen(nextOpen)
  }

  const titleText = isLocked
    ? sendJiraState.isError
      ? `JIRA 실패 상태 (reason: ${jiraReason ?? "send_failed"})`
      : disabledReason
    : isError
      ? "즉시인폼 오류 상태"
      : isChecked
        ? "즉시인폼 체크 완료"
        : "즉시인폼 체크"

  return (
    <div className="inline-flex justify-center">
      <button
        type="button"
        onClick={openDialog}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            openDialog()
          }
        }}
        disabled={isSaving}
        role="switch"
        aria-checked={isChecked}
        aria-disabled={isLocked || isSaving}
        aria-label={titleText}
        title={titleText}
        className={cn(
          "inline-flex h-5 w-5 items-center justify-center rounded-full border text-muted-foreground transition-colors focus:outline-none ",
          isError
            ? "border-destructive/60 bg-destructive/10 text-destructive"
            : isChecked
              ? "bg-primary border-primary text-primary-foreground"
              : "border-border hover:border-primary hover:text-primary",
          !isLocked && !isSaving && "cursor-pointer",
          (isLocked || isSaving) && "cursor-not-allowed opacity-60"
        )}
      >
        {isError ? <XCircle className="h-3 w-3" strokeWidth={3} /> : null}
        {!isError && isChecked ? <Check className="h-3 w-3" strokeWidth={3} /> : null}
      </button>

      <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Inform Comment 수정
            </DialogTitle>
            <DialogDescription className="sr-only">Inform 코멘트를 수정합니다.</DialogDescription>
          </DialogHeader>

          <textarea
            value={commentDraft}
            disabled={isSaving}
            onChange={(e) => {
              setCommentDraft(e.target.value)
              meta?.clearUpdateError?.(instantInformKey)
              meta?.clearUpdateError?.(commentKey)
            }}
            className="min-h-[6rem] resize-y rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed"
            aria-label="즉시 인폼 코멘트"
            placeholder="코멘트를 입력해 주세요"
            autoFocus
          />

          {errorMessage ? <div className="text-xs text-destructive">{errorMessage}</div> : null}

          <DialogFooter className="flex items-start gap-2">
            <div className="flex flex-col mr-auto text-[11px] text-muted-foreground">
              <span>Enter: 저장  |  Shift+Enter: 줄바꿈</span>
              <span className="text-primary">체크 후 배치에서 Jira 이슈가 생성됩니다.</span>
            </div>

            <Button onClick={() => void handleConfirm()} disabled={isSaving}>
              Inform
            </Button>
            <Button variant="outline" onClick={() => handleDialogClose(false)} disabled={isSaving}>
              취소
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default InstantInformCell
