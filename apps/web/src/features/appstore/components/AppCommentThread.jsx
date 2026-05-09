import { useMemo, useState } from "react"
import { Heart, MessageSquare, MoreHorizontal, Pencil, Trash2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

function getParentId(comment) {
  return comment.parentCommentId ?? comment.parentId ?? null
}

function getAuthor(comment) {
  return comment.author ?? comment.owner ?? comment.user ?? null
}

function getAuthorName(comment) {
  const author = getAuthor(comment)
  return author?.name ?? comment.authorName ?? "익명"
}

function getAuthorKnoxId(comment) {
  const author = getAuthor(comment)
  const raw =
    author?.knoxid ||
    author?.knoxId ||
    author?.knox_id ||
    comment.authorKnoxid ||
    comment.author_knoxid ||
    comment.authorKnoxId ||
    ""
  return typeof raw === "string" ? raw.trim() : ""
}

function getAuthorLabel(comment) {
  const name = getAuthorName(comment)
  const knoxId = getAuthorKnoxId(comment)
  return knoxId ? `${name} (${knoxId})` : name
}

function getAuthorInitial(comment) {
  const name = getAuthorName(comment)
  return (name?.trim()?.charAt(0) || "U").toUpperCase()
}

function buildCommentTree(flatComments) {
  const byId = new Map()
  const root = []

  flatComments.forEach((comment) => {
    byId.set(comment.id, { ...comment, children: [] })
  })

  flatComments.forEach((comment) => {
    const node = byId.get(comment.id)
    const parentId = getParentId(comment)
    if (!parentId) {
      root.push(node)
      return
    }

    const parent = byId.get(parentId)
    if (!parent) {
      root.push(node)
      return
    }

    parent.children.push(node)
  })

  const sortByCreatedAtAsc = (left, right) => {
    const leftTime = new Date(left.createdAt).getTime()
    const rightTime = new Date(right.createdAt).getTime()
    if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) return 0
    return leftTime - rightTime
  }

  const sortRecursively = (nodes) => {
    nodes.sort(sortByCreatedAtAsc)
    nodes.forEach((node) => sortRecursively(node.children))
  }
  sortRecursively(root)

  return root
}

function CommentComposer({
  placeholder,
  submitLabel,
  cancelLabel,
  isSubmitting,
  defaultValue = "",
  onSubmit,
  onCancel,
}) {
  const [value, setValue] = useState(defaultValue)
  const canSubmit = value.trim().length > 0 && !isSubmitting

  const handleSubmit = async () => {
    const trimmed = value.trim()
    if (!trimmed || !onSubmit) return

    try {
      const result = onSubmit(trimmed)
      if (result && typeof result.then === "function") {
        await result
      }
      setValue("")
    } catch {
      // 실패 시 초안을 유지합니다.
    }
  }

  return (
    <div className="mt-3 rounded-lg border bg-background p-3">
      <Textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder}
        className="min-h-[84px] resize-none"
      />
      <div className="mt-2 flex items-center justify-end gap-2">
        {onCancel ? (
          <Button variant="ghost" size="sm" onClick={onCancel} type="button">
            {cancelLabel ?? "취소"}
          </Button>
        ) : null}
        <Button size="sm" onClick={handleSubmit} disabled={!canSubmit} type="button">
          {isSubmitting ? "처리 중..." : submitLabel}
        </Button>
      </div>
    </div>
  )
}

