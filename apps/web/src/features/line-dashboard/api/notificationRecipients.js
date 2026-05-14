// 파일 경로: src/features/line-dashboard/api/notificationRecipients.js
// Drone SOP 채널 수신인 및 권한 컨텍스트 API 래퍼입니다.
import { buildBackendUrl, safeParseJson } from "@/lib/api"

import { buildApiError } from "./apiError"

export { fetchAccountUserPool } from "@/features/account"

const RECIPIENTS_PATH = "/api/v1/line-dashboard/notification-recipients"
const RECIPIENT_PERMISSIONS_PATH = "/api/v1/line-dashboard/notification-recipient-permissions"
const MY_RECIPIENT_TARGETS_PATH = "/api/v1/line-dashboard/my-notification-recipient-targets"
const NOTIFICATION_TARGETS_PATH = "/api/v1/line-dashboard/notification-targets"
const NOTIFICATION_TARGET_MAPPINGS_PATH = "/api/v1/line-dashboard/notification-target-mappings"

function normalizeUser(rawUser) {
  if (!rawUser || typeof rawUser !== "object") return null
  const userId = Number.parseInt(rawUser.userId ?? rawUser.id, 10)
  if (!Number.isFinite(userId) || userId <= 0) return null

  return {
    id: userId,
    userId,
    username: typeof rawUser.username === "string" ? rawUser.username : "",
    displayName: typeof rawUser.displayName === "string" ? rawUser.displayName : "",
    sabun: typeof rawUser.sabun === "string" ? rawUser.sabun : "",
    knoxId: typeof rawUser.knoxId === "string" ? rawUser.knoxId : "",
    email: typeof rawUser.email === "string" ? rawUser.email : "",
    department: typeof rawUser.department === "string" ? rawUser.department : "",
    line: typeof rawUser.line === "string" ? rawUser.line : "",
    userSdwtProd: typeof rawUser.userSdwtProd === "string" ? rawUser.userSdwtProd : "",
  }
}

function normalizeUsers(values) {
  return (Array.isArray(values) ? values : []).map(normalizeUser).filter(Boolean)
}

function normalizeTextValues(values) {
  return Array.isArray(values)
    ? values.filter((value) => typeof value === "string" && value.trim())
    : []
}

function normalizeMappingOptions(rawOptions) {
  const options = rawOptions && typeof rawOptions === "object" ? rawOptions : {}
  return {
    userSdwtProds: normalizeTextValues(options.userSdwtProds),
    sdwtProds: normalizeTextValues(options.sdwtProds),
  }
}

function normalizeTargetMappings(values) {
  return (Array.isArray(values) ? values : [])
    .map((mapping) => {
      if (!mapping || typeof mapping !== "object") return null
      const sdwtProd = typeof mapping.sdwtProd === "string" ? mapping.sdwtProd.trim() : ""
      const userSdwtProd = typeof mapping.userSdwtProd === "string" ? mapping.userSdwtProd.trim() : ""
      if (!sdwtProd && !userSdwtProd) return null
      return { sdwtProd, userSdwtProd }
    })
    .filter(Boolean)
}

function normalizeTarget(rawTarget, fallbackLineId = "") {
  if (!rawTarget || typeof rawTarget !== "object") return null
  const targetUserSdwtProd =
    typeof rawTarget.targetUserSdwtProd === "string" ? rawTarget.targetUserSdwtProd.trim() : ""
  if (!targetUserSdwtProd) return null

  return {
    lineId: typeof rawTarget.lineId === "string" && rawTarget.lineId.trim() ? rawTarget.lineId.trim() : fallbackLineId,
    targetUserSdwtProd,
    source: typeof rawTarget.source === "string" ? rawTarget.source : "custom",
    isConfigured: Boolean(rawTarget.isConfigured),
    jiraKey: typeof rawTarget.jiraKey === "string" ? rawTarget.jiraKey : "",
    channelEnabled: {
      jira: typeof rawTarget.jiraEnabled === "boolean" ? rawTarget.jiraEnabled : true,
      messenger: typeof rawTarget.messengerEnabled === "boolean" ? rawTarget.messengerEnabled : true,
      mail: typeof rawTarget.mailEnabled === "boolean" ? rawTarget.mailEnabled : true,
    },
    mappings: normalizeTargetMappings(rawTarget.mappings),
  }
}

function normalizeTargets(values, fallbackLineId = "") {
  return (Array.isArray(values) ? values : [])
    .map((target) => normalizeTarget(target, fallbackLineId))
    .filter(Boolean)
}

