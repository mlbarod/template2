import { useLocation, useNavigate, useParams } from "react-router-dom"

import { useActiveLineOptional } from "./lineContext"
import { normalizeTeamId } from "./teamSelection"

function getLineIdFromParams(params) {
  if (!params || typeof params !== "object") return null
  const raw = params.lineId
  if (typeof raw === "string") return raw
  if (Array.isArray(raw)) return raw[0] ?? null
  return null
}

function buildLinePath({ pathname, nextLineId, currentLineId }) {
  if (!pathname || !nextLineId) return null

  const segments = pathname.split("/").filter(Boolean)
  if (!segments.length) return null

  const esopIndex = segments.indexOf("ESOP_Dashboard")
  if (esopIndex === -1) return null

  const currentIndex = currentLineId ? segments.lastIndexOf(currentLineId) : -1

  if (currentIndex !== -1) {
    const next = [...segments]
    next[currentIndex] = nextLineId
    return `/${next.join("/")}`
  }

  if (segments[esopIndex + 1] === "tip-status") {
    return `/ESOP_Dashboard/tip-status/${nextLineId}`
  }

  return `/ESOP_Dashboard/status/${nextLineId}`
}

export function useLineSwitcher() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const params = useParams()
  const lineContext = useActiveLineOptional()

  const paramLineId = normalizeTeamId(getLineIdFromParams(params))
  const activeLineId = normalizeTeamId(lineContext?.lineId) ?? paramLineId

  const handleSelect = (nextId) => {
    const normalizedNextId = normalizeTeamId(nextId)
    if (!normalizedNextId || normalizedNextId === activeLineId) return

    if (lineContext?.setLineId) {
      lineContext.setLineId(normalizedNextId)
    }

    const target = buildLinePath({
      pathname,
      nextLineId: normalizedNextId,
      currentLineId: paramLineId,
    })
    if (target) {
      navigate(target)
    }
  }

  return { activeLineId, onSelect: handleSelect }
}
