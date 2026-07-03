// 파일 경로: src/features/l3-spider/utils/selection.js
// L3 Spider 선택/필터 상태 유틸입니다.

export const EMPTY_META = {
  dates: [],
  lineIds: [],
  processIds: [],
  edsSteps: [],
  availability: {},
  lineGroups: [],
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
  edsStepSeqs: {},
  edsStepPpids: {},
  stepPpids: {},
  ppidEqcs: {},
  ppidHighRiskEqcs: {},
  ppidBins: {},
  eqcBins: {},
  eqcAnomalyBins: {},
  eqcHighRiskBins: {},
  bins: [],
  anomalies: [],
}

export function createEmptySelection() {
  return {
    date: "",
    lineNames: new Set(),
    lineIds: new Set(),
    processIds: new Set(),
    edsSteps: new Set(),
  }
}

export const EMPTY_SELECTION = createEmptySelection()

function valuesFromSearchParams(searchParams, names) {
  const seen = new Set()
  for (const name of names) {
    for (const rawValue of searchParams.getAll(name)) {
      for (const value of rawValue.split(",")) {
        const cleaned = value.trim()
        if (cleaned) seen.add(cleaned)
      }
    }
  }
  return Array.from(seen)
}

function firstValueFromSearchParams(searchParams, names) {
  return valuesFromSearchParams(searchParams, names)[0] ?? ""
}

export function createSelectionFromSearchParams(searchParams) {
  return {
    date: firstValueFromSearchParams(searchParams, ["date"]),
    lineIds: new Set(
      valuesFromSearchParams(searchParams, ["lineId", "lineIds", "line_id", "line_ids"]),
    ),
    processIds: new Set(
      valuesFromSearchParams(
        searchParams,
        ["processId", "processIds", "process_id", "process_ids"],
      ),
    ),
    edsSteps: new Set(
      valuesFromSearchParams(searchParams, ["edsStep", "edsSteps", "eds_step", "eds_steps"]),
    ),
  }
}

export function createLeafSelectionFromSearchParams(searchParams) {
  const edsStep = firstValueFromSearchParams(searchParams, ["edsStep", "eds_step"])
  const stepSeq = firstValueFromSearchParams(searchParams, ["stepSeq", "step_seq"])
  const ppid = firstValueFromSearchParams(searchParams, ["ppid"])
  const eqpch = firstValueFromSearchParams(searchParams, ["eqpch", "eqc"])
  const binName = firstValueFromSearchParams(searchParams, ["binName", "bin_name"])

  return {
    checkedStep: edsStep && stepSeq ? `${edsStep}|||${stepSeq}` : null,
    checkedPpid: ppid || null,
    checkedEqc: eqpch || null,
    checkedBin: binName || null,
    analysisMode: binName ? "bin" : "eqpch",
  }
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
    lineNames: setToPayload(selection.lineNames ?? new Set()),
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

export function buildFilterKey(checkedEdsStep, checkedStep, checkedPpid, checkedEqc, checkedBin, resolvedEqcs, resolvedBins) {
  return JSON.stringify({
    checkedEdsStep: checkedEdsStep ?? null,
    checkedStep: checkedStep ?? null,
    checkedPpid: checkedPpid ?? null,
    checkedEqc: checkedEqc ?? null,
    checkedBin: checkedBin ?? null,
    resolvedEqcs: resolvedEqcs ?? [],
    resolvedBins: resolvedBins ?? [],
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
