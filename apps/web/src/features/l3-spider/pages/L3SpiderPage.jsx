import { useEffect, useMemo, useState } from "react"
import { Database, RefreshCw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

import { L3SpiderAnomalyTable } from "../components/L3SpiderAnomalyTable"
import { L3SpiderChart } from "../components/L3SpiderChart"
import { L3SpiderDataSelector } from "../components/L3SpiderDataSelector"
import { L3SpiderFilterPanel } from "../components/L3SpiderFilterPanel"
import { L3SpiderSummaryCards } from "../components/L3SpiderSummaryCards"
import {
  useL3SpiderData,
  useL3SpiderMeta,
  useL3SpiderSummary,
} from "../hooks/useL3SpiderQueries"
import {
  EMPTY_META,
  EMPTY_SELECTION,
  EMPTY_SUMMARY,
  createEmptyFilter,
  hasCompleteSelection,
} from "../utils/selection"

export function L3SpiderPage() {
  const [selection, setSelection] = useState(EMPTY_SELECTION)
  const [filter, setFilter] = useState(() => createEmptyFilter())
  const [checkedPpids, setCheckedPpids] = useState(new Set())
  const [checkedBins, setCheckedBins] = useState(new Set())
  const [groupBy, setGroupBy] = useState("eqc")
  const [xAxisMode, setXAxisMode] = useState("time")

  const metaQuery = useL3SpiderMeta()
  const summaryQuery = useL3SpiderSummary(selection)
  const dataQuery = useL3SpiderData(selection, filter, checkedPpids, checkedBins)

  const meta = metaQuery.data ?? EMPTY_META
  const summary = summaryQuery.data ?? EMPTY_SUMMARY
  const rows = dataQuery.data?.rows ?? []
  const isSelectionReady = hasCompleteSelection(selection)

  useEffect(() => {
    setFilter(createEmptyFilter())
    setCheckedPpids(new Set())
    setCheckedBins(new Set())
  }, [selection])

  useEffect(() => {
    if (!summaryQuery.isSuccess) return
    setCheckedPpids(new Set(Object.values(summary.stepPpids ?? {}).flat()))
    setCheckedBins(new Set(summary.bins ?? []))
  }, [summary, summaryQuery.isSuccess])

  const allRiskEqcs = useMemo(
    () => new Set((summary.anomalies ?? []).map((row) => row.eqc).filter(Boolean)),
    [summary.anomalies],
  )

  const showAllRisk = () => {
    if (allRiskEqcs.size === 0) return
    setFilter({
      selectedEqcs: allRiskEqcs,
      selectedStepBins: new Set(),
      selectedPpidBins: new Set(),
      selectedSteps: new Set(),
    })
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-muted/30">
      <header className="shrink-0 border-b bg-card px-6 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold tracking-tight">L3 Spider</h1>
              <Badge variant="outline">Parquet</Badge>
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              EDS 계측 기반 반도체 챔버 이상감지 데이터를 조회합니다.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              metaQuery.refetch()
              summaryQuery.refetch()
              dataQuery.refetch()
            }}
          >
            <RefreshCw className="size-4" />
            전체 새로고침
          </Button>
        </div>
      </header>

      <L3SpiderDataSelector
        meta={meta}
        selection={selection}
        onSelectionChange={setSelection}
        isLoading={metaQuery.isFetching}
        onRefresh={() => metaQuery.refetch()}
      />

      {metaQuery.error ? (
        <div className="mx-6 mt-3 shrink-0 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {metaQuery.error.message || "L3 Spider 메타데이터를 불러오지 못했습니다."}
        </div>
      ) : null}

      {isSelectionReady ? <L3SpiderSummaryCards stats={summary.stats} /> : null}

      {!isSelectionReady ? (
        <div className="m-6 flex flex-1 min-h-0 items-center justify-center rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
          <div className="grid justify-items-center gap-2">
            <Database className="size-6" aria-hidden="true" />
            날짜, Line, Process, EDS Step을 선택하면 요약과 차트를 조회합니다.
          </div>
        </div>
      ) : (
        <div className="grid flex-1 min-h-0 min-w-0 grid-cols-[240px,1fr] overflow-hidden">
          <L3SpiderFilterPanel
            stepPpids={summary.stepPpids ?? {}}
            bins={summary.bins ?? []}
            checkedPpids={checkedPpids}
            checkedBins={checkedBins}
            onCheckedPpidsChange={setCheckedPpids}
            onCheckedBinsChange={setCheckedBins}
            onClearChartFilter={() => setFilter(createEmptyFilter())}
          />
          <section className="grid min-h-0 min-w-0 grid-rows-[minmax(220px,0.38fr),1fr] gap-4 overflow-hidden p-4">
            <L3SpiderAnomalyTable
              anomalies={summary.anomalies ?? []}
              filter={filter}
              onFilterChange={setFilter}
              onShowAllRisk={showAllRisk}
            />
            <L3SpiderChart
              rows={rows}
              isLoading={summaryQuery.isFetching || dataQuery.isFetching}
              error={summaryQuery.error || dataQuery.error}
              groupBy={groupBy}
              onGroupByChange={setGroupBy}
              xAxisMode={xAxisMode}
              onXAxisModeChange={setXAxisMode}
            />
          </section>
        </div>
      )}
    </div>
  )
}
