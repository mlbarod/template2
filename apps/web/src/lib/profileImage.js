const DEFAULT_MINIO_BASE_URL = "http://localhost:9000"

function removeTrailingSlash(value) {
  return value.replace(/\/+$/, "")
}

function readEnvValue(...keys) {
  for (const key of keys) {
    if (!key) continue
    if (typeof import.meta !== "undefined" && import.meta.env && key in import.meta.env) {
      const value = import.meta.env[key]
      if (typeof value === "string" && value.trim()) {
        return value
      }
    }
    if (typeof process !== "undefined" && process.env && key in process.env) {
      const value = process.env[key]
      if (typeof value === "string" && value.trim()) {
        return value
      }
    }
  }
  return undefined
}

function normalizeAvatarId(value) {
  if (typeof value === "string") return value.trim()
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  return ""
}

function normalizeAvatarIdString(value) {
  return typeof value === "string" ? value.trim() : ""
}

export function getMinioBaseUrl() {
  const envValue =
    readEnvValue("VITE_MINIO_ENDPOINT", "VITE_MINIO_BASE_URL", "MINIO_ENDPOINT") ??
    DEFAULT_MINIO_BASE_URL

  return removeTrailingSlash(envValue.trim())
}

export function resolveProfileAvatarId(source) {
  if (!source || typeof source !== "object") return ""

  return (
    normalizeAvatarIdString(source.avatarid) ||
    normalizeAvatarIdString(source.avatarId) ||
    normalizeAvatarIdString(source.avatar_id) ||
    normalizeAvatarIdString(source.userid) ||
    normalizeAvatarIdString(source.userId) ||
    normalizeAvatarIdString(source.user_id)
  )
}

export function buildProfileImageUrl(avatarId) {
  const normalized = normalizeAvatarId(avatarId)
  if (!normalized) return ""

  const base = getMinioBaseUrl()
  return `${base}/profile/${encodeURIComponent(normalized)}.png`
}
