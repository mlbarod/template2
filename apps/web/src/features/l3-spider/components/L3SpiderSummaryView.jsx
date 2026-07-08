import { useEffect, useMemo, useRef, useState } from "react"
import { Activity, AlertTriangle, Cpu, Gauge, Inbox, Layers, Loader2 } from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { useAuth } from "@/lib/auth"

import { useL3SpiderDailySummary, useL3SpiderTrend } from "../hooks/useL3SpiderQueries"
import { formatNumber } from "../utils/format"
import { sortLineNames } from "../utils/selection"

const shortProcess = (value) => String(value ?? "").replace(/^process_/, "")

// High Risk / Warning 분리 표기 (빨강 / 주황)
function HrWn({ hr, wn }) {
  if (!hr && !wn) return <span className="text-muted-foreground/40">·</span>
  return (
    <span className="inline-flex items-center justify-center gap-0.5 tabular-nums leading-none">
      <span className="font-bold text-destructive">{formatNumber(hr)}</span>
      <span className="text-muted-foreground/40">/</span>
      <span className="font-semibold text-chart-4">{formatNumber(wn)}</span>
    </span>
  )
}

const STAT_DEFS = [
  { key: "groups", label: "분석 그룹", icon: Layers, tone: "text-foreground" },
  { key: "highRisk", label: "High Risk", icon: Activity, tone: "text-destructive" },
  { key: "warning", label: "Warning", icon: AlertTriangle, tone: "text-chart-4" },
  { key: "anomalies", label: "이상 건수", icon: Gauge, tone: "text-foreground" },
  { key: "highRiskEqpchs", label: "이상 EQPCH", icon: Cpu, tone: "text-destructive" },
]

function SummaryStats({ h }) {
  return (
    <Card className="min-w-0 overflow-hidden rounded-lg py-0">
      <div className="flex flex-wrap items-center">
        {STAT_DEFS.map(({ key, label, icon: Icon, tone }) => (
          <div key={key} className="flex items-center gap-3 border-r px-5 py-3 last:border-r-0">
            <Icon className={cn("size-4 shrink-0", tone)} aria-hidden="true" />
            <div className="min-w-0">
              <p className={cn("text-[22px] font-semibold leading-none tabular-nums", tone)}>
                {formatNumber(h[key])}
              </p>
              <p className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {label}
              </p>
            </div>
          </div>
        ))}
        <div className="ml-auto px-5 py-3 text-right text-xs leading-tight text-muted-foreground">
          Line {formatNumber(h.lines)} · Process {formatNumber(h.processes)} · EDS {formatNumber(h.edsSteps)}
          <br />
          Bin {formatNumber(h.binNames)} · 총 {formatNumber(h.totalRows)}행
        </div>
      </div>
    </Card>
  )
}

// 라인별 고유 색상 팔레트
const LINE_COLORS = [
  "hsl(217 91% 58%)", "hsl(142 71% 42%)", "hsl(38 92% 48%)",
  "hsl(262 83% 58%)", "hsl(326 78% 52%)", "hsl(189 94% 38%)",
  "hsl(15 88% 54%)", "hsl(88 67% 40%)", "hsl(245 72% 60%)",
  "hsl(168 76% 36%)", "hsl(284 72% 56%)", "hsl(348 83% 57%)",
  "hsl(199 89% 48%)", "hsl(113 54% 43%)", "hsl(29 92% 52%)",
  "hsl(229 76% 55%)", "hsl(310 68% 50%)", "hsl(54 90% 42%)",
  "hsl(175 72% 34%)", "hsl(3 78% 57%)",
]

