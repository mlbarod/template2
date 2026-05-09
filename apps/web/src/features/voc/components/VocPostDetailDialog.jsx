import { Loader2, MessageSquare, Pencil, Reply, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  DEFAULT_APP_CATEGORY,
  RICH_TEXT_EDITOR_FORMATS,
  RICH_TEXT_EDITOR_MODULES,
  STATUS_OPTIONS,
} from "../utils/constants"
import { formatTimestamp } from "../utils"
import { RichTextEditor } from "./RichTextEditor"
import { VocPostContent } from "./VocPostContent"
import { VocStatusBadge } from "./VocStatusBadge"

export function VocPostDetailDialog({
  open,
  selectedPost,
  onOpenChange,
  updateStatus,
  canDeletePost,
  canEditSelected,
  isEditing,
  setIsEditing,
  editForm,
  setEditForm,
  handleSaveEdit,
  handleCancelEdit,
  handleRequestDelete,
  replyDraftValue,
  updateReplyDraft,
  addReply,
  isReplyDisabled,
  isUpdating,
  isReplying,
}) {
  return (
    <Dialog open={Boolean(open && selectedPost)} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(1100px,calc(100%-2rem))] min-h-[50vh] sm:max-w-5xl">
        {selectedPost ? (
          <>
            <div className="flex justify-between">
              <DialogHeader className="items-start">
                <DialogTitle className="flex items-center gap-2">
                  <MessageSquare className="size-5" aria-hidden="true" />
                  {selectedPost.title}
                </DialogTitle>
                <DialogDescription className="flex flex-wrap items-center gap-2">
                  {selectedPost.author?.name || "작성자"} ·{" "}
                  {formatTimestamp(selectedPost.createdAt)}
                  <VocStatusBadge status={selectedPost.status} />
                  <Badge variant="outline" className="text-[11px]">
                    {selectedPost.app || DEFAULT_APP_CATEGORY}
                  </Badge>
                </DialogDescription>
              </DialogHeader>
              <div className="flex items-end">
                <div className="flex flex-wrap items-center gap-2">
                  <label
                    className="text-xs text-muted-foreground"
                    htmlFor={`${selectedPost.id}-status-modal`}
                  >
                    상태
                  </label>
                  <select
                    id={`${selectedPost.id}-status-modal`}
                    value={selectedPost.status}
                    onChange={(event) => updateStatus(selectedPost.id, event.target.value)}
                    className="h-8 rounded-md border border-input bg-background px-2 text-xs shadow-xs outline-none transition-[color,box-shadow] focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
                    disabled={!canDeletePost(selectedPost)}
                    title={
                      !canDeletePost(selectedPost)
                        ? "작성자 또는 관리자만 상태를 바꿀 수 있습니다."
                        : undefined
                    }
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.value}
                      </option>
                    ))}
                  </select>
                  <Button
                    type="button"
                    size="sm"
                    variant={isEditing ? "secondary" : "outline"}
                    onClick={isEditing ? handleSaveEdit : () => setIsEditing(true)}
                    disabled={!canEditSelected || isUpdating}
                    title={
                      !canEditSelected
                        ? "작성자 또는 관리자만 수정할 수 있습니다."
                        : isEditing
                          ? "수정 내용을 저장합니다."
                          : "제목과 내용을 수정합니다."
                    }
                  >
                    <Pencil className="mr-1 size-4" aria-hidden="true" />
                    {isEditing ? (isUpdating ? "저장 중..." : "저장") : "수정"}
                  </Button>
                  {isEditing ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={handleCancelEdit}
                      disabled={isUpdating}
                    >
                      취소
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="destructive"
                    onClick={() => handleRequestDelete(selectedPost)}
                    disabled={!canDeletePost(selectedPost)}
                    title={
                      !canDeletePost(selectedPost)
                        ? "작성자 또는 관리자만 삭제할 수 있습니다."
                        : "글을 삭제합니다."
                    }
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              </div>
            </div>

            {isEditing ? (
              <div className="space-y-3">
                <Input
                  value={editForm.title}
                  onChange={(event) =>
                    setEditForm((prev) => ({ ...prev, title: event.target.value }))
                  }
                  placeholder="제목을 입력하세요"
                  disabled={isUpdating}
                />
                <RichTextEditor
                  id="voc-edit-editor"
                  value={editForm.content}
                  onChange={(value) => setEditForm((prev) => ({ ...prev, content: value }))}
                  modules={RICH_TEXT_EDITOR_MODULES}
                  formats={RICH_TEXT_EDITOR_FORMATS}
                  ariaLabel="게시글 내용 수정"
                  readOnly={isUpdating}
                />
              </div>
            ) : (
              <VocPostContent
                content={selectedPost.content}
                className="min-h-[160px] max-h-[60vh]"
                allowResize
              />
            )}
            <div className="space-y-7 rounded-md bg-muted/30 px-3 py-1">
              {selectedPost.replies.length === 0 ? (
                <p className="text-xs text-muted-foreground">아직 답변이 없습니다.</p>
              ) : (
                selectedPost.replies.map((reply) => (
                  <div key={reply.id} className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline">답변</Badge>
                      <span className="font-medium text-foreground">
                        {reply.author?.name || "응답자"}
                      </span>
                      <span aria-hidden="true">·</span>
                      <span>{formatTimestamp(reply.createdAt)}</span>
                    </div>
                    <p className="text-sm text-foreground/90">{reply.content}</p>
                  </div>
                ))
              )}
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Input
                value={replyDraftValue}
                onChange={(event) => updateReplyDraft(selectedPost.id, event.target.value)}
                placeholder="답변을 남겨주세요"
                disabled={isReplying}
              />
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => addReply(selectedPost.id)}
                disabled={isReplyDisabled}
              >
                {isReplying ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Reply className="size-4" aria-hidden="true" />
                )}
                {isReplying ? "등록 중..." : "답변 등록"}
              </Button>
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
