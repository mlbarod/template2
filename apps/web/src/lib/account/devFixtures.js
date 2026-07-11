const DEV_FIXTURE_ENABLED = import.meta.env.DEV && import.meta.env.VITE_ACCOUNT_DEV_FIXTURES !== "0"

const DUMMY_MANAGEABLE_GROUPS = [
  {
    userSdwtProd: "SDWT_ALPHA",
    members: [
      {
        userId: 9101,
        username: "kim.minjun",
        name: "김민준",
        knoxId: "kim.minjun",
        userSdwtProd: "SDWT_ALPHA",
        role: "manager",
        grantedBy: 9001,
        grantedAt: "2026-07-10T08:30:00+09:00",
      },
      {
        userId: 9102,
        username: "lee.soyeon",
        name: "이소연",
        knoxId: "lee.soyeon",
        userSdwtProd: "SDWT_ALPHA",
        role: "member",
        grantedBy: 9001,
        grantedAt: "2026-07-09T16:10:00+09:00",
      },
    ],
  },
  {
    userSdwtProd: "SDWT_BETA",
    members: [
      {
        userId: 9103,
        username: "park.jiho",
        name: "박지호",
        knoxId: "park.jiho",
        userSdwtProd: "SDWT_BETA",
        role: "viewer",
        grantedBy: 9001,
        grantedAt: "2026-07-08T11:20:00+09:00",
      },
    ],
  },
]

const DUMMY_AFFILIATION_HISTORY = [
  {
    id: 8101,
    status: "PENDING",
    department: "Manufacturing",
    line: "Line A",
    fromUserSdwtProd: "SDWT_LEGACY",
    toUserSdwtProd: "SDWT_ALPHA",
    effectiveFrom: "2026-07-12T09:00:00+09:00",
    approvedAt: null,
    requestedAt: "2026-07-10T09:15:00+09:00",
    approvedBy: null,
    requestedBy: {
      id: 9102,
      username: "lee.soyeon",
      knoxId: "lee.soyeon",
      email: "lee.soyeon@example.test",
    },
    rejectionReason: "",
  },
  {
    id: 8102,
    status: "APPROVED",
    department: "Quality",
    line: "Line B",
    fromUserSdwtProd: "SDWT_ALPHA",
    toUserSdwtProd: "SDWT_BETA",
    effectiveFrom: "2026-07-09T10:00:00+09:00",
    approvedAt: "2026-07-09T10:25:00+09:00",
    requestedAt: "2026-07-09T09:40:00+09:00",
    approvedBy: {
      id: 9001,
      username: "account.manager",
      knoxId: "account.manager",
      email: "account.manager@example.test",
    },
    requestedBy: {
      id: 9103,
      username: "park.jiho",
      knoxId: "park.jiho",
      email: "park.jiho@example.test",
    },
    rejectionReason: "",
  },
  {
    id: 8103,
    status: "REJECTED",
    department: "Engineering",
    line: "Line C",
    fromUserSdwtProd: "SDWT_GAMMA",
    toUserSdwtProd: "SDWT_DELTA",
    effectiveFrom: "2026-07-08T13:00:00+09:00",
    approvedAt: null,
    requestedAt: "2026-07-08T12:45:00+09:00",
    approvedBy: {
      id: 9001,
      username: "account.manager",
      knoxId: "account.manager",
      email: "account.manager@example.test",
    },
    requestedBy: {
      id: 9104,
      username: "choi.yuna",
      knoxId: "choi.yuna",
      email: "choi.yuna@example.test",
    },
    rejectionReason: "요청 소속과 실제 담당 라인이 일치하지 않습니다.",
  },
]

const DUMMY_PENDING_ACCESS_USERS = [
  {
    user: {
      id: 9201,
      userId: 9201,
      username: "han.seojun",
      displayName: "한서준",
      sabun: "T9201",
      knoxId: "han.seojun",
      email: "han.seojun@example.test",
      department: "Manufacturing",
      accountDepartment: "Manufacturing",
      line: "Line A",
      userSdwtProd: "SDWT_ALPHA",
      profileRole: "viewer",
      isStaff: false,
      isSuperuser: false,
    },
    access: {
      allowed: false,
      scope: "portal",
      reason: "pending",
      department: "Manufacturing",
      departmentAllowed: false,
      status: "pending",
      role: "viewer",
      requestId: 7201,
      requestedAt: "2026-07-10T09:20:00+09:00",
      decidedAt: null,
      rejectionReason: null,
      effectiveStatus: "pending",
      explicitStatus: "pending",
      source: "explicit_pending",
      policyMatched: false,
      policy: { matched: false, reason: "not_matched", source: "none", role: "viewer" },
      canRequest: false,
      canManage: false,
    },
  },
  {
    user: {
      id: 9202,
      userId: 9202,
      username: "jung.harin",
      displayName: "정하린",
      sabun: "T9202",
      knoxId: "jung.harin",
      email: "jung.harin@example.test",
      department: "Quality",
      accountDepartment: "Quality",
      line: "Line B",
      userSdwtProd: "SDWT_BETA",
      profileRole: "manager",
      isStaff: false,
      isSuperuser: false,
    },
    access: {
      allowed: false,
      scope: "portal",
      reason: "pending",
      department: "Quality",
      departmentAllowed: false,
      status: "pending",
      role: "member",
      requestId: 7202,
      requestedAt: "2026-07-10T08:55:00+09:00",
      decidedAt: null,
      rejectionReason: null,
      effectiveStatus: "pending",
      explicitStatus: "pending",
      source: "explicit_pending",
      policyMatched: false,
      policy: { matched: false, reason: "not_matched", source: "none", role: "member" },
      canRequest: false,
      canManage: false,
    },
  },
]

