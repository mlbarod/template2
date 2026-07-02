import { buildBackendUrl, safeParseJson } from "@/lib/api"

const BASE_PATH = "/api/v1/activity"

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
          : `접속 통계 요청 실패 (${response.status})`
    const error = new Error(message)
    error.status = response.status
    error.payload = payload
    throw error
  }
  return payload
}

export function fetchAppAccessStats({ from, to, appId, period } = {}) {
  const params = new URLSearchParams()
  if (from) params.set("from", from)
  if (to) params.set("to", to)
  if (appId) params.set("appId", appId)
  if (period) params.set("period", period)
  const query = params.toString()
  return request(`/app-access-stats${query ? `?${query}` : ""}`)
}

export function syncExternalAppUsageStats() {
  return request("/app-access-sync-external", {
    method: "POST",
  })
}

export function recordAppAccess({ appId, appName, path }) {
  return request("/app-access", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ appId, appName, path }),
  })
}

export function previewManualAppAccessStats({ pastedText, sourceName }) {
  return request("/app-access-manual-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pastedText, sourceName }),
  })
}

export function commitManualAppAccessStats({ pastedText, sourceName }) {
  return request("/app-access-manual-commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pastedText, sourceName }),
  })
}
