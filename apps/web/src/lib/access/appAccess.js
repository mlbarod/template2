export function getAppAccess(user, scopeKey) {
  if (!scopeKey || !user?.app_access || typeof user.app_access !== "object") return null
  const access = user.app_access[scopeKey]
  return access && typeof access === "object" ? access : null
}

export function hasAppAccess(user, scopeKey) {
  return Boolean(getAppAccess(user, scopeKey)?.allowed)
}

export function hasEveryAppAccess(user, scopeKeys) {
  const keys = Array.isArray(scopeKeys) ? scopeKeys.filter(Boolean) : []
  return keys.every((scopeKey) => hasAppAccess(user, scopeKey))
}

export function hasAnyAppAccess(user, scopeKeys) {
  const keys = Array.isArray(scopeKeys) ? scopeKeys.filter(Boolean) : []
  return keys.some((scopeKey) => hasAppAccess(user, scopeKey))
}