const DUMMY_ACCESS_AUDIT_LOGS = [
  {
    id: 7301,
    scope: "portal",
    scopeName: "Portal",
    action: "approve",
    reason: "",
    before: { status: "pending", role: "viewer" },
    after: { status: "allowed", role: "member" },
    createdAt: "2026-07-10T10:05:00+09:00",
    actor: { id: 9001, knoxId: "account.manager", username: "account.manager", email: "account.manager@example.test" },
    targetUser: { id: 9203, knoxId: "yoon.dohyun", username: "yoon.dohyun", email: "yoon.dohyun@example.test" },
    policyRule: null,
  },
  {
    id: 7302,
    scope: "portal",
    scopeName: "Portal",
    action: "reject",
    reason: "테스트용 거절 사유입니다.",
    before: { status: "pending", role: "viewer" },
    after: { status: "denied", role: "viewer" },
    createdAt: "2026-07-10T09:40:00+09:00",
    actor: { id: 9001, knoxId: "account.manager", username: "account.manager", email: "account.manager@example.test" },
    targetUser: { id: 9204, knoxId: "kang.minji", username: "kang.minji", email: "kang.minji@example.test" },
    policyRule: null,
  },
  {
    id: 7303,
    scope: "portal",
    scopeName: "Portal",
    action: "policy_create",
    reason: "",
    before: {},
    after: {
      id: 6101,
      ruleType: "department",
      value: "Manufacturing",
      role: "viewer",
      isActive: true,
    },
    createdAt: "2026-07-09T17:30:00+09:00",
    actor: { id: 9001, knoxId: "account.manager", username: "account.manager", email: "account.manager@example.test" },
    targetUser: null,
    policyRule: {
      id: 6101,
      ruleType: "department",
      value: "Manufacturing",
      role: "viewer",
    },
  },
  {
    id: 7304,
    scope: "portal",
    scopeName: "Portal",
    action: "change_role",
    reason: "운영 담당자 테스트",
    before: { status: "allowed", role: "viewer" },
    after: { status: "allowed", role: "manager" },
    createdAt: "2026-07-09T15:10:00+09:00",
    actor: { id: 9001, knoxId: "account.manager", username: "account.manager", email: "account.manager@example.test" },
    targetUser: { id: 9205, knoxId: "oh.jisoo", username: "oh.jisoo", email: "oh.jisoo@example.test" },
    policyRule: null,
  },
]

function isEmptyArray(value) {
  return !Array.isArray(value) || value.length === 0
}

function buildPagination({ page, pageSize, total }) {
  return {
    page,
    pageSize,
    total,
    totalPages: Math.max(1, Math.ceil(total / pageSize)),
  }
}

function summarizeAccessRows(rows) {
  return rows.reduce(
    (summary, row) => {
      const status = row.access?.effectiveStatus
      const source = row.access?.source
      summary.total += 1
      summary.pageTotal += 1
      if (status === "allowed") summary.allowed += 1
      else if (status === "pending") summary.pending += 1
      else if (status === "denied") summary.denied += 1
      else if (status === "inactive") summary.inactive += 1
      else summary.notRequested += 1
      if (typeof source === "string" && source.startsWith("policy_")) summary.policyAllowed += 1
      if (source === "explicit_allowed") summary.explicitAllowed += 1
      if (source === "explicit_denied") summary.explicitDenied += 1
      return summary
    },
    {
      total: 0,
      pageTotal: 0,
      allowed: 0,
      pending: 0,
      denied: 0,
      notRequested: 0,
      inactive: 0,
      policyAllowed: 0,
      explicitAllowed: 0,
      explicitDenied: 0,
    },
  )
}

export function withDevAccountOverviewFixtures(data) {
  if (!DEV_FIXTURE_ENABLED || !data || typeof data !== "object") return data

  const groups = isEmptyArray(data.manageableGroups?.groups)
    ? DUMMY_MANAGEABLE_GROUPS
    : data.manageableGroups.groups
  const history = isEmptyArray(data.affiliationHistory)
    ? DUMMY_AFFILIATION_HISTORY
    : data.affiliationHistory

  return {
    ...data,
    affiliationHistory: history,
    manageableGroups: {
      ...(data.manageableGroups || {}),
      groups,
    },
  }
}

export function withDevManageableGroupFixtures(data) {
  if (!DEV_FIXTURE_ENABLED || !data || typeof data !== "object") return data
  if (!isEmptyArray(data.groups)) return data
  return {
    ...data,
    groups: DUMMY_MANAGEABLE_GROUPS,
  }
}

export function withDevPendingAccessUserFixtures(data, { page = 1, pageSize = 20, status = "" } = {}) {
  if (!DEV_FIXTURE_ENABLED || !data || typeof data !== "object") return data
  if (status !== "pending" || page !== 1 || !isEmptyArray(data.results)) return data

  const rows = DUMMY_PENDING_ACCESS_USERS.slice(0, pageSize)
  return {
    ...data,
    results: rows,
    summary: summarizeAccessRows(rows),
    pagination: buildPagination({ page, pageSize, total: rows.length }),
  }
}

export function withDevAccessAuditFixtures(data, { page = 1, pageSize = 20 } = {}) {
  if (!DEV_FIXTURE_ENABLED || !data || typeof data !== "object") return data
  if (page !== 1 || !isEmptyArray(data.results)) return data

  const rows = DUMMY_ACCESS_AUDIT_LOGS.slice(0, pageSize)
  return {
    ...data,
    results: rows,
    pagination: buildPagination({ page, pageSize, total: rows.length }),
  }
}