function normalizeRecipientTarget(rawTarget, fallbackLineId = "") {
  const target = normalizeTarget(rawTarget, fallbackLineId)
  if (!target) return null

  return {
    ...target,
    channels: normalizeTextValues(rawTarget?.channels),
  }
}

function normalizeRecipientTargets(values, fallbackLineId = "") {
  return (Array.isArray(values) ? values : [])
    .map((target) => normalizeRecipientTarget(target, fallbackLineId))
    .filter(Boolean)
}

export async function fetchNotificationTargets({ lineId }) {
  if (!lineId) {
    return {
      lineId: "",
      targets: [],
      targetUserSdwtProds: [],
      mappingOptions: { userSdwtProds: [], sdwtProds: [] },
    }
  }

  const response = await fetch(buildBackendUrl(NOTIFICATION_TARGETS_PATH, { lineId }), {
    cache: "no-store",
    credentials: "include",
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to load notification targets (status ${response.status})`,
    )
  }

  const targets = normalizeTargets(payload?.targets, payload?.lineId || lineId)
  return {
    lineId: payload?.lineId || lineId,
    targets,
    targetUserSdwtProds: targets.map((target) => target.targetUserSdwtProd),
    mappingOptions: normalizeMappingOptions(payload?.mappingOptions),
  }
}

export async function fetchMyNotificationRecipientTargets({ lineId }) {
  if (!lineId) {
    return { lineId: "", targets: [] }
  }

  const response = await fetch(buildBackendUrl(MY_RECIPIENT_TARGETS_PATH, { lineId }), {
    cache: "no-store",
    credentials: "include",
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to load my recipient targets (status ${response.status})`,
    )
  }

  return {
    lineId: payload?.lineId || lineId,
    targets: normalizeRecipientTargets(payload?.targets, payload?.lineId || lineId),
  }
}

export async function createNotificationTarget({ lineId, targetUserSdwtProd }) {
  const response = await fetch(buildBackendUrl(NOTIFICATION_TARGETS_PATH), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ lineId, targetUserSdwtProd }),
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to create notification target (status ${response.status})`,
    )
  }

  return {
    lineId: payload?.lineId || lineId,
    target: normalizeTarget(payload?.target, payload?.lineId || lineId),
    updated: Number(payload?.updated || 0),
  }
}

export async function createNotificationTargetMapping({
  lineId,
  targetUserSdwtProd,
  sdwtProd,
  userSdwtProd,
}) {
  const response = await fetch(buildBackendUrl(NOTIFICATION_TARGET_MAPPINGS_PATH), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ lineId, targetUserSdwtProd, sdwtProd, userSdwtProd }),
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to create target mapping (status ${response.status})`,
    )
  }

  return {
    lineId: payload?.lineId || lineId,
    target: normalizeTarget(payload?.target, payload?.lineId || lineId),
    mapping: normalizeTargetMappings([payload?.mapping])[0] || null,
  }
}

export async function fetchNotificationRecipients({ lineId, targetUserSdwtProd, channel = "mail" }) {
  if (!lineId || !targetUserSdwtProd) {
    return { recipients: [] }
  }

  const endpoint = buildBackendUrl(RECIPIENTS_PATH, { lineId, targetUserSdwtProd, channel })
  const response = await fetch(endpoint, {
    cache: "no-store",
    credentials: "include",
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to load recipients (status ${response.status})`,
    )
  }

  return {
    lineId: payload?.lineId || lineId,
    targetUserSdwtProd: payload?.targetUserSdwtProd || targetUserSdwtProd,
    channel: payload?.channel || channel,
    recipients: normalizeUsers(payload?.recipients),
  }
}

export async function fetchNotificationRecipientPermissions() {
  const response = await fetch(buildBackendUrl(RECIPIENT_PERMISSIONS_PATH), {
    cache: "no-store",
    credentials: "include",
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to load recipient permissions (status ${response.status})`,
    )
  }

  return {
    isOperator: Boolean(payload?.isOperator),
    manageableUserSdwtProds: normalizeTextValues(payload?.manageableUserSdwtProds),
  }
}

export async function updateNotificationRecipients({ lineId, targetUserSdwtProd, channel = "mail", userIds = [] }) {
  const response = await fetch(buildBackendUrl(RECIPIENTS_PATH), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      lineId,
      targetUserSdwtProd,
      channel,
      userIds,
    }),
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to update recipients (status ${response.status})`,
    )
  }

  return {
    lineId: payload?.lineId || lineId,
    targetUserSdwtProd: payload?.targetUserSdwtProd || targetUserSdwtProd,
    channel: payload?.channel || channel,
    recipients: normalizeUsers(payload?.recipients),
  }
}
