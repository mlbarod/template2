import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { Button } from "@/components/ui/button"
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
} from "@/components/ui/pagination"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

function getPaginationItems({ currentPage, totalPages, displayCount = 3 }) {
  const safeTotalPages = Math.max(1, Number(totalPages) || 1)
  const safeCurrentPage = Math.min(safeTotalPages, Math.max(1, Number(currentPage) || 1))
  const safeDisplayCount = Math.max(1, Number(displayCount) || 1)

  if (safeTotalPages <= safeDisplayCount) {
    return {
      pages: Array.from({ length: safeTotalPages }, (_, index) => index + 1),
      showLeftEllipsis: false,
      showRightEllipsis: false,
    }
  }

  const halfDisplay = Math.floor(safeDisplayCount / 2)
  let start = Math.max(1, safeCurrentPage - halfDisplay)
  let end = Math.min(safeTotalPages, start + safeDisplayCount - 1)

  if (end - start + 1 < safeDisplayCount) {
    start = Math.max(1, end - safeDisplayCount + 1)
  }

  const pages = Array.from({ length: end - start + 1 }, (_, index) => start + index)
  return {
    pages,
    showLeftEllipsis: pages[0] > 1,
    showRightEllipsis: pages[pages.length - 1] < safeTotalPages,
  }
}

export function AccountDataTablePagination({
  page = 1,
  pageSize = 20,
  total = 0,
  totalPages = 1,
  summary,
  disabled = false,
  showControls,
  onPageChange,
}) {
  const safePage = Math.max(1, Number(page) || 1)
  const safePageSize = Math.max(1, Number(pageSize) || 1)
  const safeTotal = Math.max(0, Number(total) || 0)
  const safeTotalPages = Math.max(1, Number(totalPages) || 1)
  const start = safeTotal > 0 ? (safePage - 1) * safePageSize + 1 : 0
  const end = safeTotal > 0 ? Math.min(safePage * safePageSize, safeTotal) : 0
  const canPrevious = safePage > 1
  const canNext = safePage < safeTotalPages
  const shouldShowControls = showControls ?? safeTotalPages > 1
  const { pages, showLeftEllipsis, showRightEllipsis } = getPaginationItems({
    currentPage: safePage,
    totalPages: safeTotalPages,
  })

  return (
    <div className="flex min-w-0 flex-col gap-3 border-t px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {summary || `표시 ${start.toLocaleString("ko-KR")}-${end.toLocaleString("ko-KR")} / 총 ${safeTotal.toLocaleString("ko-KR")}명`}
      </p>

      {shouldShowControls ? (
        <Pagination className="mx-0 w-auto justify-start sm:justify-end">
          <PaginationContent>
            <PaginationItem>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => onPageChange?.(safePage - 1)}
                disabled={!canPrevious || disabled}
                aria-label="이전 페이지"
              >
                <ChevronLeft className="size-4" />
                <span className="hidden sm:inline">이전</span>
              </Button>
            </PaginationItem>

            {showLeftEllipsis ? (
              <PaginationItem>
                <PaginationEllipsis />
              </PaginationItem>
            ) : null}

            {pages.map((pageNumber) => {
              const isActive = pageNumber === safePage
              return (
                <PaginationItem key={pageNumber}>
                  <Button
                    type="button"
                    size="icon-sm"
                    variant={isActive ? "default" : "ghost"}
                    onClick={() => onPageChange?.(pageNumber)}
                    disabled={disabled}
                    aria-current={isActive ? "page" : undefined}
                    aria-label={`${pageNumber}페이지`}
                  >
                    {pageNumber}
                  </Button>
                </PaginationItem>
              )
            })}

            {showRightEllipsis ? (
              <PaginationItem>
                <PaginationEllipsis />
              </PaginationItem>
            ) : null}

            <PaginationItem>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => onPageChange?.(safePage + 1)}
                disabled={!canNext || disabled}
                aria-label="다음 페이지"
              >
                <span className="hidden sm:inline">다음</span>
                <ChevronRight className="size-4" />
              </Button>
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      ) : null}
    </div>
  )
}

export function AccountDataTable({
  data,
  columns,
  getRowId,
  toolbar,
  isLoading = false,
  isFetching = false,
  error,
  emptyMessage = "표시할 사용자가 없습니다.",
  emptyAction,
  onRetry,
  pagination,
  className,
  tableClassName,
  onScrollEnd,
  ariaLabel = "사용자 목록",
}) {
  const safeData = Array.isArray(data) ? data : []
  const safeColumns = Array.isArray(columns) ? columns : []
  const table = useReactTable({
    data: safeData,
    columns: safeColumns,
    getRowId,
    getCoreRowModel: getCoreRowModel(),
  })
  const hasFooter = Boolean(pagination)
  const handleScroll = (event) => {
    if (!onScrollEnd) return
    const { scrollTop, scrollHeight, clientHeight } = event.currentTarget
    if (scrollHeight - scrollTop - clientHeight <= 96) {
      onScrollEnd()
    }
  }

  return (
    <div
      className={cn(
        "grid min-h-0 min-w-0 overflow-hidden rounded-lg border bg-card",
        toolbar && hasFooter && "grid-rows-[auto_minmax(0,1fr)_auto]",
        toolbar && !hasFooter && "grid-rows-[auto_minmax(0,1fr)]",
        !toolbar && hasFooter && "grid-rows-[minmax(0,1fr)_auto]",
        !toolbar && !hasFooter && "grid-rows-[minmax(0,1fr)]",
        className,
      )}
      aria-busy={isFetching || isLoading}
    >
      {toolbar ? <div className="min-w-0 border-b">{toolbar}</div> : null}

      <div className="min-h-0 min-w-0 overflow-auto" onScroll={handleScroll}>
        {isLoading ? (
          <div className="grid gap-3 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={`account-table-skeleton-${index}`} className="h-12 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="flex min-h-40 flex-col items-center justify-center gap-3 p-6" role="alert">
            <p className="text-sm text-destructive">{error}</p>
            {onRetry ? (
              <Button type="button" size="sm" variant="outline" onClick={onRetry}>
                <RefreshCw className="size-4" />
                다시 시도
              </Button>
            ) : null}
          </div>
        ) : table.getRowModel().rows.length === 0 ? (
          <div className="flex min-h-40 flex-col items-center justify-center gap-3 p-6 text-sm text-muted-foreground">
            <p>{emptyMessage}</p>
            {emptyAction || null}
          </div>
        ) : (
          <Table stickyHeader className={cn("min-w-[900px]", tableClassName)} aria-label={ariaLabel}>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} className="h-12 hover:bg-transparent">
                  {headerGroup.headers.map((header) => (
                    <TableHead
                      key={header.id}
                      className={cn(
                        "bg-muted/30 px-4 text-xs font-medium text-muted-foreground",
                        header.column.columnDef.meta?.headerClassName,
                      )}
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="group h-14 hover:bg-muted/40">
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={cn("px-4 py-2", cell.column.columnDef.meta?.cellClassName)}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {pagination ? (
        <AccountDataTablePagination
          {...pagination}
          summary={
            isLoading
              ? "사용자 목록을 불러오는 중..."
              : error
                ? "페이지 정보를 표시할 수 없습니다."
                : pagination.summary
          }
          showControls={isLoading || error ? false : pagination.showControls}
          disabled={pagination.disabled || isFetching || isLoading}
        />
      ) : null}
    </div>
  )
}
