import { Activity, AlertTriangle, Check, Gauge, RefreshCw } from "lucide-react"
import { useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import { EMPTY_SELECTION, sortedValues, toggleSetValue } from "../utils/selection"
import { formatNumber } from "../utils/format"

function MultiSelectColumnCard({ title, badge, disabled, placeholder, items, selected, onChange }) {
  const [query, setQuery] = useState("")
  const isActive = selected.size > 0
  const allSelected = items.length > 0 && items.every((item) => selected.has(item))

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? items.filter((item) => item.toLowerCase().includes(q)) : items
  }, [items, query])

  return (
    <Card
      className={cn(
        "grid min-h-0 grid-rows-[48px_40px_minmax(0,1fr)] gap-0 overflow-hidden rounded-xl border bg-card py-0 shadow-sm transition-all",
        isActive && "ring-2 ring-primary/50",
      )}
    >
      <div
        className={cn(
          "flex h-12 items-center border-b px-4",
          isActive ? "bg-primary/10" : "bg-muted/40",
        )}
      >
        <div className="flex h-full min-w-0 flex-1 items-center justify-between gap-2">
          <CardTitle
            className={cn(
              "truncate text-sm font-semibold leading-5",
              disabled && "text-muted-foreground",
              isActive && "text-primary",
            )}
          >
            {title}
          </CardTitle>
          {badge != null && (
            <Badge variant={isActive ? "default" : "secondary"} className="shrink-0 text-[11px]">
              {badge}
            </Badge>
          )}
        </div>
      </div>
      <div className="border-b px-2 py-1.5">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="검색…"
          className="h-7 text-xs"
          disabled={disabled}
        />
      </div>
      <CardContent className="min-h-0 overflow-y-auto bg-background/60 p-2">
        {disabled ? (
          <div className="flex h-full min-h-16 items-center justify-center text-center text-sm text-muted-foreground">
            {placeholder}
          </div>
        ) : (
          <div className="grid content-start gap-1.5">
            <button
              type="button"
              onClick={() => onChange(allSelected ? new Set() : new Set(items))}
              className={cn(
                "flex h-9 w-full items-center justify-between gap-3 rounded-md border border-transparent px-3 text-left transition",
                "hover:border-border hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                allSelected && "border-primary/30 bg-primary/10 shadow-sm",
              )}
            >
              <span className={cn("text-[13px] font-medium leading-5 text-foreground", allSelected && "text-primary")}>
                All
              </span>
              <Check className={cn("size-3 shrink-0", allSelected ? "text-primary" : "text-transparent")} />
            </button>
            <div className="h-px bg-border" />
            {filteredItems.map((item) => {
              const isSelected = selected.has(item)
              return (
                <button
                  key={item}
                  type="button"
                  onClick={() => onChange(toggleSetValue(selected, item))}
                  className={cn(
                    "flex h-9 w-full items-center justify-between gap-3 rounded-md border border-transparent px-3 text-left transition",
                    "hover:border-border hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isSelected && "border-primary/30 bg-primary/10 shadow-sm",
                  )}
                >
                  <span className={cn("flex-1 truncate text-[13px] font-medium leading-5 text-foreground", isSelected && "text-primary")}>
                    {item}
                  </span>
                  <Check className={cn("size-3 shrink-0", isSelected ? "text-primary" : "text-transparent")} />
                </button>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function InlineStats({ stats }) {
  return (
    <div className="flex items-center gap-5 border-l pl-5">
      <div className="flex items-center gap-1.5">
        <AlertTriangle className="size-3.5 shrink-0 text-chart-4" aria-hidden="true" />
        <span className="text-sm font-semibold tabular-nums text-chart-4">{formatNumber(stats?.anomalySteps)}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Anomaly Steps</span>
      </div>
      <div className="flex items-center gap-1.5">
        <Activity className="size-3.5 shrink-0 text-destructive" aria-hidden="true" />
        <span className="text-sm font-semibold tabular-nums text-destructive">{formatNumber(stats?.highRiskEqpchs)}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">High Risk EQPCH</span>
      </div>
      <div className="flex items-center gap-1.5">
        <Gauge className="size-3.5 shrink-0" aria-hidden="true" />
        <span className="text-sm font-semibold tabular-nums">{formatNumber(stats?.total)}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Total Rows</span>
      </div>
    </div>
  )
}

function SelectionStatus({ canFetch, date, isLoading, noData, selection }) {
  if (isLoading) return <span className="text-xs italic text-muted-foreground">로딩 중…</span>
  if (noData) return <span className="text-xs font-semibold text-destructive">불러올 데이터가 없습니다</span>
  if (canFetch) {
    return (
      <span className="text-xs text-muted-foreground">
        {date} · {selection.lineIds.size} lines · {selection.processIds.size} procs ·{" "}
        {selection.edsSteps.size} EDS steps
      </span>
    )
  }
  return <span className="text-xs text-muted-foreground">날짜 · 라인 · 프로세스 · EDS Step을 선택하세요</span>
}

export function L3SpiderDataSelector({
  meta,
  selection,
  onSelectionChange,
  isLoading,
  onRefresh,
  stats,
  showStats,
  rightContent,
  headerExtra,
}) {
  const availabilityForDate = selection.date ? meta.availability?.[selection.date] ?? {} : {}
  const visibleLineIds = sortedValues(Object.keys(availabilityForDate))
  const selectedVisibleLineIds = sortedValues(selection.lineIds).filter((lineId) =>
    visibleLineIds.includes(lineId),
  )
  const processIds = sortedValues(
    new Set(
      selectedVisibleLineIds.flatMap((lineId) =>
        Object.keys(availabilityForDate[lineId] ?? {}),
      ),
    ),
  )
  const selectedVisibleProcessIds = sortedValues(selection.processIds).filter((processId) =>
    processIds.includes(processId),
  )
  const edsSteps = sortedValues(
    new Set(
      selectedVisibleLineIds.flatMap((lineId) =>
        selectedVisibleProcessIds.flatMap(
          (processId) => availabilityForDate[lineId]?.[processId] ?? [],
        ),
      ),
    ),
  )
  const hasDate = Boolean(selection.date && meta.dates?.includes(selection.date))
  const canFetch =
    hasDate &&
    selection.lineIds.size > 0 &&
    selection.processIds.size > 0 &&
    selection.edsSteps.size > 0
  const noData = Boolean(selection.date && visibleLineIds.length === 0)

  const changeDate = (date) => {
    onSelectionChange({ ...EMPTY_SELECTION, date })
  }

  const changeLines = (lineIds) => {
    const nextProcessIds = new Set(
      sortedValues(selection.processIds).filter((processId) =>
        sortedValues(
          new Set(
            sortedValues(lineIds).flatMap((lineId) =>
              Object.keys(availabilityForDate[lineId] ?? {}),
            ),
          ),
        ).includes(processId),
      ),
    )
    const nextEdsSteps = new Set(
      sortedValues(selection.edsSteps).filter((edsStep) =>
        sortedValues(
          new Set(
            sortedValues(lineIds).flatMap((lineId) =>
              sortedValues(nextProcessIds).flatMap(
                (processId) => availabilityForDate[lineId]?.[processId] ?? [],
              ),
            ),
          ),
        ).includes(edsStep),
      ),
    )
    onSelectionChange({ ...selection, lineIds, processIds: nextProcessIds, edsSteps: nextEdsSteps })
  }

  const changeProcesses = (processIdsNext) => {
    const nextEdsSteps = new Set(
      sortedValues(selection.edsSteps).filter((edsStep) =>
        sortedValues(
          new Set(
            selectedVisibleLineIds.flatMap((lineId) =>
              sortedValues(processIdsNext).flatMap(
                (processId) => availabilityForDate[lineId]?.[processId] ?? [],
              ),
            ),
          ),
        ).includes(edsStep),
      ),
    )
    onSelectionChange({ ...selection, processIds: processIdsNext, edsSteps: nextEdsSteps })
  }

  const selectorCards = (
    <div className="grid h-[320px] grid-cols-3 gap-4">
      <MultiSelectColumnCard
        title="Line ID"
        badge={`${visibleLineIds.length}`}
        disabled={!selection.date}
        placeholder="날짜를 먼저 선택하세요"
        items={visibleLineIds}
        selected={selection.lineIds}
        onChange={changeLines}
      />
      <MultiSelectColumnCard
        title="Process ID"
        badge={processIds.length > 0 ? `${processIds.length}` : null}
        disabled={selectedVisibleLineIds.length === 0}
        placeholder="Line ID를 먼저 선택하세요"
        items={processIds}
        selected={selection.processIds}
        onChange={changeProcesses}
      />
      <MultiSelectColumnCard
        title="EDS Step"
        badge={edsSteps.length > 0 ? `${edsSteps.length}` : null}
        disabled={selectedVisibleProcessIds.length === 0}
        placeholder="Process ID를 먼저 선택하세요"
        items={edsSteps}
        selected={selection.edsSteps}
        onChange={(edsStepsNext) => onSelectionChange({ ...selection, edsSteps: edsStepsNext })}
      />
    </div>
  )

  return (
    <section className="shrink-0 border-b bg-card">
      <div className="flex flex-wrap items-center gap-6 px-6 py-2.5">
        <label className="flex items-center gap-2">
          <span className="w-20 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Date
          </span>
          <Input
            type="date"
            value={selection.date}
            min={meta.dates?.[0] ?? ""}
            max={meta.dates?.[meta.dates.length - 1] ?? ""}
            onChange={(event) => changeDate(event.target.value)}
            className="h-8 w-36 bg-muted/40 text-xs"
          />
        </label>
        {selection.date && !hasDate ? (
          <span className="text-xs font-medium text-destructive">해당 날짜에 데이터 없음</span>
        ) : hasDate ? (
          <span className="text-xs font-medium text-chart-2">✓ {selection.date}</span>
        ) : null}
        {showStats && stats && <InlineStats stats={stats} />}
        <div className="ml-auto flex items-center gap-3">
          <SelectionStatus
            canFetch={canFetch}
            date={selection.date}
            isLoading={isLoading}
            noData={noData}
            selection={selection}
          />
          {headerExtra}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={cn("size-4", isLoading && "animate-spin")} />
            새로고침
          </Button>
        </div>
      </div>
      {rightContent ? (
        <div className="flex min-h-0 items-stretch gap-4 border-t px-6 py-2">
          <div className="shrink-0">
            {selectorCards}
          </div>
          <div className="min-w-0 flex-1">
            {rightContent}
          </div>
        </div>
      ) : (
        <div className="border-t px-6 py-2">
          {selectorCards}
        </div>
      )}
    </section>
  )
}
