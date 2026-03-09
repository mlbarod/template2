// src/features/line-dashboard/components/DataTable.jsx
/** 
 * DataTable.jsx (React 19 최적화 버전)
 * ---------------------------------------------------------------------------
 * ✅ 핵심
 * 1) 컬럼 폭은 config에서 수동으로 정의합니다. (동적 자동폭 제거)
 * 2) <colgroup> + TH/TD width 동기화 ⇒ 컬럼 전체 폭이 일관되게 변함
 * 3) TanStack Table v8: 정렬/검색/컬럼 사이징/페이지네이션/퀵필터 그대로 유지
 * 4) React 19: useMemo/useCallback 최소화 (필요한 지점만 사용)
 *
 * ⚠️ 팁
 * - 폭 설정은 column-defs.jsx 내부의 createColumnDefs가 config.width 값을 사용해 처리합니다.
 *   화면에서 필요한 경우 config만 조정하면 됩니다.
 */

import * as React from "react"
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import {
  IconChevronDown,
  IconChevronUp,
} from "@tabler/icons-react"
import { cn } from "@/lib/utils"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/common"

import { DataTablePagination } from "./DataTablePagination"
import { DataTableToolbar } from "./DataTableToolbar"
import { StatusDistributionCard } from "./StatusDistributionCard"
import { createColumnDefs } from "../utils/dataTableColumnDefs"
import { createGlobalFilterFn } from "./GlobalFilter"
import { QuickFilters } from "./QuickFilters"
import { useDataTableState } from "../hooks/useDataTable"
import { useDataTablePresentation } from "../hooks/useDataTablePresentation"
import { useQuickFilters } from "../hooks/useQuickFilters"
import { useQuickFilterFavorites } from "../hooks/useQuickFilterFavorites"
import { useStatusChart } from "../hooks/useStatusChart"
import { numberFormatter } from "../utils/dataTableConstants"
import {
  getJustifyClass,
  getTextAlignClass,
  isNullishDisplay,
  resolveCellAlignment,
  resolveHeaderAlignment,
} from "../utils/dataTableTable"
import { formatTooltipValue } from "../utils/dataTableFormatters"
import { useAuth } from "@/lib/auth"

/* ────────────────────────────────────────────────────────────────────────────
 * 1) 라벨/문구 상수
 * ──────────────────────────────────────────────────────────────────────────── */
const EMPTY = {
  text: "",
  loading: "Loading rows…",
  noRows: "No rows returned.",
  noMatches: "No rows match your filter.",
}

const LABELS = {
  titleSuffix: "Line E-SOP Status",
  updated: "Updated",
  refresh: "Refresh",
  lineFilterModeTargetUserSdwt: "기본",
  lineFilterModeTargetUserSdwtDescription:
    "현재 Line소속 분임조로 인폼 예정인 모든 SOP 목록",
  lineFilterModeUserSdwt: "User분임조 기준",
  lineFilterModeUserSdwtDescription:
    "현재 Line에 소속된 엔지니어들이 보낸 모든 SOP 목록 (타 Line으로 보낸 SOP 포함)",
  lineFilterModeSdwt: "설비분임조 기준",
  lineFilterModeSdwtDescription:
    "현재 Line에 소속된 설비에 입력된 모든 SOP 목록 (타 Line엔지니어가 보낸 SOP 포함)",
  showing: "Showing",
  rows: "rows",
  filteredFrom: " (filtered from ",
  filteredFromSuffix: ")",
  rowsPerPage: "Rows per page",
  page: "Page",
  of: "of",
  goFirst: "Go to first page",
  goPrev: "Go to previous page",
  goNext: "Go to next page",
  goLast: "Go to last page",
}

const toWidthStyle = (size) => {
  const width = `${size}px`
  return { width, minWidth: width, maxWidth: width }
}

