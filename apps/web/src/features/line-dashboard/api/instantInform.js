import { buildBackendUrl } from "@/lib/api"

export async function instantInformDroneSop({ id, comment }) {
  if (!id) {
    throw new Error("id is required")
  }

  const endpoint = buildBackendUrl(
    `/api/v1/line-dashboard/sop/${encodeURIComponent(String(id))}/instant-inform`
  )

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ comment }),
  })

  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = typeof payload?.error === "string" ? payload.error : `Failed to instant-inform (${response.status})`
    throw new Error(message)
  }

  return payload
}
