import { BookOpen, Check, CircleHelp, Loader2, RefreshCw } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { motion } from "framer-motion"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import { L3SpiderGuideDialog } from "./L3SpiderGuideDialog"
import { EMPTY_SELECTION, sortedValues, sortLineNames, toggleSetValue } from "../utils/selection"

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
  dateLoading,
  rightContent,
  headerExtra,
  tabsSlot,
  showBody = true,
}) {
  const [guideDocumentKey, setGuideDocumentKey] = useState(null)
  const availabilityForDate = selection.date ? meta.availability?.[selection.date] ?? {} : {}
  const visibleLineIds = sortedValues(Object.keys(availabilityForDate))

  // LINE_NAME 모드에서는 lineGroups가 lineName을 (lineId, processIds[])로 매핑합니다.
  const lineGroups = meta.lineGroups ?? []
  const hasLineGroups = lineGroups.length > 0
  const lineGroupsForDate = lineGroups.filter((g) => g.lineId in availabilityForDate)
  // 선택 날짜에 '실제로 존재하는' line_name → process → [eds] (백엔드가 날짜·step_seq·제외필터 반영).
  // 패널 옵션은 전적으로 이걸로 → 그 날 데이터 없는 조합은 애초에 선택지에 안 뜬다.
  const lnaForDate = hasLineGroups ? (meta.lineNameAvailability?.[selection.date] ?? {}) : {}

  // Line 컬럼에 표시할 항목입니다. 설정이 있으면 LINE_NAME, 없으면 LINE_ID를 사용합니다.
  const lineItemsForPanel = hasLineGroups
    ? sortLineNames(Object.keys(lnaForDate))
    : visibleLineIds

  // Line 컬럼 패널의 선택값입니다. 모드에 따라 LINE_NAME 또는 LINE_ID가 들어갑니다.
  const selectedLineItemsForPanel = hasLineGroups
    ? (selection.lineNames ?? new Set())
    : selection.lineIds

  // 아래 edsStep 계산에는 항상 LINE_ID가 필요합니다.
  const selectedVisibleLineIds = sortedValues(selection.lineIds).filter((lineId) =>
    visibleLineIds.includes(lineId),
  )

  // line_name 모드에서는 선택 날짜에 실제로 존재하는 process만 허용합니다.
  const processIds = sortedValues(
    hasLineGroups
      ? new Set(
          [...(selection.lineNames ?? new Set())].flatMap((name) => Object.keys(lnaForDate[name] ?? {})),
        )
      : new Set(
          selectedVisibleLineIds.flatMap((lineId) => Object.keys(availabilityForDate[lineId] ?? {})),
        ),
  )

  const selectedVisibleProcessIds = sortedValues(selection.processIds).filter((processId) =>
    processIds.includes(processId),
  )
  // 선택된 line×process 에서 '실제 존재하는' eds 만 반환.
  // line_name 모드: lnaForDate(백엔드가 날짜·step_seq·제외필터 반영) 직접 사용 → 죽은 옵션 없음.
  // line_id 모드: 기존대로 availability 사용.
  const edsStepsFor = (lineNamesSet, lineIdList, processList) => {
    const out = new Set()
    if (hasLineGroups) {
      for (const name of lineNamesSet) {
        const procs = lnaForDate[name]
        if (!procs) continue
        for (const pid of processList) {
          for (const eds of procs[pid] ?? []) out.add(eds)
        }
      }
    } else {
      for (const lineId of lineIdList) {
        for (const pid of processList) {
          for (const eds of availabilityForDate[lineId]?.[pid] ?? []) out.add(eds)
        }
      }
    }
    return out
  }
  const edsSteps = sortedValues(
    edsStepsFor(selection.lineNames ?? new Set(), selectedVisibleLineIds, selectedVisibleProcessIds),
  )
  const hasDate = Boolean(selection.date && meta.dates?.includes(selection.date))
  const canFetch =
    hasDate &&
    selection.lineIds.size > 0 &&
    selection.processIds.size > 0 &&
    selection.edsSteps.size > 0
  const noData = Boolean(selection.date && visibleLineIds.length === 0)
  // date의 데이터 로딩이 끝나 ✓가 뜨는 순간 = Summary/Chart 선택을 유도할 시점
  const dateReady = hasDate && !dateLoading

  const changeDate = (date) => {
    onSelectionChange({ ...EMPTY_SELECTION, date })
  }

  // ✓가 새 날짜에 대해 처음 뜰 때마다 탭을 한 번 흔들어 주목을 끈다.
  const [wiggleKey, setWiggleKey] = useState(0)
  const lastWiggledDateRef = useRef(null)
  useEffect(() => {
    if (!hasDate) {
      lastWiggledDateRef.current = null
      return
    }
    if (dateReady && lastWiggledDateRef.current !== selection.date) {
      lastWiggledDateRef.current = selection.date
      setWiggleKey((k) => k + 1)
    }
  }, [dateReady, hasDate, selection.date])

  const changeLines = (selectedLineItems) => {
    let lineNames, lineIds, allowedProcessIds
    if (hasLineGroups) {
      lineNames = selectedLineItems
      // 조회용 line_id 는 lineGroups(전역)로 해석 — 행 단위 line_name 필터가 정확성 보장.
      const selectedGroups = lineGroupsForDate.filter((g) => lineNames.has(g.lineName))
      lineIds = new Set(selectedGroups.map((g) => g.lineId))
      // 선택 가능한 process 는 그 날짜 lnaForDate 기준(그 날 없는 process 배제).
      allowedProcessIds = new Set(
        [...lineNames].flatMap((name) => Object.keys(lnaForDate[name] ?? {})),
      )
    } else {
      lineNames = new Set()
      lineIds = selectedLineItems
      allowedProcessIds = new Set(
        sortedValues(lineIds).flatMap((lineId) => Object.keys(availabilityForDate[lineId] ?? {})),
      )
    }
    const nextProcessIds = new Set(
      sortedValues(selection.processIds).filter((pid) => allowedProcessIds.has(pid)),
    )
    const validEds = edsStepsFor(lineNames, sortedValues(lineIds), sortedValues(nextProcessIds))
    const nextEdsSteps = new Set(
      sortedValues(selection.edsSteps).filter((edsStep) => validEds.has(edsStep)),
    )
    onSelectionChange({ ...selection, lineNames, lineIds, processIds: nextProcessIds, edsSteps: nextEdsSteps })
  }

  const changeProcesses = (processIdsNext) => {
    const validEds = edsStepsFor(
      selection.lineNames ?? new Set(), selectedVisibleLineIds, sortedValues(processIdsNext),
    )
    const nextEdsSteps = new Set(
      sortedValues(selection.edsSteps).filter((edsStep) => validEds.has(edsStep)),
    )
    onSelectionChange({ ...selection, processIds: processIdsNext, edsSteps: nextEdsSteps })
  }

  const selectorCards = (
    <div className="grid h-[320px] grid-cols-[9rem_9rem_9rem] gap-4">
      <MultiSelectColumnCard
        title={hasLineGroups ? "Line Name" : "Line ID"}
        badge={`${lineItemsForPanel.length}`}
        disabled={!selection.date}
        placeholder="날짜를 먼저 선택하세요"
        items={lineItemsForPanel}
        selected={selectedLineItemsForPanel}
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
          <div className="flex items-center gap-3">
            {dateLoading ? (
              <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" aria-label="데이터 로딩 중" />
            ) : (
              <Check className="size-4 shrink-0 text-chart-2" aria-label="선택 완료" />
            )}
            {tabsSlot ? (
              <motion.div
                key={wiggleKey}
                animate={{ x: [0, -5, 5, -4, 4, -2, 2, 0] }}
                transition={{ duration: 0.6, ease: "easeInOut" }}
                className="flex items-center"
              >
                {tabsSlot}
              </motion.div>
            ) : null}
          </div>
        ) : null}
        <div className="ml-auto flex items-center gap-3">
          {showBody ? (
            <SelectionStatus
              canFetch={canFetch}
              date={selection.date}
              isLoading={isLoading}
              noData={noData}
              selection={selection}
            />
          ) : null}
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
          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    aria-label="L3 Spider 도움말 문서 열기"
                    title="도움말 문서"
                  >
                    <CircleHelp className="size-4" aria-hidden="true" />
                  </Button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent>도움말 문서</TooltipContent>
            </Tooltip>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel className="text-xs text-muted-foreground">L3 Spider 도움말</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={(event) => {
                  event.preventDefault()
                  setGuideDocumentKey("page")
                }}
                aria-label="L3 Spider 페이지 설명서 열기"
              >
                <BookOpen className="size-4" aria-hidden="true" />
                페이지 설명서
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={(event) => {
                  event.preventDefault()
                  setGuideDocumentKey("algorithm")
                }}
                aria-label="L3 Spider 알고리즘 설명서 열기"
              >
                <CircleHelp className="size-4" aria-hidden="true" />
                알고리즘 설명서
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <L3SpiderGuideDialog guideKey={guideDocumentKey} onGuideKeyChange={setGuideDocumentKey} />
      {showBody ? (
        rightContent ? (
          <div className="flex min-h-0 items-stretch gap-4 overflow-x-auto border-t px-6 py-2">
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
        )
      ) : null}
    </section>
  )
}
