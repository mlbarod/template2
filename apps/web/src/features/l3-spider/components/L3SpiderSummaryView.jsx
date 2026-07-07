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
const EMPTY_ARRAY = []

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

// High Risk step_seq 수 / High Risk EQPCH 수 분리 표기
function SsEq({ ss, eq }) {
  if (!ss && !eq) return <span className="text-muted-foreground/40">·</span>
  return (
    <span className="inline-flex items-center justify-center gap-0.5 tabular-nums leading-none">
      <span className="font-bold text-foreground">{formatNumber(ss)}</span>
      <span className="text-muted-foreground/40">/</span>
      <span className="font-bold text-destructive">{formatNumber(eq)}</span>
    </span>
  )
}

function MetricVal({ metric, hr, wn, ss, eq }) {
  if (metric === "hrpair") return <SsEq ss={ss} eq={eq} />
  return <HrWn hr={hr} wn={wn} />
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
  "#4f86f7", "#34c77b", "#f59e0b", "#a855f7", "#ec4899",
  "#06b6d4", "#10b981", "#6366f1", "#f43f5e", "#8b5cf6",
  "#14b8a6", "#f97316", "#84cc16", "#e879f9", "#38bdf8",
]

const DONUT_META = {
  hr:    { title: "High Risk 분포",          center: "High Risk" },
  wn:    { title: "Warning 분포",            center: "Warning" },
  total: { title: "이상 건수 분포 (HR+WN)", center: "이상 건수" },
}

