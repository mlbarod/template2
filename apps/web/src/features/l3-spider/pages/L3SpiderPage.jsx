import { useEffect, useMemo, useRef, useState } from "react"
import { ArrowDown, ArrowUp, Database } from "lucide-react"

import { Button } from "@/components/ui/button"

import { L3SpiderChart } from "../components/L3SpiderChart"
import { L3SpiderDataSelector } from "../components/L3SpiderDataSelector"
import { L3SpiderExclusionSheet } from "../components/L3SpiderExclusionSheet"
import { L3SpiderFilterPanel } from "../components/L3SpiderFilterPanel"
import {
  useL3SpiderData,
  useL3SpiderFilterCandidates,
  useL3SpiderMeta,
  useL3SpiderStats,
  useL3SpiderStructure,
} from "../hooks/useL3SpiderQueries"
import {
  EMPTY_META,
  EMPTY_SELECTION,
  hasCompleteSelection,
} from "../utils/selection"

export function L3SpiderPage() {
  const pageRef = useRef(null)
  const [pageScrollTop, setPageScrollTop] = useState(0)
  const [pageViewportHeight, setPageViewportHeight] = useState(0)
  const [selection, setSelection] = useState(EMPTY_SELECTION)
  const [checkedStep, setCheckedStep] = useState(null)
  const [checkedPpid, setCheckedPpid] = useState(null)
  const [checkedEqc, setCheckedEqc] = useState(null)   // EQPCH 모드
  const [checkedBin, setCheckedBin] = useState(null)   // Bin 모드
  // 분석 모드: EQPCH 선택 → 'eqpch' / Bin 선택 → 'bin'
  const [analysisMode, setAnalysisMode] = useState("eqpch")
  const [xAxisMode, setXAxisMode] = useState("tkin_time")


  const metaQuery = useL3SpiderMeta()
  const structureQuery = useL3SpiderStructure(selection)
  const statsQuery = useL3SpiderStats(selection)

  const meta = metaQuery.data ?? EMPTY_META
  const isSelectionReady = hasCompleteSelection(selection)

  const resetLeafSelections = () => {
    setCheckedStep(null)
    setCheckedPpid(null)
    setCheckedEqc(null)
    setCheckedBin(null)
  }

  useEffect(() => { resetLeafSelections() }, [selection])
  useEffect(() => {
    if (!structureQuery.isSuccess) return
    resetLeafSelections()
  }, [structureQuery.data, structureQuery.isSuccess])
  useEffect(() => {
    const page = pageRef.current
    if (!page) return undefined

    const updateViewport = () => setPageViewportHeight(page.clientHeight || window.innerHeight)
    updateViewport()
    const observer = new ResizeObserver(updateViewport)
    observer.observe(page)
    window.addEventListener("resize", updateViewport)
    return () => {
      observer.disconnect()
      window.removeEventListener("resize", updateViewport)
    }
  }, [])

  // checkedStep은 "eds_step|||step_seq" 복합키
  const checkedEdsStepFromKey = checkedStep ? checkedStep.split("|||")[0] : null
  const checkedStepSeq = checkedStep ? checkedStep.split("|||")[1] : null

  // ppid 선택 시 해당 경로 파일에서만 EQPCH·Bin 후보 조회
  const filterCandidatesQuery = useL3SpiderFilterCandidates(
    selection, checkedEdsStepFromKey, checkedStepSeq, checkedPpid,
  )
  const candidateEqcHighRiskBins = useMemo(
    () => filterCandidatesQuery.isSuccess
      ? (filterCandidatesQuery.data?.eqcHighRiskBins ?? {})
      : null,
    [filterCandidatesQuery.data?.eqcHighRiskBins, filterCandidatesQuery.isSuccess],
  )

  // trellis 기준: EQPCH 선택 → bin별 subplots / Bin 선택 → eqc별 subplots
  const groupBy = analysisMode === "eqpch" ? "bin" : "eqc"

  // Mode 1(EQPCH선택): 해당 EQPCH의 이상 bins만 필터
  // Mode 2(Bin선택): EQPCH 필터 해제 → 모든 EQPCH trellis
  const resolvedEqcs = useMemo(
    () => checkedBin ? [] : (checkedEqc ? [checkedEqc] : []),
    [checkedBin, checkedEqc],
  )
  const resolvedBins = useMemo(
    () => checkedBin
      ? [checkedBin]
      : (checkedEqc && candidateEqcHighRiskBins ? (candidateEqcHighRiskBins[checkedEqc] ?? []) : []),
    [checkedBin, checkedEqc, candidateEqcHighRiskBins],
  )

  const dataQuery = useL3SpiderData(
    selection, checkedEdsStepFromKey, checkedStepSeq, checkedPpid, checkedEqc, checkedBin,
    resolvedEqcs, resolvedBins,
  )
  const rows = dataQuery.data?.rows ?? []
  const handlePageScroll = (event) => {
    setPageScrollTop(event.currentTarget.scrollTop)
  }
  const handleScrollToTop = () => {
    pageRef.current?.scrollTo({ top: 0, behavior: "smooth" })
  }
  const handleScrollToBottom = () => {
    const page = pageRef.current
    if (!page) return
    page.scrollTo({ top: page.scrollHeight, behavior: "smooth" })
  }

  return (
    <div
      ref={pageRef}
      className="relative flex h-full min-h-0 min-w-0 flex-col overflow-y-auto"
      onScroll={handlePageScroll}
    >
      <L3SpiderDataSelector
        meta={meta}
        selection={selection}
        onSelectionChange={setSelection}
        isLoading={metaQuery.isFetching}
        onRefresh={() => metaQuery.refetch()}
        stats={statsQuery.data?.stats}
        showStats={isSelectionReady}
        headerExtra={<L3SpiderExclusionSheet />}
        rightContent={
          <L3SpiderFilterPanel
            edsStepSeqs={structureQuery.data?.edsStepSeqs ?? {}}
            edsStepPpids={structureQuery.data?.edsStepPpids ?? {}}
            ppidLastTkinTime={statsQuery.data?.ppidLastTkinTime ?? {}}
            selectedEdsSteps={selection.edsSteps}
            eqcHighRiskBins={candidateEqcHighRiskBins}
            isCandidatesLoading={filterCandidatesQuery.isFetching && !!checkedPpid}
            checkedStep={checkedStep}
            checkedPpid={checkedPpid}
            checkedEqc={checkedEqc}
            checkedBin={checkedBin}
            onCheckedStepChange={setCheckedStep}
            onCheckedPpidChange={setCheckedPpid}
            onCheckedEqcChange={setCheckedEqc}
            onCheckedBinChange={setCheckedBin}
            onAnalysisModeChange={setAnalysisMode}
          />
        }
      />

      {metaQuery.error ? (
        <div className="mx-6 mt-4 shrink-0 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {metaQuery.error.message || "L3 Spider 메타데이터를 불러오지 못했습니다."}
        </div>
      ) : null}

      {!isSelectionReady ? (
        <div className="m-6 flex flex-1 items-center justify-center rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground shadow-sm">
          <div className="grid justify-items-center gap-2">
            <Database className="size-6" aria-hidden="true" />
            날짜, Line, Process, EDS Step을 선택하면 요약과 차트를 조회합니다.
          </div>
        </div>
      ) : (
        <main className="grid gap-5 px-6 pb-6 pt-4">
          <L3SpiderChart
            rows={rows}
            isLoading={structureQuery.isFetching || statsQuery.isFetching || dataQuery.isFetching}
            error={structureQuery.error || statsQuery.error || dataQuery.error}
            groupBy={groupBy}
            xAxisMode={xAxisMode}
            onXAxisModeChange={setXAxisMode}
            scrollContainerRef={pageRef}
            outerScrollTop={pageScrollTop}
            outerViewportHeight={pageViewportHeight}
          />
        </main>
      )}
      <div className="fixed bottom-6 right-6 z-40 grid gap-2">
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="rounded-full bg-background shadow-lg"
          aria-label="화면 맨 위로 이동"
          onClick={handleScrollToTop}
        >
          <ArrowUp className="size-4" aria-hidden="true" />
        </Button>
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="rounded-full bg-background shadow-lg"
          aria-label="화면 맨 아래로 이동"
          onClick={handleScrollToBottom}
        >
          <ArrowDown className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </div>
  )
}
