import { buildBackendUrl } from "@/lib/api"

const endpoints = {
  overview: "/api/v1/account/overview",
  affiliation: "/api/v1/account/affiliation",
  affiliationRequests: "/api/v1/account/affiliation/requests",
  affiliationApprove: "/api/v1/account/affiliation/approve",
  affiliationMembers: "/api/v1/account/affiliation/members",
  grants: "/api/v1/account/access/grants",
  manageable: "/api/v1/account/access/manageable",
  accessUsers: "/api/v1/account/access/users",
  accessMatrix: "/api/v1/account/access/matrix",
  accessPolicyRules: "/api/v1/account/access/policy-rules",
  accessAuditLogs: "/api/v1/account/access/audit-logs",
  users: "/api/v1/account/users",
}

async function request(url, options = {}) {
  try {
    const response = await fetch(url, {
      credentials: "include",
      ...options,
    })
    const contentType = response.headers.get("content-type") || ""
    let data = null
    if (contentType.includes("application/json")) {
      try {
        data = await response.json()
      } catch {
        data = null
      }
    } else {
      const text = await response.text()
      try {
        data = text ? JSON.parse(text) : null
      } catch {
        data = text || null
      }
    }

    return { ok: response.ok, data }
  } catch (error) {
    return { ok: false, data: { error: String(error) } }
  }
}

async function unwrap(response, defaultMessage) {
  if (response.ok) return response.data
  const message = (response?.data && response.data.error) || defaultMessage
  throw new Error(message || "Request failed")
}

