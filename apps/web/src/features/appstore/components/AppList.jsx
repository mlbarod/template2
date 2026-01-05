// 앱 목록 컴포넌트
import { ArrowUpRight, Eye, Heart, MessageSquare } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

function StatBadge({ icon: Icon, value, label }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">
      <Icon className="size-3" />
      <span className="font-medium text-foreground">{value}</span>
      {label && <span className="text-[10px] text-muted-foreground">{label}</span>}
    </div>
  )
}

export function AppList({
  apps,
  selectedAppId,
  onSelect,
  onOpenLink,
  onToggleLike: _onToggleLike,
  onEdit: _onEdit,
  onDelete: _onDelete,
  isLoading,
}) {
  if (isLoading) {
    return (
      <Card className="border bg-card shadow-sm">
        <CardContent className="p-6 text-sm text-muted-foreground">목록을 불러오는 중...</CardContent>
      </Card>
    )
  }

  if (!apps?.length) {
    return (
      <Card className="border bg-card shadow-sm">
        <CardContent className="p-6 text-sm text-muted-foreground">
          조건에 맞는 앱이 없습니다. 새로운 앱을 등록해 보세요.
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fit,280px)] gap-3">
      {apps.map((app) => {
        const isSelected = selectedAppId === app.id
        const coverSrc =
          app.screenshotUrl ||
          (Array.isArray(app.screenshotUrls) ? app.screenshotUrls[app.coverScreenshotIndex ?? 0] : "")

        return (
          <Card
            key={app.id}
            onClick={() => onSelect(app.id)}
            className={cn(
              "flex h-full min-h-[200px] cursor-pointer flex-col gap-2 py-3 overflow-hidden border bg-card shadow-sm transition hover:-translate-y-0.5 hover:shadow-md",
              isSelected && "border-primary/60 ring-1 ring-primary/30",
            )}
          >
            {/* ✅ 상단을 2컬럼(그리드)로 분리 */}
            {/* 예: 뱃지(선택) */}
            <div className="flex items-center justify-between px-5 py-1">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold leading-none">
                  {app.name}
                </div>
              </div>

              <Badge
                variant="secondary"
                className="shrink-0 text-[9px] leading-none"
              >
                {app.category || "기타"}
              </Badge>
            </div>
            <div className="flex justify-center px-3 py-2">
              {/* 왼쪽: 스크린샷 */}
              <div className="relative h-32 w-60 overflow-hidden rounded-md bg-muted ring-1 ring-border">
                {coverSrc ? (
                  <img
                    src={coverSrc}
                    alt={`${app.name} 스크린샷`}
                    className="h-full w-full object-contain"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                    스크린샷 없음
                  </div>
                )}
              </div>

              {/* 오른쪽: 앱 이름 */}

            </div>

            <CardContent className="flex flex-1 flex-col gap-2 px-3 py-1">


              <Separator className="bg-border" />

              <div className="mt-auto flex items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1">
                  <StatBadge icon={Eye} value={app.viewCount} />
                  <StatBadge icon={Heart} value={app.likeCount} />
                  <StatBadge icon={MessageSquare} value={app.commentCount ?? 0} />
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 gap-1 px-2 text-xs text-primary hover:bg-primary/10"
                  onClick={(event) => {
                    event.stopPropagation()
                    onOpenLink?.(app)
                  }}
                >
                  Link
                  <ArrowUpRight className="size-3" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
