import { useEffect, useMemo, useState } from "react"
import { Activity, AlertTriangle, Cpu, Gauge, Inbox, Layers, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { useL3SpiderDailySummary } from "../hooks/useL3SpiderQueries"
import { formatNumber } from "../utils/format"

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

// 앱의 L3SpiderSummaryCards 와 동일한 stat 관용구
const STAT_DEFS = [
  { key: "anomalyGroups", label: "이상 Bin 그룹", icon: Layers, tone: "text-foreground" },
  { key: "highRisk", label: "High Risk", icon: Activity, tone: "text-destructive" },
  { key: "warning", label: "Warning", icon: AlertTriangle, tone: "text-chart-4" },
  { key: "anomalies", label: "이상 건수", icon: Gauge, tone: "text-foreground" },
  { key: "anomalyEqpchs", label: "이상 EQPCH", icon: Cpu, tone: "text-foreground" },
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
          Bin {formatNumber(h.binNames)} · Lot {formatNumber(h.lots)} · 총 {formatNumber(h.totalRows)}행
        </div>
      </div>
    </Card>
  )
}

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
            onClick={() => onSelectLine(line)}
          >
            {line}
          </Button>
        ))}
      </div>
    </div>
  )
}

function AnomalyMatrix({ matrix, lineOptions, selectedLine, onSelectLine, onDrill }) {
  const { lines = [], edsSteps = [], cells = [] } = matrix ?? {}

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
    const grand = { hr: 0, wn: 0 }
    const add = (map, key, hr, wn) => {
      const cur = map.get(key) ?? { hr: 0, wn: 0 }
      cur.hr += hr
      cur.wn += wn
      map.set(key, cur)
    }
    for (const c of visibleCells) {
      cellMap.set(`${c.line}||${c.process}||${c.edsStep}`, c)
      if (!processesByLine.has(c.line)) processesByLine.set(c.line, new Set())
      processesByLine.get(c.line).add(c.process)
      add(lineTotals, c.line, c.highRisk, c.warning)
      add(colTotals, c.edsStep, c.highRisk, c.warning)
      grand.hr += c.highRisk
      grand.wn += c.warning
    }
    return { cellMap, processesByLine, lineTotals, colTotals, grand }
  }, [visibleCells])

  return (
    <div className="max-h-[70vh] overflow-auto p-4">
      <div className="inline-grid min-w-max gap-3">
        <LineSelector
          lines={lineOptions}
          selectedLine={selectedLine}
          onSelectLine={onSelectLine}
        />
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
              const lt = lineTotals.get(line) ?? { hr: 0, wn: 0 }
              return processes.map((process, idx) => {
                let rowHr = 0
                let rowWn = 0
                for (const eds of edsSteps) {
                  const c = cellMap.get(`${line}||${process}||${eds}`)
                  if (c) {
                    rowHr += c.highRisk
                    rowWn += c.warning
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
                            <HrWn hr={lt.hr} wn={lt.wn} />
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
                            title={`${line} · ${shortProcess(process)} · ${eds}\nHigh Risk ${cell.highRisk} · Warning ${cell.warning} · bin ${cell.bins}종`}
                            className="flex h-8 w-full min-w-16 items-center justify-center rounded-md transition hover:bg-muted/50 hover:ring-1 hover:ring-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <HrWn hr={cell.highRisk} wn={cell.warning} />
                          </button>
                        </td>
                      )
                    })}
                    <td className="border-b px-2 py-2 text-center">
                      <HrWn hr={rowHr} wn={rowWn} />
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
                const ct = colTotals.get(eds) ?? { hr: 0, wn: 0 }
                return (
                  <td key={eds} className="px-2 py-2 text-center">
                    <HrWn hr={ct.hr} wn={ct.wn} />
                  </td>
                )
              })}
              <td className="px-2 py-2 text-center">
                <HrWn hr={grand.hr} wn={grand.wn} />
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}

export function L3SpiderSummaryView({ date, onDrill }) {
  const [selectedLine, setSelectedLine] = useState(null)
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
  const activeLine = selectedLine && lineOptions.includes(selectedLine)
    ? selectedLine
    : (lineOptions[0] ?? null)
  const visibleCellCount = useMemo(
    () => (data?.matrix?.cells ?? []).filter((cell) => cell.line === activeLine).length,
    [activeLine, data?.matrix?.cells],
  )

  useEffect(() => {
    if (!lineOptions.length) {
      setSelectedLine(null)
      return
    }
    if (!selectedLine || !lineOptions.includes(selectedLine)) {
      setSelectedLine(lineOptions[0])
    }
  }, [lineOptions, selectedLine])

  let content
  if (!date) {
    content = (
      <div className="flex min-h-64 items-center justify-center text-sm text-muted-foreground">
        날짜를 선택하면 해당 날짜 전체의 이상감지 요약을 조회합니다.
      </div>
    )
  } else if (query.isLoading) {
    content = (
      <div className="flex min-h-64 items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> 요약을 불러오는 중입니다.
      </div>
    )
  } else if (query.error) {
    content = (
      <div className="flex min-h-64 items-center justify-center text-sm text-destructive">
        {query.error.message || "요약을 불러오지 못했습니다."}
      </div>
    )
  } else if (!hasData) {
    content = (
      <div className="flex min-h-64 flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
        <Inbox className="size-6" aria-hidden="true" />
        <p>{date} 날짜에 데이터가 없습니다.</p>
      </div>
    )
  } else {
    content = (
      <AnomalyMatrix
        matrix={data.matrix}
        lineOptions={lineOptions}
        selectedLine={activeLine}
        onSelectLine={setSelectedLine}
        onDrill={onDrill}
      />
    )
  }

  return (
    <main className="grid gap-5 px-6 pb-6 pt-4">
      {hasData ? <SummaryStats h={h} /> : null}
      <div className="overflow-x-auto">
        <Card className="grid w-fit gap-0 overflow-hidden rounded-lg py-0">
          <CardHeader className="border-b bg-muted/50 px-4 py-2.5">
            <div className="flex items-center gap-2 whitespace-nowrap">
              <CardTitle className="text-sm">Anomaly Summary Matrix</CardTitle>
              {hasData ? (
                <>
                  <Badge variant="outline">{formatNumber(h.totalRows)} rows</Badge>
                  <Badge variant="secondary">{formatNumber(visibleCellCount)} cells</Badge>
                  <span className="ml-4 inline-flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="size-2 rounded-full bg-destructive" aria-hidden="true" />
                      High Risk
                      <span className="text-muted-foreground/40">/</span>
                      <span className="size-2 rounded-full bg-chart-4" aria-hidden="true" />
                      Warning
                    </span>
                    <span>셀 클릭 → Chart 탭</span>
                  </span>
                </>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="p-0">{content}</CardContent>
        </Card>
      </div>
    </main>
  )
}
