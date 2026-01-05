import { useMemo, useState } from "react"
import { ArrowUpRight, Eye, Heart, MessageSquare, MoreHorizontal, Pencil, Trash2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
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
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"
import { ScreenshotCarousel } from "./ScreenshotCarousel"

/**
 * 실무형 댓글/대댓글 UI 포인트
 * - 댓글은 "플랫 배열" -> parentCommentId 기준으로 트리로 변환
 * - 대댓글은 들여쓰기 + 왼쪽 세로 라인(스레드 느낌)
 * - 답글 작성은 해당 댓글 바로 아래 인라인
 * - 수정은 해당 댓글 본문을 인라인 에디터로 전환
 * - 액션은 하단에 작게(좋아요/답글/더보기)
 */

function getParentId(comment) {
  // 백엔드/모델에 맞춰 키가 다르면 여기만 맞추면 됩니다.
  return comment.parentCommentId ?? comment.parentId ?? null
}

function getAuthor(comment) {
  // 소유자 / 작성자 / 사용자 등 다양한 경우 대비
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

const DEFAULT_LOCALE = "ko-KR"
const DEFAULT_TIME_ZONE = "Asia/Seoul"

function buildDateTimeFormatter(locale, timeZone) {
  const resolvedLocale = typeof locale === "string" && locale.trim() ? locale : DEFAULT_LOCALE
  const resolvedTimeZone = typeof timeZone === "string" && timeZone.trim() ? timeZone : DEFAULT_TIME_ZONE
  try {
    return new Intl.DateTimeFormat(resolvedLocale, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: resolvedTimeZone,
    })
  } catch {
    return new Intl.DateTimeFormat(DEFAULT_LOCALE, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: DEFAULT_TIME_ZONE,
    })
  }
}

function formatDateTimeValue(value, formatter) {
  if (!value) return ""
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return formatter.format(date)
}

function buildCommentTree(flatComments) {
  const byId = new Map()
  const root = []

  flatComments.forEach((c) => {
    byId.set(c.id, { ...c, children: [] })
  })

  flatComments.forEach((c) => {
    const node = byId.get(c.id)
    const parentId = getParentId(c)
    if (!parentId) {
      root.push(node)
      return
    }
    const parent = byId.get(parentId)
    if (!parent) {
      // 부모가 없는 경우(데이터 깨짐/필터링 등) -> 루트로
      root.push(node)
      return
    }
    parent.children.push(node)
  })

  // 최신 댓글이 위/아래 원하는 정책이 있으면 여기에서 정렬
  // 예: 오래된 순
  const sortByCreatedAtAsc = (a, b) => {
    const aT = new Date(a.createdAt).getTime()
    const bT = new Date(b.createdAt).getTime()
    if (Number.isNaN(aT) || Number.isNaN(bT)) return 0
    return aT - bT
  }

  const sortRecursively = (nodes) => {
    nodes.sort(sortByCreatedAtAsc)
    nodes.forEach((n) => sortRecursively(n.children))
  }
  sortRecursively(root)

  return root
}

function DetailStat({ icon: Icon, label, value }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">
      <Icon className="size-3" />
      <span className="font-medium text-foreground">{value}</span>
      {label ? <span className="text-[10px] text-muted-foreground">{label}</span> : null}
    </div>
  )
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
    if (!trimmed) return
    if (!onSubmit) return
    try {
      const result = onSubmit(trimmed)
      if (result && typeof result.then === "function") {
        await result
      }
      setValue("")
    } catch {
      // 실패 시 초안 유지
    }
  }

  return (
    <div className="mt-3 rounded-lg border bg-background p-3">
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
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
      {/* 왼쪽 스레드 라인(대댓글 느낌) */}
      {depth > 0 ? (
        <div className="absolute left-2 top-0 h-full w-px bg-border" aria-hidden="true" />
      ) : null}

      <div className="flex gap-3">
        {/* 아바타 */}
        <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold text-foreground ring-1 ring-border">
          {getAuthorInitial(comment)}
        </div>

        {/* 본문 */}
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

            {/* 더보기 메뉴 */}
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

          {/* 내용 / 편집 */}
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
              onSubmit={async (next) => {
                if (!onUpdate) return
                try {
                  await onUpdate(comment.id, next)
                  setIsEditing(false)
                } catch {
                  // 실패 시 유지
                }
              }}
              onCancel={() => setIsEditing(false)}
            />
          )}

          {/* 액션 영역 */}
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
                  setIsReplying((v) => !v)
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
                  onClick={() => setIsCollapsed((v) => !v)}
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

          {/* 답글 작성 */}
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
                  // 실패 시 유지
                }
              }}
              onCancel={() => setIsReplying(false)}
            />
          ) : null}

          {/* 하위 댓글 */}
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

        {/* 루트 댓글 작성 */}
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

