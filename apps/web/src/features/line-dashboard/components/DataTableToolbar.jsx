// src/features/line-dashboard/components/DataTableToolbar.jsx
import { IconDatabase, IconRefresh } from "@tabler/icons-react"

import { cn } from "@/lib/utils"
import { Button } from "components/ui/button"
import { LINE_FILTER_MODE_OPTIONS } from "../utils/lineFilterMode"
import { QuickFilterFavorites } from "./QuickFilterFavorites"

/**
 * 테이블 상단의 타이틀, 즐겨찾기, 새로고침 버튼을 묶어둔 헤더입니다.
 * - DataTable은 상태 계산에 집중하고, 이 컴포넌트는 UI 조립만 담당합니다.
 */
export function DataTableToolbar({
  lineId,
  labels,
  lastUpdatedLabel,
  lineFilterMode,
  onChangeLineFilterMode,
  isRefreshing,
  onRefresh,
  favorites,
}) {
  const {
    filters,
    favorites: favoriteList,
    onSaveFavorite,
    onUpdateFavorite,
    onApplyFavorite,
    onDeleteFavorite,
    resetSignal,
  } = favorites ?? {}
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <IconDatabase className="size-5" />
          {lineId} {labels.titleSuffix}
          <span
            className="ml-2 text-[10px] font-normal text-muted-foreground self-end"
            aria-live="polite"
          >
            {labels.updated} {lastUpdatedLabel || "-"}
          </span>
        </div>
      </div>

      <div className="ml-auto flex flex-wrap items-end gap-2">
        <div className="flex flex-col items-start gap-1">
          <span className="pl-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Line Filter
          </span>
          <div
            role="radiogroup"
            aria-label="Line Filter"
            className="flex h-8 items-center gap-1 rounded-md border border-input bg-background px-1"
          >
            {LINE_FILTER_MODE_OPTIONS.map((option) => {
              const isSelected = lineFilterMode === option.value
              const description = labels[option.descriptionKey] ?? ""
              return (
                <div key={option.value} className="group relative">
                  <label
                    className={cn(
                      "inline-flex h-6 items-center gap-1.5 rounded px-2 text-[10px] font-medium text-foreground whitespace-nowrap",
                      isSelected && "text-primary"
                    )}
                  >
                    <input
                      type="radio"
                      name="line-filter-mode"
                      className="h-3.5 w-3.5 accent-primary"
                      checked={isSelected}
                      onChange={() => onChangeLineFilterMode?.(option.value)}
                    />
                    <span>{labels[option.labelKey]}</span>
                  </label>
                  <div className="pointer-events-none absolute left-1/2 top-full z-40 mt-1 w-max max-w-64 -translate-x-1/2 rounded-md bg-foreground px-2 py-1 text-[11px] text-background opacity-0 shadow-sm transition-opacity duration-100 group-hover:opacity-100">
                    {description}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
        <QuickFilterFavorites
          filters={filters}
          favorites={favoriteList}
          onSaveFavorite={onSaveFavorite}
          onUpdateFavorite={onUpdateFavorite}
          onApplyFavorite={onApplyFavorite}
          onDeleteFavorite={onDeleteFavorite}
          resetSignal={resetSignal}
        />
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          className="gap-1"
          aria-label={labels.refresh}
          title={labels.refresh}
          aria-busy={isRefreshing}
        >
          <IconRefresh className={cn("size-3", isRefreshing && "animate-spin")} />
          {labels.refresh}
        </Button>
      </div>
    </div>
  )
}
