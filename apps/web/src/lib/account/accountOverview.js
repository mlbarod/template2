import { withDevAccountOverviewFixtures } from "./devFixtures"

const REQUEST_STATUS_LABELS = {
  PENDING: { label: "대기", variant: "secondary" },
  APPROVED: { label: "승인", variant: "default" },
  REJECTED: { label: "거절", variant: "destructive" },
  SUPERSEDED: { label: "취소(대체됨)", variant: "outline" },
}

const ACCOUNT_ROLE_LABELS = {
  admin: "Admin",
  manager: "Manager",
  viewer: "Viewer",
}

export const ACCESS_ROLE_LABELS = {
  viewer: "뷰어",
  member: "멤버",
  manager: "관리자",
}

export const ACCESS_ROLE_VARIANTS = {
  viewer: "secondary",
  member: "outline",
  manager: "default",
}

export function formatAccountDate(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"
  return date.toLocaleString("ko-KR")
}

export function formatAccountDateValue(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("ko-KR")
}

export function resolveAccessRole(value) {
  return ACCESS_ROLE_LABELS[value] ? value : "viewer"
}

export function resolveLatestRequest(history = []) {
  return history.find((item) => item.status === "PENDING") || history[0] || null
}

export function getRequestStatus(status) {
  return REQUEST_STATUS_LABELS[status] || {
    label: status || "미지정",
    variant: "outline",
  }
}

export function getAccountRoleLabel(role) {
  const roleKey = (role || "").toLowerCase()
  return ACCOUNT_ROLE_LABELS[roleKey] || role || "미지정"
}

export function getPendingRequestCount(history = []) {
  return history.filter((item) => item.status === "PENDING").length
}

export function getAffiliationLabel(affiliation) {
  return [
    affiliation?.currentDepartment || "미지정",
    affiliation?.currentLine || "미지정",
    affiliation?.currentUserSdwtProd || "미지정",
  ].join(" / ")
}

export function buildManageableGroupRows(groups = []) {
  return groups.flatMap((group) =>
    (group.members?.length ? group.members : [null]).map((member) => ({
      group,
      member,
    })),
  )
}

export function countManageableGroupMembers(groups = []) {
  return groups.reduce((sum, group) => sum + (group.members?.length || 0), 0)
}

export function buildAccountSummaryModel({
  profile,
  affiliation,
  reconfirm,
  history = [],
  latestRequest,
} = {}) {
  const resolvedLatestRequest = latestRequest || resolveLatestRequest(history)
  return {
    latestRequest: resolvedLatestRequest,
    roleLabel: getAccountRoleLabel(profile?.role),
    needsReconfirm: Boolean(reconfirm?.requiresReconfirm),
    pendingRequests: getPendingRequestCount(history),
    requestStatus: resolvedLatestRequest ? getRequestStatus(resolvedLatestRequest.status) : null,
    affiliationLabel: getAffiliationLabel(affiliation),
    latestRequestValue: resolvedLatestRequest
      ? `${resolvedLatestRequest.fromUserSdwtProd || "-"} → ${resolvedLatestRequest.toUserSdwtProd || "-"}`
      : "요청 없음",
    latestRequestDescription: resolvedLatestRequest
      ? `요청 시각: ${formatAccountDate(resolvedLatestRequest.requestedAt)}`
      : "소속 변경 요청 이력이 없습니다.",
  }
}

export function normalizeAccountOverview(data) {
  if (!data || typeof data !== "object") return data

  const fixtureData = withDevAccountOverviewFixtures(data)
  const history = Array.isArray(fixtureData.affiliationHistory) ? fixtureData.affiliationHistory : []
  const manageableGroups = Array.isArray(fixtureData.manageableGroups?.groups)
    ? fixtureData.manageableGroups.groups
    : []
  const latestRequest = resolveLatestRequest(history)

  return {
    ...fixtureData,
    affiliationHistory: history,
    manageableGroups: {
      ...(fixtureData.manageableGroups || {}),
      groups: manageableGroups,
    },
    accountSummary: buildAccountSummaryModel({
      profile: fixtureData.user,
      affiliation: fixtureData.affiliation,
      reconfirm: fixtureData.affiliationReconfirm,
      history,
      latestRequest,
    }),
  }
}
