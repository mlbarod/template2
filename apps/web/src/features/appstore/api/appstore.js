// 앱스토어 API 요청 유틸 (React Query 전용)

import { buildBackendUrl } from "@/lib/api"
import { normalizeCoverIndex, normalizeScreenshotUrls } from "../utils/appScreenshots"

function parseJson(response) {
  return response
    .json()
    .catch(() => ({}))
    .then((data) => ({ data, ok: response.ok, status: response.status }))
}

async function request(path, options = {}) {
  const endpoint = buildBackendUrl(path)
  const response = await fetch(endpoint, {
    credentials: "include",
    cache: "no-store",
    ...options,
  })
  const { data, ok, status } = await parseJson(response)
  if (!ok) {
    const message = typeof data?.error === "string" ? data.error : `Request failed (${status})`
    const error = new Error(message)
    error.status = status
    throw error
  }
  return data
}

function ensureString(value) {
  return typeof value === "string" ? value : ""
}

function normalizeUser(rawUser) {
  if (!rawUser || typeof rawUser !== "object") return null
  return {
    id: rawUser.id ?? null,
    name: ensureString(rawUser.name) || "사용자",
    knoxid: ensureString(rawUser.knoxid),
  }
}

function normalizeComment(raw) {
  if (!raw || typeof raw !== "object") return null
  const id = raw.id ?? raw.commentId ?? raw.pk ?? null
  if (id == null) return null
  return {
    id,
    appId: raw.appId ?? raw.app_id ?? null,
    parentCommentId: raw.parentCommentId ?? raw.parent_comment_id ?? raw.parentId ?? raw.parent_id ?? null,
    content: ensureString(raw.content),
    createdAt: ensureString(raw.createdAt || raw.created_at),
    updatedAt: ensureString(raw.updatedAt || raw.updated_at || raw.createdAt || raw.created_at),
    author: normalizeUser(raw.author),
    likeCount: Number(raw.likeCount ?? raw.like_count ?? 0) || 0,
    liked: Boolean(raw.liked),
    canEdit: Boolean(raw.canEdit),
    canDelete: Boolean(raw.canDelete),
  }
}

function normalizeApp(raw) {
  if (!raw || typeof raw !== "object") return null
  const id = raw.id ?? raw.appId ?? raw.pk ?? null
  if (id == null) return null
  const comments = Array.isArray(raw.comments)
    ? raw.comments.map(normalizeComment).filter(Boolean)
    : undefined

  const screenshotUrl = ensureString(raw.screenshotUrl || raw.screenshot_url)
  const screenshotUrls = normalizeScreenshotUrls(raw.screenshotUrls || raw.screenshot_urls)
  const coverScreenshotIndexRaw = raw.coverScreenshotIndex ?? raw.cover_screenshot_index ?? 0

  const resolvedScreenshotUrls = screenshotUrls.length
    ? screenshotUrls
    : screenshotUrl
      ? [screenshotUrl]
      : []
  const resolvedCoverIndex = normalizeCoverIndex(coverScreenshotIndexRaw, resolvedScreenshotUrls.length)

  return {
    id,
    name: ensureString(raw.name),
    category: ensureString(raw.category),
    description: ensureString(raw.description),
    url: ensureString(raw.url),
    manualUrl: ensureString(raw.manualUrl || raw.manual_url),
    contactName: ensureString(raw.contactName || raw.contact_name),
    contactKnoxid: ensureString(raw.contactKnoxid || raw.contact_knoxid),
    screenshotUrl,
    screenshotUrls: resolvedScreenshotUrls,
    coverScreenshotIndex: resolvedCoverIndex,
    viewCount: Number(raw.viewCount ?? raw.view_count ?? 0) || 0,
    likeCount: Number(raw.likeCount ?? raw.like_count ?? 0) || 0,
    commentCount: Number(raw.commentCount ?? raw.comment_count ?? comments?.length ?? 0) || 0,
    createdAt: ensureString(raw.createdAt || raw.created_at),
    updatedAt: ensureString(raw.updatedAt || raw.updated_at || raw.createdAt || raw.created_at),
    owner: normalizeUser(raw.owner),
    liked: Boolean(raw.liked),
    canEdit: Boolean(raw.canEdit),
    canDelete: Boolean(raw.canDelete),
    comments,
  }
}

export async function fetchApps() {
  const payload = await request("/api/v1/appstore/apps")
  const apps = Array.isArray(payload?.results)
    ? payload.results.map(normalizeApp).filter(Boolean)
    : []
  return {
    apps,
    total: typeof payload?.total === "number" ? payload.total : apps.length,
  }
}

export async function fetchApp(appId) {
  const payload = await request(`/api/v1/appstore/apps/${appId}`)
  const app = normalizeApp(payload?.app)
  if (!app) {
    throw new Error("Invalid app payload")
  }
  return { app }
}

export async function createApp(input) {
  const payload = await request("/api/v1/appstore/apps", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })
  const app = normalizeApp(payload?.app)
  if (!app) {
    throw new Error("Invalid app payload")
  }
  return app
}

export async function updateApp(appId, updates) {
  const payload = await request(`/api/v1/appstore/apps/${appId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  })
  const app = normalizeApp(payload?.app)
  if (!app) {
    throw new Error("Invalid app payload")
  }
  return app
}

export async function deleteApp(appId) {
  await request(`/api/v1/appstore/apps/${appId}`, { method: "DELETE" })
  return { appId }
}

export async function toggleLike(appId) {
  const payload = await request(`/api/v1/appstore/apps/${appId}/like`, {
    method: "POST",
  })
  return {
    appId,
    liked: Boolean(payload?.liked),
    likeCount: Number(payload?.likeCount ?? 0) || 0,
  }
}

export async function incrementView(appId) {
  const payload = await request(`/api/v1/appstore/apps/${appId}/view`, {
    method: "POST",
  })
  return {
    appId,
    viewCount: Number(payload?.viewCount ?? 0) || 0,
  }
}

export async function fetchComments(appId) {
  const payload = await request(`/api/v1/appstore/apps/${appId}/comments`)
  const comments = Array.isArray(payload?.comments)
    ? payload.comments.map(normalizeComment).filter(Boolean)
    : []
  return {
    comments,
    total: typeof payload?.total === "number" ? payload.total : comments.length,
  }
}

export async function createComment(appId, content, parentCommentId) {
  const body = { content }
  if (parentCommentId != null) {
    body.parentCommentId = parentCommentId
  }
  const payload = await request(`/api/v1/appstore/apps/${appId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const comment = normalizeComment(payload?.comment)
  if (!comment) {
    throw new Error("Invalid comment payload")
  }
  return comment
}

export async function updateComment(appId, commentId, content) {
  const payload = await request(`/api/v1/appstore/apps/${appId}/comments/${commentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  })
  const comment = normalizeComment(payload?.comment)
  if (!comment) {
    throw new Error("Invalid comment payload")
  }
  return comment
}

export async function deleteComment(appId, commentId) {
  await request(`/api/v1/appstore/apps/${appId}/comments/${commentId}`, {
    method: "DELETE",
  })
  return { appId, commentId }
}

export async function toggleCommentLike(appId, commentId) {
  const payload = await request(`/api/v1/appstore/apps/${appId}/comments/${commentId}/like`, {
    method: "POST",
  })
  return {
    appId,
    commentId,
    liked: Boolean(payload?.liked),
    likeCount: Number(payload?.likeCount ?? 0) || 0,
  }
}
