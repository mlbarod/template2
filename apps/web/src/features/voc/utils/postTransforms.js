import { DEFAULT_APP_CATEGORY, STATUS_OPTIONS } from "./constants"
import { sanitizeContentHtml } from "./index"

export const EMPTY_POSTS = []

const EMPTY_STATUS_COUNTS = STATUS_OPTIONS.reduce(
  (acc, option) => ({ ...acc, [option.value]: 0 }),
  {},
)

export function sanitizeVocPost(post) {
  if (!post || post.id == null) return null
  const appValue = typeof post.app === "string" ? post.app.trim() : ""
  return {
    ...post,
    app: appValue || DEFAULT_APP_CATEGORY,
    content: sanitizeContentHtml(post.content),
    replies: Array.isArray(post.replies)
      ? post.replies
          .map((reply) => {
            if (!reply || reply.id == null) return null
            return {
              ...reply,
              content: typeof reply.content === "string" ? reply.content.trim() : "",
            }
          })
          .filter(Boolean)
      : [],
  }
}

export function normalizeVocPosts(rawPosts) {
  if (!Array.isArray(rawPosts)) return []
  return rawPosts.map(sanitizeVocPost).filter(Boolean)
}

export function buildVocStatusCounts(posts, providedCounts) {
  if (providedCounts && typeof providedCounts === "object") {
    return { ...EMPTY_STATUS_COUNTS, ...providedCounts }
  }

  return posts.reduce((acc, post) => {
    if (post?.status && typeof acc[post.status] === "number") {
      acc[post.status] += 1
    }
    return acc
  }, { ...EMPTY_STATUS_COUNTS })
}

export function getVocPostAuthorKey(post) {
  return post?.author?.id || post?.author?.email || post?.author?.name
}
