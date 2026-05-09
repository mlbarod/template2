const FALLBACK_CATEGORY = "기타"
const ALL_CATEGORY = "all"

function getCategory(app) {
  return app?.category || FALLBACK_CATEGORY
}

function normalizeSearchText(value) {
  return typeof value === "string" ? value.trim().toLowerCase() : ""
}

export function buildAppCategories(apps) {
  const unique = new Set([ALL_CATEGORY])
  apps.forEach((app) => {
    unique.add(getCategory(app))
  })
  return Array.from(unique)
}

export function buildFormCategoryOptions(apps) {
  const unique = new Set()
  apps.forEach((app) => {
    const value = typeof app.category === "string" ? app.category.trim() : ""
    if (value) unique.add(value)
  })
  return Array.from(unique)
}

export function buildCategoryCounts(apps) {
  return apps.reduce((acc, app) => {
    const key = getCategory(app)
    acc[key] = (acc[key] ?? 0) + 1
    return acc
  }, {})
}

export function filterApps(apps, { category, query }) {
  const normalizedQuery = normalizeSearchText(query)

  return apps.filter((app) => {
    const categoryValueRaw = getCategory(app)
    const matchesCategory = category === ALL_CATEGORY || categoryValueRaw === category
    const name = normalizeSearchText(app.name)
    const description = normalizeSearchText(app.description)
    const categoryValue = normalizeSearchText(categoryValueRaw)
    const matchesQuery =
      !normalizedQuery ||
      name.includes(normalizedQuery) ||
      description.includes(normalizedQuery) ||
      categoryValue.includes(normalizedQuery)

    return matchesCategory && matchesQuery
  })
}
