import { RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import { EMPTY_SELECTION, sortedValues, toggleSetValue } from "../utils/selection"

function CheckboxPill({ checked, disabled, label, onChange }) {
  return (
    <label
      className={cn(
        "inline-flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition",
        checked
          ? "border-primary/50 bg-primary/10 text-primary"
          : "border-border bg-muted/40 text-muted-foreground",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={onChange}
        className="size-3.5 accent-primary"
      />
      <span>{label}</span>
    </label>
  )
}

function OptionGroup({ title, items, selected, disabled, onChange }) {
  const allChecked = items.length > 0 && items.every((item) => selected.has(item))
  const someChecked = selected.size > 0 && !allChecked

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="w-20 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </span>
      <CheckboxPill
        label="All"
        checked={allChecked}
        disabled={disabled || items.length === 0}
        onChange={() => onChange(allChecked ? new Set() : new Set(items))}
      />
      <div className="h-4 w-px shrink-0 bg-border" />
      <div className="flex min-w-0 flex-1 flex-wrap gap-1.5">
        {items.length === 0 ? (
          <span className="text-xs text-muted-foreground">선택 가능한 항목이 없습니다.</span>
        ) : (
          items.map((item) => (
            <CheckboxPill
              key={item}
              label={item}
              checked={selected.has(item)}
              disabled={disabled}
              onChange={() => onChange(toggleSetValue(selected, item))}
            />
          ))
        )}
      </div>
      <div className="ml-auto shrink-0 text-[10px] text-muted-foreground">
        {someChecked
          ? `${selected.size}/${items.length}`
          : allChecked
            ? "All selected"
            : `${selected.size}/${items.length}`}
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
    onSelectionChange({
      ...EMPTY_SELECTION,
      date,
    })
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
    onSelectionChange({
      ...selection,
      lineIds,
      processIds: nextProcessIds,
      edsSteps: nextEdsSteps,
    })
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
    onSelectionChange({
      ...selection,
      processIds: processIdsNext,
      edsSteps: nextEdsSteps,
    })
  }

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
        <div className="ml-auto flex items-center gap-3">
          <SelectionStatus
            canFetch={canFetch}
            date={selection.date}
            isLoading={isLoading}
            noData={noData}
            selection={selection}
          />
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
      <div className="grid gap-2 border-t px-6 py-2">
        <OptionGroup
          title="Line ID"
          items={visibleLineIds}
          selected={selection.lineIds}
          disabled={!selection.date}
          onChange={changeLines}
        />
        <OptionGroup
          title="Process ID"
          items={processIds}
          selected={selection.processIds}
          disabled={selectedVisibleLineIds.length === 0}
          onChange={changeProcesses}
        />
        <OptionGroup
          title="EDS Step"
          items={edsSteps}
          selected={selection.edsSteps}
          disabled={selectedVisibleProcessIds.length === 0}
          onChange={(edsStepsNext) =>
            onSelectionChange({ ...selection, edsSteps: edsStepsNext })}
        />
      </div>
    </section>
  )
}
