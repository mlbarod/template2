// 파일 경로: src/features/line-dashboard/utils/lineSettings.js
// 라인 설정(조기 알림) 화면에서 공유하는 정규화/포맷 유틸 모음

export function normalizeUserSdwt(values) {
  if (!Array.isArray(values)) return []
  const deduped = new Set()
  return values
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter((value) => {
      if (!value) return false
      if (deduped.has(value)) return false
      deduped.add(value)
      return true
    })
}

export function normalizeEntry(entry, fallbackLineId = "") {
  if (!entry || typeof entry !== "object") return null
  const rawId = entry.id ?? entry?.ID
  if (rawId === null || rawId === undefined) return null

  const lineId =
    typeof entry.lineId === "string"
      ? entry.lineId
      : typeof entry.line_id === "string"
        ? entry.line_id
        : fallbackLineId

  const mainStepRaw =
    typeof entry.mainStep === "string"
      ? entry.mainStep
      : typeof entry.main_step === "string"
        ? entry.main_step
        : ""

  const customRaw =
    entry.customEndStep !== undefined
      ? entry.customEndStep
      : entry.custom_end_step

  const customEndStep =
    customRaw === null || customRaw === undefined
      ? ""
      : typeof customRaw === "string"
        ? customRaw
        : String(customRaw)

  const updatedBy =
    typeof entry.updatedBy === "string"
      ? entry.updatedBy
      : typeof entry.updated_by === "string"
        ? entry.updated_by
        : ""

  const updatedAtRaw = entry.updatedAt ?? entry.updated_at
  const updatedAt =
    typeof updatedAtRaw === "string" || typeof updatedAtRaw === "number"
      ? String(updatedAtRaw)
      : updatedAtRaw && typeof updatedAtRaw === "object" && typeof updatedAtRaw.toString === "function"
        ? updatedAtRaw.toString()
        : ""

  return {
    id: String(rawId),
    lineId,
    mainStep: mainStepRaw,
    customEndStep,
    updatedBy: formatUpdatedBy(updatedBy),
    updatedAt,
  }
}

export function sortEntries(entries) {
  return [...entries].sort((a, b) =>
    a.mainStep.localeCompare(b.mainStep, undefined, { numeric: true, sensitivity: "base" })
  )
}

export function formatUpdatedAt(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })
}

export function formatUpdatedBy(value) {
  if (typeof value !== "string") return ""
  const trimmed = value.trim()
  if (!trimmed) return ""
  const atIndex = trimmed.indexOf("@")
  return atIndex > 0 ? trimmed.slice(0, atIndex) : trimmed
}

export function unwrapErrorMessage(message) {
  if (typeof message === "string") {
    try {
      const parsed = JSON.parse(message)
      if (parsed && typeof parsed.error === "string" && parsed.error.trim()) {
        return parsed.error
      }
    } catch {
      // 동작 없음
    }
    return message
  }
  return ""
}

export function normalizeDraft(value) {
  return typeof value === "string" ? value.trim() : ""
}

export function isDuplicateMessage(message) {
  if (!message) return false
  const lower = message.toLowerCase()
  return (
    lower.includes("already") ||
    lower.includes("duplicate") ||
    lower.includes("uniq") ||
    lower.includes("main step")
  )
}

export function getRecipientPrimaryText(user) {
  return user?.displayName || user?.username || user?.knoxId || user?.sabun || `User ${user?.userId || user?.id}`
}

export function getRecipientUserId(user) {
  if (user?.recipientType === "external") return null
  const userId = Number.parseInt(user?.userId ?? user?.id, 10)
  return Number.isFinite(userId) && userId > 0 ? userId : null
}

export function getRecipientKey(user) {
  if (typeof user?.recipientKey === "string" && user.recipientKey.trim()) {
    return user.recipientKey.trim()
  }
  const externalKnoxId = user?.externalKnoxId || user?.knoxId
  if (user?.recipientType === "external" && externalKnoxId) {
    return `external:${String(externalKnoxId).trim().toLowerCase()}`
  }
  const userId = getRecipientUserId(user)
  return userId ? `user:${userId}` : ""
}

export function getRecipientExternalKnoxId(user) {
  if (user?.recipientType !== "external") return ""
  const externalKnoxId = user?.externalKnoxId || user?.knoxId
  return typeof externalKnoxId === "string" ? externalKnoxId.trim().toLowerCase() : ""
}

export function getRecipientSecondaryText(user) {
  const userSdwtProd = typeof user?.userSdwtProd === "string" && user.userSdwtProd.trim()
    ? user.userSdwtProd.trim()
    : "user_sdwt_prod 없음"
  return user?.recipientType === "external" ? `미가입 ${userSdwtProd}` : userSdwtProd
}

export function getRecipientListText(user) {
  const name =
    user?.displayName ||
    user?.username ||
    user?.sabun ||
    user?.knoxId ||
    `User ${user?.userId || user?.id}`
  const knoxId = user?.knoxId || ""
  return knoxId && name !== knoxId ? `${name}(${knoxId})` : name
}

export function mergeRecipientUsers(currentUsers, nextUsers) {
  const byKey = new Map()
  for (const user of currentUsers || []) {
    const recipientKey = getRecipientKey(user)
    if (recipientKey) {
      const userId = getRecipientUserId(user)
      byKey.set(recipientKey, { ...user, recipientKey, userId, id: userId || recipientKey })
    }
  }
  for (const user of nextUsers || []) {
    const recipientKey = getRecipientKey(user)
    if (recipientKey) {
      const userId = getRecipientUserId(user)
      byKey.set(recipientKey, { ...user, recipientKey, userId, id: userId || recipientKey })
    }
  }
  return Array.from(byKey.values()).sort((a, b) =>
    `${a.userSdwtProd || ""}${getRecipientPrimaryText(a)}`.localeCompare(
      `${b.userSdwtProd || ""}${getRecipientPrimaryText(b)}`,
    ),
  )
}

export function sameUserSdwtProd(left, right) {
  return String(left || "").trim().toLowerCase() === String(right || "").trim().toLowerCase()
}

export function getRecipientPickerUsers(results) {
  return mergeRecipientUsers(results?.group || [], results?.search || [])
}
