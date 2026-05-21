import { useEffect, useMemo, useRef } from "react"
import { BarChart3 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { statusLabel, statusTone } from "../utils/format"
import { sortedValues } from "../utils/selection"

const STATUS_ORDER = ["High Risk Chamber", "Warning", "Normal (Ref)"]
const STATUS_COLORS = {
  "High Risk Chamber": "var(--destructive)",
  Warning: "var(--chart-4)",
  "Normal (Ref)": "var(--muted-foreground)",
}

let plotlyLoader = null

function loadPlotly() {
  if (!plotlyLoader) {
    plotlyLoader = import("plotly.js-dist-min").then((module) => module.default ?? module)
  }
  return plotlyLoader
}

function formatGroupTitle(key) {
  return key || "미분류"
}

function groupRows(rows, groupBy) {
  const groups = new Map()
  rows.forEach((row) => {
    const key =
      groupBy === "stepBin"
        ? `${row.stepSeq || "-"} / ${row.binName || "-"}`
        : row.eqc || "미분류"
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(row)
  })
  return sortedValues(groups.keys()).map((key) => ({ key, rows: groups.get(key) }))
}

function PlotPanel({ rows, title, xAxisMode }) {
  const plotRef = useRef(null)

  const traces = useMemo(
    () =>
      STATUS_ORDER.map((status) => {
        const statusRows = rows.filter((row) => row.displayStatus === status)
        return {
          type: "scatter",
          mode: "markers",
          name: statusLabel(status),
          x: statusRows.map((row) => (xAxisMode === "wafer" ? row.waferId : row.tkinTime)),
          y: statusRows.map((row) => Number(row.binValue)),
          text: statusRows.map(
            (row) =>
              [
                `EQC: ${row.eqc ?? "-"}`,
                `Step: ${row.stepSeq ?? "-"}`,
                `PPID: ${row.ppid ?? "-"}`,
                `Wafer: ${row.waferId ?? "-"}`,
                `Bin: ${row.binName ?? "-"}`,
                `Status: ${statusLabel(row.displayStatus)}`,
              ].join("<br />"),
          ),
          hovertemplate: "%{text}<br />Value: %{y}<extra></extra>",
          marker: {
            color: STATUS_COLORS[status],
            size: status === "High Risk Chamber" ? 9 : 7,
            symbol: status === "High Risk Chamber" ? "diamond" : "circle",
            line: {
              color: STATUS_COLORS[status],
              width: 1,
            },
          },
        }
      }).filter((trace) => trace.x.length > 0),
    [rows, xAxisMode],
  )

  useEffect(() => {
    const plotElement = plotRef.current
    if (!plotElement) return undefined
    let active = true
    let plotlyApi = null
    const layout = {
      autosize: true,
      height: 320,
      margin: { l: 56, r: 20, t: 36, b: 54 },
      title: { text: title, font: { size: 13 } },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { color: "var(--foreground)", size: 11 },
      xaxis: {
        title: xAxisMode === "wafer" ? "Wafer" : "TKIN Time",
        gridcolor: "var(--border)",
        zerolinecolor: "var(--border)",
        automargin: true,
      },
      yaxis: {
        title: "Bin Value",
        gridcolor: "var(--border)",
        zerolinecolor: "var(--border)",
        automargin: true,
      },
      legend: {
        orientation: "h",
        x: 0,
        y: -0.24,
      },
    }
    const config = {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    }
    loadPlotly().then((plotly) => {
      if (!active) return
      plotlyApi = plotly
      plotly.react(plotElement, traces, layout, config)
    })
    return () => {
      active = false
      if (plotlyApi) plotlyApi.purge(plotElement)
    }
  }, [title, traces, xAxisMode])

  return <div ref={plotRef} className="h-80 min-w-0" />
}

export function L3SpiderChart({
  rows,
  isLoading,
  error,
  groupBy,
  onGroupByChange,
  xAxisMode,
  onXAxisModeChange,
}) {
  const groups = useMemo(() => groupRows(rows, groupBy), [groupBy, rows])
  const trellisLabel = groupBy === "eqc" ? "EQC" : "Step/Bin"

  return (
    <Card className="grid min-h-0 grid-rows-[auto,1fr] gap-0 overflow-hidden rounded-lg py-0">
      <CardHeader className="border-b bg-muted/50 px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CardTitle className="text-sm">Scatter Plot — Trellis by</CardTitle>
            <Badge variant="secondary">{trellisLabel}</Badge>
            <Badge variant="outline">{rows.length} rows</Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant={groupBy === "eqc" ? "default" : "outline"}
              size="sm"
              onClick={() => onGroupByChange("eqc")}
            >
              EQC
            </Button>
            <Button
              type="button"
              variant={groupBy === "stepBin" ? "default" : "outline"}
              size="sm"
              onClick={() => onGroupByChange("stepBin")}
            >
              Step/Bin
            </Button>
            <Button
              type="button"
              variant={xAxisMode === "time" ? "default" : "outline"}
              size="sm"
              onClick={() => onXAxisModeChange(xAxisMode === "time" ? "wafer" : "time")}
            >
              {xAxisMode === "time" ? "Time" : "Wafer"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 overflow-y-auto p-4">
        {isLoading ? (
          <div className="flex h-full min-h-64 items-center justify-center text-sm text-muted-foreground">
            차트 데이터를 불러오는 중입니다.
          </div>
        ) : error ? (
          <div className="flex h-full min-h-64 items-center justify-center text-sm text-destructive">
            {error.message || "차트 데이터를 불러오지 못했습니다."}
          </div>
        ) : groups.length === 0 ? (
          <div className="flex h-full min-h-64 flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
            <BarChart3 className="size-6" aria-hidden="true" />
            <p>High Risk 목록에서 EQC 또는 PPID를 선택하면 차트가 표시됩니다.</p>
          </div>
        ) : (
          <div className={cn("grid gap-4", groupBy === "eqc" ? "grid-cols-2" : "grid-cols-1")}>
            {groups.map((group) => (
              <section key={group.key} className="min-w-0 rounded-lg border bg-background p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <h3 className="truncate text-sm font-semibold">{formatGroupTitle(group.key)}</h3>
                  <div className="flex gap-1">
                    {STATUS_ORDER.map((status) => (
                      <span key={status} className={`rounded-full border px-2 py-0.5 text-[10px] ${statusTone(status)}`}>
                        {group.rows.filter((row) => row.displayStatus === status).length}
                      </span>
                    ))}
                  </div>
                </div>
                <PlotPanel rows={group.rows} title={formatGroupTitle(group.key)} xAxisMode={xAxisMode} />
              </section>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
