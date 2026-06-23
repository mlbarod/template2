// 파일 경로: src/features/pm-spider/utils/format.js
// PM SPIDER 화면 표시와 요청 payload 변환 유틸입니다.

export const DEFAULT_PM_FORM = {
  lineId: "",
  eqpId: "",
  fdcBin: "",
  pmTimestamp: "",
}

export const PM_SPIDER_CATEGORIES = [
  {
    id: "ag-trace",
    label: "AG TRACE",
    type: "ag",
    typeLabel: "AG",
    kind: "trace",
    sourceLabel: "Trace",
    description: "ag wafer",
  },
  {
    id: "ag-oes",
    label: "AG OES",
    type: "ag",
    typeLabel: "AG",
    kind: "oes",
    sourceLabel: "OES",
    description: "ag wafer",
  },
  {
    id: "process-trace",
    label: "PROCESS TRACE",
    type: "process",
    typeLabel: "PROCESS",
    kind: "trace",
    sourceLabel: "Trace",
    description: "process wafer",
  },
  {
    id: "process-oes",
    label: "PROCESS OES",
    type: "process",
    typeLabel: "PROCESS",
    kind: "oes",
    sourceLabel: "OES",
    description: "process wafer",
  },
]

export function splitCsv(value) {
  if (!value) return []
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

export function hasRequiredPmFilters(form) {
  return Boolean(form.lineId && form.eqpId && form.fdcBin && form.pmTimestamp)
}

export function buildPmSpiderPayload(form) {
  if (!hasRequiredPmFilters(form)) return null
  return {
    lineId: form.lineId.trim(),
    eqpId: form.eqpId.trim(),
    fdcBin: (form.fdcBin || "").trim(),
    pmTimestamp: form.pmTimestamp,
    dtValues: form.pmTimestamp ? [form.pmTimestamp] : [],
    traceDataSource: "trace",
    oesDataSource: "oes",
  }
}

export function buildPmSpiderTypePayloads(payload) {
  if (!payload) return []
  return ["ag", "process"].map((type) => ({
    type,
    payload: {
      ...payload,
      type,
      includeDetails: false,
    },
  }))
}

export function formatNumber(value, digits = 3) {
  if (value === null || value === undefined || value === "") return "-"
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
  }).format(numeric)
}

export function formatPercent(value) {
  if (value === null || value === undefined || value === "") return "-"
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return "-"
  return `${formatNumber(numeric * 100, 1)}%`
}

export function formatDateTime(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

export function normalizeOptions(values) {
  return Array.isArray(values) ? values.filter(Boolean) : []
}
