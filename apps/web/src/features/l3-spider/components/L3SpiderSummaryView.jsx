import { useEffect, useMemo, useRef, useState } from "react"
import { Inbox, ListFilter, Loader2, Maximize2, Minimize2 } from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { Tooltip as UITooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import { useAuth } from "@/lib/auth"

import { useL3SpiderDailySummary, useL3SpiderTrend } from "../hooks/useL3SpiderQueries"
import { formatNumber } from "../utils/format"
import { sortLineNames } from "../utils/selection"

const shortProcess = (value) => String(value ?? "").replace(/^process_/, "")
const EMPTY_ARRAY = []

// 라인별 고유 색상 팔레트
const LINE_COLORS = [
  "rgb(37, 99, 235)", "rgb(22, 163, 74)", "rgb(217, 119, 6)",
  "rgb(124, 58, 237)", "rgb(219, 39, 119)", "rgb(8, 145, 178)",
  "rgb(220, 38, 38)", "rgb(101, 163, 13)", "rgb(79, 70, 229)",
  "rgb(13, 148, 136)", "rgb(147, 51, 234)", "rgb(225, 29, 72)",
  "rgb(2, 132, 199)", "rgb(21, 128, 61)", "rgb(234, 88, 12)",
  "rgb(67, 56, 202)", "rgb(190, 24, 93)", "rgb(161, 98, 7)",
  "rgb(15, 118, 110)", "rgb(185, 28, 28)",
]
const HIGH_RISK_BAR_COLOR = "rgb(220, 38, 38)"
const ANOMALY_BAR_COLOR = "rgb(217, 119, 6)"
const LINE_TOTAL_ITEMS = [
  { key: "groups", label: "분석 그룹", className: "text-foreground", tooltip: "이상 감지 분석 대상인 (line_id × process_id × eds_step) 조합의 수입니다." },
  { key: "warning", label: "Warning", className: "text-chart-4" },
  { key: "highRisk", label: "High Risk", className: "text-destructive" },
  { key: "anomalies", label: "이상 건수", className: "text-foreground" },
  { key: "highRiskEqpchs", label: "이상 EQPCH", className: "text-destructive" },
]

// 전 라인 요약 테이블 — 이상감지 없는 라인도 포함, 클릭 시 매트릭스 필터, 드래그로 순서 변경
function LineTable({ rows, selectedLine, onSelectLine, onReorder, runStatsMap = {} }) {
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
      <table className="w-full table-fixed border-collapse text-[14px]">
        <colgroup>
          <col className="w-7" />
          <col className="w-[100px]" />
          <col className="w-[60px]" />
          <col className="w-[60px]" />
          <col className="w-[60px]" />
          <col className="w-[62px]" />
        </colgroup>
        <thead className="sticky top-0 z-10 bg-card">
          <tr className="h-[58px] border-b">
            <th className="px-1 py-0" />
            <th className="px-2 py-0 text-left font-semibold text-muted-foreground">line_name</th>
            <th className="py-0 pl-1 pr-3 text-right font-semibold text-muted-foreground">분석 step_seq</th>
            <th className="px-1 py-0 text-right font-semibold text-chart-4">Warning</th>
            <th className="px-1 py-0 text-right font-semibold text-destructive">High Risk</th>
            <th className="py-0 pl-1 pr-1 text-right font-semibold text-muted-foreground">합계</th>
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
                  "h-[54px] border-b transition-colors cursor-pointer",
                  isDragTarget && "border-t-2 border-t-primary",
                  isSelected
                    ? "bg-primary/10 hover:bg-primary/15"
                    : "hover:bg-muted/40",
                  !r.active && "opacity-40",
                )}
              >
                <td
                  className="w-6 cursor-grab px-1 py-1 text-center text-base text-muted-foreground/50 active:cursor-grabbing"
                  onClick={(e) => e.stopPropagation()}
                >
                  ⠿
                </td>
                <td className={cn(
                  "truncate px-2 py-1 font-mono font-semibold",
                  isSelected ? "text-primary" : "text-foreground",
                )}>
                  {r.line}
                </td>
                <td className="py-1 pl-1 pr-3 text-right tabular-nums text-[13px] text-muted-foreground">
                  {runStatsMap[r.line] != null
                    ? formatNumber(runStatsMap[r.line])
                    : <span className="text-muted-foreground/25">—</span>}
                </td>
                {r.active ? (
                  <>
                    <td className="px-1 py-1 text-right tabular-nums">
                      {r.wn > 0
                        ? <span className="font-semibold text-chart-4">{formatNumber(r.wn)}</span>
                        : <span className="text-muted-foreground/40">·</span>}
                    </td>
                    <td className="px-1 py-1 text-right tabular-nums">
                      {r.hr > 0
                        ? <span className="font-bold text-destructive">{formatNumber(r.hr)}</span>
                        : <span className="text-muted-foreground/40">·</span>}
                    </td>
                    <td className="py-1 pl-1 pr-1 text-right tabular-nums font-medium">
                      {total > 0
                        ? <span className="text-foreground">{formatNumber(total)}</span>
                        : <span className="text-muted-foreground/40">·</span>}
                    </td>
                  </>
                ) : (
                  <td colSpan={3} className="py-1 pl-2 pr-1 text-center text-[11px] font-normal text-muted-foreground">
                    이상없음
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function RunStatsSection({ runStats }) {
  const { totalRows = 0, byLine = [] } = runStats ?? {}
  if (!byLine.length) return null
  const totalStepSeqs = byLine.reduce((s, r) => s + r.stepSeqCount, 0)
  return (
    <div className="shrink-0 border-t">
      <div className="flex h-9 shrink-0 items-center justify-between border-b bg-muted/30 px-4">
        <span className="text-[13px] font-semibold text-muted-foreground">알고리즘 실행 현황</span>
        <span className="text-[13px] tabular-nums text-muted-foreground">
          총 <span className="font-semibold text-foreground">{formatNumber(totalRows)}</span> row 검토
        </span>
      </div>
      <div className="max-h-[160px] overflow-y-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="sticky top-0 border-b bg-muted/40 text-muted-foreground">
              <th className="py-1.5 pl-4 pr-2 text-left font-medium">line_id</th>
              <th className="px-2 py-1.5 text-right font-medium">step_seq 수</th>
              <th className="py-1.5 pl-2 pr-4 text-right font-medium">row 수</th>
            </tr>
          </thead>
          <tbody>
            {byLine.map((r) => (
              <tr key={r.lineId} className="border-b last:border-0 hover:bg-muted/30">
                <td className="py-1.5 pl-4 pr-2 font-medium">{r.lineId}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{formatNumber(r.stepSeqCount)}</td>
                <td className="py-1.5 pl-2 pr-4 text-right tabular-nums">{formatNumber(r.rowCnt)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t bg-muted/20 font-semibold text-muted-foreground">
              <td className="py-1.5 pl-4 pr-2">합계</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{formatNumber(totalStepSeqs)}</td>
              <td className="py-1.5 pl-2 pr-4 text-right tabular-nums">{formatNumber(totalRows)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}

function LineSummaryTotals({ headline, runStats }) {
  const combinations = runStats?.combinations ?? 0
  const runRows = runStats?.totalRows ?? 0
  const row1 = [
    { value: runRows, label: "분석 ROWS", className: "text-foreground" },
    {
      value: combinations || (headline?.groups ?? 0),
      label: "분석 그룹수",
      className: "text-foreground",
      tooltip: "이상 감지 분석 대상인 (line_id × process_id × eds_step × step_seq) 조합의 수입니다.",
    },
    { value: headline?.highRiskEqpchs ?? 0, label: "이상 EQPCH", className: "text-destructive" },
  ]
  const row2 = [
    { value: headline?.warning ?? 0, label: "Warning", className: "text-chart-4" },
    { value: headline?.highRisk ?? 0, label: "High Risk", className: "text-destructive" },
    { value: headline?.anomalies ?? 0, label: "이상 건수", className: "text-foreground" },
  ]
  const renderCell = ({ value, label, className, tooltip }) => {
    const inner = (
      <div className={cn("min-w-0 px-1 py-1.5 text-center", tooltip && "cursor-default")}>
        <p className={cn("truncate text-[14px] font-bold leading-none tabular-nums", className)}>
          {formatNumber(value)}
        </p>
        <p className="mt-1 truncate text-[10px] font-medium text-muted-foreground">{label}</p>
      </div>
    )
    if (!tooltip) return <div key={label} className="min-w-0 px-1 py-1.5 text-center">
      <p className={cn("truncate text-[14px] font-bold leading-none tabular-nums", className)}>{formatNumber(value)}</p>
      <p className="mt-1 truncate text-[10px] font-medium text-muted-foreground">{label}</p>
    </div>
    return (
      <UITooltip key={label}>
        <TooltipTrigger asChild>{inner}</TooltipTrigger>
        <TooltipContent side="top" className="max-w-[220px] text-center text-xs">{tooltip}</TooltipContent>
      </UITooltip>
    )
  }
  return (
    <div className="shrink-0 border-t bg-muted/40">
      <div className="flex items-center justify-center border-b py-1">
        <span className="text-[15px] font-semibold text-muted-foreground">Total</span>
      </div>
      <div className="grid grid-cols-3 divide-x border-b">
        {row1.map(renderCell)}
      </div>
      <div className="grid grid-cols-3 divide-x">
        {row2.map(renderCell)}
      </div>
    </div>
  )
}

function ColumnFilter({ values, selected, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const isFiltered = selected.length > 0 && selected.length < values.length

  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  const allChecked = selected.length === 0
  const isChecked = (v) => allChecked || selected.includes(v)

  function toggle(v) {
    if (allChecked) {
      onChange(values.filter((x) => x !== v))
    } else {
      const next = selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]
      onChange(next.length === values.length ? [] : next)
    }
  }

  return (
    <div ref={ref} className="relative inline-flex items-center">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex size-5 items-center justify-center rounded hover:bg-muted/60",
          isFiltered ? "text-primary" : "text-muted-foreground/50 hover:text-muted-foreground"
        )}
      >
        <ListFilter className="size-3.5" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 max-h-56 min-w-[160px] overflow-auto rounded-md border bg-popover shadow-md">
          <div className="p-1">
            <label className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-muted">
              <input type="checkbox" checked={allChecked} onChange={() => onChange([])} className="size-3.5 accent-primary" />
              <span className="font-medium">전체 선택</span>
            </label>
            <div className="my-1 border-t" />
            {values.map((v) => (
              <label key={v} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-muted">
                <input type="checkbox" checked={isChecked(v)} onChange={() => toggle(v)} className="size-3.5 accent-primary" />
                <span className="font-mono">{v}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ProcessEdsSummaryCard({ matrix, selectedLine, onDrill, isMaximized, onToggleMaximized, className }) {
  const { cells = EMPTY_ARRAY } = matrix ?? {}
  const { rows, lineCount, processCount, edsCount } = useMemo(() => {
    const scopedCells = selectedLine ? cells.filter((cell) => cell.line === selectedLine) : cells
    const lineSet = new Set()
    const processSet = new Set()
    const edsSet = new Set()
    const totals = { highRisk: 0, warning: 0, stepSeq: 0, eqpch: 0 }
    const lineOrder = new Map(sortLineNames([...new Set(scopedCells.map((cell) => cell.line))]).map((line, index) => [line, index]))
    const rows = scopedCells
      .filter((cell) => (cell.highRisk ?? 0) + (cell.warning ?? 0) > 0)
      .map((cell) => {
        const highRisk = cell.highRisk ?? 0
        const warning = cell.warning ?? 0
        const stepSeq = cell.hrStepSeqs ?? 0
        const eqpch = cell.hrEqpchs ?? 0
        lineSet.add(cell.line)
        processSet.add(cell.process)
        edsSet.add(cell.edsStep)
        totals.highRisk += highRisk
        totals.warning += warning
        totals.stepSeq += stepSeq
        totals.eqpch += eqpch
        return {
          key: `${cell.line}||${cell.process}||${cell.edsStep}`,
          line: cell.line,
          process: cell.process,
          edsStep: cell.edsStep,
          highRisk,
          warning,
          stepSeq,
          eqpch,
        }
      })
      .sort((a, b) => {
        const lineDelta = (lineOrder.get(a.line) ?? 0) - (lineOrder.get(b.line) ?? 0)
        return lineDelta
          || String(a.process).localeCompare(String(b.process), undefined, { numeric: true })
          || String(a.edsStep).localeCompare(String(b.edsStep), undefined, { numeric: true })
      })
    return {
      rows,
      totals,
      lineCount: lineSet.size,
      processCount: processSet.size,
      edsCount: edsSet.size,
    }
  }, [cells, selectedLine])

  const hasRows = rows.length > 0

  const [filters, setFilters] = useState({ lineName: [], processId: [], edsStep: [] })

  const uniqueLineNames = useMemo(() => [...new Set(rows.map((r) => r.line))].sort(), [rows])
  const uniqueProcessIds = useMemo(() => [...new Set(rows.map((r) => r.process))].sort(), [rows])
  const uniqueEdsSteps = useMemo(() => [...new Set(rows.map((r) => String(r.edsStep)))].sort(), [rows])

  const filteredRows = useMemo(() => {
    if (!filters.lineName.length && !filters.processId.length && !filters.edsStep.length) return rows
    return rows.filter((row) => {
      if (filters.lineName.length && !filters.lineName.includes(row.line)) return false
      if (filters.processId.length && !filters.processId.includes(row.process)) return false
      if (filters.edsStep.length && !filters.edsStep.includes(String(row.edsStep))) return false
      return true
    })
  }, [rows, filters])

  const filteredTotals = useMemo(() => filteredRows.reduce(
    (acc, row) => ({
      highRisk: acc.highRisk + row.highRisk,
      warning: acc.warning + row.warning,
      stepSeq: acc.stepSeq + row.stepSeq,
      eqpch: acc.eqpch + row.eqpch,
    }),
    { highRisk: 0, warning: 0, stepSeq: 0, eqpch: 0 }
  ), [filteredRows])

  return (
    <Card className={cn("flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-lg py-0 gap-0", className)}>
      <div className="flex h-11 shrink-0 items-center gap-2 border-b bg-muted/50 px-4">
        <CardTitle className="text-[15px]">라인별 세부 요약</CardTitle>
        <Badge variant={selectedLine ? "secondary" : "outline"} className="min-w-[86px] justify-center text-xs">
          {selectedLine ? `${selectedLine} 선택` : "전체 라인"}
        </Badge>
        {!selectedLine ? <Badge variant="outline" className="text-xs">{formatNumber(lineCount)} Line</Badge> : null}
        <Badge variant="outline" className="text-xs">{formatNumber(processCount)} Process</Badge>
        <Badge variant="outline" className="text-xs">{formatNumber(edsCount)} EDS</Badge>
        <Badge variant="secondary" className="text-xs">
          {formatNumber(filteredRows.length)}{filteredRows.length !== rows.length ? `/${formatNumber(rows.length)}` : ""} rows
        </Badge>
        <button
          type="button"
          onClick={onToggleMaximized}
          className="ml-auto inline-flex size-7 shrink-0 items-center justify-center rounded border bg-background text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={isMaximized ? "라인별 세부 요약 축소" : "라인별 세부 요약 최대화"}
          title={isMaximized ? "축소" : "최대화"}
        >
          {isMaximized ? (
            <Minimize2 className="size-4" aria-hidden="true" />
          ) : (
            <Maximize2 className="size-4" aria-hidden="true" />
          )}
        </button>
      </div>
      <CardContent className="min-h-0 flex-1 overflow-auto p-0">
        {!hasRows ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            선택 범위에 표시할 라인별 세부 요약이 없습니다.
          </div>
        ) : (
          <table className="w-full min-w-[760px] border-collapse text-[14px] leading-tight">
            <colgroup>
              <col className="w-32" />
              <col className="w-36" />
              <col className="w-36" />
              <col className="w-24" />
              <col className="w-24" />
              <col className="w-24" />
              <col className="w-24" />
            </colgroup>
            <thead className="sticky top-0 z-10 bg-card">
              <tr className="h-[58px] border-b text-muted-foreground">
                <th className="sticky left-0 z-20 bg-card px-3 py-0 text-left font-semibold">
                  <span className="flex items-center gap-1.5">
                    Line_name
                    <ColumnFilter values={uniqueLineNames} selected={filters.lineName} onChange={(v) => setFilters((f) => ({ ...f, lineName: v }))} />
                  </span>
                </th>
                <th className="px-3 py-0 text-left font-semibold">
                  <span className="flex items-center gap-1.5">
                    process_id
                    <ColumnFilter values={uniqueProcessIds} selected={filters.processId} onChange={(v) => setFilters((f) => ({ ...f, processId: v }))} />
                  </span>
                </th>
                <th className="px-3 py-0 text-left font-semibold">
                  <span className="flex items-center gap-1.5">
                    eds_step
                    <ColumnFilter values={uniqueEdsSteps} selected={filters.edsStep} onChange={(v) => setFilters((f) => ({ ...f, edsStep: v }))} />
                  </span>
                </th>
                <th className="px-3 py-0 text-right font-semibold text-chart-4">Warning</th>
                <th className="px-3 py-0 text-right font-semibold text-destructive">High Risk</th>
                <th className="px-3 py-0 text-right font-semibold">이상 step_seq</th>
                <th className="pl-3 pr-6 py-0 text-right font-semibold">이상 EQPCH</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr
                  key={row.key}
                  onClick={() => onDrill?.({ line: row.line, process: row.process, edsStep: row.edsStep })}
                  className="cursor-pointer border-b hover:bg-muted/30"
                >
                  <td className="sticky left-0 z-[1] bg-card px-3 py-1 font-mono font-semibold text-foreground">
                    {row.line}
                  </td>
                  <td className="px-3 py-1 font-mono font-semibold text-foreground">
                    {shortProcess(row.process)}
                  </td>
                  <td className="px-3 py-1 font-mono font-semibold text-foreground">
                    {row.edsStep}
                  </td>
                  <td className="px-3 py-1 text-right tabular-nums font-semibold text-chart-4">
                    {formatNumber(row.warning)}
                  </td>
                  <td className="px-3 py-1 text-right tabular-nums font-semibold text-destructive">
                    {formatNumber(row.highRisk)}
                  </td>
                  <td className="px-3 py-1 text-right tabular-nums font-semibold">
                    {formatNumber(row.stepSeq)}
                  </td>
                  <td className="pl-3 pr-6 py-1 text-right tabular-nums font-semibold">
                    {formatNumber(row.eqpch)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-muted/50 font-semibold">
                <td className="sticky left-0 z-[1] bg-muted/50 px-3 py-1">합계</td>
                <td className="px-3 py-1" />
                <td className="px-3 py-1" />
                <td className="px-3 py-1 text-right tabular-nums text-chart-4">{formatNumber(filteredTotals.warning)}</td>
                <td className="px-3 py-1 text-right tabular-nums text-destructive">{formatNumber(filteredTotals.highRisk)}</td>
                <td className="px-3 py-1 text-right tabular-nums">{formatNumber(filteredTotals.stepSeq)}</td>
                <td className="pl-3 pr-6 py-1 text-right tabular-nums">{formatNumber(filteredTotals.eqpch)}</td>
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

function TrendValueLabel({ x, y, width, height, value }) {
  const numericValue = Number(value ?? 0)
  const labelX = Number(x ?? 0)
  const labelY = Number(y ?? 0)
  const labelWidth = Number(width ?? 0)
  const labelHeight = Number(height ?? 0)
  if (numericValue <= 0 || labelHeight < 8 || labelWidth < 20) return null
  return (
    <text
      x={labelX + labelWidth / 2}
      y={Math.max(12, labelY - 6)}
      textAnchor="middle"
      fill="var(--foreground)"
      fontSize={11}
      fontWeight={700}
      pointerEvents="none"
    >
      {formatNumber(numericValue)}
    </text>
  )
}

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

  // focusLine 선택 시 seriesKeys를 해당 라인의 process_id로 전환
  const effectiveSeriesKeys = useMemo(() => {
    if (!focusLine) return allLineNames
    return sortLineNames([...new Set(scopedPoints.map((p) => p.processId).filter(Boolean))])
  }, [focusLine, allLineNames, scopedPoints])

  // 날짜 범위 필터 — 전체 데이터에서 최신 기준 N일치만
  const filteredPoints = useMemo(() => {
    if (!scopedPoints.length) return []
    if (rangeDays === 0) return scopedPoints
    const allDates = [...new Set(scopedPoints.map((p) => p.date))].sort()
    const cutoff = allDates[Math.max(0, allDates.length - rangeDays)]
    return scopedPoints.filter((p) => p.date >= cutoff)
  }, [scopedPoints, rangeDays])

  // 데이터 변환: [{date, lineName, processId, hr, wn}] → recharts용 [{date, ...series}]
  const { chartData, seriesKeys } = useMemo(() => {
    if (!filteredPoints.length) return { chartData: [], seriesKeys: [] }
    const getValue = (p) => metric === "hr" ? p.hr : p.hr + p.wn
    // focusLine 선택 시 process_id 기준 피벗, 아니면 lineName 기준
    const getKey = focusLine ? (p) => p.processId : (p) => p.lineName

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

    // perLine / perProcess: pivot — 날짜 갭은 0으로 채움
    // 날짜 × 시리즈 조합이 2000 초과 시 렌더링 폭발 방지를 위해 sum으로 폴백
    const dateSet = new Set()
    for (const p of filteredPoints) dateSet.add(p.date)
    const rawDates = [...dateSet].sort()
    const dates = rawDates.length > 1
      ? makeDateRange(rawDates[0], rawDates[rawDates.length - 1])
      : rawDates
    if (dates.length * effectiveSeriesKeys.length > 2000) {
      const byDate = new Map()
      for (const p of filteredPoints) byDate.set(p.date, (byDate.get(p.date) ?? 0) + getValue(p))
      const chartData = [...byDate.entries()].sort(([a], [b]) => a.localeCompare(b))
        .map(([date, value]) => ({ date: fmtDate(date), value }))
      return { chartData, seriesKeys: ["value"] }
    }

    const byDateSeries = new Map()
    for (const p of filteredPoints) {
      const k = getKey(p)
      if (!byDateSeries.has(p.date)) byDateSeries.set(p.date, {})
      byDateSeries.get(p.date)[k] = (byDateSeries.get(p.date)[k] ?? 0) + getValue(p)
    }
    const chartData = dates.map((d) => {
      const vals = byDateSeries.get(d) ?? {}
      const row = { date: fmtDate(d) }
      for (const k of effectiveSeriesKeys) row[k] = vals[k] ?? 0
      return row
    })
    return { chartData, seriesKeys: effectiveSeriesKeys }
  }, [filteredPoints, metric, grouping, effectiveSeriesKeys, focusLine])

  return (
    <Card className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-lg py-0 gap-0">
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
              High Risk
            </button>
            <button type="button" onClick={() => setMetric("total")}
              className={cn("rounded px-2 py-0.5 font-medium transition-colors",
                metric === "total" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")}>
              High Risk+Warning
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
              {focusLine ? "process_id별" : "라인별"}
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
            <BarChart data={chartData} margin={{ top: 20, right: 12, left: 0, bottom: 4 }} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal vertical />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={false}
                width={52}
                tickFormatter={(v) => formatNumber(v)}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  fontSize: 13,
                }}
                formatter={(value, name) => [formatNumber(value), name === "value" ? (metric === "hr" ? "High Risk" : "이상 건수") : name]}
                labelFormatter={(label) => `날짜: ${label}`}
                cursor={{ fill: "var(--muted)", opacity: 0.5 }}
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
                  name={metric === "hr" ? "전체 High Risk" : "전체 이상 건수 (High Risk+Warning)"}
                  fill={metric === "hr" ? HIGH_RISK_BAR_COLOR : ANOMALY_BAR_COLOR}
                  radius={[3, 3, 0, 0]}
                  maxBarSize={48}
                >
                  <LabelList dataKey="value" content={TrendValueLabel} />
                </Bar>
              ) : (seriesKeys.length <= 20 ? seriesKeys : seriesKeys.slice(0, 20)).map((key, i) => (
                <Bar
                  key={key}
                  dataKey={key}
                  name={key}
                  stackId="a"
                  fill={LINE_COLORS[i % LINE_COLORS.length]}
                  radius={i === seriesKeys.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
                  maxBarSize={48}
                >
                  <LabelList dataKey={key} content={TrendValueLabel} />
                </Bar>
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
  const [isDetailMaximized, setIsDetailMaximized] = useState(false)

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

  const runStatsMap = useMemo(() => {
    const map = {}
    for (const entry of (data?.runStats?.byLine ?? [])) {
      map[entry.lineName ?? entry.lineId] = entry.stepSeqCount
    }
    return map
  }, [data?.runStats?.byLine])

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
      <main className="flex min-h-0 flex-1 min-w-0 overflow-hidden px-5 pb-5 pt-3">
        <Card className="flex min-h-0 flex-1 rounded-lg">
          <CardContent className="flex min-h-0 flex-1 items-center justify-center p-6 text-sm text-muted-foreground">
            {message}
          </CardContent>
        </Card>
      </main>
    )
  }

  return (
    <main className="flex min-h-0 flex-1 min-w-0 overflow-hidden px-5 pb-5 pt-3">
      <div className="grid h-full min-h-0 flex-1 min-w-0 grid-cols-[420px_minmax(0,1fr)] grid-rows-[minmax(0,4fr)_minmax(0,5fr)] gap-4 overflow-hidden">
        {isDetailMaximized ? (
          <ProcessEdsSummaryCard
            className="col-span-2 row-span-2"
            matrix={data.matrix}
            selectedLine={activeLine}
            onDrill={onDrill}
            isMaximized={isDetailMaximized}
            onToggleMaximized={() => setIsDetailMaximized(false)}
          />
        ) : (
          <>
            <Card className="row-span-2 flex min-h-0 min-w-0 flex-col overflow-hidden rounded-lg py-0 gap-0">
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
                <LineTable rows={orderedLineSummary} selectedLine={activeLine} onSelectLine={onSelectLine} onReorder={handleReorder} runStatsMap={runStatsMap} />
              </CardContent>
              <LineSummaryTotals headline={h} runStats={data?.runStats} />
              <RunStatsSection runStats={data.runStats} />
            </Card>

            <TrendChartCard
              trendPoints={trendQuery.data?.points ?? []}
              allLineNames={trendLineNames}
              focusLine={activeLine ?? undefined}
            />

            <ProcessEdsSummaryCard
              matrix={data.matrix}
              selectedLine={activeLine}
              onDrill={onDrill}
              isMaximized={isDetailMaximized}
              onToggleMaximized={() => setIsDetailMaximized(true)}
            />
          </>
        )}
      </div>
    </main>
  )
}
