// 파일 경로: src/features/line-dashboard/hooks/useLineSettings.js
// 라인 조기 알림 설정 데이터를 관리하는 전용 훅 (비동기 로딩 + CRUD 포함)
import * as React from "react"

import {
  createNotificationTarget,
  createNotificationTargetMapping,
  createLineSetting,
  deleteNotificationTargetMapping,
  deleteLineSetting,
  fetchNotificationRecipients,
  fetchNotificationTargets,
  fetchUserSdwtJiraKey,
  fetchLineSettings,
  updateLineSetting,
  updateNotificationRecipients,
  updateUserSdwtJiraKey,
} from "../api"
import { timeFormatter } from "../utils/formatters"
import { sortEntries } from "../utils/lineSettings"

const EMPTY_TIMESTAMP = "-"
const EMPTY_MAPPING_OPTIONS = { userSdwtProds: [], sdwtProds: [] }
const EMPTY_MAPPING_OPTION_LINES = []
const DEFAULT_CHANNEL_ENABLED = { jira: true, messenger: true, mail: true }
const DEFAULT_NEED_TO_SEND_RULE = { commentKeyword: "", enabled: false, ignoreSampleType: false }
const DEFAULT_MESSENGER_FORCE_NEW_CHATROOM = false

const normalizeId = (value) => String(value ?? "")
const nowLabel = () => timeFormatter.format(new Date())

