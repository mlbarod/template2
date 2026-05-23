// 파일 경로: src/features/line-dashboard/components/LineSettingsPage.jsx
import * as React from "react"

import { useAuth } from "@/lib/auth"
import { LineSettingsHeader } from "./LineSettingsHeader"
import { AlarmChannelSettingsCard } from "./cards/AlarmChannelSettingsCard"
import { EarlyInformSettingsCard } from "./cards/EarlyInformSettingsCard"
import { NeedToSendCommentRuleCard } from "./cards/NeedToSendCommentRuleCard"
import { MyRecipientTargetsCard } from "./cards/MyRecipientTargetsCard"
import { NotificationTargetCard } from "./cards/NotificationTargetCard"
import { RecipientSettingsCards } from "./sections/RecipientSettingsCards"
import {
  fetchAccountUserPool,
  fetchMyNotificationRecipientTargets,
  fetchNotificationRecipientPermissions,
} from "../api"
import { useLineSettings } from "../hooks/useLineSettings"
import {
  DEFAULT_CHANNEL_ENABLED,
  DEFAULT_NEED_TO_SEND_RULE,
  DUPLICATE_MESSAGE,
  DUPLICATE_TARGET_MAPPING_MESSAGE,
  DUPLICATE_TARGET_MESSAGE,
  MAX_FIELD_LENGTH,
  MAX_JIRA_KEY_LENGTH,
  MAX_NEED_TO_SEND_KEYWORD_LENGTH,
  MAX_TARGET_FIELD_LENGTH,
  RECIPIENT_CHANNEL_CONFIG,
  RECIPIENT_CHANNELS,
} from "../utils/lineSettingsConfig"
import {
  showAlarmChannelApplyToast,
  showCreateToast,
  showDeleteToast,
  showJiraKeyToast,
  showNeedToSendRuleApplyToast,
  showNeedToSendRuleToast,
  showRecipientCandidatesToast,
  showRecipientsSaveToast,
  showRequestErrorToast,
  showTargetCreateToast,
  showTargetMappingCreateToast,
  showUpdateToast,
} from "../utils/lineSettingsToasts"
import { validateStepDraft } from "../utils/lineSettingsValidation"
import {
  getRecipientExternalKnoxId,
  getRecipientKey,
  getRecipientPickerUsers,
  getRecipientUserId,
  isDuplicateMessage,
  mergeRecipientUsers,
  sameUserSdwtProd,
} from "../utils/lineSettings"

function normalizeMappingOptionValue(value) {
  return typeof value === "string" ? value.trim() : String(value ?? "").trim()
}

function findMappingDefaultOption(values, preferredValue) {
  const options = Array.isArray(values) ? values : []
  if (options.length === 0) return ""
  const normalizedPreferred = String(preferredValue || "").trim().toLowerCase()
  if (normalizedPreferred) {
    const matched = options.find((value) => (
      typeof value === "string" && value.trim().toLowerCase() === normalizedPreferred
    ))
    if (matched) return matched
  }
  return options[0] || ""
}

function buildMappingOptionsFromValues(values) {
  const normalizedValues = Array.isArray(values)
    ? values.map(normalizeMappingOptionValue).filter(Boolean)
    : []
  const uniqueValues = Array.from(new Set(normalizedValues))
  return { userSdwtProds: uniqueValues, sdwtProds: uniqueValues }
}

function buildMappingLineOptions({ lineRows, currentLineId, currentValues }) {
  const currentLine = normalizeMappingOptionValue(currentLineId)
  const normalizedCurrentLineId = normalizeMappingOptionValue(currentLineId).toLowerCase()
  const currentOption = currentLine
    ? {
        lineId: currentLine,
        values: buildMappingOptionsFromValues(currentValues).userSdwtProds,
      }
    : null
  const otherOptions = (Array.isArray(lineRows) ? lineRows : [])
    .map((row) => {
      const rowLineId = normalizeMappingOptionValue(row?.lineId)
      if (!rowLineId || rowLineId.toLowerCase() === normalizedCurrentLineId) return null
      const values = buildMappingOptionsFromValues(row?.userSdwtProds).userSdwtProds
      return values.length > 0 ? { lineId: rowLineId, values } : null
    })
    .filter(Boolean)
    .sort((a, b) => a.lineId.localeCompare(b.lineId))

  return currentOption ? [currentOption, ...otherOptions] : otherOptions
}

function getMappingLineOptionValues(lineOptions, selectedLineId) {
  const normalizedSelectedLineId = normalizeMappingOptionValue(selectedLineId)
  const option = (Array.isArray(lineOptions) ? lineOptions : []).find((row) => (
    normalizeMappingOptionValue(row?.lineId).toLowerCase() === normalizedSelectedLineId.toLowerCase()
  ))
  return Array.isArray(option?.values) ? option.values : []
}

function buildMappingValueLineLabels(lineRows, currentLineId) {
  const normalizedCurrentLineId = normalizeMappingOptionValue(currentLineId).toLowerCase()
  const labels = {}

  if (!Array.isArray(lineRows)) return {}

  lineRows.forEach((row) => {
    const rowLineId = normalizeMappingOptionValue(row?.lineId)
    const values = Array.isArray(row?.userSdwtProds) ? row.userSdwtProds : []
    values.forEach((value) => {
      const normalizedValue = normalizeMappingOptionValue(value)
      if (!rowLineId || !normalizedValue) return
      const key = normalizedValue.toLowerCase()
      if (rowLineId.toLowerCase() !== normalizedCurrentLineId) {
        labels[key] = rowLineId
      }
    })
  })

  return labels
}

function buildTargetMappingKey({ userSdwtProd, sdwtProd }) {
  return `${String(userSdwtProd || "").trim().toLowerCase()}::${String(sdwtProd || "").trim().toLowerCase()}`
}