// 전 라인 요약 테이블 — 이상감지 없는 라인도 포함, 클릭 시 매트릭스 필터, 드래그로 순서 변경
function LineTable({ rows, selectedLine, onSelectLine, onReorder }) {
  const dragIdx = useRef(null)
  const [dragOver, setDragOver] = useState(null)

  function handleDragStart(e, idx) {
    dragIdx.current = idx
    e.dataTransfer.effectAllowed = "move"
  }
  function handleDragOver(e, idx) {
    e.preventDefault()
    e.dataTransfer.dropEffect = "move"
    if (idx !== dragIdx.current) setDragOver(idx)
  }
  function handleDrop(e, idx) {
    e.preventDefault()
    if (dragIdx.current !== null && dragIdx.current !== idx) {
      onReorder?.(dragIdx.current, idx)
    }
    dragIdx.current = null
    setDragOver(null)
  }
  function handleDragEnd() {
    dragIdx.current = null
    setDragOver(null)
  }

  return (
    <div className="h-full min-h-0 overflow-y-auto">
      <table className="w-full table-fixed border-collapse text-[13px]">
        <colgroup>
          <col className="w-7" />
          <col />
          <col className="w-14" />
          <col className="w-14" />
          <col className="w-16" />
        </colgroup>
        <thead className="sticky top-0 z-10 bg-card">
          <tr className="border-b">
            <th className="px-1 py-2" />
            <th className="px-2 py-2 text-left font-semibold text-muted-foreground">Line</th>
            <th className="px-2 py-2 text-right font-semibold text-destructive">HR</th>
            <th className="px-2 py-2 text-right font-semibold text-chart-4">WN</th>
            <th className="px-2 py-2 text-right font-semibold text-muted-foreground">합계</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => {
            const isSelected = r.line === selectedLine
            const isDragTarget = dragOver === idx
            const total = r.hr + r.wn
            return (
              <tr
                key={r.line}
                draggable
                onDragStart={(e) => handleDragStart(e, idx)}
                onDragOver={(e) => handleDragOver(e, idx)}
                onDrop={(e) => handleDrop(e, idx)}
                onDragEnd={handleDragEnd}
                onClick={() => onSelectLine?.(isSelected ? null : r.line)}
                className={cn(
                  "border-b transition-colors cursor-pointer",
                  isDragTarget && "border-t-2 border-t-primary",
                  isSelected
                    ? "bg-primary/10 hover:bg-primary/15"
                    : "hover:bg-muted/40",
                  !r.active && "opacity-40",
                )}
              >
                <td
                  className="w-6 cursor-grab px-1 py-1.5 text-center text-base text-muted-foreground/50 active:cursor-grabbing"
                  onClick={(e) => e.stopPropagation()}
                >
                  ⠿
                </td>
                <td className={cn(
                  "truncate px-2 py-1.5 font-mono font-semibold",
                  isSelected ? "text-primary" : "text-foreground",
                )}>
                  {r.line}
                  {!r.active && (
                    <span className="ml-1.5 text-[11px] font-normal text-muted-foreground">(이상 없음)</span>
                  )}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">
                  {r.hr > 0
                    ? <span className="font-bold text-destructive">{formatNumber(r.hr)}</span>
                    : <span className="text-muted-foreground/40">·</span>}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">
                  {r.wn > 0
                    ? <span className="font-semibold text-chart-4">{formatNumber(r.wn)}</span>
                    : <span className="text-muted-foreground/40">·</span>}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums font-medium">
                  {total > 0
                    ? <span className="text-foreground">{formatNumber(total)}</span>
                    : <span className="text-muted-foreground/40">·</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ProcessEdsSummaryCard({ matrix, selectedLine, onDrill }) {
  const { edsSteps = [], cells = [] } = matrix ?? {}
  const showLineColumn = !selectedLine
  const scopedCells = useMemo(
    () => selectedLine ? cells.filter((cell) => cell.line === selectedLine) : cells,
    [cells, selectedLine],
  )

  const { rows, activeEdsSteps, cellMap, rowTotals, colTotals, grand, cellCount, lineCount, processCount } = useMemo(() => {
    const cellMap = new Map()
    const rowMap = new Map()
    const lineSet = new Set()
    const processSet = new Set()
    const edsSet = new Set()
    const rowTotals = new Map()
    const colTotals = new Map()
    const grand = { hr: 0, wn: 0 }

    function addTotals(map, key, hr, wn) {
      const current = map.get(key) ?? { hr: 0, wn: 0 }
      current.hr += hr
      current.wn += wn
      map.set(key, current)
    }

    for (const cell of scopedCells) {
      const hr = cell.highRisk ?? 0
      const wn = cell.warning ?? 0
      if (hr + wn <= 0) continue

      const rowKey = selectedLine ? cell.process : `${cell.line}||${cell.process}`
      if (!rowMap.has(rowKey)) {
        rowMap.set(rowKey, { key: rowKey, line: cell.line, process: cell.process })
      }

      const key = `${rowKey}||${cell.edsStep}`
      const current = cellMap.get(key) ?? { hr: 0, wn: 0 }
      current.hr += hr
      current.wn += wn
      cellMap.set(key, current)

      lineSet.add(cell.line)
      processSet.add(cell.process)
      edsSet.add(cell.edsStep)
      addTotals(rowTotals, rowKey, hr, wn)
      addTotals(colTotals, cell.edsStep, hr, wn)
      grand.hr += hr
      grand.wn += wn
    }

    const activeEdsSteps = (edsSteps.length ? edsSteps : [...edsSet]).filter((eds) => edsSet.has(eds))
    const lineOrder = new Map(sortLineNames([...lineSet]).map((line, index) => [line, index]))
    const rows = [...rowMap.values()].sort((a, b) => {
      if (!selectedLine) {
        const lineDelta = (lineOrder.get(a.line) ?? 0) - (lineOrder.get(b.line) ?? 0)
        if (lineDelta) return lineDelta
      }
      const left = rowTotals.get(a.key) ?? { hr: 0, wn: 0 }
      const right = rowTotals.get(b.key) ?? { hr: 0, wn: 0 }
      return (right.hr + right.wn) - (left.hr + left.wn)
        || String(a.process).localeCompare(String(b.process), undefined, { numeric: true })
    })

    return {
      rows,
      activeEdsSteps,
      cellMap,
      rowTotals,
      colTotals,
      grand,
      cellCount: cellMap.size,
      lineCount: lineSet.size,
      processCount: processSet.size,
    }
  }, [scopedCells, edsSteps, selectedLine])

  const hasRows = rows.length > 0 && activeEdsSteps.length > 0

  return (
    <Card className="flex h-[560px] min-w-0 flex-col overflow-hidden rounded-lg py-0">
      <div className="flex h-11 shrink-0 items-center gap-2 border-b bg-muted/50 px-4">
        <CardTitle className="text-[15px]">Process ID x EDS Step 이상감지 요약</CardTitle>
        <Badge variant={selectedLine ? "secondary" : "outline"} className="min-w-[86px] justify-center text-xs">
          {selectedLine ? `${selectedLine} 선택` : "전체 라인"}
        </Badge>
        {!selectedLine ? <Badge variant="outline" className="text-xs">{formatNumber(lineCount)} Line</Badge> : null}
        <Badge variant="outline" className="text-xs">{formatNumber(processCount)} Process</Badge>
        <Badge variant="outline" className="text-xs">{formatNumber(activeEdsSteps.length)} EDS</Badge>
        <Badge variant="secondary" className="text-xs">{formatNumber(cellCount)} cells</Badge>
        <span className="ml-auto text-[13px] text-muted-foreground">
          HR <span className="font-semibold text-destructive">{formatNumber(grand.hr)}</span>
          <span className="px-1 text-muted-foreground/40">/</span>
          WN <span className="font-semibold text-chart-4">{formatNumber(grand.wn)}</span>
        </span>
      </div>
      <CardContent className="min-h-0 flex-1 overflow-auto p-3">
        {!hasRows ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            선택 범위에 표시할 Process x EDS 이상감지가 없습니다.
          </div>
        ) : (
          <table className="w-full min-w-max border-collapse text-[13px] leading-tight">
            <colgroup>
              {showLineColumn ? <col className="w-32" /> : null}
              <col className="w-36" />
              {activeEdsSteps.map((eds) => (
                <col key={eds} className="w-[82px]" />
              ))}
              <col className="w-24" />
            </colgroup>
            <thead className="sticky top-0 z-10 bg-card">
              <tr className="text-muted-foreground">
                {showLineColumn ? (
                  <th className="sticky left-0 z-20 border-b bg-card px-3 py-2 text-left font-semibold">line_name</th>
                ) : null}
                <th className={cn(
                  "sticky z-20 border-b bg-card px-3 py-2 text-left font-semibold",
                  showLineColumn ? "left-32" : "left-0",
                )}>
                  Process ID
                </th>
                {activeEdsSteps.map((eds) => (
                  <th key={eds} className="border-b bg-card px-2 py-2 text-center font-semibold">{eds}</th>
                ))}
                <th className="border-b bg-card px-2 py-2 text-center font-semibold">합계</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const rowTotal = rowTotals.get(row.key) ?? { hr: 0, wn: 0 }
                return (
                  <tr key={row.key} className="hover:bg-muted/30">
                    {showLineColumn ? (
                      <td className="sticky left-0 z-[1] border-b bg-card px-3 py-2 font-mono font-semibold text-foreground">
                        {row.line}
                      </td>
                    ) : null}
                    <td className={cn(
                      "sticky z-[1] border-b bg-card px-3 py-2 font-mono font-semibold text-foreground",
                      showLineColumn ? "left-32" : "left-0",
                    )}>
                      {shortProcess(row.process)}
                    </td>
                    {activeEdsSteps.map((eds) => {
                      const cell = cellMap.get(`${row.key}||${eds}`)
                      if (!cell) {
                        return <td key={eds} className="border-b px-1.5 py-1.5 text-center text-muted-foreground/40">·</td>
                      }
                      return (
                        <td key={eds} className="border-b px-1.5 py-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              onDrill?.({ line: row.line, process: row.process, edsStep: eds })
                            }}
                            title={`${row.line} · ${shortProcess(row.process)} · ${eds} · High Risk ${cell.hr} · Warning ${cell.wn}`}
                            className="flex h-8 w-full min-w-16 items-center justify-center rounded-md transition hover:bg-muted/50 hover:ring-1 hover:ring-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <HrWn hr={cell.hr} wn={cell.wn} />
                          </button>
                        </td>
                      )
                    })}
                    <td className="border-b px-2 py-2 text-center">
                      <HrWn hr={rowTotal.hr} wn={rowTotal.wn} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr className="bg-muted/50 font-semibold">
                {showLineColumn ? (
                  <td className="sticky left-0 z-[1] bg-muted/50 px-3 py-2">합계</td>
                ) : null}
                <td className={cn(
                  "sticky z-[1] bg-muted/50 px-3 py-2",
                  showLineColumn ? "left-32" : "left-0",
                )}>
                  {showLineColumn ? "" : "합계"}
                </td>
                {activeEdsSteps.map((eds) => {
                  const colTotal = colTotals.get(eds) ?? { hr: 0, wn: 0 }
                  return (
                    <td key={eds} className="px-2 py-2 text-center">
                      <HrWn hr={colTotal.hr} wn={colTotal.wn} />
                    </td>
                  )
                })}
                <td className="px-2 py-2 text-center">
                  <HrWn hr={grand.hr} wn={grand.wn} />
                </td>
              </tr>
            </tfoot>
          </table>
        )}
      </CardContent>
    </Card>
  )
}

// 날짜 "2026-06-20" → "06-20"
const fmtDate = (d) => String(d ?? "").slice(5)

// startStr~endStr 사이 모든 날짜(UTC 기준) 배열 반환 — 최대 366일 캡
function makeDateRange(startStr, endStr) {
  const dates = []
  const cur = new Date(startStr + "T00:00:00Z")
  const end = new Date(endStr + "T00:00:00Z")
  while (+cur <= +end && dates.length < 366) {
    dates.push(cur.toISOString().slice(0, 10))
    cur.setUTCDate(cur.getUTCDate() + 1)
  }
  return dates
}

const RANGE_OPTIONS = [
  { label: "7일", value: 7 },
  { label: "14일", value: 14 },
  { label: "30일", value: 30 },
  { label: "90일", value: 90 },
  { label: "전체", value: 0 },
]

// 트렌드 바 차트 카드 — recharts BarChart
function TrendChartCard({ trendPoints, allLineNames, focusLine }) {
  const [metric, setMetric] = useState("hr")     // "hr" | "total"
  const [grouping, setGrouping] = useState("sum") // "sum" | "perLine"
  const [rangeDays, setRangeDays] = useState(7)   // 0 = 전체

  // focusLine 선택 시 해당 라인만, 아니면 전체
  const scopedPoints = useMemo(
    () => focusLine ? (trendPoints ?? []).filter((p) => p.lineName === focusLine) : (trendPoints ?? []),
    [trendPoints, focusLine],
  )

  // focusLine 선택 시 seriesKeys를 해당 라인만으로 좁힘
  const effectiveLineNames = useMemo(
    () => focusLine ? [focusLine] : allLineNames,
    [focusLine, allLineNames],
  )

  // 날짜 범위 필터 — 전체 데이터에서 최신 기준 N일치만
  const filteredPoints = useMemo(() => {
    if (!scopedPoints.length) return []
    if (rangeDays === 0) return scopedPoints
    const allDates = [...new Set(scopedPoints.map((p) => p.date))].sort()
    const cutoff = allDates[Math.max(0, allDates.length - rangeDays)]
    return scopedPoints.filter((p) => p.date >= cutoff)
  }, [scopedPoints, rangeDays])

  // 데이터 변환: [{date, lineName, hr, wn}] → recharts용 [{date, ...series}]
  const { chartData, seriesKeys } = useMemo(() => {
    if (!filteredPoints.length) return { chartData: [], seriesKeys: [] }
    const getValue = (p) => metric === "hr" ? p.hr : p.hr + p.wn

    if (grouping === "sum") {
      const byDate = new Map()
      for (const p of filteredPoints) {
        byDate.set(p.date, (byDate.get(p.date) ?? 0) + getValue(p))
      }
      // 이상감지 없는 날짜는 0으로 채워 연속 time-series 유지
      const sortedKeys = [...byDate.keys()].sort()
      if (sortedKeys.length > 1) {
        for (const d of makeDateRange(sortedKeys[0], sortedKeys[sortedKeys.length - 1])) {
          if (!byDate.has(d)) byDate.set(d, 0)
        }
      }
      const chartData = [...byDate.entries()].sort(([a], [b]) => a.localeCompare(b))
        .map(([date, value]) => ({ date: fmtDate(date), value }))
      return { chartData, seriesKeys: ["value"] }
    }

    // perLine: pivot — 날짜 갭은 0으로 채움
    // 날짜 × 라인 조합이 2000 초과 시 렌더링 폭발 방지를 위해 sum으로 폴백
    const dateSet = new Set()
    for (const p of filteredPoints) dateSet.add(p.date)
    const rawDates = [...dateSet].sort()
    const dates = rawDates.length > 1
      ? makeDateRange(rawDates[0], rawDates[rawDates.length - 1])
      : rawDates
    if (dates.length * effectiveLineNames.length > 2000) {
      const byDate = new Map()
      for (const p of filteredPoints) byDate.set(p.date, (byDate.get(p.date) ?? 0) + getValue(p))
      const chartData = [...byDate.entries()].sort(([a], [b]) => a.localeCompare(b))
        .map(([date, value]) => ({ date: fmtDate(date), value }))
      return { chartData, seriesKeys: ["value"] }
    }

    const byDateLine = new Map()
    for (const p of filteredPoints) {
      if (!byDateLine.has(p.date)) byDateLine.set(p.date, {})
      byDateLine.get(p.date)[p.lineName] = (byDateLine.get(p.date)[p.lineName] ?? 0) + getValue(p)
    }
    const chartData = dates.map((d) => {
      const lineValues = byDateLine.get(d) ?? {}
      const row = { date: fmtDate(d) }
      for (const ln of effectiveLineNames) row[ln] = lineValues[ln] ?? 0
      return row
    })
    return { chartData, seriesKeys: effectiveLineNames }
  }, [filteredPoints, metric, grouping, effectiveLineNames])

  return (
    <Card className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-lg py-0">
      <div className="shrink-0 flex flex-wrap items-center gap-2 border-b bg-muted/50 px-4 py-1.5">
          <CardTitle className="text-[15px]">일자별 이상감지 트렌드</CardTitle>
          <Badge
            variant="secondary"
            className={cn("min-w-[72px] justify-center text-xs", !focusLine && "invisible")}
          >
            {focusLine ?? "전체"}
          </Badge>
          {/* 기간 선택 */}
          <div className="flex items-center rounded border bg-background p-0.5 text-[13px]">
            {RANGE_OPTIONS.map((opt) => (
              <button key={opt.value} type="button" onClick={() => setRangeDays(opt.value)}
                className={cn("rounded px-2 py-0.5 font-medium transition-colors",
                  rangeDays === opt.value ? "bg-muted text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>
                {opt.label}
              </button>
            ))}
          </div>
          {/* Y축 토글 */}
          <div className="flex items-center rounded border bg-background p-0.5 text-[13px]">
            <button type="button" onClick={() => setMetric("hr")}
              className={cn("rounded px-2 py-0.5 font-medium transition-colors",
                metric === "hr" ? "bg-destructive/10 text-destructive" : "text-muted-foreground hover:text-foreground")}>
              HR
            </button>
            <button type="button" onClick={() => setMetric("total")}
              className={cn("rounded px-2 py-0.5 font-medium transition-colors",
                metric === "total" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")}>
              HR+WN
            </button>
          </div>
          {/* 계열 토글 */}
          <div className="flex items-center rounded border bg-background p-0.5 text-[13px]">
            <button type="button" onClick={() => setGrouping("sum")}
              className={cn("rounded px-2 py-0.5 font-medium transition-colors",
                grouping === "sum" ? "bg-background text-foreground shadow-sm ring-1 ring-border" : "text-muted-foreground hover:text-foreground")}>
              전체 합산
            </button>
            <button type="button" onClick={() => setGrouping("perLine")}
              className={cn("rounded px-2 py-0.5 font-medium transition-colors",
                grouping === "perLine" ? "bg-background text-foreground shadow-sm ring-1 ring-border" : "text-muted-foreground hover:text-foreground")}>
              라인별
            </button>
          </div>
      </div>
      <CardContent className="min-h-[180px] flex-1 p-2">
        {chartData.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            트렌드 데이터가 없습니다.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%" debounce={60}>
            <BarChart data={chartData} margin={{ top: 4, right: 12, left: 0, bottom: 4 }} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal vertical />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={false}
                width={52}
                tickFormatter={(v) => formatNumber(v)}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "6px",
                  fontSize: 13,
                }}
                formatter={(value, name) => [formatNumber(value), name === "value" ? (metric === "hr" ? "High Risk" : "이상 건수") : name]}
                labelFormatter={(label) => `날짜: ${label}`}
                cursor={{ fill: "hsl(var(--muted))", opacity: 0.5 }}
              />
              <Legend
                layout="vertical"
                align="right"
                verticalAlign="middle"
                width={150}
                iconType="square"
                iconSize={8}
                wrapperStyle={{ fontSize: 12, lineHeight: "18px", maxHeight: "100%", overflowY: "auto", paddingLeft: 12 }}
              />
              {grouping === "sum" ? (
                <Bar
                  dataKey="value"
                  name={metric === "hr" ? "전체 High Risk" : "전체 이상 건수 (HR+WN)"}
                  fill={metric === "hr" ? "hsl(var(--destructive))" : "hsl(var(--chart-4))"}
                  radius={[3, 3, 0, 0]}
                  maxBarSize={48}
                />
              ) : (seriesKeys.length <= 20 ? seriesKeys : seriesKeys.slice(0, 20)).map((key, i) => (
                <Bar
                  key={key}
                  dataKey={key}
                  name={key}
                  stackId="a"
                  fill={LINE_COLORS[i % LINE_COLORS.length]}
                  radius={i === seriesKeys.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
                  maxBarSize={48}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}

export function L3SpiderSummaryView({ date, onDrill, selectedLine, onSelectLine, lineGroups }) {
  const query = useL3SpiderDailySummary(date)
  const trendQuery = useL3SpiderTrend()
  const data = query.data
  const h = data?.headline
  const hasData = Boolean(h && h.totalRows > 0)

  // 오늘 이상감지가 있는 라인 (활성)
  const activeLineOptions = useMemo(
    () => sortLineNames(data?.matrix?.lines ?? []),
    [data?.matrix?.lines],
  )
  // 전체 알려진 라인 (lineGroups 기반, end_fab 마지막)
  const allLineOptions = useMemo(() => {
    const fromGroups = sortLineNames([...new Set((lineGroups ?? []).map((g) => g.lineName))])
    const base = fromGroups.length ? fromGroups : []
    const baseSet = new Set(base)
    const extras = activeLineOptions.filter((l) => !baseSet.has(l))
    return extras.length ? sortLineNames([...base, ...extras]) : base.length ? base : activeLineOptions
  }, [lineGroups, activeLineOptions])

  // 선택된 라인 — 활성/비활성 모두 허용 (트렌드 필터링 등)
  const activeLine = selectedLine ?? null

  // 라인별 이상감지 롤업 — 모든 알려진 라인 포함
  const lineSummary = useMemo(() => {
    const totals = new Map()
    for (const c of data?.matrix?.cells ?? []) {
      const cur = totals.get(c.line) ?? { hr: 0, wn: 0 }
      cur.hr += c.highRisk ?? 0
      cur.wn += c.warning ?? 0
      totals.set(c.line, cur)
    }
    const activeSet = new Set(activeLineOptions)
    return allLineOptions.map((line) => ({
      line,
      hr: totals.get(line)?.hr ?? 0,
      wn: totals.get(line)?.wn ?? 0,
      active: activeSet.has(line),
    }))
  }, [data?.matrix?.cells, allLineOptions, activeLineOptions])

  // 트렌드 차트용 line_name 목록 (트렌드 데이터에 등장하는 라인, end_fab 마지막 정렬)
  const trendLineNames = useMemo(
    () => sortLineNames([...new Set((trendQuery.data?.points ?? []).map((p) => p.lineName))]),
    [trendQuery.data?.points],
  )

  // 유저 지정 순서 (드래그로 변경, null = 기본 정렬) — 로그인 사용자별 localStorage 영속
  const { user } = useAuth()
  const storageKey = user?.email ? `l3spider:lineOrder:${user.email}` : null

  const [customLineOrder, setCustomLineOrder] = useState(null)

  // 사용자 확인 후 저장된 순서 복원 (사용자 변경 시 재실행)
  useEffect(() => {
    if (!storageKey) return
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) setCustomLineOrder(JSON.parse(saved))
    } catch {}
  }, [storageKey])

  // 순서 변경 시 저장 (null 리셋은 저장하지 않음 — 별도로 removeItem)
  useEffect(() => {
    if (!storageKey || customLineOrder === null) return
    try {
      localStorage.setItem(storageKey, JSON.stringify(customLineOrder))
    } catch {}
  }, [storageKey, customLineOrder])

  function handleReorder(fromIdx, toIdx) {
    const names = lineSummary.map((r) => r.line)
    const next = customLineOrder ? [...customLineOrder] : [...names]
    const [moved] = next.splice(fromIdx, 1)
    next.splice(toIdx, 0, moved)
    setCustomLineOrder(next)
  }

  function resetLineOrder() {
    setCustomLineOrder(null)
    if (storageKey) localStorage.removeItem(storageKey)
  }

  const orderedLineSummary = useMemo(() => {
    if (!customLineOrder) return lineSummary
    const map = new Map(lineSummary.map((r) => [r.line, r]))
    const ordered = customLineOrder.map((name) => map.get(name)).filter(Boolean)
    const extras = lineSummary.filter((r) => !customLineOrder.includes(r.line))
    return [...ordered, ...extras]
  }, [lineSummary, customLineOrder])

  if (!date || query.isLoading || query.error || !hasData) {
    let message
    if (!date && (trendQuery.isLoading || !lineGroups)) {
      message = (
        <span className="inline-flex items-center gap-2">
          <Loader2 className="size-4 animate-spin" /> 데이터를 불러오는 중입니다.
        </span>
      )
    } else if (!date) {
      message = "날짜를 선택하면 해당 날짜 전체의 이상감지 요약을 조회합니다."
    } else if (query.isLoading) {
      message = (
        <span className="inline-flex items-center gap-2">
          <Loader2 className="size-4 animate-spin" /> 요약을 불러오는 중입니다.
        </span>
      )
    } else if (query.error) {
      message = <span className="text-destructive">{query.error.message || "요약을 불러오지 못했습니다."}</span>
    } else {
      message = (
        <span className="inline-flex flex-col items-center gap-2 text-center">
          <Inbox className="size-6" aria-hidden="true" />
          {date} 날짜에 데이터가 없습니다.
        </span>
      )
    }
    return (
      <main className="grid gap-5 px-6 pb-6 pt-4">
        <Card className="rounded-lg">
          <CardContent className="flex min-h-64 items-center justify-center p-6 text-sm text-muted-foreground">
            {message}
          </CardContent>
        </Card>
      </main>
    )
  }

  return (
    <main className="grid gap-4 px-5 pb-5 pt-3">
      <SummaryStats h={h} />

      <div className="grid h-[520px] min-w-0 grid-cols-[420px_minmax(0,1fr)] gap-4">
        <Card className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-lg py-0">
          <div className="flex h-10 shrink-0 items-center gap-2 border-b bg-muted/50 px-4">
            <CardTitle className="text-[15px]">라인별 이상감지 요약</CardTitle>
            <Badge variant="outline" className="text-xs">{formatNumber(allLineOptions.length)}개</Badge>
            {customLineOrder && (
              <button
                type="button"
                onClick={resetLineOrder}
                className="text-[13px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                순서초기화
              </button>
            )}
            <button
              type="button"
              onClick={() => onSelectLine?.(null)}
              disabled={!activeLine}
              className={cn(
                "ml-auto text-[13px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline",
                !activeLine && "invisible pointer-events-none",
              )}
            >
              해제
            </button>
          </div>
          <CardContent className="min-h-0 flex-1 p-0">
            <LineTable rows={orderedLineSummary} selectedLine={activeLine} onSelectLine={onSelectLine} onReorder={handleReorder} />
          </CardContent>
        </Card>

        <TrendChartCard
          trendPoints={trendQuery.data?.points ?? []}
          allLineNames={trendLineNames}
          focusLine={activeLine ?? undefined}
        />
      </div>

      <ProcessEdsSummaryCard
        matrix={data.matrix}
        selectedLine={activeLine}
        onDrill={onDrill}
      />
    </main>
  )
}
