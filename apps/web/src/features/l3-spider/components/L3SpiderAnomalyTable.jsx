import { MousePointer2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import { createEmptyFilter, sameSet } from "../utils/selection"

function buildEqcFilter(row) {
  return {
    selectedEqcs: new Set([row.eqc]),
    selectedStepBins: new Set([`${row.stepSeq}|||${row.binName}`]),
    selectedPpidBins: new Set(),
    selectedSteps: new Set(),
  }
}

function buildPpidFilter(row) {
  return {
    selectedEqcs: new Set(),
    selectedStepBins: new Set(),
    selectedPpidBins: new Set([`${row.stepSeq}|||${row.ppid}|||${row.binName}`]),
    selectedSteps: new Set(),
  }
}

function isSameFilter(left, right) {
  return (
    sameSet(left.selectedEqcs, right.selectedEqcs) &&
    sameSet(left.selectedStepBins, right.selectedStepBins) &&
    sameSet(left.selectedPpidBins, right.selectedPpidBins) &&
    sameSet(left.selectedSteps, right.selectedSteps)
  )
}

export function L3SpiderAnomalyTable({ anomalies, filter, onFilterChange, onShowAllRisk }) {
  const hasRows = anomalies.length > 0

  const applyFilter = (nextFilter) => {
    onFilterChange(isSameFilter(filter, nextFilter) ? createEmptyFilter() : nextFilter)
  }

  return (
    <Card className="grid min-h-0 grid-rows-[auto,1fr] gap-0 overflow-hidden rounded-lg py-0">
      <CardHeader className="border-b bg-muted/50 px-4 py-2.5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CardTitle className="text-sm">High Risk 목록</CardTitle>
            <Badge variant="outline">{anomalies.length}</Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" disabled={!hasRows} onClick={onShowAllRisk}>
              전체 위험 표시
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 overflow-auto p-0">
        {!hasRows ? (
          <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 p-6 text-center text-sm text-muted-foreground">
            <MousePointer2 className="size-5" aria-hidden="true" />
            선택 조건에 해당하는 High Risk 항목이 없습니다.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 border-b bg-muted text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-medium">EDS</th>
                <th className="px-3 py-2 text-left font-medium">Step</th>
                <th className="px-3 py-2 text-left font-medium">PPID</th>
                <th className="px-3 py-2 text-left font-medium">EQC</th>
                <th className="px-3 py-2 text-left font-medium">Bin</th>
                <th className="px-3 py-2 text-right font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((row, index) => (
                <tr key={`${row.edsStep}-${row.stepSeq}-${row.ppid}-${row.eqc}-${row.binName}-${index}`} className="border-b last:border-b-0 hover:bg-muted/40">
                  <td className="whitespace-nowrap px-3 py-2">{row.edsStep}</td>
                  <td className="whitespace-nowrap px-3 py-2">{row.stepSeq}</td>
                  <td className="max-w-56 truncate px-3 py-2">{row.ppid}</td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <Badge variant="outline">{row.eqc}</Badge>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">{row.binName}</td>
                  <td className="px-3 py-2">
                    <div className="flex justify-end gap-2">
                      <Button type="button" variant="ghost" size="sm" onClick={() => applyFilter(buildEqcFilter(row))}>
                        EQC
                      </Button>
                      <Button type="button" variant="ghost" size="sm" onClick={() => applyFilter(buildPpidFilter(row))}>
                        PPID
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  )
}
