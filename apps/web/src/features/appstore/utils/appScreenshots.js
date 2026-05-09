export function normalizeScreenshotUrls(values) {
  if (!Array.isArray(values)) return []
  return values
    .filter((value) => typeof value === "string" && value.trim())
    .map((value) => value.trim())
}

export function normalizeCoverIndex(value, total) {
  if (!total) return 0
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 0
  const integer = Math.floor(numeric)
  if (integer < 0 || integer >= total) return 0
  return integer
}

export function resolveAppScreenshots(app) {
  const screenshotUrls = normalizeScreenshotUrls(app?.screenshotUrls)
  const fallbackUrl = typeof app?.screenshotUrl === "string" ? app.screenshotUrl.trim() : ""
  const urls = screenshotUrls.length ? screenshotUrls : fallbackUrl ? [fallbackUrl] : []
  return {
    urls,
    coverIndex: normalizeCoverIndex(app?.coverScreenshotIndex, urls.length),
  }
}

export function getCoverScreenshotUrl(app) {
  const { urls, coverIndex } = resolveAppScreenshots(app)
  return urls[coverIndex] || ""
}