export function useLineSettings({ lineId, userSdwtProd, loadRecipients = true }) {
  const [entries, setEntries] = React.useState([])
  const [userSdwtValues, setUserSdwtValues] = React.useState([])
  const [mappingOptions, setMappingOptions] = React.useState(EMPTY_MAPPING_OPTIONS)
  const [mappingOptionLines, setMappingOptionLines] = React.useState(EMPTY_MAPPING_OPTION_LINES)
  const [notificationTargets, setNotificationTargets] = React.useState([])
  const [jiraKey, setJiraKey] = React.useState("")
  const [channelEnabled, setChannelEnabled] = React.useState(DEFAULT_CHANNEL_ENABLED)
  const [needToSendRule, setNeedToSendRule] = React.useState(DEFAULT_NEED_TO_SEND_RULE)
  const [messengerForceNewChatroom, setMessengerForceNewChatroom] = React.useState(
    DEFAULT_MESSENGER_FORCE_NEW_CHATROOM,
  )
  const [mailRecipients, setMailRecipients] = React.useState([])
  const [mailRecipientsTargetUserSdwtProd, setMailRecipientsTargetUserSdwtProd] = React.useState("")
  const [messengerRecipients, setMessengerRecipients] = React.useState([])
  const [messengerRecipientsTargetUserSdwtProd, setMessengerRecipientsTargetUserSdwtProd] = React.useState("")
  const [jiraKeyError, setJiraKeyError] = React.useState(null)
  const [mailRecipientsError, setMailRecipientsError] = React.useState(null)
  const [messengerRecipientsError, setMessengerRecipientsError] = React.useState(null)
  const [error, setError] = React.useState(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [isJiraKeyLoading, setIsJiraKeyLoading] = React.useState(false)
  const [isMailRecipientsLoading, setIsMailRecipientsLoading] = React.useState(false)
  const [isMessengerRecipientsLoading, setIsMessengerRecipientsLoading] = React.useState(false)
  const [hasLoadedOnce, setHasLoadedOnce] = React.useState(false)
  const [lastUpdatedLabel, setLastUpdatedLabel] = React.useState(EMPTY_TIMESTAMP)

  const hasLoadedRef = React.useRef(false)
  const refreshRequestRef = React.useRef(0)
  const contextRef = React.useRef({ lineId, userSdwtProd })
  contextRef.current = { lineId, userSdwtProd }

  const isCurrentContext = React.useCallback((requestLineId, requestUserSdwtProd) => {
    const context = contextRef.current
    return context.lineId === requestLineId && context.userSdwtProd === requestUserSdwtProd
  }, [])

  const resetForLineChange = React.useCallback(() => {
    refreshRequestRef.current += 1
    setEntries([])
    setUserSdwtValues([])
    setMappingOptions(EMPTY_MAPPING_OPTIONS)
    setMappingOptionLines(EMPTY_MAPPING_OPTION_LINES)
    setNotificationTargets([])
    setJiraKey("")
    setChannelEnabled(DEFAULT_CHANNEL_ENABLED)
    setNeedToSendRule(DEFAULT_NEED_TO_SEND_RULE)
    setMessengerForceNewChatroom(DEFAULT_MESSENGER_FORCE_NEW_CHATROOM)
    setMailRecipients([])
    setMailRecipientsTargetUserSdwtProd("")
    setMessengerRecipients([])
    setMessengerRecipientsTargetUserSdwtProd("")
    setJiraKeyError(null)
    setMailRecipientsError(null)
    setMessengerRecipientsError(null)
    setError(null)
    setIsLoading(false)
    setIsJiraKeyLoading(false)
    setIsMailRecipientsLoading(false)
    setIsMessengerRecipientsLoading(false)
    setLastUpdatedLabel(EMPTY_TIMESTAMP)
    setHasLoadedOnce(false)
    hasLoadedRef.current = false
  }, [])

  React.useEffect(() => {
    resetForLineChange()
  }, [lineId, resetForLineChange])

  React.useEffect(() => {
    refreshRequestRef.current += 1
    setJiraKey("")
    setChannelEnabled(DEFAULT_CHANNEL_ENABLED)
    setNeedToSendRule(DEFAULT_NEED_TO_SEND_RULE)
    setMessengerForceNewChatroom(DEFAULT_MESSENGER_FORCE_NEW_CHATROOM)
    setMailRecipients([])
    setMailRecipientsTargetUserSdwtProd(userSdwtProd || "")
    setMessengerRecipients([])
    setMessengerRecipientsTargetUserSdwtProd(userSdwtProd || "")
    setJiraKeyError(null)
    setMailRecipientsError(null)
    setMessengerRecipientsError(null)
    setIsJiraKeyLoading(false)
    setIsMailRecipientsLoading(false)
    setIsMessengerRecipientsLoading(false)
  }, [userSdwtProd])

  const refresh = React.useCallback(async () => {
    const requestId = refreshRequestRef.current + 1
    refreshRequestRef.current = requestId
    const requestLineId = lineId
    const requestUserSdwtProd = userSdwtProd
    const isCurrentRefresh = () =>
      refreshRequestRef.current === requestId &&
      isCurrentContext(requestLineId, requestUserSdwtProd)

    // 라인을 선택하지 않은 경우: 네트워크 호출을 생략하고 초기 상태만 반환
    if (!lineId) {
      resetForLineChange()
      if (!hasLoadedRef.current) {
        hasLoadedRef.current = true
        setHasLoadedOnce(true)
      }
      return { ok: true }
    }

    const shouldLoadRecipients = Boolean(loadRecipients && userSdwtProd)
    setIsLoading(true)
    setIsJiraKeyLoading(true)
    setIsMailRecipientsLoading(shouldLoadRecipients)
    setIsMessengerRecipientsLoading(shouldLoadRecipients)
    setError(null)
    setJiraKeyError(null)
    setMailRecipientsError(null)
    setMessengerRecipientsError(null)
    if (hasLoadedRef.current) {
      setLastUpdatedLabel("Updating…")
    }

    try {
      const [
        settingsResult,
        targetsResult,
        jiraResult,
        mailRecipientsResult,
        messengerRecipientsResult,
      ] = await Promise.allSettled([
        fetchLineSettings(lineId),
        fetchNotificationTargets({ lineId }),
        userSdwtProd
          ? fetchUserSdwtJiraKey(userSdwtProd)
          : Promise.resolve({
              jiraKey: "",
              messengerForceNewChatroom: DEFAULT_MESSENGER_FORCE_NEW_CHATROOM,
            }),
        shouldLoadRecipients
          ? fetchNotificationRecipients({
              lineId: requestLineId,
              targetUserSdwtProd: userSdwtProd,
              channel: "mail",
            })
          : Promise.resolve({ recipients: [] }),
        shouldLoadRecipients
          ? fetchNotificationRecipients({
              lineId: requestLineId,
              targetUserSdwtProd: userSdwtProd,
              channel: "messenger",
            })
          : Promise.resolve({ recipients: [] }),
      ])
      if (!isCurrentRefresh()) {
        return { ok: false, stale: true }
      }

      let ok = true
      if (settingsResult.status === "fulfilled") {
        const { entries: loadedEntries } = settingsResult.value
        setEntries(sortEntries(loadedEntries || []))
        setLastUpdatedLabel(nowLabel())
      } else {
        const message =
          settingsResult.reason instanceof Error
            ? settingsResult.reason.message
            : "Failed to load settings"
        setError(message)
        if (!hasLoadedRef.current) {
          setLastUpdatedLabel(EMPTY_TIMESTAMP)
        }
        ok = false
      }

      if (targetsResult.status === "fulfilled") {
        setNotificationTargets(targetsResult.value?.targets || [])
        setUserSdwtValues(targetsResult.value?.targetUserSdwtProds || [])
        setMappingOptions(targetsResult.value?.mappingOptions || EMPTY_MAPPING_OPTIONS)
        setMappingOptionLines(targetsResult.value?.mappingOptionLines || EMPTY_MAPPING_OPTION_LINES)
      } else {
        const message =
          targetsResult.reason instanceof Error
            ? targetsResult.reason.message
            : "Failed to load notification targets"
        setError(message)
        setNotificationTargets([])
        setUserSdwtValues([])
        setMappingOptions(EMPTY_MAPPING_OPTIONS)
        setMappingOptionLines(EMPTY_MAPPING_OPTION_LINES)
        ok = false
      }

      if (jiraResult.status === "fulfilled") {
        setJiraKey(jiraResult.value?.jiraKey || "")
        setChannelEnabled(jiraResult.value?.channelEnabled || DEFAULT_CHANNEL_ENABLED)
        setNeedToSendRule(jiraResult.value?.needToSendRule || DEFAULT_NEED_TO_SEND_RULE)
        setMessengerForceNewChatroom(
          Boolean(jiraResult.value?.messengerForceNewChatroom),
        )
      } else {
        const message =
          jiraResult.reason instanceof Error
            ? jiraResult.reason.message
            : "Failed to load Jira key"
        setJiraKeyError(message)
        setJiraKey("")
        setChannelEnabled(DEFAULT_CHANNEL_ENABLED)
        setNeedToSendRule(DEFAULT_NEED_TO_SEND_RULE)
        setMessengerForceNewChatroom(DEFAULT_MESSENGER_FORCE_NEW_CHATROOM)
        ok = false
      }

      if (mailRecipientsResult.status === "fulfilled") {
        setMailRecipients(mailRecipientsResult.value?.recipients || [])
        setMailRecipientsTargetUserSdwtProd(requestUserSdwtProd || "")
      } else {
        const message =
          mailRecipientsResult.reason instanceof Error
            ? mailRecipientsResult.reason.message
            : "Failed to load mail recipients"
        setMailRecipientsError(message)
        setMailRecipients([])
        setMailRecipientsTargetUserSdwtProd(requestUserSdwtProd || "")
        ok = false
      }

      if (messengerRecipientsResult.status === "fulfilled") {
        setMessengerRecipients(messengerRecipientsResult.value?.recipients || [])
        setMessengerRecipientsTargetUserSdwtProd(requestUserSdwtProd || "")
      } else {
        const message =
          messengerRecipientsResult.reason instanceof Error
            ? messengerRecipientsResult.reason.message
            : "Failed to load messenger recipients"
        setMessengerRecipientsError(message)
        setMessengerRecipients([])
        setMessengerRecipientsTargetUserSdwtProd(requestUserSdwtProd || "")
        ok = false
      }

      return { ok }
    } finally {
      if (isCurrentRefresh()) {
        setIsLoading(false)
        setIsJiraKeyLoading(false)
        setIsMailRecipientsLoading(false)
        setIsMessengerRecipientsLoading(false)
        if (!hasLoadedRef.current) {
          hasLoadedRef.current = true
          setHasLoadedOnce(true)
        }
      }
    }
  }, [isCurrentContext, lineId, loadRecipients, resetForLineChange, userSdwtProd])

  React.useEffect(() => {
    refresh()
  }, [refresh])

  const createEntry = React.useCallback(
    async ({ mainStep, customEndStep }) => {
      const { entry } = await createLineSetting({ lineId, mainStep, customEndStep })
      if (entry) {
        setEntries((prev) =>
          sortEntries([...prev.filter((item) => item.id !== entry.id), entry]),
        )
        setLastUpdatedLabel(nowLabel())
      }
      return entry
    },
    [lineId],
  )

  const updateEntry = React.useCallback(
    async ({ id, mainStep, customEndStep }) => {
      const { entry } = await updateLineSetting({ id, lineId, mainStep, customEndStep })
      if (entry) {
        setEntries((prev) =>
          sortEntries(prev.map((item) => (item.id === entry.id ? entry : item))),
        )
        setLastUpdatedLabel(nowLabel())
      }
      return entry
    },
    [lineId],
  )

  const deleteEntry = React.useCallback(async ({ id }) => {
    await deleteLineSetting({ id })
    const normalizedId = normalizeId(id)
    setEntries((prev) => prev.filter((item) => normalizeId(item.id) !== normalizedId))
    setLastUpdatedLabel(nowLabel())
    return { ok: true }
  }, [])

  const updateJiraKey = React.useCallback(
    async ({ jiraKey: nextJiraKey, channelEnabled: nextChannelEnabled }) => {
      if (!userSdwtProd) {
        throw new Error("Select a notification target to update Jira key")
      }
      const requestLineId = lineId
      const requestUserSdwtProd = userSdwtProd
      const {
        jiraKey: savedKey,
        channelEnabled: savedChannelEnabled,
        needToSendRule: savedNeedToSendRule,
        messengerForceNewChatroom: savedMessengerForceNewChatroom,
      } = await updateUserSdwtJiraKey({
        lineId: requestLineId,
        userSdwtProd,
        jiraKey: nextJiraKey,
        channelEnabled: nextChannelEnabled || channelEnabled,
      })
      if (isCurrentContext(requestLineId, requestUserSdwtProd)) {
        setJiraKey(savedKey || "")
        setChannelEnabled(savedChannelEnabled || DEFAULT_CHANNEL_ENABLED)
        setNeedToSendRule(savedNeedToSendRule || DEFAULT_NEED_TO_SEND_RULE)
        setMessengerForceNewChatroom(Boolean(savedMessengerForceNewChatroom))
        setJiraKeyError(null)
        setLastUpdatedLabel(nowLabel())
      }
      return {
        jiraKey: savedKey,
        channelEnabled: savedChannelEnabled || DEFAULT_CHANNEL_ENABLED,
        needToSendRule: savedNeedToSendRule || DEFAULT_NEED_TO_SEND_RULE,
        messengerForceNewChatroom: Boolean(savedMessengerForceNewChatroom),
      }
    },
    [channelEnabled, isCurrentContext, lineId, userSdwtProd],
  )

  const updateNeedToSendRule = React.useCallback(
    async ({ needToSendRule: nextNeedToSendRule }) => {
      if (!userSdwtProd) {
        throw new Error("Select a notification target to update needtosend rule")
      }
      const requestLineId = lineId
      const requestUserSdwtProd = userSdwtProd
      const {
        jiraKey: savedKey,
        channelEnabled: savedChannelEnabled,
        needToSendRule: savedNeedToSendRule,
        messengerForceNewChatroom: savedMessengerForceNewChatroom,
      } = await updateUserSdwtJiraKey({
        lineId: requestLineId,
        userSdwtProd,
        needToSendRule: nextNeedToSendRule || needToSendRule,
      })
      if (isCurrentContext(requestLineId, requestUserSdwtProd)) {
        setJiraKey(savedKey || "")
        setChannelEnabled(savedChannelEnabled || DEFAULT_CHANNEL_ENABLED)
        setNeedToSendRule(savedNeedToSendRule || DEFAULT_NEED_TO_SEND_RULE)
        setMessengerForceNewChatroom(Boolean(savedMessengerForceNewChatroom))
        setJiraKeyError(null)
        setLastUpdatedLabel(nowLabel())
      }
      return {
        jiraKey: savedKey,
        channelEnabled: savedChannelEnabled || DEFAULT_CHANNEL_ENABLED,
        needToSendRule: savedNeedToSendRule || DEFAULT_NEED_TO_SEND_RULE,
        messengerForceNewChatroom: Boolean(savedMessengerForceNewChatroom),
      }
    },
    [isCurrentContext, lineId, needToSendRule, userSdwtProd],
  )

  const updateRecipients = React.useCallback(
    async ({ channel, userIds, externalKnoxIds = [] }) => {
      if (!lineId) {
        throw new Error("Select a line to update recipients")
      }
      if (!userSdwtProd) {
        throw new Error("Select a notification target to update recipients")
      }
      const requestLineId = lineId
      const requestUserSdwtProd = userSdwtProd
      const { recipients } = await updateNotificationRecipients({
        lineId: requestLineId,
        targetUserSdwtProd: userSdwtProd,
        channel,
        userIds,
        externalKnoxIds,
      })
      const isCurrent = isCurrentContext(requestLineId, requestUserSdwtProd)
      if (isCurrent) {
        if (channel === "messenger") {
          setMessengerRecipients(recipients || [])
          setMessengerRecipientsTargetUserSdwtProd(requestUserSdwtProd || "")
          setMessengerRecipientsError(null)
        } else {
          setMailRecipients(recipients || [])
          setMailRecipientsTargetUserSdwtProd(requestUserSdwtProd || "")
          setMailRecipientsError(null)
        }
        setLastUpdatedLabel(nowLabel())
      }
      return { recipients: recipients || [], stale: !isCurrent }
    },
    [isCurrentContext, lineId, userSdwtProd],
  )

  const updateMailRecipients = React.useCallback(
    ({ userIds, externalKnoxIds }) =>
      updateRecipients({ channel: "mail", userIds, externalKnoxIds }),
    [updateRecipients],
  )

  const updateMessengerForceNewChatroom = React.useCallback(
    async ({ forceNewChatroom }) => {
      if (!userSdwtProd) {
        throw new Error("Select a notification target to update messenger chatroom option")
      }
      const requestLineId = lineId
      const requestUserSdwtProd = userSdwtProd
      const {
        jiraKey: savedKey,
        channelEnabled: savedChannelEnabled,
        needToSendRule: savedNeedToSendRule,
        messengerForceNewChatroom: savedMessengerForceNewChatroom,
      } = await updateUserSdwtJiraKey({
        lineId: requestLineId,
        userSdwtProd,
        messengerForceNewChatroom: Boolean(forceNewChatroom),
      })
      if (isCurrentContext(requestLineId, requestUserSdwtProd)) {
        setJiraKey(savedKey || "")
        setChannelEnabled(savedChannelEnabled || DEFAULT_CHANNEL_ENABLED)
        setNeedToSendRule(savedNeedToSendRule || DEFAULT_NEED_TO_SEND_RULE)
        setMessengerForceNewChatroom(Boolean(savedMessengerForceNewChatroom))
        setJiraKeyError(null)
        setLastUpdatedLabel(nowLabel())
      }
      return {
        jiraKey: savedKey,
        channelEnabled: savedChannelEnabled || DEFAULT_CHANNEL_ENABLED,
        needToSendRule: savedNeedToSendRule || DEFAULT_NEED_TO_SEND_RULE,
        messengerForceNewChatroom: Boolean(savedMessengerForceNewChatroom),
      }
    },
    [isCurrentContext, lineId, userSdwtProd],
  )

  const createTarget = React.useCallback(
    async ({ targetUserSdwtProd }) => {
      if (!lineId) {
        throw new Error("Select a line to create target")
      }
      const { target } = await createNotificationTarget({ lineId, targetUserSdwtProd })
      if (target) {
        setNotificationTargets((prev) => {
          const key = target.targetUserSdwtProd.toLowerCase()
          return [
            target,
            ...prev.filter((item) => item.targetUserSdwtProd.toLowerCase() !== key),
          ].sort((left, right) => left.targetUserSdwtProd.localeCompare(right.targetUserSdwtProd))
        })
        setUserSdwtValues((prev) => {
          const values = Array.from(new Set([target.targetUserSdwtProd, ...prev]))
          return values.sort()
        })
        setMappingOptions((prev) => {
          const values = Array.from(new Set([target.targetUserSdwtProd, ...(prev?.userSdwtProds || [])])).sort()
          return { userSdwtProds: values, sdwtProds: values }
        })
        setMappingOptionLines((prev) => {
          const normalizedLineId = String(target.lineId || lineId || "").trim()
          if (!normalizedLineId) return prev
          const nextValue = target.targetUserSdwtProd
          let found = false
          const nextLines = (Array.isArray(prev) ? prev : []).map((line) => {
            if (String(line?.lineId || "").trim().toLowerCase() !== normalizedLineId.toLowerCase()) {
              return line
            }
            found = true
            return {
              lineId: line.lineId,
              userSdwtProds: Array.from(new Set([nextValue, ...(line.userSdwtProds || [])])).sort(),
            }
          })
          if (found) return nextLines
          return [...nextLines, { lineId: normalizedLineId, userSdwtProds: [nextValue] }]
        })
      }
      return target
    },
    [lineId],
  )

  const createTargetMapping = React.useCallback(
    async ({ targetUserSdwtProd, sdwtProd, userSdwtProd: sourceUserSdwtProd }) => {
      if (!lineId) {
        throw new Error("Select a line to create target mapping")
      }
      if (!targetUserSdwtProd) {
        throw new Error("Select a notification target to create mapping")
      }
      const { target } = await createNotificationTargetMapping({
        lineId,
        targetUserSdwtProd,
        sdwtProd,
        userSdwtProd: sourceUserSdwtProd,
      })
      if (target) {
        setNotificationTargets((prev) => {
          const key = target.targetUserSdwtProd.toLowerCase()
          return [
            target,
            ...prev.filter((item) => item.targetUserSdwtProd.toLowerCase() !== key),
          ].sort((left, right) => left.targetUserSdwtProd.localeCompare(right.targetUserSdwtProd))
        })
        setUserSdwtValues((prev) => {
          const values = Array.from(new Set([target.targetUserSdwtProd, ...prev]))
          return values.sort()
        })
        setLastUpdatedLabel(nowLabel())
      }
      return target
    },
    [lineId],
  )

  const deleteTargetMapping = React.useCallback(
    async ({ targetUserSdwtProd, sdwtProd, userSdwtProd: sourceUserSdwtProd }) => {
      if (!lineId) {
        throw new Error("Select a line to delete target mapping")
      }
      if (!targetUserSdwtProd) {
        throw new Error("Select a notification target to delete mapping")
      }
      const { target } = await deleteNotificationTargetMapping({
        lineId,
        targetUserSdwtProd,
        sdwtProd,
        userSdwtProd: sourceUserSdwtProd,
      })
      if (target) {
        setNotificationTargets((prev) => {
          const key = target.targetUserSdwtProd.toLowerCase()
          return [
            target,
            ...prev.filter((item) => item.targetUserSdwtProd.toLowerCase() !== key),
          ].sort((left, right) => left.targetUserSdwtProd.localeCompare(right.targetUserSdwtProd))
        })
        setLastUpdatedLabel(nowLabel())
      }
      return target
    },
    [lineId],
  )

  const updateMessengerRecipients = React.useCallback(
    ({ userIds, externalKnoxIds }) =>
      updateRecipients({ channel: "messenger", userIds, externalKnoxIds }),
    [updateRecipients],
  )

  return {
    entries,
    userSdwtValues,
    mappingOptions,
    mappingOptionLines,
    notificationTargets,
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
  }
}
