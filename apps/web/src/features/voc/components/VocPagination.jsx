import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Loader2,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export function VocPagination({
  isLoading,
  isRefreshing,
  filteredCount,
  visibleCount,
  statusFilter,
  pagination,
  onFirstPage,
  onPrevPage,
  onNextPage,
  onLastPage,
  onChangePageSize,
}) {
  return (
    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span aria-live="polite">
          {isLoading
            ? "VOC 게시글을 불러오는 중입니다..."
            : `총 ${filteredCount}건 중 ${visibleCount}건 표시`}
        </span>
        {statusFilter ? (
          <Badge variant="secondary" className="text-[11px]">
            {statusFilter} 상태
          </Badge>
        ) : null}
        {isRefreshing ? (
          <span className="inline-flex items-center gap-1 text-primary">
            <Loader2 className="size-3 animate-spin" aria-hidden="true" />
            새로고침 중
          </span>
        ) : null}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={onFirstPage}
            disabled={pagination.currentPage <= 1}
            aria-label="Go to first page"
            title="Go to first page"
          >
            <ChevronsLeft className="size-4" aria-hidden="true" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onPrevPage}
            disabled={pagination.currentPage <= 1}
            aria-label="Go to previous page"
            title="Go to previous page"
          >
            <ChevronLeft className="size-4" aria-hidden="true" />
          </Button>
          <span className="px-2 text-sm font-medium" aria-live="polite">
            Page {pagination.currentPage} of {pagination.totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={onNextPage}
            disabled={pagination.currentPage >= pagination.totalPages}
            aria-label="Go to next page"
            title="Go to next page"
          >
            <ChevronRight className="size-4" aria-hidden="true" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onLastPage}
            disabled={pagination.currentPage >= pagination.totalPages}
            aria-label="Go to last page"
            title="Go to last page"
          >
            <ChevronsRight className="size-4" aria-hidden="true" />
          </Button>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-xs text-muted-foreground">Rows per page</span>
          <select
            value={pagination.pageSize}
            onChange={(event) => onChangePageSize(Number(event.target.value))}
            className="h-8 rounded-md border border-input bg-background px-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
            aria-label="Rows per page"
            title="Rows per page"
          >
            {[5, 8, 10, 15, 20].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  )
}