export function LineSettingsPage({ lineId = "", mode = "notification" }) {
  const isRecipientSettings = mode === "recipients"
  const isNotificationSettings = !isRecipientSettings
  const { user } = useAuth()
  const [selectedUserSdwtProd, setSelectedUserSdwtProd] = React.useState("")
  const [isGlobalOperator, setIsGlobalOperator] = React.useState(false)
  const [hasLoadedPermissionContext, setHasLoadedPermissionContext] = React.useState(false)
  const {
    entries,
    notificationTargets,
    userSdwtValues,
    mappingOptions,
    mappingOptionLines,
    jiraKey,
    channelEnabled,
    needToSendRule,
    messengerForceNewChatroom,
    mailRecipients,
    mailRecipientsTargetUserSdwtProd,
    messengerRecipients,
    messengerRecipientsTargetUserSdwtProd,
    jiraKeyError,
    mailRecipientsError,
    messengerRecipientsError,
    error,
    isLoading,
    isJiraKeyLoading,
    isMailRecipientsLoading,
    isMessengerRecipientsLoading,
    hasLoadedOnce,
    lastUpdatedLabel,
    refresh,
    createEntry,
    updateEntry,
    deleteEntry,
    updateJiraKey,
    updateNeedToSendRule,
    updateMessengerForceNewChatroom,
    createTarget,
    createTargetMapping,
    deleteTargetMapping,
    updateMailRecipients,
    updateMessengerRecipients,
  } = useLineSettings({
    lineId,
    userSdwtProd: selectedUserSdwtProd,
    loadRecipients: isRecipientSettings && isGlobalOperator,
  })

  const [formValues, setFormValues] = React.useState({ mainStep: "", customEndStep: "" })
  const [formError, setFormError] = React.useState(null)
  const [isCreating, setIsCreating] = React.useState(false)

  const [editingId, setEditingId] = React.useState(null)
  const [editDraft, setEditDraft] = React.useState({ mainStep: "", customEndStep: "" })
  const [rowErrors, setRowErrors] = React.useState({})
  const [savingMap, setSavingMap] = React.useState({})
  const [newTargetDraft, setNewTargetDraft] = React.useState("")
  const [targetFormError, setTargetFormError] = React.useState(null)
  const [isCreatingTarget, setIsCreatingTarget] = React.useState(false)
  const [mappingDraft, setMappingDraft] = React.useState({
    userSdwtProd: "",
    userSdwtProds: [],
    sdwtProd: "",
  })
  const [mappingFormError, setMappingFormError] = React.useState(null)
  const [mappingUserLineId, setMappingUserLineId] = React.useState("")
  const [mappingSdwtLineId, setMappingSdwtLineId] = React.useState("")
  const [isCreatingMapping, setIsCreatingMapping] = React.useState(false)
  const [deletingMappingKey, setDeletingMappingKey] = React.useState("")
  const [jiraKeyDraft, setJiraKeyDraft] = React.useState("")
  const [channelEnabledDraft, setChannelEnabledDraft] = React.useState(DEFAULT_CHANNEL_ENABLED)
  const [needToSendRuleDraft, setNeedToSendRuleDraft] = React.useState(DEFAULT_NEED_TO_SEND_RULE)
  const [jiraKeyFormError, setJiraKeyFormError] = React.useState(null)
  const [isSavingJiraKey, setIsSavingJiraKey] = React.useState(false)
  const [needToSendRuleFormError, setNeedToSendRuleFormError] = React.useState(null)
  const [isSavingNeedToSendRule, setIsSavingNeedToSendRule] = React.useState(false)
  const [isSavingMessengerForceNewChatroom, setIsSavingMessengerForceNewChatroom] = React.useState(false)
  const [recipientDrafts, setRecipientDrafts] = React.useState({ mail: [], messenger: [] })
  const [recipientDraftTargets, setRecipientDraftTargets] = React.useState({ mail: "", messenger: "" })
  const [recipientSearches, setRecipientSearches] = React.useState({ mail: "", messenger: "" })
  const [recipientPickerOpen, setRecipientPickerOpen] = React.useState({ mail: false, messenger: false })
  const [recipientPickerTabs, setRecipientPickerTabs] = React.useState({ mail: "group", messenger: "group" })
  const [recipientPickerResults, setRecipientPickerResults] = React.useState({
    mail: { group: [], search: [] },
    messenger: { group: [], search: [] },
  })
  const [recipientPickerSelectedIds, setRecipientPickerSelectedIds] = React.useState({ mail: [], messenger: [] })
  const [recipientSourceDepartments, setRecipientSourceDepartments] = React.useState({ mail: "", messenger: "" })
  const [recipientSourceSdwt, setRecipientSourceSdwt] = React.useState({ mail: "", messenger: "" })
  const [recipientSourceSdwtOptions, setRecipientSourceSdwtOptions] = React.useState({ mail: [], messenger: [] })
  const [accountDepartmentValues, setAccountDepartmentValues] = React.useState([])
  const [accountUserSdwtValues, setAccountUserSdwtValues] = React.useState([])
  const [myRecipientTargets, setMyRecipientTargets] = React.useState([])
  const [myRecipientTargetsError, setMyRecipientTargetsError] = React.useState(null)
  const [recipientActionErrors, setRecipientActionErrors] = React.useState({ mail: null, messenger: null })
  const [isMyRecipientTargetsLoading, setIsMyRecipientTargetsLoading] = React.useState(false)
  const [isSearchingRecipients, setIsSearchingRecipients] = React.useState({ mail: false, messenger: false })
  const [isLoadingSourceGroups, setIsLoadingSourceGroups] = React.useState({ mail: false, messenger: false })
  const [isLoadingSourceUsers, setIsLoadingSourceUsers] = React.useState({ mail: false, messenger: false })
  const [isSavingRecipients, setIsSavingRecipients] = React.useState({ mail: false, messenger: false })
  const recipientContextRef = React.useRef({ lineId, selectedUserSdwtProd })
  const sourceGroupRequestRef = React.useRef({ mail: 0, messenger: 0 })
  const sourceLoadRequestRef = React.useRef({ mail: 0, messenger: 0 })
  const didResetMappingDraftRef = React.useRef(false)
  recipientContextRef.current = { lineId, selectedUserSdwtProd }

  const isRefreshing = isLoading && hasLoadedOnce
  const title = isRecipientSettings ? "E-SOP 수신인 설정" : "E-SOP 알림 설정"
  const settingsGridClassName = isRecipientSettings
    ? "grid h-full min-h-0 min-w-0 grid-cols-1 grid-rows-3 gap-3 xl:grid-cols-3 xl:grid-rows-1"
    : "grid h-full min-h-0 min-w-0 grid-cols-1 gap-3"
  const settingsBodyClassName = isRecipientSettings
    ? "flex min-h-0 flex-1 overflow-hidden pr-1"
    : "flex flex-1 min-h-0 min-w-0 flex-col"
  const selectedNotificationTarget = notificationTargets.find(
    (target) => target.targetUserSdwtProd === selectedUserSdwtProd,
  )
  const canManageRecipients = Boolean(selectedUserSdwtProd && isGlobalOperator)
  const canManageChannelSettings = Boolean(lineId && selectedUserSdwtProd && user?.is_superuser)
  const canCreateTarget = Boolean(lineId && isGlobalOperator)
  const canManageMappings = Boolean(selectedNotificationTarget && isGlobalOperator)
  const mappingUserLineOptions = React.useMemo(
    () => buildMappingLineOptions({
      lineRows: mappingOptionLines,
      currentLineId: lineId,
      currentValues: mappingOptions?.userSdwtProds,
    }),
    [lineId, mappingOptionLines, mappingOptions?.userSdwtProds],
  )
  const mappingSdwtLineOptions = React.useMemo(
    () => buildMappingLineOptions({
      lineRows: mappingOptionLines,
      currentLineId: lineId,
      currentValues: mappingOptions?.sdwtProds,
    }),
    [lineId, mappingOptionLines, mappingOptions?.sdwtProds],
  )
  const effectiveMappingOptions = React.useMemo(
    () => ({
      userSdwtProds: getMappingLineOptionValues(mappingUserLineOptions, mappingUserLineId),
      sdwtProds: getMappingLineOptionValues(mappingSdwtLineOptions, mappingSdwtLineId),
    }),
    [mappingSdwtLineId, mappingSdwtLineOptions, mappingUserLineId, mappingUserLineOptions],
  )
  const mappingValueLineLabels = React.useMemo(
    () => buildMappingValueLineLabels(mappingOptionLines, lineId),
    [lineId, mappingOptionLines],
  )
  const isRecipientDraftCurrent = React.useMemo(
    () => ({
      mail: sameUserSdwtProd(recipientDraftTargets.mail, selectedUserSdwtProd),
      messenger: sameUserSdwtProd(recipientDraftTargets.messenger, selectedUserSdwtProd),
    }),
    [recipientDraftTargets.mail, recipientDraftTargets.messenger, selectedUserSdwtProd],
  )
  const currentRecipientDrafts = React.useMemo(
    () => ({
      mail: isRecipientDraftCurrent.mail ? recipientDrafts.mail : [],
      messenger: isRecipientDraftCurrent.messenger ? recipientDrafts.messenger : [],
    }),
    [isRecipientDraftCurrent.mail, isRecipientDraftCurrent.messenger, recipientDrafts.mail, recipientDrafts.messenger],
  )

  const isCurrentRecipientContext = React.useCallback((requestLineId, requestUserSdwtProd) => {
    const context = recipientContextRef.current
    return (
      context.lineId === requestLineId &&
      sameUserSdwtProd(context.selectedUserSdwtProd, requestUserSdwtProd)
    )
  }, [])

  const loadMyRecipientTargets = React.useCallback(async () => {
    const requestLineId = lineId
    const requestUserId = user?.id
    if (!isRecipientSettings || !requestLineId || !requestUserId) {
      setMyRecipientTargets([])
      setMyRecipientTargetsError(null)
      setIsMyRecipientTargetsLoading(false)
      return { ok: true }
    }

    setIsMyRecipientTargetsLoading(true)
    setMyRecipientTargetsError(null)
    try {
      const { targets } = await fetchMyNotificationRecipientTargets({ lineId: requestLineId })
      if (recipientContextRef.current.lineId !== requestLineId) {
        return { ok: false, stale: true }
      }
      setMyRecipientTargets(targets || [])
      return { ok: true }
    } catch (requestError) {
      if (recipientContextRef.current.lineId !== requestLineId) {
        return { ok: false, stale: true }
      }
      const message =
        requestError instanceof Error ? requestError.message : "Failed to load my recipient targets"
      setMyRecipientTargets([])
      setMyRecipientTargetsError(message)
      return { ok: false }
    } finally {
      if (recipientContextRef.current.lineId === requestLineId) {
        setIsMyRecipientTargetsLoading(false)
      }
    }
  }, [isRecipientSettings, lineId, user?.id])

  const handleRefresh = React.useCallback(() => {
    if (!lineId) return
    refresh()
    void loadMyRecipientTargets()
  }, [lineId, loadMyRecipientTargets, refresh])

  const handleFormChange = React.useCallback((key, value) => {
    setFormValues((prev) => ({ ...prev, [key]: value }))
  }, [])

  const clearRecipientGroupResults = React.useCallback((channel) => {
    const previousGroupIds = new Set(
      (recipientPickerResults[channel]?.group || []).map(getRecipientKey).filter(Boolean),
    )
    setRecipientPickerResults((prev) => ({
      ...prev,
      [channel]: { ...(prev[channel] || { group: [], search: [] }), group: [] },
    }))
    setRecipientPickerSelectedIds((prev) => ({
      ...prev,
      [channel]: (prev[channel] || []).filter((recipientKey) => !previousGroupIds.has(recipientKey)),
    }))
  }, [recipientPickerResults])

  const handleRecipientSourceDepartmentChange = React.useCallback(
    async (channel, value) => {
      const config = RECIPIENT_CHANNEL_CONFIG[channel]
      const sourceDepartment = String(value || "").trim()
      sourceGroupRequestRef.current[channel] += 1
      sourceLoadRequestRef.current[channel] += 1
      const requestId = sourceGroupRequestRef.current[channel]
      const requestLineId = lineId
      const requestTarget = selectedUserSdwtProd

      setRecipientSourceDepartments((prev) => ({ ...prev, [channel]: sourceDepartment }))
      setRecipientSourceSdwt((prev) => ({ ...prev, [channel]: "" }))
      setRecipientSourceSdwtOptions((prev) => ({ ...prev, [channel]: [] }))
      setIsLoadingSourceUsers((prev) => ({ ...prev, [channel]: false }))
      clearRecipientGroupResults(channel)

      if (!sourceDepartment) {
        setIsLoadingSourceGroups((prev) => ({ ...prev, [channel]: false }))
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
        return
      }
      if (!canManageRecipients) {
        setIsLoadingSourceGroups((prev) => ({ ...prev, [channel]: false }))
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
        return
      }

      setIsLoadingSourceGroups((prev) => ({ ...prev, [channel]: true }))
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
      const isCurrentLoad = () =>
        sourceGroupRequestRef.current[channel] === requestId &&
        isCurrentRecipientContext(requestLineId, requestTarget)
      try {
        const { userSdwtProds } = await fetchAccountUserPool({
          department: sourceDepartment,
          contactField: config.contactField,
          limit: 1,
          includeExternalSnapshots: true,
        })
        if (!isCurrentLoad()) return
        setRecipientSourceSdwtOptions((prev) => ({ ...prev, [channel]: userSdwtProds || [] }))
        if (!userSdwtProds?.length) {
          setRecipientActionErrors((prev) => ({ ...prev, [channel]: "Department에 소속이 없습니다." }))
        }
      } catch (requestError) {
        if (!isCurrentLoad()) return
        const message =
          requestError instanceof Error ? requestError.message : "Failed to load departments"
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: message }))
        showRequestErrorToast(message)
      } finally {
        if (isCurrentLoad()) {
          setIsLoadingSourceGroups((prev) => ({ ...prev, [channel]: false }))
        }
      }
    },
    [
      canManageRecipients,
      clearRecipientGroupResults,
      isCurrentRecipientContext,
      lineId,
      selectedUserSdwtProd,
    ],
  )

  const handleRecipientSourceSdwtChange = React.useCallback((channel, value) => {
    sourceLoadRequestRef.current[channel] += 1
    setRecipientSourceSdwt((prev) => ({ ...prev, [channel]: value }))
    setIsLoadingSourceUsers((prev) => ({ ...prev, [channel]: false }))
    clearRecipientGroupResults(channel)
  }, [clearRecipientGroupResults])

  const handleRecipientSearchChange = React.useCallback((channel, value) => {
    setRecipientSearches((prev) => ({ ...prev, [channel]: value }))
  }, [])

  const handleRecipientPickerOpenChange = React.useCallback((channel, open) => {
    setRecipientPickerOpen((prev) => ({ ...prev, [channel]: open }))
  }, [])

  const handleRecipientPickerTabChange = React.useCallback((channel, value) => {
    setRecipientPickerTabs((prev) => ({ ...prev, [channel]: value }))
  }, [])

  const resolveDefaultRecipientDepartment = React.useCallback(() => {
    const userDepartment = typeof user?.department === "string" ? user.department.trim() : ""
    if (!userDepartment) return ""
    const normalizedUserDepartment = userDepartment.toLowerCase()
    return (
      accountDepartmentValues.find((department) => (
        typeof department === "string" && department.trim().toLowerCase() === normalizedUserDepartment
      )) || userDepartment
    )
  }, [accountDepartmentValues, user?.department])

  const handleOpenRecipientPicker = React.useCallback(
    (channel) => {
      const config = RECIPIENT_CHANNEL_CONFIG[channel]
      if (!selectedUserSdwtProd) {
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: "알림 Target을 선택하세요." }))
        return
      }
      setRecipientActionErrors((prev) => ({
        ...prev,
        [channel]: canManageRecipients ? null : config.permissionErrorText,
      }))
      setRecipientPickerOpen((prev) => ({ ...prev, [channel]: true }))
      if (canManageRecipients && !recipientSourceDepartments[channel]) {
        const defaultDepartment = resolveDefaultRecipientDepartment()
        if (defaultDepartment) {
          void handleRecipientSourceDepartmentChange(channel, defaultDepartment)
        }
      }
    },
    [
      canManageRecipients,
      handleRecipientSourceDepartmentChange,
      recipientSourceDepartments,
      resolveDefaultRecipientDepartment,
      selectedUserSdwtProd,
    ],
  )

  const handleRecipientPickerUserToggle = React.useCallback((channel, recipientKey, checked) => {
    setRecipientPickerSelectedIds((prev) => {
      const current = new Set(prev[channel] || [])
      if (checked) {
        current.add(recipientKey)
      } else {
        current.delete(recipientKey)
      }
      return { ...prev, [channel]: Array.from(current) }
    })
  }, [])

  const handleRecipientPickerAllToggle = React.useCallback((channel, users, checked) => {
    setRecipientPickerSelectedIds((prev) => {
      const current = new Set(prev[channel] || [])
      for (const user of users || []) {
        const recipientKey = getRecipientKey(user)
        if (!recipientKey) continue
        if (checked) {
          current.add(recipientKey)
        } else {
          current.delete(recipientKey)
        }
      }
      return { ...prev, [channel]: Array.from(current) }
    })
  }, [])

  React.useEffect(() => {
    if (!lineId || userSdwtValues.length === 0) {
      setSelectedUserSdwtProd("")
      return
    }
    if (!userSdwtValues.includes(selectedUserSdwtProd)) {
      setSelectedUserSdwtProd(userSdwtValues[0])
    }
  }, [lineId, selectedUserSdwtProd, userSdwtValues])

  React.useEffect(() => {
    setNewTargetDraft("")
    setTargetFormError(null)
  }, [lineId])

  React.useLayoutEffect(() => {
    if (!lineId || !selectedUserSdwtProd) {
      setMappingUserLineId("")
      setMappingSdwtLineId("")
      setMappingDraft({ userSdwtProd: "", userSdwtProds: [], sdwtProd: "" })
      return
    }

    const defaultUserOption = mappingUserLineOptions.find((option) => option.lineId === lineId) || mappingUserLineOptions[0]
    const defaultSdwtOption = mappingSdwtLineOptions.find((option) => option.lineId === lineId) || mappingSdwtLineOptions[0]
    const defaultUserValue = defaultUserOption?.values?.[0] || ""
    const defaultSdwtValue = defaultSdwtOption?.values?.[0] || ""

    setMappingUserLineId(defaultUserOption?.lineId || lineId || "")
    setMappingSdwtLineId(defaultSdwtOption?.lineId || lineId || "")
    setMappingDraft({
      userSdwtProd: defaultUserValue,
      userSdwtProds: defaultUserValue ? [defaultUserValue] : [],
      sdwtProd: defaultSdwtValue,
    })
    didResetMappingDraftRef.current = true
    setMappingFormError(null)
  }, [lineId, mappingSdwtLineOptions, mappingUserLineOptions, selectedUserSdwtProd])

  React.useEffect(() => {
    if (!lineId) {
      if (mappingUserLineId) setMappingUserLineId("")
      if (mappingSdwtLineId) setMappingSdwtLineId("")
      return
    }

    if (mappingUserLineOptions.length > 0 && !mappingUserLineOptions.some((option) => option.lineId === mappingUserLineId)) {
      const defaultUserOption = mappingUserLineOptions.find((option) => option.lineId === lineId) || mappingUserLineOptions[0]
      setMappingUserLineId(defaultUserOption.lineId)
    }

    if (mappingSdwtLineOptions.length > 0 && !mappingSdwtLineOptions.some((option) => option.lineId === mappingSdwtLineId)) {
      const defaultSdwtOption = mappingSdwtLineOptions.find((option) => option.lineId === lineId) || mappingSdwtLineOptions[0]
      setMappingSdwtLineId(defaultSdwtOption.lineId)
    }
  }, [lineId, mappingSdwtLineId, mappingSdwtLineOptions, mappingUserLineId, mappingUserLineOptions])

  React.useEffect(() => {
    void loadMyRecipientTargets()
  }, [loadMyRecipientTargets])

  React.useEffect(() => {
    if (didResetMappingDraftRef.current) {
      didResetMappingDraftRef.current = false
      setMappingFormError(null)
      setIsCreatingMapping(false)
      setDeletingMappingKey("")
      return
    }

    setMappingDraft((prev) => {
      const previousUserSdwtProds = Array.isArray(prev.userSdwtProds) ? prev.userSdwtProds : []
      const nextUserSdwtProds = previousUserSdwtProds.filter((value) => (
        effectiveMappingOptions.userSdwtProds.includes(value)
      ))
      const nextUserSdwtProd = nextUserSdwtProds[0] || (
        effectiveMappingOptions.userSdwtProds.includes(prev.userSdwtProd)
          ? prev.userSdwtProd
          : findMappingDefaultOption(effectiveMappingOptions.userSdwtProds, selectedUserSdwtProd)
      )
      const resolvedUserSdwtProds = nextUserSdwtProds.length > 0
        ? nextUserSdwtProds
        : nextUserSdwtProd
          ? [nextUserSdwtProd]
          : []
      const nextSdwtProd = effectiveMappingOptions.sdwtProds.includes(prev.sdwtProd)
        ? prev.sdwtProd
        : findMappingDefaultOption(effectiveMappingOptions.sdwtProds, selectedUserSdwtProd)
      if (
        prev.userSdwtProd === nextUserSdwtProd &&
        prev.sdwtProd === nextSdwtProd &&
        previousUserSdwtProds.length === resolvedUserSdwtProds.length &&
        previousUserSdwtProds.every((value, index) => value === resolvedUserSdwtProds[index])
      ) {
        return prev
      }
      return {
        userSdwtProd: nextUserSdwtProd,
        userSdwtProds: resolvedUserSdwtProds,
        sdwtProd: nextSdwtProd,
      }
    })
    setMappingFormError(null)
    setIsCreatingMapping(false)
    setDeletingMappingKey("")
  }, [effectiveMappingOptions, lineId, selectedUserSdwtProd])

  React.useEffect(() => {
    setJiraKeyDraft(jiraKey || "")
    setChannelEnabledDraft(channelEnabled || DEFAULT_CHANNEL_ENABLED)
    setNeedToSendRuleDraft(needToSendRule || DEFAULT_NEED_TO_SEND_RULE)
    setJiraKeyFormError(null)
    setNeedToSendRuleFormError(null)
    setIsSavingJiraKey(false)
    setIsSavingNeedToSendRule(false)
  }, [channelEnabled, jiraKey, lineId, needToSendRule, selectedUserSdwtProd])

  React.useEffect(() => {
    sourceGroupRequestRef.current.mail += 1
    sourceGroupRequestRef.current.messenger += 1
    sourceLoadRequestRef.current.mail += 1
    sourceLoadRequestRef.current.messenger += 1
    setRecipientDrafts({ mail: [], messenger: [] })
    setRecipientDraftTargets({ mail: selectedUserSdwtProd || "", messenger: selectedUserSdwtProd || "" })
    setRecipientActionErrors({ mail: null, messenger: null })
    setRecipientPickerOpen({ mail: false, messenger: false })
    setRecipientPickerResults({ mail: { group: [], search: [] }, messenger: { group: [], search: [] } })
    setRecipientPickerSelectedIds({ mail: [], messenger: [] })
    setRecipientSourceDepartments({ mail: "", messenger: "" })
    setRecipientSourceSdwt({ mail: "", messenger: "" })
    setRecipientSourceSdwtOptions({ mail: [], messenger: [] })
    setIsLoadingSourceGroups({ mail: false, messenger: false })
    setIsLoadingSourceUsers({ mail: false, messenger: false })
    setIsSavingRecipients({ mail: false, messenger: false })
  }, [lineId, selectedUserSdwtProd])

  React.useEffect(() => {
    if (!sameUserSdwtProd(mailRecipientsTargetUserSdwtProd, selectedUserSdwtProd)) {
      return
    }
    setRecipientDrafts((prev) => ({ ...prev, mail: mailRecipients || [] }))
    setRecipientDraftTargets((prev) => ({ ...prev, mail: selectedUserSdwtProd || "" }))
    setRecipientActionErrors((prev) => ({ ...prev, mail: null }))
    setRecipientPickerResults((prev) => ({ ...prev, mail: { group: [], search: [] } }))
    setRecipientPickerSelectedIds((prev) => ({ ...prev, mail: [] }))
  }, [mailRecipients, mailRecipientsTargetUserSdwtProd, selectedUserSdwtProd])

  React.useEffect(() => {
    if (!sameUserSdwtProd(messengerRecipientsTargetUserSdwtProd, selectedUserSdwtProd)) {
      return
    }
    setRecipientDrafts((prev) => ({ ...prev, messenger: messengerRecipients || [] }))
    setRecipientDraftTargets((prev) => ({ ...prev, messenger: selectedUserSdwtProd || "" }))
    setRecipientActionErrors((prev) => ({ ...prev, messenger: null }))
    setRecipientPickerResults((prev) => ({ ...prev, messenger: { group: [], search: [] } }))
    setRecipientPickerSelectedIds((prev) => ({ ...prev, messenger: [] }))
  }, [messengerRecipients, messengerRecipientsTargetUserSdwtProd, selectedUserSdwtProd])

  React.useEffect(() => {
    let isActive = true
    setIsGlobalOperator(false)
    setHasLoadedPermissionContext(false)

    async function loadRecipientOptions() {
      try {
        const [{ departments, userSdwtProds }, permissionContext] = await Promise.all([
          fetchAccountUserPool({ limit: 1, includeExternalSnapshots: true }),
          fetchNotificationRecipientPermissions(),
        ])
        if (isActive) {
          setAccountDepartmentValues(departments || [])
          setAccountUserSdwtValues(userSdwtProds || [])
          setIsGlobalOperator(Boolean(permissionContext?.isOperator))
          setHasLoadedPermissionContext(true)
        }
      } catch (requestError) {
        if (isActive) {
          const message =
            requestError instanceof Error ? requestError.message : "Failed to load user groups"
          setIsGlobalOperator(false)
          setHasLoadedPermissionContext(true)
          setAccountDepartmentValues([])
          setAccountUserSdwtValues([])
          setRecipientActionErrors({ mail: message, messenger: message })
        }
      }
    }

    loadRecipientOptions()
    return () => {
      isActive = false
    }
  }, [user?.id])

  const resetForm = React.useCallback(() => {
    setFormValues({ mainStep: "", customEndStep: "" })
    setFormError(null)
  }, [])

  const handleCreate = React.useCallback(
    async (event) => {
      event.preventDefault()
      if (!lineId) {
        setFormError("Select a line to add an override")
        return
      }

      const { normalizedMainStep, normalizedCustom, error: draftError } = validateStepDraft({
        mainStep: formValues.mainStep,
        customEndStep: formValues.customEndStep,
      })
      if (draftError) {
        setFormError(draftError)
        return
      }

      setIsCreating(true)
      setFormError(null)

      try {
        const entry = await createEntry({
          mainStep: normalizedMainStep,
          customEndStep: normalizedCustom.length > 0 ? normalizedCustom : null,
        })
        if (entry) {
          resetForm()
          showCreateToast()
        }
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to create entry"
        const friendlyMessage =
          requestError?.status === 409 || isDuplicateMessage(message)
            ? DUPLICATE_MESSAGE
            : message
        setFormError(friendlyMessage)
        showRequestErrorToast(friendlyMessage)
      } finally {
        setIsCreating(false)
      }
    },
    [createEntry, formValues.customEndStep, formValues.mainStep, lineId, resetForm],
  )

  const handleCreateTarget = React.useCallback(async () => {
    const normalized = newTargetDraft.trim()
    if (!lineId) {
      setTargetFormError("라인을 먼저 선택하세요.")
      return
    }
    if (!normalized) {
      setTargetFormError("추가할 알림 Target을 입력하세요.")
      return
    }
    if (normalized.length > MAX_TARGET_FIELD_LENGTH) {
      setTargetFormError("알림 Target은 64자 이하로 입력하세요.")
      return
    }
    if (!canCreateTarget) {
      setTargetFormError("알림 Target 추가 권한이 없습니다.")
      return
    }

    setIsCreatingTarget(true)
    setTargetFormError(null)
    try {
      const target = await createTarget({ targetUserSdwtProd: normalized })
      if (target?.targetUserSdwtProd) {
        setSelectedUserSdwtProd(target.targetUserSdwtProd)
        setNewTargetDraft("")
        showTargetCreateToast(target.targetUserSdwtProd)
      }
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to create target"
      const friendlyMessage =
        requestError?.status === 409 || isDuplicateMessage(message)
          ? DUPLICATE_TARGET_MESSAGE
          : message
      setTargetFormError(friendlyMessage)
      showRequestErrorToast(friendlyMessage)
    } finally {
      setIsCreatingTarget(false)
    }
  }, [canCreateTarget, createTarget, lineId, newTargetDraft])

  const handleMappingDraftChange = React.useCallback((key, value) => {
    setMappingDraft((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleMappingUserLineChange = React.useCallback((value) => {
    setMappingUserLineId(value)
    setMappingFormError(null)
  }, [])

  const handleMappingSdwtLineChange = React.useCallback((value) => {
    setMappingSdwtLineId(value)
    setMappingFormError(null)
  }, [])

  const handleSelectNotificationTarget = React.useCallback((value) => {
    setSelectedUserSdwtProd(value)
  }, [])

  const handleCreateTargetMapping = React.useCallback(async (event) => {
    event.preventDefault()
    const normalizedUserSdwtProds = (
      Array.isArray(mappingDraft.userSdwtProds) && mappingDraft.userSdwtProds.length > 0
        ? mappingDraft.userSdwtProds
        : [mappingDraft.userSdwtProd]
    )
      .map((value) => String(value || "").trim())
      .filter(Boolean)
    const normalizedSdwtProd = mappingDraft.sdwtProd.trim()
    if (!selectedUserSdwtProd) {
      setMappingFormError("알림 Target을 먼저 선택하세요.")
      return
    }
    if (normalizedUserSdwtProds.length === 0) {
      setMappingFormError("분임조원 값을 입력하세요.")
      return
    }
    if (!normalizedSdwtProd) {
      setMappingFormError("분임조설비 값을 입력하세요.")
      return
    }
    if (
      normalizedUserSdwtProds.some((value) => value.length > MAX_TARGET_FIELD_LENGTH) ||
      normalizedSdwtProd.length > MAX_TARGET_FIELD_LENGTH
    ) {
      setMappingFormError("지정 조합 값은 64자 이하로 입력하세요.")
      return
    }
    if (!canManageMappings) {
      setMappingFormError("지정 조합 추가 권한이 없습니다.")
      return
    }
    const duplicateUserSdwtProds = normalizedUserSdwtProds.filter((userSdwtProd) =>
      notificationTargets.some(
        (target) =>
          Array.isArray(target.mappings) &&
          target.mappings.some(
            (mapping) =>
              sameUserSdwtProd(mapping.userSdwtProd, userSdwtProd) &&
              sameUserSdwtProd(mapping.sdwtProd, normalizedSdwtProd),
          ),
      ),
    )
    if (duplicateUserSdwtProds.length > 0) {
      setMappingFormError(DUPLICATE_TARGET_MAPPING_MESSAGE)
      return
    }

    setIsCreatingMapping(true)
    setMappingFormError(null)
    try {
      for (const userSdwtProd of normalizedUserSdwtProds) {
        await createTargetMapping({
          targetUserSdwtProd: selectedUserSdwtProd,
          userSdwtProd,
          sdwtProd: normalizedSdwtProd,
        })
      }
      const toastUserLabel = normalizedUserSdwtProds.length > 1
        ? `${normalizedUserSdwtProds[0]} 외 ${normalizedUserSdwtProds.length - 1}개`
        : normalizedUserSdwtProds[0]
      showTargetMappingCreateToast(toastUserLabel, normalizedSdwtProd)
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to create target mapping"
      const friendlyMessage =
        requestError?.status === 409 || isDuplicateMessage(message)
          ? DUPLICATE_TARGET_MAPPING_MESSAGE
          : message
      setMappingFormError(friendlyMessage)
      showRequestErrorToast(friendlyMessage)
    } finally {
      setIsCreatingMapping(false)
    }
  }, [
    canManageMappings,
    createTargetMapping,
    mappingDraft.sdwtProd,
    mappingDraft.userSdwtProd,
    mappingDraft.userSdwtProds,
    notificationTargets,
    selectedUserSdwtProd,
  ])

  const handleDeleteTargetMapping = React.useCallback(async (mapping) => {
    const normalizedUserSdwtProd = String(mapping?.userSdwtProd || "").trim()
    const normalizedSdwtProd = String(mapping?.sdwtProd || "").trim()
    if (!selectedUserSdwtProd) {
      setMappingFormError("알림 Target을 먼저 선택하세요.")
      return
    }
    if (!normalizedUserSdwtProd || !normalizedSdwtProd) {
      setMappingFormError("삭제할 지정 조합 값을 확인할 수 없습니다.")
      return
    }
    if (!canManageMappings) {
      setMappingFormError("지정 조합 삭제 권한이 없습니다.")
      return
    }
    const confirmed = window.confirm(
      `${normalizedUserSdwtProd} 분임조원이 ${normalizedSdwtProd} 설비로 보낸 E-SOP 지정 조합을 삭제할까요?`,
    )
    if (!confirmed) return

    const mappingKey = buildTargetMappingKey({
      userSdwtProd: normalizedUserSdwtProd,
      sdwtProd: normalizedSdwtProd,
    })
    setDeletingMappingKey(mappingKey)
    setMappingFormError(null)
    try {
      await deleteTargetMapping({
        targetUserSdwtProd: selectedUserSdwtProd,
        userSdwtProd: normalizedUserSdwtProd,
        sdwtProd: normalizedSdwtProd,
      })
      showDeleteToast()
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to delete target mapping"
      setMappingFormError(message)
      showRequestErrorToast(message)
    } finally {
      setDeletingMappingKey("")
    }
  }, [canManageMappings, deleteTargetMapping, selectedUserSdwtProd])

  const handleJiraKeySave = React.useCallback(
    async (event) => {
      event.preventDefault()
      if (!selectedUserSdwtProd) {
        setJiraKeyFormError("알림 Target을 선택하세요.")
        return
      }

      const normalized = jiraKeyDraft.trim()
      if (!normalized) {
        setJiraKeyFormError("Jira Project Key를 입력하세요.")
        return
      }
      if (normalized.length > MAX_JIRA_KEY_LENGTH) {
        setJiraKeyFormError(`Jira key must be ${MAX_JIRA_KEY_LENGTH} characters or fewer`)
        return
      }
      if (!canManageChannelSettings) {
        setJiraKeyFormError("Jira Project Key 변경 권한이 없습니다.")
        return
      }

      setIsSavingJiraKey(true)
      setJiraKeyFormError(null)

      try {
        await updateJiraKey({ jiraKey: normalized, channelEnabled: channelEnabledDraft })
        showJiraKeyToast()
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to update Jira key"
        setJiraKeyFormError(message)
        showRequestErrorToast(message)
      } finally {
        setIsSavingJiraKey(false)
      }
    },
    [canManageChannelSettings, channelEnabledDraft, jiraKeyDraft, selectedUserSdwtProd, updateJiraKey],
  )

  const handleChannelEnabledChange = React.useCallback(async (channelKey, isEnabled) => {
    if (!selectedUserSdwtProd) {
      setJiraKeyFormError("알림 Target을 선택하세요.")
      return
    }
    if (!canManageChannelSettings) {
      setJiraKeyFormError("알람 채널 설정 변경 권한이 없습니다.")
      return
    }

    const previousDraft = channelEnabledDraft
    const nextDraft = { ...channelEnabledDraft, [channelKey]: isEnabled }
    setChannelEnabledDraft(nextDraft)
    setIsSavingJiraKey(true)
    setJiraKeyFormError(null)
    try {
      await updateJiraKey({ jiraKey: jiraKey || "", channelEnabled: nextDraft })
      showAlarmChannelApplyToast(channelKey, isEnabled)
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update alarm channel"
      setChannelEnabledDraft(previousDraft)
      setJiraKeyFormError(message)
      showRequestErrorToast(message)
    } finally {
      setIsSavingJiraKey(false)
    }
  }, [
    canManageChannelSettings,
    channelEnabledDraft,
    jiraKey,
    selectedUserSdwtProd,
    updateJiraKey,
  ])

  const handleNeedToSendRuleDraftChange = React.useCallback(async (key, value) => {
    if (key === "commentKeyword") {
      setNeedToSendRuleDraft((prev) => {
        const nextKeyword = String(value ?? "")
        return { ...prev, commentKeyword: nextKeyword, enabled: nextKeyword.trim() ? true : prev.enabled }
      })
      setNeedToSendRuleFormError(null)
      return
    }

    if (!selectedUserSdwtProd) {
      setNeedToSendRuleFormError("알림 Target을 선택하세요.")
      return
    }
    if (!canManageChannelSettings) {
      setNeedToSendRuleFormError("자동 예약 코멘트 규칙 변경 권한이 없습니다.")
      return
    }

    const previousDraft = needToSendRuleDraft
    const normalizedKeyword = String(needToSendRuleDraft.commentKeyword || "").trim()
    const nextRule = {
      commentKeyword: normalizedKeyword,
      enabled: key === "enabled" ? Boolean(value) : Boolean(needToSendRuleDraft.enabled),
      ignoreSampleType: key === "ignoreSampleType" ? Boolean(value) : Boolean(needToSendRuleDraft.ignoreSampleType),
    }
    if (nextRule.enabled && !normalizedKeyword) {
      setNeedToSendRuleFormError("자동 예약을 활성화하려면 포함 키워드를 입력하세요.")
      return
    }

    setNeedToSendRuleDraft(nextRule)
    setIsSavingNeedToSendRule(true)
    setNeedToSendRuleFormError(null)
    try {
      await updateNeedToSendRule({ needToSendRule: nextRule })
      showNeedToSendRuleApplyToast(key, Boolean(value))
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update needtosend rule"
      setNeedToSendRuleDraft(previousDraft)
      setNeedToSendRuleFormError(message)
      showRequestErrorToast(message)
    } finally {
      setIsSavingNeedToSendRule(false)
    }
  }, [
    canManageChannelSettings,
    needToSendRuleDraft,
    selectedUserSdwtProd,
    updateNeedToSendRule,
  ])

  const handleNeedToSendRuleSave = React.useCallback(
    async (event) => {
      event.preventDefault()
      if (!selectedUserSdwtProd) {
        setNeedToSendRuleFormError("알림 Target을 선택하세요.")
        return
      }
      if (!canManageChannelSettings) {
        setNeedToSendRuleFormError("자동 예약 코멘트 규칙 변경 권한이 없습니다.")
        return
      }

      const normalizedKeyword = String(needToSendRuleDraft.commentKeyword || "").trim()
      if (normalizedKeyword.length > MAX_NEED_TO_SEND_KEYWORD_LENGTH) {
        setNeedToSendRuleFormError(`포함 키워드는 ${MAX_NEED_TO_SEND_KEYWORD_LENGTH}자 이하여야 합니다.`)
        return
      }
      if (needToSendRuleDraft.enabled && !normalizedKeyword) {
        setNeedToSendRuleFormError("자동 예약을 활성화하려면 포함 키워드를 입력하세요.")
        return
      }

      const nextRule = {
        commentKeyword: normalizedKeyword,
        enabled: Boolean(needToSendRuleDraft.enabled),
        ignoreSampleType: Boolean(needToSendRuleDraft.ignoreSampleType),
      }
      setIsSavingNeedToSendRule(true)
      setNeedToSendRuleFormError(null)

      try {
        await updateNeedToSendRule({ needToSendRule: nextRule })
        showNeedToSendRuleToast()
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to update needtosend rule"
        setNeedToSendRuleFormError(message)
        showRequestErrorToast(message)
      } finally {
        setIsSavingNeedToSendRule(false)
      }
    },
    [canManageChannelSettings, needToSendRuleDraft, selectedUserSdwtProd, updateNeedToSendRule],
  )

  const handleRecipientSearch = React.useCallback(
    async (channel, event) => {
      event.preventDefault()
      const config = RECIPIENT_CHANNEL_CONFIG[channel]
      const normalized = String(recipientSearches[channel] || "").trim()
      if (!normalized) {
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: "검색어를 입력하세요." }))
        return
      }
      if (!canManageRecipients) {
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
        return
      }

      setIsSearchingRecipients((prev) => ({ ...prev, [channel]: true }))
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
      try {
        const { results } = await fetchAccountUserPool({
          search: normalized,
          contactField: config.contactField,
          limit: 20,
          includeExternalSnapshots: true,
        })
        const previousSearchIds = new Set(
          (recipientPickerResults[channel]?.search || []).map(getRecipientKey).filter(Boolean),
        )
        setRecipientPickerResults((prev) => ({
          ...prev,
          [channel]: { ...(prev[channel] || { group: [], search: [] }), search: results || [] },
        }))
        setRecipientPickerSelectedIds((prev) => ({
          ...prev,
          [channel]: (prev[channel] || []).filter((userId) => !previousSearchIds.has(userId)),
        }))
        if (!results?.length) {
          setRecipientActionErrors((prev) => ({ ...prev, [channel]: "검색 결과가 없습니다." }))
        }
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to search users"
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: message }))
        showRequestErrorToast(message)
      } finally {
        setIsSearchingRecipients((prev) => ({ ...prev, [channel]: false }))
      }
    },
    [canManageRecipients, recipientPickerResults, recipientSearches],
  )

  const handleRemoveRecipientUser = React.useCallback((channel, userToRemove) => {
    const config = RECIPIENT_CHANNEL_CONFIG[channel]
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
      return
    }
    const removeKey = getRecipientKey(userToRemove)
    if (!removeKey) return
    setRecipientDrafts((prev) => ({
      ...prev,
      [channel]: prev[channel].filter((item) => getRecipientKey(item) !== removeKey),
    }))
  }, [canManageRecipients])

  const handleLoadSourceRecipients = React.useCallback(async (channel) => {
    const config = RECIPIENT_CHANNEL_CONFIG[channel]
    const sourceDepartment = recipientSourceDepartments[channel]
    const sourceSdwt = recipientSourceSdwt[channel]
    if (!sourceDepartment) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: "Department를 먼저 선택하세요." }))
      return
    }
    if (!sourceSdwt) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: "불러올 소속을 선택하세요." }))
      return
    }
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
      return
    }

    setIsLoadingSourceUsers((prev) => ({ ...prev, [channel]: true }))
    setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
    const requestId = sourceLoadRequestRef.current[channel] + 1
    sourceLoadRequestRef.current[channel] = requestId
    const requestLineId = lineId
    const requestTarget = selectedUserSdwtProd
    const requestSourceSdwt = sourceSdwt
    const previousGroupIds = new Set(
      (recipientPickerResults[channel]?.group || []).map(getRecipientKey).filter(Boolean),
    )
    const isCurrentLoad = () =>
      sourceLoadRequestRef.current[channel] === requestId &&
      isCurrentRecipientContext(requestLineId, requestTarget)
    try {
      const { results } = await fetchAccountUserPool({
        department: sourceDepartment,
        userSdwtProd: requestSourceSdwt,
        contactField: config.contactField,
        limit: "all",
        includeExternalSnapshots: true,
      })
      if (!isCurrentLoad()) {
        return
      }
      const loadedUsers = results || []
      setRecipientPickerResults((prev) => ({
        ...prev,
        [channel]: { ...(prev[channel] || { group: [], search: [] }), group: loadedUsers },
      }))
      setRecipientPickerSelectedIds((prev) => {
        const current = new Set(
          (prev[channel] || []).filter((recipientKey) => !previousGroupIds.has(recipientKey)),
        )
        for (const user of loadedUsers) {
          const recipientKey = getRecipientKey(user)
          if (recipientKey) current.add(recipientKey)
        }
        return { ...prev, [channel]: Array.from(current) }
      })
      if (loadedUsers.length === 0) {
        setRecipientActionErrors((prev) => ({ ...prev, [channel]: "소속 사용자 결과가 없습니다." }))
      }
    } catch (requestError) {
      if (!isCurrentLoad()) {
        return
      }
      const message =
        requestError instanceof Error ? requestError.message : "Failed to load users"
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: message }))
      showRequestErrorToast(message)
    } finally {
      if (isCurrentLoad()) {
        setIsLoadingSourceUsers((prev) => ({ ...prev, [channel]: false }))
      }
    }
  }, [
    canManageRecipients,
    isCurrentRecipientContext,
    lineId,
    recipientPickerResults,
    recipientSourceDepartments,
    recipientSourceSdwt,
    selectedUserSdwtProd,
  ])

  const handleApplyRecipientPicker = React.useCallback((channel) => {
    const config = RECIPIENT_CHANNEL_CONFIG[channel]
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
      return
    }

    const selectedIds = new Set(recipientPickerSelectedIds[channel] || [])
    const selectedUsers = getRecipientPickerUsers(recipientPickerResults[channel]).filter((user) => {
      const recipientKey = getRecipientKey(user)
      return recipientKey && selectedIds.has(recipientKey)
    })
    if (selectedUsers.length === 0) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: "적용할 인원을 선택하세요." }))
      return
    }

    setRecipientDraftTargets((prev) => ({ ...prev, [channel]: selectedUserSdwtProd || "" }))
    setRecipientDrafts((prev) => ({
      ...prev,
      [channel]: mergeRecipientUsers(prev[channel], selectedUsers),
    }))
    setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
    setRecipientPickerOpen((prev) => ({ ...prev, [channel]: false }))
    showRecipientCandidatesToast(selectedUsers.length)
  }, [canManageRecipients, recipientPickerResults, recipientPickerSelectedIds, selectedUserSdwtProd])

  const handleRecipientsSave = React.useCallback(async (channel) => {
    const config = RECIPIENT_CHANNEL_CONFIG[channel]
    if (!selectedUserSdwtProd) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: "알림 Target을 선택하세요." }))
      return
    }
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: config.permissionErrorText }))
      return
    }

    setIsSavingRecipients((prev) => ({ ...prev, [channel]: true }))
    setRecipientActionErrors((prev) => ({ ...prev, [channel]: null }))
    const requestLineId = lineId
    const requestTarget = selectedUserSdwtProd
    try {
      const userIds = currentRecipientDrafts[channel]
        .map(getRecipientUserId)
        .filter(Boolean)
      const externalKnoxIds = currentRecipientDrafts[channel]
        .map(getRecipientExternalKnoxId)
        .filter(Boolean)
      const updater = channel === "messenger" ? updateMessengerRecipients : updateMailRecipients
      const result = await updater({ userIds, externalKnoxIds })
      if (result?.stale) {
        return
      }
      void loadMyRecipientTargets()
      showRecipientsSaveToast(config.saveDescription)
    } catch (requestError) {
      if (!isCurrentRecipientContext(requestLineId, requestTarget)) {
        return
      }
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update recipients"
      setRecipientActionErrors((prev) => ({ ...prev, [channel]: message }))
      showRequestErrorToast(message)
    } finally {
      if (isCurrentRecipientContext(requestLineId, requestTarget)) {
        setIsSavingRecipients((prev) => ({ ...prev, [channel]: false }))
      }
    }
  }, [
    canManageRecipients,
    currentRecipientDrafts,
    isCurrentRecipientContext,
    lineId,
    loadMyRecipientTargets,
    selectedUserSdwtProd,
    updateMailRecipients,
    updateMessengerRecipients,
  ])

  const handleMessengerForceNewChatroomChange = React.useCallback(async (checked) => {
    if (!selectedUserSdwtProd) {
      setRecipientActionErrors((prev) => ({ ...prev, messenger: "알림 Target을 선택하세요." }))
      return
    }
    if (!canManageRecipients) {
      setRecipientActionErrors((prev) => ({
        ...prev,
        messenger: RECIPIENT_CHANNEL_CONFIG.messenger.permissionErrorText,
      }))
      return
    }
    if (
      checked &&
      !window.confirm(
        "다음 메신저 발송 시 현재 저장된 메신저 수신인 기준으로 새 대화방을 생성해 전송합니다.\n동의하면 새 대화방 생성 옵션이 체크됩니다.",
      )
    ) {
      return
    }

    const requestLineId = lineId
    const requestTarget = selectedUserSdwtProd
    setIsSavingMessengerForceNewChatroom(true)
    setRecipientActionErrors((prev) => ({ ...prev, messenger: null }))
    try {
      await updateMessengerForceNewChatroom({ forceNewChatroom: checked })
      showUpdateToast()
    } catch (requestError) {
      if (!isCurrentRecipientContext(requestLineId, requestTarget)) {
        return
      }
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Failed to update messenger chatroom option"
      setRecipientActionErrors((prev) => ({ ...prev, messenger: message }))
      showRequestErrorToast(message)
    } finally {
      if (isCurrentRecipientContext(requestLineId, requestTarget)) {
        setIsSavingMessengerForceNewChatroom(false)
      }
    }
  }, [
    canManageRecipients,
    isCurrentRecipientContext,
    lineId,
    selectedUserSdwtProd,
    updateMessengerForceNewChatroom,
  ])

  const startEditing = React.useCallback((entry) => {
    setEditingId(entry.id)
    setEditDraft({ mainStep: entry.mainStep, customEndStep: entry.customEndStep ?? "" })
    setRowErrors((prev) => {
      if (!(entry.id in prev)) return prev
      const next = { ...prev }
      delete next[entry.id]
      return next
    })
  }, [])

  const cancelEditing = React.useCallback(() => {
    setEditingId(null)
    setEditDraft({ mainStep: "", customEndStep: "" })
  }, [])

  const handleEditChange = React.useCallback((key, value) => {
    setEditDraft((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleSave = React.useCallback(async () => {
    if (!editingId) return
    const entry = entries.find((item) => item.id === editingId)
    if (!entry) {
      cancelEditing()
      return
    }

    const { normalizedMainStep, normalizedCustom, error: draftError } = validateStepDraft({
      mainStep: editDraft.mainStep,
      customEndStep: editDraft.customEndStep,
    })
    const updates = {}

    if (draftError) {
      setRowErrors((prev) => ({ ...prev, [entry.id]: draftError }))
      return
    }

    if (normalizedMainStep !== entry.mainStep) {
      updates.mainStep = normalizedMainStep
    }

    const normalizedOriginal = (entry.customEndStep ?? "").trim()
    if (normalizedCustom !== normalizedOriginal) {
      updates.customEndStep = normalizedCustom.length > 0 ? normalizedCustom : null
    }

    if (Object.keys(updates).length === 0) {
      cancelEditing()
      return
    }

    setSavingMap((prev) => ({ ...prev, [entry.id]: true }))
    setRowErrors((prev) => {
      if (!(entry.id in prev)) return prev
      const next = { ...prev }
      delete next[entry.id]
      return next
    })

    try {
      await updateEntry({ id: entry.id, ...updates })
      showUpdateToast()
      cancelEditing()
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update entry"
      setRowErrors((prev) => ({ ...prev, [entry.id]: message }))
      showRequestErrorToast(message)
    } finally {
      setSavingMap((prev) => {
        if (!(entry.id in prev)) return prev
        const next = { ...prev }
        delete next[entry.id]
        return next
      })
    }
  }, [cancelEditing, editDraft.customEndStep, editDraft.mainStep, editingId, entries, updateEntry])

  const handleDelete = React.useCallback(
    async (entry) => {
      if (!entry) return
      const confirmed = window.confirm(
        `Delete override for main step "${entry.mainStep}"? This action cannot be undone.`,
      )
      if (!confirmed) return

      setSavingMap((prev) => ({ ...prev, [entry.id]: true }))
      setRowErrors((prev) => {
        if (!(entry.id in prev)) return prev
        const next = { ...prev }
        delete next[entry.id]
        return next
      })

      try {
        await deleteEntry({ id: entry.id })
        if (editingId === entry.id) {
          cancelEditing()
        }
        showDeleteToast()
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to delete entry"
        setRowErrors((prev) => ({ ...prev, [entry.id]: message }))
        showRequestErrorToast(message)
      } finally {
        setSavingMap((prev) => {
          if (!(entry.id in prev)) return prev
          const next = { ...prev }
          delete next[entry.id]
          return next
        })
      }
    },
    [cancelEditing, deleteEntry, editingId],
  )

  const notificationTargetCard = (
    <NotificationTargetCard
      lineId={lineId}
      newTargetDraft={newTargetDraft}
      maxTargetFieldLength={MAX_TARGET_FIELD_LENGTH}
      canCreateTarget={canCreateTarget}
      isCreateTargetPermissionLoading={!hasLoadedPermissionContext}
      canManageMappings={canManageMappings}
      isCreatingTarget={isCreatingTarget}
      isCreatingMapping={isCreatingMapping}
      deletingMappingKey={deletingMappingKey}
      targetFormError={targetFormError}
      mappingFormError={mappingFormError}
      mappingDraft={mappingDraft}
      mappingOptions={effectiveMappingOptions}
      mappingUserLineId={mappingUserLineId}
      mappingSdwtLineId={mappingSdwtLineId}
      mappingUserLineOptions={mappingUserLineOptions}
      mappingSdwtLineOptions={mappingSdwtLineOptions}
      mappingOptionLinesError={null}
      mappingValueLineLabels={mappingValueLineLabels}
      isMappingOptionLinesLoading={false}
      userSdwtValues={userSdwtValues}
      selectedUserSdwtProd={selectedUserSdwtProd}
      selectedNotificationTarget={selectedNotificationTarget}
      onTargetDraftChange={setNewTargetDraft}
      onMappingDraftChange={handleMappingDraftChange}
      onMappingUserLineChange={handleMappingUserLineChange}
      onMappingSdwtLineChange={handleMappingSdwtLineChange}
      onCreateTarget={handleCreateTarget}
      onCreateTargetMapping={handleCreateTargetMapping}
      onDeleteTargetMapping={handleDeleteTargetMapping}
      onSelectTarget={handleSelectNotificationTarget}
    />
  )

  const alarmChannelSettingsCard = (
    <AlarmChannelSettingsCard
      selectedUserSdwtProd={selectedUserSdwtProd}
      jiraKeyDraft={jiraKeyDraft}
      channelEnabledDraft={channelEnabledDraft}
      maxJiraKeyLength={MAX_JIRA_KEY_LENGTH}
      jiraKeyFormError={jiraKeyFormError}
      jiraKeyError={jiraKeyError}
      isJiraKeyLoading={isJiraKeyLoading}
      isSavingJiraKey={isSavingJiraKey}
      canManage={canManageChannelSettings}
      onJiraKeyDraftChange={setJiraKeyDraft}
      onChannelEnabledChange={handleChannelEnabledChange}
      onSaveJiraKey={handleJiraKeySave}
    />
  )

  const needToSendCommentRuleCard = (
    <NeedToSendCommentRuleCard
      selectedUserSdwtProd={selectedUserSdwtProd}
      ruleDraft={needToSendRuleDraft}
      maxKeywordLength={MAX_NEED_TO_SEND_KEYWORD_LENGTH}
      formError={needToSendRuleFormError}
      isLoading={isJiraKeyLoading}
      isSaving={isSavingNeedToSendRule}
      canManage={canManageChannelSettings}
      onDraftChange={handleNeedToSendRuleDraftChange}
      onSave={handleNeedToSendRuleSave}
    />
  )

  const myRecipientTargetsCard = (
    <MyRecipientTargetsCard
      lineId={lineId}
      targets={myRecipientTargets}
      selectedUserSdwtProd={selectedUserSdwtProd}
      isLoading={isMyRecipientTargetsLoading}
      error={myRecipientTargetsError}
      onSelectTarget={handleSelectNotificationTarget}
    />
  )

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col gap-3 overflow-hidden">
      <LineSettingsHeader
        lineId={lineId}
        title={title}
        lastUpdatedLabel={lastUpdatedLabel}
        isRefreshing={isRefreshing}
        onRefresh={handleRefresh}
      />

      {error && (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <div className={settingsBodyClassName}>
        <div className={settingsGridClassName}>
          {isNotificationSettings && (
            <EarlyInformSettingsCard
              lineId={lineId}
              formError={formError}
              formValues={formValues}
              maxFieldLength={MAX_FIELD_LENGTH}
              isCreating={isCreating}
              entries={entries}
              isLoading={isLoading}
              hasLoadedOnce={hasLoadedOnce}
              editingId={editingId}
              editDraft={editDraft}
              savingMap={savingMap}
              rowErrors={rowErrors}
              onCreate={handleCreate}
              onFormChange={handleFormChange}
              onEditChange={handleEditChange}
              onSave={handleSave}
              onCancelEditing={cancelEditing}
              onStartEditing={startEditing}
              onDelete={handleDelete}
            />
          )}

          {isRecipientSettings ? (
            <div className="h-full min-h-0 min-w-0">
              {notificationTargetCard}
            </div>
          ) : null}

          {isRecipientSettings ? (
            <div className="grid h-full min-h-0 min-w-0 grid-rows-[auto_auto_minmax(0,1fr)] gap-3">
              {alarmChannelSettingsCard}
              {needToSendCommentRuleCard}
              <div className="min-h-0">{myRecipientTargetsCard}</div>
            </div>
          ) : null}

          {isRecipientSettings ? (
            <div className="grid h-full min-h-0 min-w-0 grid-rows-2 gap-3">
              <RecipientSettingsCards
                recipientChannels={RECIPIENT_CHANNELS}
                selectedUserSdwtProd={selectedUserSdwtProd}
                canManageRecipients={canManageRecipients}
                currentRecipientDrafts={currentRecipientDrafts}
                isMessengerRecipientsLoading={isMessengerRecipientsLoading}
                isMailRecipientsLoading={isMailRecipientsLoading}
                onRemoveUser={handleRemoveRecipientUser}
                onSave={handleRecipientsSave}
                onOpenPicker={handleOpenRecipientPicker}
                isRecipientDraftCurrent={isRecipientDraftCurrent}
                isSavingRecipients={isSavingRecipients}
                messengerForceNewChatroom={messengerForceNewChatroom}
                isSavingMessengerForceNewChatroom={isSavingMessengerForceNewChatroom}
                onMessengerForceNewChatroomChange={handleMessengerForceNewChatroomChange}
                recipientActionErrors={recipientActionErrors}
                messengerRecipientsError={messengerRecipientsError}
                mailRecipientsError={mailRecipientsError}
                recipientPickerOpen={recipientPickerOpen}
                recipientPickerTabs={recipientPickerTabs}
                accountDepartmentValues={accountDepartmentValues}
                accountUserSdwtValues={accountUserSdwtValues}
                recipientSourceDepartments={recipientSourceDepartments}
                recipientSourceSdwtOptions={recipientSourceSdwtOptions}
                recipientSourceSdwt={recipientSourceSdwt}
                onPickerOpenChange={handleRecipientPickerOpenChange}
                onPickerTabChange={handleRecipientPickerTabChange}
                onSourceDepartmentChange={handleRecipientSourceDepartmentChange}
                onSourceSdwtChange={handleRecipientSourceSdwtChange}
                isLoadingSourceGroups={isLoadingSourceGroups}
                isLoadingSourceUsers={isLoadingSourceUsers}
                onLoadSourceRecipients={handleLoadSourceRecipients}
                recipientSearches={recipientSearches}
                onRecipientSearchChange={handleRecipientSearchChange}
                isSearchingRecipients={isSearchingRecipients}
                onRecipientSearch={handleRecipientSearch}
                recipientPickerResults={recipientPickerResults}
                recipientPickerSelectedIds={recipientPickerSelectedIds}
                onRecipientPickerUserToggle={handleRecipientPickerUserToggle}
                onRecipientPickerAllToggle={handleRecipientPickerAllToggle}
                onApplyRecipientPicker={handleApplyRecipientPicker}
              />
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
