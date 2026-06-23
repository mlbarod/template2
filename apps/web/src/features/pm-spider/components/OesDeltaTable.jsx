import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import { formatNumber, formatPercent } from "../utils/format"

export function OesDeltaTable({ rows, stepRows, title = "OES worst step / wavelength" }) {
  const safeRows = Array.isArray(rows) ? rows : []
  const safeStepRows = Array.isArray(stepRows) ? stepRows : []

  return (
    <Card className="grid min-h-0 grid-rows-[auto,1fr] rounded-lg py-0">
      <CardHeader className="border-b bg-muted/50 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm">{title}</CardTitle>
          <div className="flex gap-2">
            <Badge variant="outline">{safeStepRows.length} steps</Badge>
            <Badge variant="outline">{safeRows.length} wavelengths</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid min-h-0 grid-rows-[auto,1fr] gap-3 p-4">
        <div className="flex min-h-0 gap-2 overflow-x-auto">
          {safeStepRows.length === 0 ? (
            <span className="text-xs text-muted-foreground">step 요약 데이터가 없습니다.</span>
          ) : (
            safeStepRows.map((row) => (
              <div key={row.step} className="min-w-36 rounded-md border bg-background px-3 py-2">
                <p className="truncate text-xs font-semibold">{row.step}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  worst {formatNumber(row.minScore ?? row.maxScore)} · λ {row.wavelengthCount}
                </p>
              </div>
            ))
          )}
        </div>

        <div className="min-h-0 overflow-auto rounded-md border">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="sticky top-0 bg-card text-xs text-muted-foreground">
              <tr className="border-b">
                <th className="px-3 py-2 text-left font-medium">Step</th>
                <th className="px-3 py-2 text-right font-medium">Wavelength</th>
                <th className="px-3 py-2 text-right font-medium">Before</th>
                <th className="px-3 py-2 text-right font-medium">After</th>
                <th className="px-3 py-2 text-right font-medium">Delta</th>
                <th className="px-3 py-2 text-right font-medium">Relative</th>
                <th className="px-3 py-2 text-right font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {safeRows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-10 text-center text-sm text-muted-foreground">
                    OES 전후 delta 데이터가 없습니다.
                  </td>
                </tr>
              ) : (
                safeRows.map((row) => (
                  <tr key={`${row.step}-${row.wavelength}`} className="border-b hover:bg-muted/40">
                    <td className="max-w-[180px] truncate px-3 py-2 font-medium">{row.step}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.wavelength, 5)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.beforeMean)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.afterMean)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.delta)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatPercent(row.relativeDelta)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.score)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
