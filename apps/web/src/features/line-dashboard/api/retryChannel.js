import { buildBackendUrl } from "@/lib/api"

export async function retryDroneSopChannel({ id, channel }) {
  if (!id) {
    throw new Error("id is required")
  }
  if (typeof channel !== "string" || !channel.trim()) {
    throw new Error("channel is required")
  }

  const endpoint = buildBackendUrl(
    `/api/v1/line-dashboard/sop/${encodeURIComponent(String(id))}/retry-channel`
  )

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ channel: channel.trim().toLowerCase() }),
  })

  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = typeof payload?.error === "string" ? payload.error : `Failed to retry channel (${response.status})`
    throw new Error(message)
  }

  return payload
}
