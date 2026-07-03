import { useMemo } from "react"
import { Activity, AlertTriangle, Cpu, Gauge, Inbox, Layers, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { useL3SpiderDailySummary } from "../hooks/useL3SpiderQueries"
import { formatNumber } from "../utils/format"

const shortProcess = (value) => String(value ?? "").replace(/^process_/, "")
const EMPTY_LIST = []

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

// High Risk step_seq 수 / High Risk EQPCH 수 분리 표기 (기본색 / 빨강)
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

// metric 값에 따라 표시 지표를 전환합니다.
function MetricVal({ metric, hr, wn, ss, eq }) {
  if (metric === "hrpair") return <SsEq ss={ss} eq={eq} />
  return <HrWn hr={hr} wn={wn} />
}

// 앱의 L3SpiderSummaryCards 와 동일한 stat 관용구
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
              <p className={cn("text-xl font-semibold leading-none tabular-nums", tone)}>
                {formatNumber(h[key])}
              </p>
              <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {label}
              </p>
            </div>
          </div>
        ))}
        <div className="ml-auto px-5 py-3 text-right text-[11px] leading-tight text-muted-foreground">
          Line {formatNumber(h.lines)} · Process {formatNumber(h.processes)} · EDS {formatNumber(h.edsSteps)}
          <br />
          Bin {formatNumber(h.binNames)} · 총 {formatNumber(h.totalRows)}행
        </div>
      </div>
    </Card>
  )
}

// 두 표가 공유하는 Line 필터 (선택은 상위로 끌어올려 Chart 탭 왕복에도 유지)
function LineSelector({ lines, selectedLine, onSelectLine }) {
  if (lines.length <= 1) return null

  return (
    <div className="flex min-w-0 items-center gap-2 rounded-md border bg-muted/30 px-2 py-1.5">
      <span className="shrink-0 text-xs font-medium text-muted-foreground">Line</span>
      <div className="flex min-w-0 flex-wrap items-center gap-1">
        {lines.map((line) => (
          <Button
            key={line}
            type="button"
            variant={selectedLine === line ? "default" : "outline"}
            size="sm"
            className="h-7 px-2.5 text-xs"
            aria-pressed={selectedLine === line}
            onClick={() => onSelectLine?.(line)}
          >
            {line}
          </Button>
        ))}
      </div>
    </div>
  )
}

function LegendDot({ className }) {
  return <span className={cn("size-2 rounded-full", className)} aria-hidden="true" />
}

function AnomalyMatrix({ matrix, selectedLine, onDrill, metric }) {
  const { edsSteps = EMPTY_LIST, cells = EMPTY_LIST } = matrix ?? {}
  const lines = matrix?.lines ?? EMPTY_LIST

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
    <div className="max-h-[70vh] overflow-auto p-4">
      <table className="w-auto border-collapse text-xs leading-tight">
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
                        <span className="text-[10px] font-normal">
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

// 매트릭스 표 카드 (헤더 + 범례 + 매트릭스). 두 지표(count / hrpair)에 재사용
function MatrixCard({ title, legend, rows, cells, matrix, metric, selectedLine, onDrill }) {
  return (
    <Card className="flex min-w-0 flex-1 flex-col gap-0 overflow-hidden rounded-lg py-0">
      <CardHeader className="border-b bg-muted/50 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <CardTitle className="text-sm">{title}</CardTitle>
          {rows != null ? <Badge variant="outline">{formatNumber(rows)} rows</Badge> : null}
          {cells != null ? <Badge variant="secondary">{formatNumber(cells)} cells</Badge> : null}
          <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            {legend}
            <span>셀 클릭 → Chart 탭</span>
          </span>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <AnomalyMatrix matrix={matrix} metric={metric} selectedLine={selectedLine} onDrill={onDrill} />
      </CardContent>
    </Card>
  )
}

export function L3SpiderSummaryView({ date, onDrill, selectedLine, onSelectLine }) {
  const query = useL3SpiderDailySummary(date)
  const data = query.data
  const h = data?.headline
  const hasData = Boolean(h && h.totalRows > 0)
  const lineOptions = useMemo(
    () => [...(data?.matrix?.lines ?? [])].sort((a, b) =>
      String(a).localeCompare(String(b), undefined, { numeric: true }),
    ),
    [data?.matrix?.lines],
  )
  // 상위(page)가 보관한 선택값이 유효하면 그대로, 아니면 첫 라인으로 폴백(파생값이라 탭 왕복에도 안전)
  const activeLine = selectedLine && lineOptions.includes(selectedLine)
    ? selectedLine
    : (lineOptions[0] ?? null)
  const visibleCellCount = useMemo(
    () => (data?.matrix?.cells ?? []).filter((cell) => cell.line === activeLine).length,
    [activeLine, data?.matrix?.cells],
  )

  if (!date || query.isLoading || query.error || !hasData) {
    let message
    if (!date) {
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
    <main className="grid gap-5 px-6 pb-6 pt-4">
      <SummaryStats h={h} />
      <LineSelector lines={lineOptions} selectedLine={activeLine} onSelectLine={onSelectLine} />
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        <MatrixCard
          title="Anomaly Summary — High Risk / Warning"
          rows={h.totalRows}
          cells={visibleCellCount}
          legend={(
            <span className="inline-flex items-center gap-1.5">
              <LegendDot className="bg-destructive" />
              High Risk
              <span className="text-muted-foreground/40">/</span>
              <LegendDot className="bg-chart-4" />
              Warning
            </span>
          )}
          matrix={data.matrix}
          metric="count"
          selectedLine={activeLine}
          onDrill={onDrill}
        />
        <MatrixCard
          title="High Risk 발생 — step_seq 수 / EQPCH 수"
          legend={(
            <span className="inline-flex items-center gap-1.5">
              <LegendDot className="bg-foreground" />
              step_seq 수
              <span className="text-muted-foreground/40">/</span>
              <LegendDot className="bg-destructive" />
              EQPCH 수
            </span>
          )}
          matrix={data.matrix}
          metric="hrpair"
          selectedLine={activeLine}
          onDrill={onDrill}
        />
      </div>
    </main>
  )
}
