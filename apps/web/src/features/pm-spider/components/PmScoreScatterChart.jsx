import { useMemo } from "react"
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts"
import { LineChartIcon } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

const COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

function buildLabel(row) {
  return row.itemName || row.traceSensor || [row.step, row.wavelength].filter(Boolean).join(" / ") || "score"
}

function buildTrend(rows, selectedLabel) {
  const safeRows = (Array.isArray(rows) ? rows : [])
    .map((row) => ({
      ...row,
      cycleIndex: Number(row.cycleIndex),
      score: Number(row.score),
      label: buildLabel(row),
    }))
    .filter((row) => Number.isFinite(row.cycleIndex) && Number.isFinite(row.score))

  const currentWorstLabels = safeRows
    .filter((row) => row.cycleIndex === 0)
    .sort((left, right) => left.score - right.score)
    .map((row) => row.label)

  const labels = []
  if (selectedLabel && safeRows.some((row) => row.label === selectedLabel)) {
    labels.push(selectedLabel)
  }
  currentWorstLabels.forEach((label) => {
    if (!labels.includes(label)) {
      labels.push(label)
    }
  })
  safeRows.forEach((row) => {
    if (labels.length < 8 && !labels.includes(row.label)) {
      labels.push(row.label)
    }
  })

  const visibleLabels = labels.slice(0, 8)
  const points = new Map()
  safeRows
    .filter((row) => visibleLabels.includes(row.label))
    .forEach((row) => {
      const key = row.cycleIndex
      if (!points.has(key)) {
        points.set(key, {
          cycleIndex: row.cycleIndex,
          pmDate: row.pmDate,
          phase: row.phase,
        })
      }
      points.get(key)[row.label] = row.score
    })

  return {
    labels: visibleLabels,
    rows: Array.from(points.values()).sort((left, right) => left.cycleIndex - right.cycleIndex),
  }
}

export function PmScoreScatterChart({ title, rows, selectedLabel }) {
  const chart = useMemo(() => buildTrend(rows, selectedLabel), [rows, selectedLabel])
  const cycleTicks = chart.rows.map((row) => row.cycleIndex)
  const cycleDomain = cycleTicks.length
    ? [Math.min(...cycleTicks), Math.max(...cycleTicks)]
    : [0, 0]
  const config = Object.fromEntries(
    chart.labels.map((label, index) => [
      label,
      { label, color: COLORS[index % COLORS.length] },
    ]),
  )

  return (
    <Card className="flex h-full min-h-0 flex-col rounded-lg py-0">
      <div className="shrink-0 border-b bg-muted/50 px-3 py-1.5">
        <p className="text-xs font-medium text-muted-foreground">{title}</p>
      </div>
      <CardContent className="flex-1 min-h-0 p-3">
        {chart.rows.length === 0 ? (
          <div className="flex h-full min-h-60 flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-sm text-muted-foreground">
            <LineChartIcon className="size-6" aria-hidden="true" />
            <span>PM 주기별 score 데이터가 없습니다.</span>
          </div>
        ) : (
          <ChartContainer config={config} className="h-full min-h-60">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart.rows} margin={{ top: 12, right: 16, bottom: 24, left: 0 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="cycleIndex"
                  type="number"
                  allowDecimals={false}
                  domain={cycleDomain}
                  ticks={cycleTicks}
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border)" }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border)" }}
                  width={56}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Legend verticalAlign="top" height={28} iconType="circle" />
                {chart.labels.map((label, index) => (
                  <Line
                    key={label}
                    type="monotone"
                    dataKey={label}
                    stroke={COLORS[index % COLORS.length]}
                    strokeWidth={label === selectedLabel ? 3 : 2}
                    dot={{ r: label === selectedLabel ? 4 : 3 }}
                    activeDot={{ r: 5 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  )
}
