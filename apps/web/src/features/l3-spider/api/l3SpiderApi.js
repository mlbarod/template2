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

export function fetchL3SpiderSummary(selection) {
  return postJson("/summary", selection)
}

export function fetchL3SpiderData(selection) {
  return postJson("/data", selection)
}
