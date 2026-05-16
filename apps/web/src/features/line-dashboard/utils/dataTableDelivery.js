// 파일 경로: src/features/line-dashboard/utils/dataTableDelivery.js
// Delivery row 정규화와 채널별 상태 요약을 담당하는 순수 유틸입니다.
import { deriveFlagState } from "./dataTableFlagState"

export const DELIVERY_CHANNELS = [
  { channel: "jira", field: "delivery_jira", fallbackField: "send_jira", label: "Jira", shortLabel: "Jira" },
  {
    channel: "messenger",
    field: "delivery_messenger",
    fallbackField: "send_messenger",
    label: "Teams",
    shortLabel: "Teams",
  },
  { channel: "mail", field: "delivery_mail", fallbackField: "send_mail", label: "Mail", shortLabel: "Mail" },
]

export const DELIVERY_STATUS_LABELS = {
  success: "성공",
  failed: "실패",
  pending: "대기",
  disabled: "비활성",
  partial_failed: "일부 실패",
  partial_success: "일부 성공",
  unknown: "미확인",
}

const CHANNEL_REASON_KEYS = {
  delivery_jira: ["jiraReason", "jira_reason"],
  delivery_messenger: ["messengerReason", "messenger_reason"],
  delivery_mail: ["mailReason", "mail_reason"],
  send_jira: ["jiraReason", "jira_reason"],
  send_messenger: ["messengerReason", "messenger_reason"],
  send_mail: ["mailReason", "mail_reason"],
}

export function resolveChannelReason(rowOriginal, channelKey) {
  if (!rowOriginal) return null
  const keys = CHANNEL_REASON_KEYS[channelKey] ?? []
  for (const key of keys) {
    const raw = rowOriginal?.[key]
    if (typeof raw === "string" && raw.trim()) return raw.trim()
  }
  return null
}

export function normalizeTextValue(value) {
  if (typeof value === "string") {
    const trimmed = value.trim()
    return trimmed || null
  }
  if (value === null || value === undefined) return null
  const stringValue = String(value).trim()
  return stringValue || null
}

export function normalizeDeliveryRows(rowOriginal) {
  const rawRows = rowOriginal?.deliveryRows ?? rowOriginal?.delivery_rows
  if (!Array.isArray(rawRows)) return []
  return rawRows
    .map((row) => {
      const target = normalizeTextValue(row?.targetUserSdwtProd ?? row?.target_user_sdwt_prod)
      const channel = normalizeTextValue(row?.channel)
      if (!target || !channel) return null
      return {
        id: row?.id,
        dispatchId: row?.dispatchId ?? row?.dispatch_id ?? null,
        target,
        channel,
        dispatchStatus: normalizeTextValue(row?.dispatchStatus ?? row?.dispatch_status),
        commentOverride: normalizeTextValue(row?.commentOverride ?? row?.comment_override),
        status: normalizeTextValue(row?.status)?.toLowerCase() ?? "unknown",
        reason: normalizeTextValue(row?.reason),
        externalKey: normalizeTextValue(row?.externalKey ?? row?.external_key),
        sentComment: normalizeTextValue(row?.sentComment ?? row?.sent_comment),
        sentAt: row?.sentAt ?? row?.sent_at ?? null,
        updatedAt: row?.updatedAt ?? row?.updated_at ?? null,
      }
    })
    .filter(Boolean)
}

export function hasDeliveryRows(rowOriginal) {
  return normalizeDeliveryRows(rowOriginal).length > 0
}

export function uniqueDeliveryTargets(deliveryRows, fallbackTarget) {
  const targets = []
  const seen = new Set()
  for (const row of deliveryRows) {
    const key = row.target.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    targets.push(row.target)
    break
  }
  const fallback = normalizeTextValue(fallbackTarget)
  if (targets.length === 0 && fallback && !seen.has(fallback.toLowerCase())) {
    targets.unshift(fallback)
  }
  return targets
}

export function filterDeliveryRowsForPrimaryTarget(deliveryRows, fallbackTarget) {
  const primaryTarget = uniqueDeliveryTargets(deliveryRows, fallbackTarget)[0]
  if (!primaryTarget) return []
  const primaryKey = primaryTarget.toLowerCase()
  return deliveryRows.filter((row) => row.target.toLowerCase() === primaryKey)
}

function summarizeDeliveryRows(channelRows) {
  const counts = channelRows.reduce(
    (acc, row) => {
      const status = row.status in DELIVERY_STATUS_LABELS ? row.status : "unknown"
      acc[status] = (acc[status] ?? 0) + 1
      return acc
    },
    { success: 0, failed: 0, pending: 0, disabled: 0, unknown: 0 }
  )
  const total = channelRows.length
  const status = (() => {
    if (counts.failed > 0) return counts.failed === total ? "failed" : "partial_failed"
    if (counts.pending > 0 || counts.unknown > 0) return "pending"
    if (counts.disabled === total) return "disabled"
    if (counts.success === total) return "success"
    if (counts.success > 0) return "partial_success"
    return "unknown"
  })()

  return { status, total, ...counts }
}

export function summarizeExistingDeliveryChannel(deliveryRows, channel) {
  const channelRows = deliveryRows.filter((row) => row.channel === channel)
  if (!channelRows.length) return null
  return summarizeDeliveryRows(channelRows)
}

export function summarizeDeliveryChannel(deliveryRows, channel, fallbackValue) {
  const channelRows = deliveryRows.filter((row) => row.channel === channel)
  if (!channelRows.length) {
    const fallbackState = deriveFlagState(fallbackValue, 0)
    return {
      status: fallbackState.isError ? "failed" : fallbackState.isOn ? "success" : "pending",
      total: 0,
      success: fallbackState.isOn ? 1 : 0,
      failed: fallbackState.isError ? 1 : 0,
      pending: fallbackState.state === "off" ? 1 : 0,
      disabled: 0,
    }
  }

  return summarizeDeliveryRows(channelRows)
}

export function summarizeRowDeliveryChannel(rowOriginal, channelKey) {
  const channel = DELIVERY_CHANNELS.find(
    (item) => item.channel === channelKey || item.field === channelKey || item.fallbackField === channelKey
  )
  if (!channel) return null
  const deliveryRows = normalizeDeliveryRows(rowOriginal)
  if (deliveryRows.length) return summarizeExistingDeliveryChannel(deliveryRows, channel.channel)
  return summarizeDeliveryChannel(
    deliveryRows,
    channel.channel,
    rowOriginal?.[channel.field] ?? rowOriginal?.[channel.fallbackField]
  )
}

export function isDeliveryChannelSuccessful(rowOriginal, channelKey) {
  const summary = summarizeRowDeliveryChannel(rowOriginal, channelKey)
  return Boolean(summary && summary.success > 0 && summary.failed === 0)
}

export function getDeliveryStatusLabel(summary) {
  const label = DELIVERY_STATUS_LABELS[summary.status] ?? DELIVERY_STATUS_LABELS.unknown
  if (!summary.total || summary.total <= 1) return label
  if (summary.status === "success") return `${label} ${summary.success}/${summary.total}`
  if (summary.status === "failed" || summary.status === "partial_failed") {
    return `${label} ${summary.failed}/${summary.total}`
  }
  if (summary.status === "pending") return `${label} ${summary.pending + summary.unknown}/${summary.total}`
  if (summary.status === "disabled") return `${label} ${summary.disabled}/${summary.total}`
  return `${label} ${summary.success}/${summary.total}`
}
