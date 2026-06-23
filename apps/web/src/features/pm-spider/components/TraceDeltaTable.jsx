import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import { formatNumber, formatPercent } from "../utils/format"

export function TraceDeltaTable({ rows }) {
  const safeRows = Array.isArray(rows) ? rows : []

  return (
    <Card className="grid min-h-0 grid-rows-[auto,1fr] rounded-lg py-0">
      <CardHeader className="border-b bg-muted/50 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm">Trace worst sensors</CardTitle>
          <Badge variant="outline">{safeRows.length} sensors</Badge>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 overflow-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="sticky top-0 bg-card text-xs text-muted-foreground">
            <tr className="border-b">
              <th className="px-3 py-2 text-left font-medium">Sensor</th>
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
                <td colSpan={6} className="px-3 py-10 text-center text-sm text-muted-foreground">
                  trace 전후 delta 데이터가 없습니다.
                </td>
              </tr>
            ) : (
              safeRows.map((row) => (
                <tr key={row.traceSensor} className="border-b hover:bg-muted/40">
                  <td className="max-w-[240px] truncate px-3 py-2 font-medium">{row.traceSensor}</td>
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
      </CardContent>
    </Card>
  )
}