function TableBodyRows({
  table,
  emptyStateColSpan,
  isInitialLoading,
  rowsError,
  hasNoRows,
}) {
  if (isInitialLoading) {
    return (
      <TableRow>
        <TableCell
          colSpan={emptyStateColSpan}
          className="h-24 text-center text-sm text-muted-foreground"
          aria-live="polite"
        >
          {EMPTY.loading}
        </TableCell>
      </TableRow>
    )
  }

  if (rowsError) {
    return (
      <TableRow>
        <TableCell
          colSpan={emptyStateColSpan}
          className="h-24 text-center text-sm text-destructive"
          role="alert"
        >
          {rowsError}
        </TableCell>
      </TableRow>
    )
  }

  if (hasNoRows) {
    return (
      <TableRow>
        <TableCell
          colSpan={emptyStateColSpan}
          className="h-24 text-center text-sm text-muted-foreground"
          aria-live="polite"
        >
          {EMPTY.noRows}
        </TableCell>
      </TableRow>
    )
  }

  const visibleRows = table.getRowModel().rows
  if (visibleRows.length === 0) {
    return (
      <TableRow>
        <TableCell
          colSpan={emptyStateColSpan}
          className="h-24 text-center text-sm text-muted-foreground"
          aria-live="polite"
        >
          {EMPTY.noMatches}
        </TableCell>
      </TableRow>
    )
  }

  return visibleRows.map((row) => (
    <TableRow key={row.id}>
      {row.getVisibleCells().map((cell) => {
        const isEditable = Boolean(cell.column.columnDef.meta?.isEditable)
        const align = resolveCellAlignment(cell.column.columnDef.meta)
        const textAlignClass = getTextAlignClass(align)
        const isProcessFlowCell = cell.column.id === "process_flow"

        const raw = cell.getValue()
        const content = isNullishDisplay(raw)
          ? EMPTY.text
          : flexRender(cell.column.columnDef.cell, cell.getContext())
        const shouldTruncate = !isProcessFlowCell
        const tooltip = shouldTruncate ? formatTooltipValue(raw) : undefined

        return (
          <TableCell
            key={cell.id}
            data-editable={isEditable ? "true" : "false"}
            style={toWidthStyle(cell.column.getSize())}
            className={cn(
              "align-center",
              textAlignClass,
              !isEditable && "caret-transparent focus:outline-none",
              isProcessFlowCell && "cursor-grab select-none active:cursor-grabbing"
            )}
          >
            <div
              className={cn(
                "max-w-full",
                shouldTruncate ? "truncate" : "break-words"
              )}
              title={tooltip}
            >
              {content}
            </div>
          </TableCell>
        )
      })}
    </TableRow>
  ))
}

/**
 * @param {{ lineId: string }} props
 */