function normalizeUser(rawUser) {
  if (!rawUser || typeof rawUser !== "object") return null
  const recipientType = rawUser.recipientType === "external" ? "external" : "user"
  const userId = Number.parseInt(rawUser.userId ?? rawUser.id, 10)
  const knoxId = typeof rawUser.knoxId === "string" ? rawUser.knoxId : ""
  const externalKnoxId = typeof rawUser.externalKnoxId === "string" ? rawUser.externalKnoxId : knoxId
  if (recipientType === "user" && (!Number.isFinite(userId) || userId <= 0)) return null
  if (recipientType === "external" && !externalKnoxId) return null
  const recipientKey =
    typeof rawUser.recipientKey === "string" && rawUser.recipientKey.trim()
      ? rawUser.recipientKey.trim()
      : recipientType === "external"
        ? `external:${externalKnoxId.toLowerCase()}`
        : `user:${userId}`

  return {
    id: recipientType === "external" ? recipientKey : userId,
    userId: recipientType === "external" ? null : userId,
    recipientType,
    recipientKey,
    externalKnoxId,
    username: typeof rawUser.username === "string" ? rawUser.username : "",
    displayName: typeof rawUser.displayName === "string" ? rawUser.displayName : "",
    sabun: typeof rawUser.sabun === "string" ? rawUser.sabun : "",
    knoxId,
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

export async function fetchAccountUserPool({
  search = "",
  department = "",
  userSdwtProd = "",
  contactField = "",
  limit = 50,
  includeExternalSnapshots = false,
} = {}) {
  const params = new URLSearchParams()
  if (search) params.set("search", search)
  if (department) params.set("department", department)
  if (userSdwtProd) params.set("userSdwtProd", userSdwtProd)
  if (contactField) params.set("contactField", contactField)
  if (includeExternalSnapshots) params.set("includeExternalSnapshots", "true")
  params.set("limit", String(limit))

  const url = buildBackendUrl(`${endpoints.users}?${params.toString()}`)
  const response = await request(url, { cache: "no-store" })
  const payload = await unwrap(response, "Failed to load account users")
  return {
    results: normalizeUsers(payload?.results),
    departments: normalizeTextValues(payload?.departments),
    userSdwtProds: normalizeTextValues(payload?.userSdwtProds),
  }
}

export const accountApi = {
  fetchUserPool: fetchAccountUserPool,

  async fetchAffiliation() {
    const url = buildBackendUrl(endpoints.affiliation)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load affiliation")
  },

  async fetchOverview() {
    const url = buildBackendUrl(endpoints.overview)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load account overview")
  },

  async updateAffiliation(payload) {
    const url = buildBackendUrl(endpoints.affiliation)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update affiliation")
  },

  async fetchManageableGroups() {
    const url = buildBackendUrl(endpoints.manageable)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load group members")
  },

  async fetchAffiliationRequests({
    page = 1,
    pageSize = 20,
    status = "pending",
    search = "",
    userSdwtProd = "",
  } = {}) {
    const params = new URLSearchParams()
    params.set("page", String(page))
    params.set("page_size", String(pageSize))
    if (status) params.set("status", status)
    if (search) params.set("q", search)
    if (userSdwtProd) params.set("user_sdwt_prod", userSdwtProd)

    const url = buildBackendUrl(`${endpoints.affiliationRequests}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load affiliation requests")
  },

  async fetchAffiliationMembers({ userSdwtProd } = {}) {
    if (!userSdwtProd) {
      return { userSdwtProd: "", members: [] }
    }
    const params = new URLSearchParams()
    params.set("user_sdwt_prod", userSdwtProd)
    const url = buildBackendUrl(`${endpoints.affiliationMembers}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load affiliation members")
  },

  async decideAffiliationRequest(payload) {
    const url = buildBackendUrl(endpoints.affiliationApprove)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update affiliation request")
  },

  async updateGrant(payload) {
    const url = buildBackendUrl(endpoints.grants)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update grant")
  },

  async fetchAccessUsers({
    page = 1,
    pageSize = 20,
    status = "",
    source = "",
    search = "",
    department = "",
    scope = "portal",
  } = {}) {
    const params = new URLSearchParams()
    params.set("page", String(page))
    params.set("page_size", String(pageSize))
    if (status) params.set("status", status)
    if (source) params.set("source", source)
    if (search) params.set("q", search)
    if (department) params.set("department", department)
    if (scope) params.set("scope", scope)

    const url = buildBackendUrl(`${endpoints.accessUsers}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load access users")
  },

  async fetchAccessMatrix({ page = 1, pageSize = 20, search = "", department = "" } = {}) {
    const params = new URLSearchParams()
    params.set("page", String(page))
    params.set("page_size", String(pageSize))
    if (search) params.set("q", search)
    if (department) params.set("department", department)

    const url = buildBackendUrl(`${endpoints.accessMatrix}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load app access matrix")
  },

  async decideAccessUser({ userId, ...payload }) {
    const url = buildBackendUrl(`${endpoints.accessUsers}/${userId}/decision`)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update access user")
  },

  async fetchAccessPolicyRules({ scope = "portal" } = {}) {
    const params = new URLSearchParams()
    if (scope) params.set("scope", scope)
    const url = buildBackendUrl(`${endpoints.accessPolicyRules}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load access policy rules")
  },

  async createAccessPolicyRule(payload) {
    const url = buildBackendUrl(endpoints.accessPolicyRules)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to create access policy rule")
  },

  async updateAccessPolicyRule({ id, ...payload }) {
    const url = buildBackendUrl(`${endpoints.accessPolicyRules}/${id}`)
    const response = await request(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update access policy rule")
  },

  async deleteAccessPolicyRule({ id }) {
    const url = buildBackendUrl(`${endpoints.accessPolicyRules}/${id}`)
    const response = await request(url, { method: "DELETE" })
    return unwrap(response, "Failed to delete access policy rule")
  },

  async fetchAccessAuditLogs({
    page = 1,
    pageSize = 20,
    scope = "",
    userId = "",
    action = "",
  } = {}) {
    const params = new URLSearchParams()
    params.set("page", String(page))
    params.set("page_size", String(pageSize))
    if (scope) params.set("scope", scope)
    if (userId) params.set("userId", String(userId))
    if (action) params.set("action", action)

    const url = buildBackendUrl(`${endpoints.accessAuditLogs}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load access audit logs")
  },
}
