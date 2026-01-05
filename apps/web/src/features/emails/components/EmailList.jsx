import {
  IconChevronLeft,
  IconChevronRight,
  IconChevronsLeft,
  IconChevronsRight,
} from "@tabler/icons-react"
import { ArrowRightLeft, Mail, RefreshCcw, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

import { DEFAULT_EMAIL_PAGE_SIZE, EMAIL_PAGE_SIZE_OPTIONS } from "../utils/emailPagination"
import { formatEmailDate } from "../utils/date"

const pillBaseClass =
  "inline-flex h-8 items-center rounded-full border px-3 text-xs font-semibold leading-none"
const pillInteractiveClass =
  "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-60"
const deletePillClass = "border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/15"
const countPillClass = "border-primary/20 bg-primary/10 text-primary"

function SelectionCheckbox({ checked, onCheckedChange, className, ...props }) {
  return (
    <input
      type="checkbox"
      checked={checked}
      onChange={(event) => {
        event.stopPropagation()
        onCheckedChange?.(event.target.checked)
      }}
      onClick={(event) => event.stopPropagation()}
      className={cn(
        "h-4 w-4 cursor-pointer rounded border border-input bg-background text-primary shadow-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className
      )}
      {...props}
    />
  )
}

export function EmailList({
  emails = [],
  selectedIds = [],
  onToggleSelect,
  onToggleSelectAll,
  onSelectEmail,
  onDeleteEmail,
  isLoading,
  onBulkDelete,
  isBulkDeleting = false,
  onMoveEmails,
  moveTargets = [],
  isMoving = false,
  currentPage = 1,
  totalPages = 1,
  pageSize = DEFAULT_EMAIL_PAGE_SIZE,
  pageSizeOptions = EMAIL_PAGE_SIZE_OPTIONS,
  onPageChange,
  onPageSizeChange,
  onReload,
  isReloading = false,
  showAffiliationBadge = false,
  activeEmailId = null,
}) {
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [moveTarget, setMoveTarget] = useState("")
  const allSelected = emails.length > 0 && emails.every((email) => selectedIds.includes(email.id))
  const hasSelection = selectedIds.length > 0
  const isDeleteDialogOpen = Boolean(deleteTarget)
  const canMove = Boolean(onMoveEmails && hasSelection && moveTarget)
  const deleteTargetLabel =
    deleteTarget?.type === "bulk"
      ? `${deleteTarget?.count ?? selectedIds.length}개의 메일`
      : deleteTarget?.subject?.trim() || "이 메일"

  const handleRequestSingleDelete = (email) => {
    if (!email?.id) return
    setDeleteTarget({ type: "single", emailId: email.id, subject: email.subject })
  }

  const handleRequestBulkDelete = () => {
    if (!hasSelection) return
    setDeleteTarget({ type: "bulk", count: selectedIds.length })
  }

  const handleCloseDeleteDialog = () => {
    setDeleteTarget(null)
  }

  const handleConfirmDelete = () => {
    if (!deleteTarget) return
    if (deleteTarget.type === "single" && deleteTarget.emailId) {
      onDeleteEmail?.(deleteTarget.emailId)
    } else if (deleteTarget.type === "bulk" && hasSelection) {
      onBulkDelete?.()
    }
    setDeleteTarget(null)
  }

  useEffect(() => {
    if (!moveTarget) return
    const exists = Array.isArray(moveTargets)
      ? moveTargets.some((target) => target?.value === moveTarget)
      : false
    if (!exists) {
      setMoveTarget("")
    }
  }, [moveTarget, moveTargets])

  return (
    <div className="flex h-full min-w-0 flex-col rounded-xl border bg-card/60 p-2 shadow-sm">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-3">
          <SelectionCheckbox
            checked={allSelected}
            onCheckedChange={onToggleSelectAll}
            aria-label="전체 선택"
          />
          <div>
            <p className="text-sm font-semibold leading-tight">메일함</p>
            <p className="text-xs text-muted-foreground">최신순으로 정렬됩니다</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onReload ? (
            <Button
              variant="secondary"
              size="sm"
              className="gap-2"
              onClick={onReload}
              disabled={isReloading}
            >
              <RefreshCcw className={cn("h-4 w-4", isReloading ? "animate-spin" : "")} />
              새로고침
            </Button>
          ) : null}
          {hasSelection && onBulkDelete ? (
            <button
              type="button"
              className={cn(pillBaseClass, pillInteractiveClass, deletePillClass, "gap-1")}
              onClick={handleRequestBulkDelete}
              disabled={isBulkDeleting}
            >
              <Trash2 className="h-3.5 w-3.5" />
              선택 삭제
            </button>
          ) : null}
          {onMoveEmails && moveTargets.length > 0 ? (
            <div className="flex items-center gap-2">
              <Select value={moveTarget} onValueChange={setMoveTarget}>
                <SelectTrigger className="h-8 w-40 text-xs">
                  <SelectValue placeholder="이동할 메일함" />
                </SelectTrigger>
                <SelectContent>
                  {moveTargets.map((target) => (
                    <SelectItem key={target.value} value={target.value}>
                      {target.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => onMoveEmails(moveTarget)}
                disabled={!canMove || isMoving}
              >
                <ArrowRightLeft className="h-4 w-4" />
                이동
              </Button>
            </div>
          ) : null}
          <span className={cn(pillBaseClass, countPillClass)} aria-live="polite">
            {emails.length}개 표시
          </span>
        </div>
      </div>

      <div className="flex-1 min-h-0 min-w-0 overflow-y-auto overflow-x-hidden">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            메일을 불러오는 중입니다...
          </div>
        ) : emails.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-muted-foreground">
            <Mail className="h-8 w-8" />
            <p className="text-sm">표시할 메일이 없습니다.</p>
          </div>
        ) : (
          <ul className="divide-y">
            {emails.map((email) => {
              const emailSubject =
                typeof email.subject === "string" && email.subject.trim() ? email.subject : "메일"
              const isSelected = selectedIds.includes(email.id)
              const isActive = activeEmailId === email.id
              const rawAffiliation =
                typeof email.userSdwtProd === "string" ? email.userSdwtProd.trim() : ""
              const affiliationLabel = rawAffiliation || "미분류"
              const isRagIndexed = email.ragIndexStatus === "INDEXED"
              const showRagBadge = isRagIndexed && Boolean(email.ragDocId)
              return (
                <li
                  key={email.id}
                  className={cn(
                    "flex min-w-0 cursor-pointer items-start gap-3 overflow-hidden px-4 py-3 transition hover:bg-muted/60",
                    isSelected ? "bg-muted/60" : "",
                    isActive ? "ring-1 ring-primary/40 bg-muted/50" : ""
                  )}
                  onClick={() => onSelectEmail?.(email.id)}
                  aria-current={isActive ? "true" : undefined}
                >
                  <div className="pt-1">
                    <SelectionCheckbox
                      checked={isSelected}
                      onCheckedChange={() => onToggleSelect?.(email.id)}
                      aria-label={`${emailSubject} 선택`}
                    />
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div className="flex min-w-0 items-center justify-between gap-2">
                      <p className="min-w-0 flex-1 truncate text-sm font-semibold">
                        {email.subject || "(제목 없음)"}
                      </p>
                      <span className="shrink-0 text-[11px] text-muted-foreground">
                        {formatEmailDate(email.receivedAt)}
                      </span>
                    </div>
                    <p className="truncate text-xs text-muted-foreground">From: {email.sender}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {showAffiliationBadge ? (
                      <Badge variant="outline" className="text-[10px]">
                        {affiliationLabel}
                      </Badge>
                    ) : null}
                    {showRagBadge ? (
                      <Badge variant="outline" className="text-[10px] uppercase">
                        RAG
                      </Badge>
                    ) : null}
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8"
                      onClick={(event) => {
                        event.stopPropagation()
                        handleRequestSingleDelete(email)
                      }}
                      aria-label="메일 삭제"
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage <= 1}
            onClick={() => onPageChange?.(1)}
            aria-label="첫 페이지"
            title="첫 페이지"
          >
            <IconChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage <= 1}
            onClick={() => onPageChange?.(currentPage - 1)}
            aria-label="이전 페이지"
            title="이전 페이지"
          >
            <IconChevronLeft className="h-4 w-4" />
          </Button>
          <span className="px-2 text-xs text-muted-foreground" aria-live="polite">
            페이지 {currentPage} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage >= totalPages}
            onClick={() => onPageChange?.(currentPage + 1)}
            aria-label="다음 페이지"
            title="다음 페이지"
          >
            <IconChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage >= totalPages}
            onClick={() => onPageChange?.(totalPages)}
            aria-label="마지막 페이지"
            title="마지막 페이지"
          >
            <IconChevronsRight className="h-4 w-4" />
          </Button>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <span className="text-xs text-muted-foreground">페이지당</span>
          <select
            value={pageSize}
            onChange={(event) => onPageSizeChange?.(event.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
            aria-label="페이지당 표시 개수"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size}개
              </option>
            ))}
          </select>
        </label>
      </div>
      <Dialog
        open={isDeleteDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            handleCloseDeleteDialog()
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>메일 삭제</DialogTitle>
            <DialogDescription>
              {deleteTarget?.type === "bulk"
                ? `${deleteTargetLabel}을(를) 삭제할까요? 선택한 메일은 복구할 수 없습니다.`
                : `"${deleteTargetLabel}"을 삭제할까요? 삭제 후에는 복구할 수 없습니다.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={handleCloseDeleteDialog}>
              취소
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleteTarget?.type === "bulk" && isBulkDeleting}
            >
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
