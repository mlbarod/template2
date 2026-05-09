import { ArrowUpRight, Eye, Heart, MessageSquare, MoreHorizontal, Pencil, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"
import { CommentThread } from "./AppCommentThread"
import { ScreenshotCarousel } from "./ScreenshotCarousel"
import { resolveAppScreenshots } from "../utils/appScreenshots"

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

function DetailStat({ icon: Icon, label, value }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">
      <Icon className="size-3" />
      <span className="font-medium text-foreground">{value}</span>
      {label ? <span className="text-[10px] text-muted-foreground">{label}</span> : null}
    </div>
  )
}

export function AppDetail({
  app,
  isLoading,
  onOpenLink,
  onOpenManual,
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
  const { urls: resolvedScreenshotUrls, coverIndex } = resolveAppScreenshots(app)
  const contactParts = [app.contactName, app.contactKnoxid]
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter(Boolean)
  const contactText = contactParts.length ? contactParts.join(" · ") : "담당자 정보 없음"
  const manualUrl = typeof app.manualUrl === "string" ? app.manualUrl.trim() : ""
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
              {manualUrl ? (
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-8 gap-1.5 px-2 text-xs"
                  onClick={() => onOpenManual?.(app)}
                  type="button"
                >
                  Manual
                  <ArrowUpRight className="size-4" />
                </Button>
              ) : null}
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

                <dt className="flex items-center text-muted-foreground">
                  설명
                </dt>
                <dd className="flex items-center text-muted-foreground whitespace-pre-wrap break-words">
                  {app.description?.trim() ? app.description : "설명 없음"}
                </dd>
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
