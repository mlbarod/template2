// 파일 경로: src/features/l3-spider/hooks/useL3SpiderQueries.js
// L3 Spider 서버 데이터 조회 훅입니다.
import { useQuery } from "@tanstack/react-query"

import {
  fetchL3SpiderData,
  fetchL3SpiderMeta,
  fetchL3SpiderSummary,
  l3SpiderQueryKeys,
} from "../api"
import {
  buildFilterKey,
  buildSelectionKey,
  buildSelectionPayload,
  hasChartFilter,
  hasCompleteSelection,
  setToPayload,
} from "../utils/selection"

export function useL3SpiderMeta() {
  return useQuery({
    queryKey: l3SpiderQueryKeys.meta(),
    queryFn: fetchL3SpiderMeta,
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

export function useL3SpiderData(selection, filter, checkedPpids, checkedBins) {
  const selectionKey = buildSelectionKey(selection)
  const filterKey = buildFilterKey(filter, checkedPpids, checkedBins)
  return useQuery({
    queryKey: l3SpiderQueryKeys.data(selectionKey, filterKey),
    queryFn: () =>
      fetchL3SpiderData(
        buildSelectionPayload(selection, {
          selectedEqcs: setToPayload(filter.selectedEqcs),
          selectedStepBins: setToPayload(filter.selectedStepBins),
          selectedPpidBins: setToPayload(filter.selectedPpidBins),
          selectedSteps: setToPayload(filter.selectedSteps),
          checkedPpids: setToPayload(checkedPpids),
          checkedBins: setToPayload(checkedBins),
        }),
      ),
    enabled: hasCompleteSelection(selection) && hasChartFilter(filter),
  })
}
