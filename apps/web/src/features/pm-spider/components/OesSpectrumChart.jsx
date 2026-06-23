import { useMemo } from "react"
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts"
import { Waves } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

import { formatNumber } from "../utils/format"

const COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

function buildSpectrumRows(rows) {
  const safeRows = (Array.isArray(rows) ? rows : [])
    .map((row) => ({
      ...row,
      wavelength: Number(row.wavelength),
      value: Number(row.value),
      series: `${row.phase || "cycle"} ${row.cycleIndex}`,
    }))
    .filter((row) => Number.isFinite(row.wavelength) && Number.isFinite(row.value))
  const series = Array.from(new Set(safeRows.map((row) => row.series))).slice(0, 8)
  const points = new Map()
  safeRows.forEach((row) => {
    const key = row.wavelength
    if (!points.has(key)) {
      points.set(key, { wavelength: row.wavelength })
    }
    points.get(key)[row.series] = row.value
  })
  return {
    series,
    rows: Array.from(points.values()).sort((a, b) => a.wavelength - b.wavelength),
  }
}

export function OesSpectrumChart({ title, rows, isLoading = false }) {
  const chart = useMemo(() => buildSpectrumRows(rows), [rows])
  const config = Object.fromEntries(
    chart.series.map((series, index) => [
      series,
      { label: series, color: COLORS[index % COLORS.length] },
    ]),
  )

  return (
    <Card className="grid min-h-0 grid-rows-[auto,1fr] rounded-lg py-0">
      <CardHeader className="border-b bg-muted/50 px-3 py-2">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 p-3">
        {isLoading ? (
          <div className="flex h-full min-h-60 flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-sm text-muted-foreground">
            <Waves className="size-6" aria-hidden="true" />
            <span>선택한 OES spectrum 데이터를 조회하는 중입니다.</span>
          </div>
        ) : chart.rows.length === 0 ? (
          <div className="flex h-full min-h-60 flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-sm text-muted-foreground">
            <Waves className="size-6" aria-hidden="true" />
            <span>선택한 OES spectrum 데이터가 없습니다.</span>
          </div>
        ) : (
          <ChartContainer config={config} className="h-full min-h-60">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart.rows} margin={{ top: 12, right: 16, bottom: 24, left: 0 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="wavelength"
                  type="category"
                  tickFormatter={(value) => formatNumber(value, 1)}
                  minTickGap={32}
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
                {chart.series.map((series, index) => (
                  <Line
                    key={series}
                    type="monotone"
                    dataKey={series}
                    stroke={COLORS[index % COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
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
