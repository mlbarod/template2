// 파일 경로: src/features/pm-spider/api/pmSpiderApi.js
// PM SPIDER 백엔드 API 요청 유틸입니다.
import { buildBackendUrl, safeParseJson } from "@/lib/api"

const BASE_PATH = "/api/v1/pm-comparison"

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
          : `PM SPIDER 요청 실패 (${response.status})`
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

export function fetchPmSpiderMeta(selection = {}) {
  const params = new URLSearchParams()
  for (const key of ["lineId", "eqpId", "fdcBin", "pmTimestamp", "type", "traceDataSource"]) {
    const value = selection[key]
    if (value) params.set(key, value)
  }
  const query = params.toString()
  return request(query ? `/meta?${query}` : "/meta")
}

export function fetchPmSpiderResult(payload) {
  return postJson("/compare", payload)
}
