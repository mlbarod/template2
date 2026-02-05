import { useEffect, useMemo } from "react"

import { useAuth } from "@/lib/auth"
import { useAssistantRagIndexes } from "./useAssistantRagIndexes"
import { useAssistantRagIndexStore } from "../store/useAssistantRagIndexStore"

const DEFAULT_RAG_PUBLIC_GROUP = "rag-public"
const DEFAULT_RAG_INDEX = "rp-unclassified"

function normalizeString(value) {
  return typeof value === "string" ? value.trim() : ""
}

function normalizeList(values) {
  if (!Array.isArray(values)) return []
  const normalized = values
    .map((value) => normalizeString(value))
    .filter(Boolean)
  return Array.from(new Set(normalized))
}

function buildSortedOptions(values) {
  return normalizeList(values).sort((a, b) => a.localeCompare(b))
}

export function useAssistantRagIndex() {
  const { user } = useAuth()
  const ragIndexesQuery = useAssistantRagIndexes()
  const ragData = ragIndexesQuery.data || {}
  const currentUserSdwtProd =
    normalizeString(user?.user_sdwt_prod) || normalizeString(ragData.currentUserSdwtProd)

  const ragPublicGroup = normalizeString(ragData.ragPublicGroup) || DEFAULT_RAG_PUBLIC_GROUP
  const rawRagIndexes = normalizeList(ragData.ragIndexes)
  const permissionGroupOptions = buildSortedOptions([
    ...normalizeList(ragData.permissionGroups),
    ragPublicGroup,
    currentUserSdwtProd,
  ])
  const defaultRagIndex =
    normalizeString(ragData.defaultRagIndex) || rawRagIndexes[0] || DEFAULT_RAG_INDEX
  const ragIndexOptions = buildSortedOptions([...rawRagIndexes, defaultRagIndex])

  const defaultPermissionGroups = useMemo(() => {
    if (currentUserSdwtProd) {
      return normalizeList([currentUserSdwtProd])
    }
    return normalizeList([ragPublicGroup])
  }, [currentUserSdwtProd, ragPublicGroup])

  const defaultRagIndexNames = useMemo(() => {
    return normalizeList([defaultRagIndex])
  }, [defaultRagIndex])

  const permissionGroups = useAssistantRagIndexStore((state) => state.permissionGroups)
  const ragIndexNames = useAssistantRagIndexStore((state) => state.ragIndexNames)
  const permissionGroupsSource = useAssistantRagIndexStore((state) => state.permissionGroupsSource)
  const ragIndexNamesSource = useAssistantRagIndexStore((state) => state.ragIndexNamesSource)
  const setPermissionGroups = useAssistantRagIndexStore((state) => state.setPermissionGroups)
  const setRagIndexNames = useAssistantRagIndexStore((state) => state.setRagIndexNames)

  useEffect(() => {
    if (permissionGroupsSource === "user") return
    setPermissionGroups(defaultPermissionGroups, "default")
  }, [defaultPermissionGroups, permissionGroupsSource, setPermissionGroups])

  useEffect(() => {
    if (ragIndexNamesSource === "user") return
    setRagIndexNames(defaultRagIndexNames, "default")
  }, [defaultRagIndexNames, ragIndexNamesSource, setRagIndexNames])

  const normalizedPermissionGroups = normalizeList(permissionGroups)
  const filteredPermissionGroups = normalizedPermissionGroups.filter((value) =>
    permissionGroupOptions.includes(value),
  )

  useEffect(() => {
    if (!normalizedPermissionGroups.length) return
    if (filteredPermissionGroups.length === normalizedPermissionGroups.length) return
    setPermissionGroups(filteredPermissionGroups, "user")
  }, [filteredPermissionGroups, normalizedPermissionGroups, setPermissionGroups])

  const resolvedPermissionGroups = filteredPermissionGroups.length
    ? filteredPermissionGroups
    : defaultPermissionGroups
  const candidateRagIndexNames = ragIndexNames.length ? ragIndexNames : defaultRagIndexNames
  let resolvedRagIndexNames = normalizeList(candidateRagIndexNames).filter((value) =>
    ragIndexOptions.includes(value),
  )
  if (!resolvedRagIndexNames.length && ragIndexOptions.length) {
    resolvedRagIndexNames = [ragIndexOptions[0]]
  }

  return {
    permissionGroups: resolvedPermissionGroups,
    setPermissionGroups,
    ragIndexNames: resolvedRagIndexNames,
    setRagIndexNames,
    permissionGroupOptions,
    ragIndexOptions,
    defaultPermissionGroups,
    defaultRagIndexNames,
    isLoading: ragIndexesQuery.isLoading,
    isError: ragIndexesQuery.isError,
    errorMessage: ragIndexesQuery.isError ? ragIndexesQuery.error?.message || "" : "",
  }
}
