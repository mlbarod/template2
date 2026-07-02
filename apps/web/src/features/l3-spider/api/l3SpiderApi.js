// 파일 경로: src/features/l3-spider/api/l3SpiderApi.js
// L3 Spider 백엔드 API 요청 유틸입니다.
import { buildBackendUrl, safeParseJson } from "@/lib/api"

const BASE_PATH = "/api/v1/l3_spider"

async function request(path, options = {}) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}${path}`), {
    credentials: "include",
    cache: "no-store",
    ...options,
  })
  const payload = await safeParseJson(response)
  if (!response.ok) {
    const message =
      typeof payload?.error === "string"
        ? payload.error
        : typeof payload?.detail === "string"
          ? payload.detail
          : `L3 Spider 요청 실패 (${response.status})`
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return payload
}

function postJson(path, body) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

export function fetchL3SpiderMeta() {
  return request("/meta")
}

export function fetchL3SpiderStructure(selection) {
  return postJson("/structure", selection)
}

export function fetchL3SpiderStats(selection) {
  return postJson("/stats", selection)
}

export function fetchL3SpiderSummary(selection) {
  return postJson("/summary", selection)
}

export function fetchL3SpiderDailySummary(payload) {
  return postJson("/daily-summary", payload)
}

export function fetchL3SpiderData(selection) {
  return postJson("/data", selection).then(({ cols, colData }) => {
    if (!cols?.length || !colData?.length) return { rows: [] }
    const n = colData[0].length
    const rows = new Array(n)
    for (let i = 0; i < n; i++) {
      const obj = {}
      for (let j = 0; j < cols.length; j++) obj[cols[j]] = colData[j][i]
      rows[i] = obj
    }
    return { rows }
  })
}

export function fetchL3SpiderFilterCandidates(params) {
  return postJson("/filter-candidates", params)
}

export function fetchExclusionFilters() {
  return request("/exclusion-filters")
}

export function fetchMailRules() {
  return request("/mail-rules")
}

export function createExclusionFilter(data) {
  return postJson("/exclusion-filters", data)
}

export function createMailRule(data) {
  return postJson("/mail-rules", data)
}

export function updateExclusionFilter(id, data) {
  return request(`/exclusion-filters/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
}

export function updateMailRule(id, data) {
  return request(`/mail-rules/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
}

export function updateMailRulePermissions(id, permissions) {
  return request(`/mail-rules/${id}/permissions`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ permissions }),
  })
}

export function testSendMailRule(id) {
  return postJson(`/mail-rules/${id}/test-send`, {})
}

export async function deleteExclusionFilter(id) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/exclusion-filters/${id}`), {
    method: "DELETE",
    credentials: "include",
    cache: "no-store",
  })
  if (!response.ok) {
    let message = `L3 Spider 요청 실패 (${response.status})`
    try {
      const payload = await response.json()
      if (typeof payload?.error === "string") message = payload.error
    } catch (_error) {
      // 응답 본문을 읽지 못하면 기본 상태 코드 메시지를 사용합니다.
    }
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return null
}

export async function deleteMailRule(id) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/mail-rules/${id}`), {
    method: "DELETE",
    credentials: "include",
    cache: "no-store",
  })
  if (!response.ok) {
    let message = `L3 Spider 요청 실패 (${response.status})`
    try {
      const payload = await response.json()
      if (typeof payload?.error === "string") message = payload.error
    } catch (_error) {
      // 응답 본문을 읽지 못하면 기본 상태 코드 메시지를 사용합니다.
    }
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return null
}
