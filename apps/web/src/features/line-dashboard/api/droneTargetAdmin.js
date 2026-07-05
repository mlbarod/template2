// 파일 경로: src/features/line-dashboard/api/droneTargetAdmin.js
// superuser 전용 drone_sop_target 관리 API 래퍼입니다.
import { buildBackendUrl, safeParseJson } from "@/lib/api"

import { buildApiError } from "./apiError"

const DRONE_TARGET_ADMIN_PATH = "/api/v1/line-dashboard/admin/drone-targets"

function normalizeText(value) {
  return typeof value === "string" ? value.trim() : ""
}

function normalizeNumber(value) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizeDroneTarget(rawTarget) {
  if (!rawTarget || typeof rawTarget !== "object") return null
  const id = Number.parseInt(rawTarget.id, 10)
  if (!Number.isFinite(id) || id <= 0) return null

  return {
    id,
    lineId: normalizeText(rawTarget.lineId),
    targetUserSdwtProd: normalizeText(rawTarget.targetUserSdwtProd),
    mappingCount: normalizeNumber(rawTarget.mappingCount),
    recipientCount: normalizeNumber(rawTarget.recipientCount),
    channelConfigCount: normalizeNumber(rawTarget.channelConfigCount),
    dispatchCount: normalizeNumber(rawTarget.dispatchCount),
    hasNeedToSendRule: Boolean(rawTarget.hasNeedToSendRule),
    createdAt: normalizeText(rawTarget.createdAt),
    updatedAt: normalizeText(rawTarget.updatedAt),
  }
}

function normalizeTargets(values) {
  return (Array.isArray(values) ? values : [])
    .map((target) => normalizeDroneTarget(target))
    .filter(Boolean)
}

async function parseDroneTargetAdminResponse(response, fallbackMessage) {
  const payload = await safeParseJson(response)
  if (!response.ok) {
    throw buildApiError(response, payload, fallbackMessage)
  }
  return payload
}

export async function fetchDroneTargetAdminRows() {
  const response = await fetch(buildBackendUrl(DRONE_TARGET_ADMIN_PATH), {
    cache: "no-store",
    credentials: "include",
  })
  const payload = await parseDroneTargetAdminResponse(
    response,
    `Failed to load drone targets (status ${response.status})`,
  )

  return {
    targets: normalizeTargets(payload?.targets),
    rowCount: normalizeNumber(payload?.rowCount),
  }
}

export async function createDroneTargetAdminRow({ lineId, targetUserSdwtProd }) {
  const response = await fetch(buildBackendUrl(DRONE_TARGET_ADMIN_PATH), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ lineId, targetUserSdwtProd }),
  })
  const payload = await parseDroneTargetAdminResponse(
    response,
    `Failed to create drone target (status ${response.status})`,
  )

  return { target: normalizeDroneTarget(payload?.target), created: Boolean(payload?.created) }
}

export async function updateDroneTargetAdminRow({ id, lineId, targetUserSdwtProd }) {
  const response = await fetch(buildBackendUrl(DRONE_TARGET_ADMIN_PATH), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ id, lineId, targetUserSdwtProd }),
  })
  const payload = await parseDroneTargetAdminResponse(
    response,
    `Failed to update drone target (status ${response.status})`,
  )

  return { target: normalizeDroneTarget(payload?.target), updated: Boolean(payload?.updated) }
}

export async function deleteDroneTargetAdminRow({ id }) {
  const response = await fetch(buildBackendUrl(DRONE_TARGET_ADMIN_PATH), {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ id }),
  })
  const payload = await parseDroneTargetAdminResponse(
    response,
    `Failed to delete drone target (status ${response.status})`,
  )

  return {
    deleted: Boolean(payload?.deleted),
    target: normalizeDroneTarget(payload?.target),
  }
}