export function DataTable({ lineId }) {
  /* ──────────────────────────────────────────────────────────────────────────
   * 2) 데이터/상태 훅
   *    - rows: 서버/쿼리로 가져온 원본 데이터
   *    - filteredRows: QuickFilters + GlobalFilter 적용된 "현재 보이는" 데이터
   * ──────────────────────────────────────────────────────────────────────── */
  const {
    columns,
    rows,
    filter,
    setFilter,
    sorting,
    setSorting,
    lineFilterMode,
    setLineFilterMode,
    isLoadingRows,
    rowsError,
    fetchRows,
    tableMeta,
    setRecentHoursRange: syncRecentHoursRange,
  } = useDataTableState({ lineId })
  const { user } = useAuth()

  const quickFilterOptions = React.useMemo(
    () => ({ currentUserEmail: user?.email ?? null }),
    [user?.email]
  )

  const {
    sections,
    filters,
    filteredRows,
    activeCount,
    toggleFilter,
    resetFilters,
    replaceFilters,
  } = useQuickFilters(columns, rows, quickFilterOptions)

  const {
    favorites,
    saveFavorite,
    updateFavorite,
    applyFavorite,
    deleteFavorite,
  } = useQuickFilterFavorites({
    filters,
    sections,
    replaceFilters,
    ownerId: user?.email ?? null,
    lineId,
  })
  const [favoriteResetSignal, setFavoriteResetSignal] = React.useState(0)

  React.useEffect(() => {
    if (!syncRecentHoursRange) return
    syncRecentHoursRange(filters?.recent_hours ?? null)
  }, [filters?.recent_hours, syncRecentHoursRange])

  const statusSection = React.useMemo(
    () => sections.find((section) => section?.key === "status"),
    [sections]
  )

  const statusChart = useStatusChart({ filteredRows, statusSection })

  /* ──────────────────────────────────────────────────────────────────────────
   * 3) React 19 스타일: 필요한 지점만 useMemo
   * ──────────────────────────────────────────────────────────────────────── */
  const columnDefs = React.useMemo(() => {
    const firstVisibleRow = filteredRows?.[0]
    return createColumnDefs(columns, undefined, firstVisibleRow)
  }, [columns, filteredRows])

  // 글로벌 필터 함수: 컬럼 스키마가 바뀔 때만 재생성
  const globalFilterFn = React.useMemo(
    () => createGlobalFilterFn(columns),
    [columns]
  )

  /* 페이지네이션/컬럼 사이징 로컬 상태 */
  const [pagination, setPagination] = React.useState({ pageIndex: 0, pageSize: 15 })
  const [columnSizing, setColumnSizing] = React.useState({})

  /* TanStack Table 인스턴스 */
  const table = useReactTable({
    data: filteredRows,               // ✅ 보이는 데이터로 테이블 구성
    columns: columnDefs,              // ✅ config 기반 폭을 사용하는 컬럼 정의
    meta: tableMeta,
    state: {
      sorting,
      globalFilter: filter,
      pagination,
      columnSizing,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setFilter,
    onPaginationChange: setPagination,
    onColumnSizingChange: setColumnSizing,
    globalFilterFn,
    autoResetPageIndex: false,

    // Row models
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),

    // 드래그 중 실시간 리사이즈 반영
    columnResizeMode: "onChange",
  })

  /* 파생 값(렌더 편의) */
  const statusChartData = statusChart.data ?? []
  const statusChartConfig = statusChart.config ?? {}
  const {
    visibleColumns,
    emptyStateColSpan,
    totalLoaded,
    filteredTotal,
    hasNoRows,
    currentPage,
    totalPages,
    currentPageSize,
    isRefreshing,
    isInitialLoading,
    lastUpdatedLabel,
  } = useDataTablePresentation({
    table,
    columns,
    rows,
    filteredRows,
    filters,
    filter,
    sorting,
    isLoadingRows,
    rowsError,
    setPagination,
  })

  /* ──────────────────────────────────────────────────────────────────────────
   * 5) 이벤트 핸들러
   * ──────────────────────────────────────────────────────────────────────── */
  const handleClearFilters = React.useCallback(() => {
    resetFilters()
    setFavoriteResetSignal((previous) => previous + 1)
  }, [resetFilters])

  function handleRefresh() {
    void fetchRows()
  }

  /* ──────────────────────────────────────────────────────────────────────────
   * 7) 렌더
   *    - table-fixed + colgroup: 컬럼 단위 폭이 확실히 적용
   *    - Table 전체 width는 table.getTotalSize()로 지정 (px 문자열)
   * ──────────────────────────────────────────────────────────────────────── */
  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col">
      {/* 상단: 타이틀/리프레시 */}
      <DataTableToolbar
        lineId={lineId}
        labels={LABELS}
        lastUpdatedLabel={lastUpdatedLabel}
        lineFilterMode={lineFilterMode}
        onChangeLineFilterMode={setLineFilterMode}
        isRefreshing={isRefreshing}
        onRefresh={handleRefresh}
        favorites={{
          filters,
          favorites,
          onSaveFavorite: saveFavorite,
          onUpdateFavorite: updateFavorite,
          onApplyFavorite: applyFavorite,
          onDeleteFavorite: deleteFavorite,
          resetSignal: favoriteResetSignal,
        }}
      />
      <div className="mb-2">
        <QuickFilters
          sections={sections}
          filters={filters}
          activeCount={activeCount}
          onToggle={toggleFilter}
          onClear={handleClearFilters}
          globalFilterValue={filter}
          onGlobalFilterChange={setFilter}
          statusSidebar={
            <StatusDistributionCard
              data={statusChartData}
              config={statusChartConfig}
              total={filteredTotal}
            />
          }
        />
      </div>
      {/* 테이블 */}
      <div
        className="flex-1 min-h-0 min-w-0 overflow-y-auto rounded-lg border bg-background"
        aria-busy={isRefreshing}
      >
        <Table
          className="table-fixed w-full font-light"
          style={{ width: `${table.getTotalSize()}px`, tableLayout: "fixed" }}
          stickyHeader
        >
          {/* ✅ 컬럼 전체 폭 동기화: colgroup에 getVisibleLeafColumns() 사이즈를 반영 */}
          <colgroup>
            {visibleColumns.map((column) => (
              <col key={column.id} style={toWidthStyle(column.getSize())} />
            ))}
          </colgroup>

          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort()
                  const sortDirection = header.column.getIsSorted() // "asc" | "desc" | false 값
                  const meta = header.column.columnDef.meta
                  const align = resolveHeaderAlignment(meta)
                  const justifyClass = getJustifyClass(align)
                  const headerContent = flexRender(header.column.columnDef.header, header.getContext())

                  const ariaSort =
                    sortDirection === "asc"
                      ? "ascending"
                      : sortDirection === "desc"
                        ? "descending"
                        : "none"

                  return (
                    <TableHead
                      key={header.id}
                      className={cn("relative whitespace-nowrap sticky top-0 z-10 bg-muted ")}
                      style={toWidthStyle(header.getSize())}
                      scope="col"
                      aria-sort={ariaSort}
                    >
                      {canSort ? (
                        <button
                          className={cn("flex w-full items-center gap-1", justifyClass)}
                          onClick={header.column.getToggleSortingHandler()}
                          aria-label={`Sort by ${String(header.column.id)}`}
                        >
                          {headerContent}
                          {sortDirection === "asc" && <IconChevronUp className="size-4" />}
                          {sortDirection === "desc" && <IconChevronDown className="size-4" />}
                        </button>
                      ) : (
                        <div className={cn("flex w-full items-center gap-1", justifyClass)}>
                          {headerContent}
                        </div>
                      )}

                      {/* 컬럼 리사이저 (시각적 핸들) */}
                      <span
                        onMouseDown={header.getResizeHandler()}
                        onTouchStart={header.getResizeHandler()}
                        className="absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none"
                        role="separator"
                        aria-orientation="vertical"
                        aria-label={`Resize column ${String(header.column.id)}`}
                        tabIndex={-1}
                      />
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>

          <TableBody>
            <TableBodyRows
              table={table}
              emptyStateColSpan={emptyStateColSpan}
              isInitialLoading={isInitialLoading}
              rowsError={rowsError}
              hasNoRows={hasNoRows}
            />
          </TableBody>
        </Table>
      </div>

      {/* 하단: 요약/페이지네이션 */}
      <DataTablePagination
        labels={LABELS}
        numberFormatter={numberFormatter}
        table={table}
        currentPage={currentPage}
        totalPages={totalPages}
        currentPageSize={currentPageSize}
        filteredTotal={filteredTotal}
        totalLoaded={totalLoaded}
        pagination={pagination}
      />
    </section>
  )
}