function CommentItem({
  comment,
  depth,
  onAdd,
  onUpdate,
  onDelete,
  onToggleLike,
  isAdding,
  updatingCommentId,
  deletingCommentId,
  togglingLikeId,
  isTogglingLike,
}) {
  const [isReplying, setIsReplying] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)

  const authorLabel = getAuthorLabel(comment)
  const timeText = comment.createdAtLabel || comment.createdAt || ""
  const canEdit = Boolean(comment?.canEdit)
  const canDelete = Boolean(comment?.canDelete)
  const showActions = canEdit || canDelete
  const isUpdating = updatingCommentId === comment.id
  const isDeleting = deletingCommentId === comment.id
  const isToggling = isTogglingLike && togglingLikeId === comment.id
  const hasChildren = Array.isArray(comment.children) && comment.children.length > 0

  return (
    <div className={cn("relative", depth > 0 && "pl-6")}>
      {depth > 0 ? (
        <div className="absolute left-2 top-0 h-full w-px bg-border" aria-hidden="true" />
      ) : null}

      <div className="flex gap-3">
        <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold text-foreground ring-1 ring-border">
          {getAuthorInitial(comment)}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="truncate text-sm font-semibold">{authorLabel}</span>
                {timeText ? (
                  <span className="text-xs text-muted-foreground">{timeText}</span>
                ) : null}
              </div>
            </div>

            {showActions ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8" type="button">
                    <MoreHorizontal className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {canEdit ? (
                    <DropdownMenuItem
                      onClick={() => {
                        setIsEditing(true)
                        setIsReplying(false)
                      }}
                    >
                      <Pencil className="mr-2 size-4" />
                      수정
                    </DropdownMenuItem>
                  ) : null}
                  {canDelete ? (
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => onDelete?.(comment.id)}
                      disabled={isDeleting}
                    >
                      <Trash2 className="mr-2 size-4" />
                      {isDeleting ? "삭제 중..." : "삭제"}
                    </DropdownMenuItem>
                  ) : null}
                </DropdownMenuContent>
              </DropdownMenu>
            ) : null}
          </div>

          {!isEditing ? (
            <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground">
              {comment.content ?? ""}
            </p>
          ) : (
            <CommentComposer
              placeholder="댓글을 수정해 주세요."
              submitLabel={isUpdating ? "수정 중..." : "수정 완료"}
              cancelLabel="닫기"
              isSubmitting={isUpdating}
              defaultValue={comment.content ?? ""}
              onSubmit={async (nextContent) => {
                if (!onUpdate) return
                try {
                  await onUpdate(comment.id, nextContent)
                  setIsEditing(false)
                } catch {
                  // 실패 시 편집 상태를 유지합니다.
                }
              }}
              onCancel={() => setIsEditing(false)}
            />
          )}

          {!isEditing ? (
            <div className="mt-2 flex flex-wrap items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => onToggleLike?.(comment.id)}
                disabled={isToggling}
                type="button"
              >
                <Heart className={cn("size-4", comment.liked && "fill-primary text-primary")} />
                <span>{comment.likeCount ?? 0}</span>
              </Button>

              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => {
                  setIsReplying((value) => !value)
                  setIsEditing(false)
                }}
                type="button"
              >
                <MessageSquare className="size-4" />
                답글
              </Button>

              {hasChildren ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setIsCollapsed((value) => !value)}
                  type="button"
                >
                  {isCollapsed ? `답글 ${comment.children.length}개 보기` : "답글 접기"}
                </Button>
              ) : null}

              {isReplying ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setIsReplying(false)}
                  type="button"
                >
                  <X className="size-4" />
                  닫기
                </Button>
              ) : null}
            </div>
          ) : null}

          {isReplying && !isEditing ? (
            <CommentComposer
              placeholder="답글을 입력해 주세요."
              submitLabel="답글 등록"
              cancelLabel="취소"
              isSubmitting={isAdding}
              onSubmit={async (content) => {
                if (!onAdd) return
                try {
                  await onAdd(content, comment.id)
                  setIsReplying(false)
                } catch {
                  // 실패 시 답글 작성 상태를 유지합니다.
                }
              }}
              onCancel={() => setIsReplying(false)}
            />
          ) : null}

          {hasChildren && !isCollapsed ? (
            <div className="mt-3 space-y-4">
              {comment.children.map((child) => (
                <CommentItem
                  key={child.id}
                  comment={child}
                  depth={depth + 1}
                  onAdd={onAdd}
                  onUpdate={onUpdate}
                  onDelete={onDelete}
                  onToggleLike={onToggleLike}
                  isAdding={isAdding}
                  updatingCommentId={updatingCommentId}
                  deletingCommentId={deletingCommentId}
                  togglingLikeId={togglingLikeId}
                  isTogglingLike={isTogglingLike}
                />
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export function CommentThread({
  comments,
  onAdd,
  onUpdate,
  onDelete,
  onToggleLike,
  isAdding,
  updatingCommentId,
  deletingCommentId,
  togglingLikeId,
  isTogglingLike,
}) {
  const tree = useMemo(() => buildCommentTree(Array.isArray(comments) ? comments : []), [comments])

  return (
    <Card className="border bg-card shadow-sm">
      <div className="px-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-col">
            <h3 className="text-base font-semibold">댓글</h3>
            <p className="text-sm text-muted-foreground">
              피드백/질문을 남기면 담당자가 확인할 수 있어요.
            </p>
          </div>
          <div className="text-sm text-muted-foreground">총 {comments?.length ?? 0}개</div>
        </div>

        <Separator className="my-4" />

        {tree.length ? (
          <div className="space-y-6">
            {tree.map((comment) => (
              <CommentItem
                key={comment.id}
                comment={comment}
                depth={0}
                onAdd={onAdd}
                onUpdate={onUpdate}
                onDelete={onDelete}
                onToggleLike={onToggleLike}
                isAdding={isAdding}
                updatingCommentId={updatingCommentId}
                deletingCommentId={deletingCommentId}
                togglingLikeId={togglingLikeId}
                isTogglingLike={isTogglingLike}
              />
            ))}
          </div>
        ) : (
          <div className="py-10 text-center text-sm text-muted-foreground">
            아직 댓글이 없어요. 첫 댓글을 남겨보세요!
          </div>
        )}

        <Separator className="my-4" />

        <CommentComposer
          placeholder="댓글을 입력해 주세요."
          submitLabel="댓글 등록"
          isSubmitting={isAdding}
          onSubmit={async (content) => {
            if (!onAdd) return
            await onAdd(content, null)
          }}
        />
      </div>
    </Card>
  )
}
