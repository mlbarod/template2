// src/features/line-dashboard/utils/dataTableColumnNormalizers.js
// 셀 렌더러에서 공통으로 쓰는 값 정규화 유틸입니다.
import { deriveFlagState, toTinyIntFlag } from "./dataTableFlagState"

export function toHttpUrl(raw) {
  if (raw == null) return null
  const value = String(raw).trim()
  if (!value) return null
  if (/^https?:\/\//i.test(value)) return value
  return `https://${value}`
}

export function splitHttpUrls(raw) {
  if (raw == null) return []
  return String(raw)
    .split(",")
    .map((value) => toHttpUrl(value))
    .filter(Boolean)
}

function normalizeDefectUrlEntry(entry, index) {
  if (typeof entry === "object" && !Array.isArray(entry)) {
    const href = toHttpUrl(entry.map_url)
    if (!href) return null
    const label = String(entry.label ?? entry.step_seq ?? entry.step_desc ?? index + 1).trim()
    const imageRows = Array.isArray(entry.image_rows) ? entry.image_rows : []
    const imageUrls = Array.isArray(entry.image_urls) ? entry.image_urls.map(toHttpUrl).filter(Boolean) : []
    const mapFile = String(entry.map_file ?? "").trim()
    return { href, label: label || String(index + 1), imageRows, imageUrls, mapFile }
  }
  return null
}

export function parseDefectUrls(raw) {
  if (raw == null) return []
  const value = String(raw).trim()
  if (!value) return []

  try {
    const parsed = JSON.parse(value)
    if (Array.isArray(parsed)) {
      return parsed
        .map((entry, index) => normalizeDefectUrlEntry(entry, index))
        .filter(Boolean)
    }
  } catch {
    // 신규 데이터는 defect_json 기반 JSON 배열만 사용합니다.
  }

  return []
}

export function getRecordId(rowOriginal) {
  const rawId = rowOriginal?.id
  if (rawId === undefined || rawId === null) return null
  return String(rawId)
}

export function normalizeJiraKey(raw) {
  if (raw == null) return null
  const key = String(raw).trim().toUpperCase()
  return /^[A-Z0-9]+-\d+$/.test(key) ? key : null
}

export function buildJiraBrowseUrl(jiraKey) {
  const key = normalizeJiraKey(jiraKey)
  return key ? `https://jira.samsungds.net/browse/${key}` : null
}

export function normalizeComment(raw) {
  if (typeof raw === "string") return raw
  if (raw == null) return ""
  return String(raw)
}

export function normalizeNeedToSend(raw) {
  // needtosend은 저장 실패 시 값이 남지 않으므로 음수 상태(-1 등)는 0으로 정리한다.
  return Math.max(0, toTinyIntFlag(raw, 0))
}

export function normalizeInstantInform(raw) {
  return toTinyIntFlag(raw, 0)
}

export function normalizeBinaryFlag(raw) {
  return deriveFlagState(raw, 0).isOn
}

export function normalizeStatus(raw) {
  if (raw == null) return null
  return String(raw).trim().toUpperCase().replace(/\s+/g, "_")
}