export function AppDetail({
  app,
  isLoading,
  onOpenLink,
  onToggleLike,
  onEdit,
  onDelete,
  onAddComment,
  onUpdateComment,
  onDeleteComment,
  onToggleCommentLike,
  isLiking,
  isAddingComment,
  updatingCommentId,
  deletingCommentId,
  togglingCommentLikeId,
  isTogglingCommentLike,
}) {
  const { config: appConfig } = useAuth()
  const dateTimeFormatter = buildDateTimeFormatter(appConfig?.locale, appConfig?.timeZone)
  const formatDateTime = (value) => formatDateTimeValue(value, dateTimeFormatter)

  if (isLoading) {
    return (
      <Card className="border bg-card shadow-sm">
        <div className="px-6 text-sm text-muted-foreground">상세 정보를 불러오는 중...</div>
      </Card>
    )
  }

  if (!app) {
    return (
      <Card className="border bg-card shadow-sm">
        <div className="px-6 text-sm text-muted-foreground">앱을 선택해 주세요.</div>
      </Card>
    )
  }

  const comments = Array.isArray(app.comments) ? app.comments : []
  const decoratedComments = comments.map((comment) => ({
    ...comment,
    createdAtLabel: formatDateTime(comment.createdAt),
    updatedAtLabel: formatDateTime(comment.updatedAt),
  }))
  const commentCount =
    typeof app.commentCount === "number" ? app.commentCount : comments.length
  const screenshotUrls = Array.isArray(app.screenshotUrls) ? app.screenshotUrls : []
  const resolvedScreenshotUrls = screenshotUrls.length
    ? screenshotUrls
    : app.screenshotUrl
      ? [app.screenshotUrl]
      : []
  const coverIndex = Number.isInteger(app.coverScreenshotIndex) ? app.coverScreenshotIndex : 0
  const contactParts = [app.contactName, app.contactKnoxid]
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter(Boolean)
  const contactText = contactParts.length ? contactParts.join(" · ") : "담당자 정보 없음"
  const canManage = Boolean(app.canEdit || app.canDelete)
  const createdAtLabel = formatDateTime(app.createdAt)
  const updatedAtLabel = formatDateTime(app.updatedAt)

  const handleAddComment = async (content, parentCommentId) => {
    if (!onAddComment) return undefined
    return await onAddComment(app.id, content, parentCommentId)
  }

  const handleUpdateComment = async (commentId, content) => {
    if (!onUpdateComment) return undefined
    return await onUpdateComment(app.id, commentId, content)
  }

  const handleDeleteComment = async (commentId) => {
    if (!onDeleteComment) return undefined
    return await onDeleteComment(app.id, commentId)
  }

  const handleToggleCommentLike = (commentId) => {
    onToggleCommentLike?.(app.id, commentId)
  }

  return (
    <div className="grid gap-4">
      <Card className="border bg-card shadow-sm gap-2 ">
        <div className="grid gap-3 px-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-lg font-semibold">{app.name || "이름 없음"}</h3>
                <Badge variant="secondary" className="rounded-full">
                  {app.category || "기타"}
                </Badge>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5 px-2 text-xs"
                onClick={() => onToggleLike?.(app)}
                disabled={isLiking}
                type="button"
              >
                <Heart className={cn("size-4", app.liked && "fill-primary text-primary")} />
                <span>{app.likeCount ?? 0}</span>
              </Button>
              {app.url ? (
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-8 gap-1.5 px-2 text-xs"
                  onClick={() => onOpenLink?.(app)}
                  type="button"
                >
                  Link
                  <ArrowUpRight className="size-4" />
                </Button>
              ) : null}
              {canManage ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8" type="button">
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {app.canEdit ? (
                      <DropdownMenuItem onClick={() => onEdit?.(app)}>
                        <Pencil className="mr-2 size-4" />
                        수정
                      </DropdownMenuItem>
                    ) : null}
                    {app.canDelete ? (
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => onDelete?.(app)}
                      >
                        <Trash2 className="mr-2 size-4" />
                        삭제
                      </DropdownMenuItem>
                    ) : null}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap justify-start gap-2">
            <DetailStat icon={Eye} value={app.viewCount ?? 0} label="조회" />
            <DetailStat icon={Heart} value={app.likeCount ?? 0} label="좋아요" />
            <DetailStat icon={MessageSquare} value={commentCount} label="댓글" />
          </div>
          <Separator />

          <div className="grid gap-4 md:grid-cols-[500px_1fr]">
            <ScreenshotCarousel
              images={resolvedScreenshotUrls}
              altBase={`${app.name || "앱"} 스크린샷`}
              initialIndex={coverIndex}
            />
            <div className="grid grid-rows-2">
              <dl className="grid grid-cols-[40px_1fr] gap-x-3 gap-y-1 rounded-md p-3 text-sm">
                <dt className="flex items-center text-muted-foreground">
                  담당자
                </dt>
                <dd className="flex items-center text-foreground truncate">
                  {contactText}
                </dd>

                {createdAtLabel && (
                  <>
                    <dt className="flex items-center text-muted-foreground">
                      등록
                    </dt>
                    <dd className="flex items-center text-muted-foreground">
                      {createdAtLabel}
                    </dd>
                  </>
                )}

                {updatedAtLabel && (
                  <>
                    <dt className="flex items-center text-muted-foreground">
                      수정
                    </dt>
                    <dd className="flex items-center text-muted-foreground">
                      {updatedAtLabel}
                    </dd>
                  </>
                )}
              </dl>
            </div>
          </div>
        </div>
      </Card>

      <CommentThread
        comments={decoratedComments}
        onAdd={handleAddComment}
        onUpdate={handleUpdateComment}
        onDelete={handleDeleteComment}
        onToggleLike={handleToggleCommentLike}
        isAdding={isAddingComment}
        updatingCommentId={updatingCommentId}
        deletingCommentId={deletingCommentId}
        togglingLikeId={togglingCommentLikeId}
        isTogglingLike={isTogglingCommentLike}
      />
    </div>
  )
}
