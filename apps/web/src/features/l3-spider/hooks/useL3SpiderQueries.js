// 파일 경로: src/features/l3-spider/hooks/useL3SpiderQueries.js
import { useQuery } from "@tanstack/react-query"

import {
  fetchL3SpiderData,
  fetchL3SpiderFilterCandidates,
  fetchL3SpiderMeta,
  fetchL3SpiderStats,
  fetchL3SpiderStructure,
  fetchL3SpiderSummary,
  l3SpiderQueryKeys,
} from "../api"
import {
  buildFilterKey,
  buildSelectionKey,
  buildSelectionPayload,
  hasCompleteSelection,
} from "../utils/selection"

export function useL3SpiderMeta() {
  return useQuery({
    queryKey: l3SpiderQueryKeys.meta(),
    queryFn: fetchL3SpiderMeta,
  })
}

export function useL3SpiderStructure(selection) {
  const selectionKey = buildSelectionKey(selection)
  return useQuery({
    queryKey: l3SpiderQueryKeys.structure(selectionKey),
    queryFn: () => fetchL3SpiderStructure(buildSelectionPayload(selection)),
    enabled: hasCompleteSelection(selection),
  })
}

export function useL3SpiderStats(selection) {
  const selectionKey = buildSelectionKey(selection)
  return useQuery({
    queryKey: l3SpiderQueryKeys.stats(selectionKey),
    queryFn: () => fetchL3SpiderStats(buildSelectionPayload(selection)),
    enabled: hasCompleteSelection(selection),
  })
}

export function useL3SpiderSummary(selection) {
  const selectionKey = buildSelectionKey(selection)
  return useQuery({
    queryKey: l3SpiderQueryKeys.summary(selectionKey),
    queryFn: () => fetchL3SpiderSummary(buildSelectionPayload(selection)),
    enabled: hasCompleteSelection(selection),
  })
}

// ppid 선택 시 해당 경로의 파일에서 high risk EQPCH·Bin 후보만 반환
export function useL3SpiderFilterCandidates(selection, edsStep, stepSeq, ppid) {
  const enabled = Boolean(
    hasCompleteSelection(selection) && edsStep && stepSeq && ppid,
  )
  const key = JSON.stringify({
    date: selection.date,
    lineIds: [...(selection.lineIds ?? [])].sort(),
    processIds: [...(selection.processIds ?? [])].sort(),
    edsStep,
    stepSeq,
    ppid,
  })
  return useQuery({
    queryKey: l3SpiderQueryKeys.filterCandidates(key),
    queryFn: () =>
      fetchL3SpiderFilterCandidates({
        dates: [selection.date],
        lineIds: [...(selection.lineIds ?? [])],
        processIds: [...(selection.processIds ?? [])],
        edsStep,
        stepSeq,
        ppid,
      }),
    enabled,
  })
}

// resolvedEqcs: bin 선택 시 [] (전체 EQPCH), 아니면 [checkedEqc]
// resolvedBins: bin 선택 시 [checkedBin], 아니면 이상 감지 bins 목록
export function useL3SpiderData(selection, checkedEdsStep, checkedStep, checkedPpid, checkedEqc, checkedBin, resolvedEqcs, resolvedBins) {
  const selectionKey = buildSelectionKey(selection)
  const filterKey = buildFilterKey(checkedEdsStep, checkedStep, checkedPpid, checkedEqc, checkedBin, resolvedEqcs, resolvedBins)
  return useQuery({
    queryKey: l3SpiderQueryKeys.data(selectionKey, filterKey),
    queryFn: () =>
      fetchL3SpiderData(
        buildSelectionPayload(selection, {
          selectedEqcs: resolvedEqcs,
          selectedSteps: checkedStep ? [checkedStep] : [],
          checkedEdsSteps: checkedEdsStep ? [checkedEdsStep] : [],
          checkedPpids: checkedPpid ? [checkedPpid] : [],
          checkedBins: resolvedBins,
          selectedStepBins: [],
          selectedPpidBins: [],
        }),
      ),
    enabled: hasCompleteSelection(selection) && (checkedEqc !== null || checkedBin !== null),
  })
}
