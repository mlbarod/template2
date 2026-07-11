import { buildBackendUrl, safeParseJson } from "@/lib/api"

const BASE_PATH = "/api/v1/l0_spider"

async function request(path, searchParams) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}${path}`, searchParams), {
    credentials: "include",
    cache: "no-store",
  })
  const payload = await safeParseJson(response)
  if (!response.ok) {
    const message =
      typeof payload?.error === "string"
        ? payload.error
        : typeof payload?.detail === "string"
          ? payload.detail
          : `L0 Spider 요청 실패 (${response.status})`
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return payload
}

export function fetchHardSpecMeta(params) {
  return request("/hard-spec/meta", params)
}

export function fetchHardSpecRecommendations(params) {
  return request("/hard-spec/recommendations", params)
}
