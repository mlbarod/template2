// 파일 경로: src/features/l3-spider/utils/selection.js
// L3 Spider 선택/필터 상태 유틸입니다.

export const EMPTY_META = {
  dates: [],
  lineIds: [],
  processIds: [],
  edsSteps: [],
  availability: {},
}

export const EMPTY_STATS = {
  total: 0,
  normal: 0,
  warning: 0,
  risk: 0,
  anomalySteps: 0,
  highRiskEqpchs: 0,
}

export const EMPTY_SUMMARY = {
  stats: EMPTY_STATS,
  stepPpids: {},
  bins: [],
  anomalies: [],
}

export const EMPTY_SELECTION = {
  date: "",
  lineIds: new Set(),
  processIds: new Set(),
  edsSteps: new Set(),
}

export function createEmptyFilter() {
  return {
    selectedStepBins: new Set(),
    selectedPpidBins: new Set(),
    selectedEqcs: new Set(),
    selectedSteps: new Set(),
  }
}

export function sortedValues(values) {
  return Array.from(values || []).sort((left, right) =>
    String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: "base" })
  )
}

export function sameSet(left, right) {
  if (left.size !== right.size) return false
  for (const value of left) {
    if (!right.has(value)) return false
  }
  return true
}

export function toggleSetValue(values, value) {
  const next = new Set(values)
  if (next.has(value)) {
    next.delete(value)
  } else {
    next.add(value)
  }
  return next
}

export function setToPayload(values) {
  return sortedValues(values)
}

export function buildSelectionPayload(selection, extra = {}) {
  return {
    dates: selection.date ? [selection.date] : [],
    lineIds: setToPayload(selection.lineIds),
    processIds: setToPayload(selection.processIds),
    edsSteps: setToPayload(selection.edsSteps),
    ...extra,
  }
}

export function hasCompleteSelection(selection) {
  return Boolean(
    selection.date &&
      selection.lineIds.size > 0 &&
      selection.processIds.size > 0 &&
      selection.edsSteps.size > 0,
  )
}

export function buildSelectionKey(selection) {
  return JSON.stringify(buildSelectionPayload(selection))
}

export function buildFilterKey(filter, checkedPpids, checkedBins) {
  return JSON.stringify({
    selectedEqcs: setToPayload(filter.selectedEqcs),
    selectedStepBins: setToPayload(filter.selectedStepBins),
    selectedPpidBins: setToPayload(filter.selectedPpidBins),
    selectedSteps: setToPayload(filter.selectedSteps),
    checkedPpids: setToPayload(checkedPpids),
    checkedBins: setToPayload(checkedBins),
  })
}

export function hasChartFilter(filter) {
  return (
    filter.selectedEqcs.size > 0 ||
    filter.selectedStepBins.size > 0 ||
    filter.selectedPpidBins.size > 0 ||
    filter.selectedSteps.size > 0
  )
}
