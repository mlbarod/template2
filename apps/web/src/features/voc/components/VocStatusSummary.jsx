import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

import { STATUS_OPTIONS } from "../utils/constants"
import { VocStatusBadge } from "./VocStatusBadge"

export function VocStatusSummary({
  totalPosts,
  statusCounts,
  statusFilter,
  isMyPostsOnly,
  onClearStatusFilter,
  onToggleStatusFilter,
  onToggleMyPostsOnly,
}) {
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>상태별 문의 현황</span>
          <span className="rounded-full bg-muted px-2 py-1 text-xs font-semibold text-foreground shadow-xs">
            {statusFilter ? `${statusFilter}만 보기` : "전체 보기"}
            {isMyPostsOnly ? " · 내 VOC" : ""}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant={isMyPostsOnly ? "secondary" : "outline"}
            size="sm"
            onClick={onToggleMyPostsOnly}
            aria-pressed={isMyPostsOnly}
          >
            내 VOC
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClearStatusFilter}
            disabled={!statusFilter}
          >
            필터 해제
          </Button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <button
          type="button"
          onClick={onClearStatusFilter}
          className={`rounded-lg border px-4 py-2 text-left shadow-xs transition hover:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 ${
            !statusFilter ? "border-primary bg-primary/10" : "bg-muted/40"
          }`}
          aria-pressed={!statusFilter}
          aria-label="모든 상태 보기"
        >
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>전체</span>
            <Badge variant="outline" className="border-primary/40 text-[11px]">
              all
            </Badge>
          </div>
          <div className="mt-2 text-2xl font-semibold">{totalPosts}</div>
        </button>
        {STATUS_OPTIONS.map((option) => (
          <button
            type="button"
            key={option.value}
            onClick={() => onToggleStatusFilter(option.value)}
            className={`rounded-lg border px-4 py-2 text-left shadow-xs transition hover:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 ${
              statusFilter === option.value ? "border-primary bg-primary/10" : "bg-muted/40"
            }`}
            aria-pressed={statusFilter === option.value}
          >
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{option.value}</span>
              <VocStatusBadge status={option.value} />
            </div>
            <div className="mt-2 text-2xl font-semibold">
              {statusCounts[option.value] ?? 0}
            </div>
          </button>
        ))}
      </div>
    </>
  )
}