// SVG 도넛 차트 — metric: "hr" | "wn" | "total"
// focusLine 선택 시 해당 라인의 process_id별 집계로 전환
function DonutChartCard({ lineSummary, cells, metric, focusLine }) {
  const { arcs, total, C, R } = useMemo(() => {
    const R = 30
    const C = 2 * Math.PI * R
    const getValue = (row) => metric === "hr" ? row.hr : metric === "wn" ? row.wn : row.hr + row.wn

    let rows
    if (focusLine) {
      // 선택된 라인의 process별 집계
      const byProcess = new Map()
      for (const c of (cells ?? [])) {
        if (c.line !== focusLine) continue
        const key = c.process
        const cur = byProcess.get(key) ?? { key, hr: 0, wn: 0 }
        cur.hr += c.highRisk
        cur.wn += c.warning
        byProcess.set(key, cur)
      }
      rows = [...byProcess.values()]
        .sort((a, b) => String(a.key).localeCompare(String(b.key), undefined, { numeric: true }))
        .filter((r) => getValue(r) > 0)
        .map((r) => ({ ...r, label: shortProcess(r.key) }))
    } else {
      rows = lineSummary
        .filter((r) => getValue(r) > 0)
        .map((r) => ({ ...r, key: r.line, label: r.line }))
    }

    const total = rows.reduce((s, r) => s + getValue(r), 0)
    const GAP = rows.length > 1 ? 1.5 : 0
    let off = 0
    const arcs = rows.map((r, i) => {
      const val = getValue(r)
      const fullLen = total > 0 ? (val / total) * C : 0
      const len = Math.max(0, fullLen - GAP)
      const seg = { key: r.key, label: r.label, val, color: LINE_COLORS[i % LINE_COLORS.length], len, off: off + GAP / 2 }
      off += fullLen
      return seg
    })
    return { arcs, total, C, R }
  }, [lineSummary, cells, metric, focusLine])

  const SW = 11
  const { title, center } = DONUT_META[metric] ?? DONUT_META.total

  return (
    <Card className="flex flex-col overflow-hidden rounded-lg py-0">
      <div className="shrink-0 flex items-center border-b bg-muted/50 px-4 h-9">
        <CardTitle className="text-[15px]">{title}</CardTitle>
      </div>
      <CardContent className="flex min-h-0 flex-1 items-center justify-center gap-3 px-3 py-2">
        <svg className="shrink-0" width="88" height="88" viewBox="0 0 88 88" aria-label={`${center} ${total}`}>
          <g transform="rotate(-90 44 44)">
            {total === 0 ? (
              <circle cx="44" cy="44" r={R} fill="none" stroke="hsl(var(--muted))" strokeWidth={SW} />
            ) : arcs.map((arc) => (
              <circle
                key={arc.key}
                cx="44" cy="44" r={R} fill="none"
                stroke={arc.color} strokeWidth={SW}
                strokeDasharray={`${arc.len} ${C}`}
                strokeDashoffset={-arc.off}
                strokeLinecap="butt"
              />
            ))}
          </g>
          <text x="44" y="40" textAnchor="middle" fontSize="14" fontWeight="700"
            fill="hsl(var(--foreground))">{formatNumber(total)}</text>
          <text x="44" y="53" textAnchor="middle" fontSize="8" fontWeight="600"
            fill="hsl(var(--muted-foreground))">{center}</text>
        </svg>
        {/* 범례 */}
        <div className="grid min-w-0 flex-1 gap-1 text-xs">
          {arcs.map((arc) => (
            <span key={arc.key} className="flex min-w-0 items-center gap-1">
              <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: arc.color }} aria-hidden="true" />
              <span className="min-w-0 truncate text-muted-foreground">{arc.label}</span>
              <span className="ml-auto shrink-0 tabular-nums font-semibold">{formatNumber(arc.val)}</span>
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

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
    <div className="min-h-0 overflow-y-auto">
      <table className="w-full border-collapse text-[13px]">
        <thead className="sticky top-0 z-10 bg-card">
          <tr className="border-b">
            <th className="w-6 px-1 py-2" />
            <th className="px-3 py-2 text-left font-semibold text-muted-foreground">Line</th>
            <th className="px-3 py-2 text-center font-semibold text-destructive">HR</th>
            <th className="px-3 py-2 text-center font-semibold text-chart-4">WN</th>
            <th className="px-3 py-2 text-center font-semibold text-muted-foreground">합계</th>
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
                  "px-3 py-1.5 font-mono font-semibold",
                  isSelected ? "text-primary" : "text-foreground",
                )}>
                  {r.line}
                  {!r.active && (
                    <span className="ml-1.5 text-[11px] font-normal text-muted-foreground">(이상 없음)</span>
                  )}
                </td>
                <td className="px-3 py-1.5 text-center tabular-nums">
                  {r.hr > 0
                    ? <span className="font-bold text-destructive">{formatNumber(r.hr)}</span>
                    : <span className="text-muted-foreground/40">·</span>}
                </td>
                <td className="px-3 py-1.5 text-center tabular-nums">
                  {r.wn > 0
                    ? <span className="font-semibold text-chart-4">{formatNumber(r.wn)}</span>
                    : <span className="text-muted-foreground/40">·</span>}
                </td>
                <td className="px-3 py-1.5 text-center tabular-nums font-medium">
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

function LegendDot({ className }) {
  return <span className={cn("size-2 rounded-full", className)} aria-hidden="true" />
}

function AnomalyMatrix({ matrix, selectedLine, onDrill, metric }) {
  const { edsSteps = EMPTY_ARRAY, cells = EMPTY_ARRAY } = matrix ?? {}
  const lines = matrix?.lines ?? EMPTY_ARRAY

  const visibleLines = useMemo(
    () => selectedLine ? lines.filter((line) => line === selectedLine) : lines,
    [lines, selectedLine],
  )
  const visibleCells = useMemo(
    () => selectedLine ? cells.filter((cell) => cell.line === selectedLine) : cells,
    [cells, selectedLine],
  )

  const { cellMap, processesByLine, lineTotals, colTotals, grand } = useMemo(() => {
    const cellMap = new Map()
    const processesByLine = new Map()
    const lineTotals = new Map()
    const colTotals = new Map()
    const grand = { hr: 0, wn: 0, ss: 0, eq: 0 }
    const add = (map, key, c) => {
      const cur = map.get(key) ?? { hr: 0, wn: 0, ss: 0, eq: 0 }
      cur.hr += c.highRisk
      cur.wn += c.warning
      cur.ss += c.hrStepSeqs || 0
      cur.eq += c.hrEqpchs || 0
      map.set(key, cur)
    }
    for (const c of visibleCells) {
      cellMap.set(`${c.line}||${c.process}||${c.edsStep}`, c)
      if (!processesByLine.has(c.line)) processesByLine.set(c.line, new Set())
      processesByLine.get(c.line).add(c.process)
      add(lineTotals, c.line, c)
      add(colTotals, c.edsStep, c)
      grand.hr += c.highRisk
      grand.wn += c.warning
      grand.ss += c.hrStepSeqs || 0
      grand.eq += c.hrEqpchs || 0
    }
    return { cellMap, processesByLine, lineTotals, colTotals, grand }
  }, [visibleCells])

  return (
    <div className="overflow-x-auto p-4">
      <table className="w-auto border-collapse text-[13px] leading-tight">
        <colgroup>
          <col className="w-24" />
          <col className="w-28" />
          {edsSteps.map((eds) => (
            <col key={eds} className="w-[72px]" />
          ))}
          <col className="w-20" />
        </colgroup>
        <thead className="sticky top-0 z-10 bg-card">
          <tr className="text-muted-foreground">
            <th className="sticky left-0 z-10 border-b bg-card px-3 py-2 text-left font-semibold">Line</th>
            <th className="border-b bg-card px-2.5 py-2 text-left font-semibold">Process</th>
            {edsSteps.map((eds) => (
              <th key={eds} className="border-b bg-card px-2 py-2 text-center font-semibold">{eds}</th>
            ))}
            <th className="border-b bg-card px-2 py-2 text-center font-semibold">합계</th>
          </tr>
        </thead>
        <tbody>
          {visibleLines.map((line) => {
            const processes = Array.from(processesByLine.get(line) ?? []).sort((a, b) =>
              String(a).localeCompare(String(b), undefined, { numeric: true }),
            )
            const lt = lineTotals.get(line) ?? { hr: 0, wn: 0, ss: 0, eq: 0 }
            return processes.map((process, idx) => {
              let rowHr = 0
              let rowWn = 0
              let rowSs = 0
              let rowEq = 0
              for (const eds of edsSteps) {
                const c = cellMap.get(`${line}||${process}||${eds}`)
                if (c) {
                  rowHr += c.highRisk
                  rowWn += c.warning
                  rowSs += c.hrStepSeqs || 0
                  rowEq += c.hrEqpchs || 0
                }
              }
              return (
                <tr key={`${line}||${process}`} className="hover:bg-muted/30">
                  {idx === 0 ? (
                    <td
                      rowSpan={processes.length}
                      className="sticky left-0 z-[1] border-b bg-card px-3 py-2 align-top font-mono font-semibold text-foreground"
                    >
                      <div className="flex flex-col gap-1 leading-tight">
                        <span>{line}</span>
                        <span className="text-[11px] font-normal">
                          <MetricVal metric={metric} hr={lt.hr} wn={lt.wn} ss={lt.ss} eq={lt.eq} />
                        </span>
                      </div>
                    </td>
                  ) : null}
                  <td className="border-b px-2.5 py-2 font-mono text-muted-foreground">{shortProcess(process)}</td>
                  {edsSteps.map((eds) => {
                    const cell = cellMap.get(`${line}||${process}||${eds}`)
                    if (!cell) {
                      return <td key={eds} className="border-b px-1.5 py-1.5 text-center text-muted-foreground/40">·</td>
                    }
                    return (
                      <td key={eds} className="border-b px-1.5 py-1.5">
                        <button
                          type="button"
                          onClick={() => onDrill?.({ line, process, edsStep: eds })}
                          title={`${line} · ${shortProcess(process)} · ${eds}\nHigh Risk ${cell.highRisk} · Warning ${cell.warning}\nHigh Risk step_seq ${cell.hrStepSeqs ?? 0} · EQPCH ${cell.hrEqpchs ?? 0} · bin ${cell.bins}종`}
                          className="flex h-8 w-full min-w-16 items-center justify-center rounded-md transition hover:bg-muted/50 hover:ring-1 hover:ring-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <MetricVal metric={metric} hr={cell.highRisk} wn={cell.warning} ss={cell.hrStepSeqs} eq={cell.hrEqpchs} />
                        </button>
                      </td>
                    )
                  })}
                  <td className="border-b px-2 py-2 text-center">
                    <MetricVal metric={metric} hr={rowHr} wn={rowWn} ss={rowSs} eq={rowEq} />
                  </td>
                </tr>
              )
            })
          })}
        </tbody>
        <tfoot>
          <tr className="bg-muted/50 font-semibold">
            <td className="sticky left-0 z-[1] bg-muted/50 px-3 py-2" colSpan={2}>합계</td>
            {edsSteps.map((eds) => {
              const ct = colTotals.get(eds) ?? { hr: 0, wn: 0, ss: 0, eq: 0 }
              return (
                <td key={eds} className="px-2 py-2 text-center">
                  <MetricVal metric={metric} hr={ct.hr} wn={ct.wn} ss={ct.ss} eq={ct.eq} />
                </td>
              )
            })}
            <td className="px-2 py-2 text-center">
              <MetricVal metric={metric} hr={grand.hr} wn={grand.wn} ss={grand.ss} eq={grand.eq} />
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

// 매트릭스 카드 (헤더 + 범례 + 테이블)
function MatrixCard({ title, legend, rows, cells, matrix, metric, selectedLine, onDrill }) {
  return (
    <Card className="flex min-w-0 flex-1 flex-col gap-0 overflow-hidden rounded-lg py-0">
      <div className="shrink-0 flex flex-wrap items-center gap-x-2 gap-y-1 border-b bg-muted/50 px-4 py-1.5">
        <CardTitle className="text-[15px]">{title}</CardTitle>
        {rows != null ? <Badge variant="outline">{formatNumber(rows)} rows</Badge> : null}
        {cells != null ? <Badge variant="secondary">{formatNumber(cells)} cells</Badge> : null}
        <span className="inline-flex items-center gap-2 text-[13px] text-muted-foreground">
          {legend}
          <span>셀 클릭 → Chart 탭</span>
        </span>
      </div>
      <CardContent className="min-h-0 p-0">
        <AnomalyMatrix matrix={matrix} metric={metric} selectedLine={selectedLine} onDrill={onDrill} />
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
    <Card className="flex min-h-[240px] min-w-0 flex-col overflow-hidden rounded-lg py-0">
      <div className="shrink-0 flex flex-wrap items-center gap-2 border-b bg-muted/50 px-4 py-1.5">
          <CardTitle className="text-[15px]">일자별 이상감지 트렌드</CardTitle>
          {focusLine && (
            <Badge variant="secondary" className="text-xs">{focusLine}</Badge>
          )}
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
            <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
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
                iconType="square"
                iconSize={8}
                wrapperStyle={{ fontSize: 12, paddingTop: 4 }}
              />
              {grouping === "sum" ? (
                <Bar
                  dataKey="value"
                  name={metric === "hr" ? "전체 High Risk" : "전체 이상 건수 (HR+WN)"}
                  fill={metric === "hr" ? "#ef4444" : "#f97316"}
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
    } catch {
      // localStorage 접근 실패 시 기본 정렬을 유지한다.
    }
  }, [storageKey])

  // 순서 변경 시 저장 (null 리셋은 저장하지 않음 — 별도로 removeItem)
  useEffect(() => {
    if (!storageKey || customLineOrder === null) return
    try {
      localStorage.setItem(storageKey, JSON.stringify(customLineOrder))
    } catch {
      // 저장 실패는 화면 동작을 막지 않는다.
    }
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

  const countLegend = (
    <>
      <LegendDot className="bg-destructive" />High Risk
      <span className="text-muted-foreground/40">/</span>
      <LegendDot className="bg-chart-4" />Warning
    </>
  )
  const hrpairLegend = (
    <>
      <LegendDot className="bg-foreground" />step_seq 수
      <span className="text-muted-foreground/40">/</span>
      <LegendDot className="bg-destructive" />EQPCH 수
    </>
  )

  const matrixCells = data?.matrix?.cells?.length ?? 0
  const matrixRows = data?.matrix?.lines?.length ?? 0

  return (
    <main className="grid gap-4 px-5 pb-5 pt-3">
      {/* 집계 카드 */}
      <SummaryStats h={h} />

      {/* col1=1fr(라인테이블 2행span), col2=1.4fr(도넛2개+트렌드) */}
      <div className="gap-4" style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gridTemplateRows: "auto minmax(180px, 1fr)", minHeight: 400 }}>
        {/* col1 row1+2: 라인별 현황 테이블 */}
        <Card
          className="flex min-h-0 flex-col overflow-hidden rounded-lg py-0"
          style={{ gridColumn: 1, gridRow: "1 / span 2" }}
        >
          <div className="shrink-0 flex items-center gap-2 border-b bg-muted/50 px-4 h-9">
            <CardTitle className="text-[15px]">라인별 현황</CardTitle>
            <Badge variant="outline" className="text-xs">{allLineOptions.length}개</Badge>
            {customLineOrder && (
              <button
                type="button"
                onClick={resetLineOrder}
                className="text-[13px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                순서초기화
              </button>
            )}
            {activeLine && (
              <button
                type="button"
                onClick={() => onSelectLine?.(null)}
                className="ml-auto text-[13px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                해제
              </button>
            )}
          </div>
          <CardContent className="min-h-0 flex-1 overflow-y-auto p-0">
            <LineTable rows={orderedLineSummary} selectedLine={activeLine} onSelectLine={onSelectLine} onReorder={handleReorder} />
          </CardContent>
        </Card>

        {/* col2 row1: 도넛 차트 3개 나란히 */}
        <div className="grid grid-cols-3 gap-3" style={{ gridColumn: 2, gridRow: 1 }}>
          <DonutChartCard lineSummary={lineSummary} cells={data?.matrix?.cells ?? []} metric="hr" focusLine={activeLine} />
          <DonutChartCard lineSummary={lineSummary} cells={data?.matrix?.cells ?? []} metric="wn" focusLine={activeLine} />
          <DonutChartCard lineSummary={lineSummary} cells={data?.matrix?.cells ?? []} metric="total" focusLine={activeLine} />
        </div>

        {/* col2 row2: 트렌드 바 차트 */}
        <TrendChartCard
          trendPoints={trendQuery.data?.points ?? []}
          allLineNames={trendLineNames}
          focusLine={activeLine ?? undefined}
        />
      </div>

      {/* 매트릭스 헤더 */}
      {activeLine && (
        <div className="flex items-center gap-3">
          <span className="text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">매트릭스</span>
          <Badge variant="secondary" className="text-[11px]">{activeLine} 필터 중</Badge>
        </div>
      )}

      {/* 매트릭스 나란히 */}
      <div className="grid grid-cols-2 gap-4">
        <MatrixCard
          title="Anomaly Summary"
          legend={countLegend}
          rows={matrixRows}
          cells={matrixCells}
          matrix={data.matrix}
          metric="count"
          selectedLine={activeLine}
          onDrill={onDrill}
        />
        <MatrixCard
          title="High Risk 발생"
          legend={hrpairLegend}
          matrix={data.matrix}
          metric="hrpair"
          selectedLine={activeLine}
          onDrill={onDrill}
        />
      </div>
    </main>
  )
}
