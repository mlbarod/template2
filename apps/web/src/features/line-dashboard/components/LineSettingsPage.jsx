// 파일 경로: src/features/line-dashboard/components/LineSettingsPage.jsx
import * as React from "react"
import {
  IconDeviceFloppy,
  IconPencil,
  IconPlus,
  IconRefresh,
  IconSettings,
  IconTrash,
  IconX,
} from "@tabler/icons-react"
import { AlertCircleIcon, BadgeCheckIcon } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/common"
import { useAuth } from "@/lib/auth"
import { useLineSettings } from "../hooks/useLineSettings"
import { buildToastOptions } from "../utils/toast"
import { formatUpdatedAt, isDuplicateMessage, normalizeDraft } from "../utils/lineSettings"

const LABELS = {
  titleSuffix: "Line E-SOP Settings",
  subtitle: "E-SOP가 종료 되기전에 미리 Inform할 Step을 설정합니다.",
  jiraTitle: "Jira Project Key",
  jiraDescription: "User SDWT별 Jira 프로젝트 키를 설정합니다.",
  jiraHelper: "설정된 키는 Jira 이슈 생성 시 사용됩니다.",
  badgesTitle: "User SDWT",
  badgesDescription: "라인에 등록된 User SDWT를 표시합니다.",
  jiraUserSdwtLabel: "User SDWT",
  jiraUserSdwtPlaceholder: "User SDWT 선택",
  jiraPlaceholder: "ex) DRONE",
  jiraSave: "Save",
  addTitle: "E-SOP Custom End Step 추가",
  mainStep: "Main Step",
  customEndStep: "Early Inform Step",
  lineId: "Line ID",
  updatedBy: "Updated By",
  updatedAt: "Updated At",
  addButton: "Add",
  refresh: "Refresh",
  updated: "Updated",
  loading: "Loading entries…",
  empty: "No overrides found for this line.",
  addDescription: "line_id는 선택한 값으로 자동 저장되며 수정할 수 없습니다.",
}

const DUPLICATE_MESSAGE = "이미 등록된 스텝입니다. 다른 스텝을 입력해주세요."
const MAX_FIELD_LENGTH = 50
const MAX_JIRA_KEY_LENGTH = 64

function validateStepDraft({ mainStep, customEndStep }) {
  const normalizedMainStep = normalizeDraft(mainStep)
  const normalizedCustom = normalizeDraft(customEndStep ?? "")

  if (!normalizedMainStep) {
    return { error: "Main step is required" }
  }
  if (normalizedMainStep.length > MAX_FIELD_LENGTH) {
    return { error: `Main step must be ${MAX_FIELD_LENGTH} characters or fewer` }
  }
  if (normalizedCustom.length > MAX_FIELD_LENGTH) {
    return { error: `Custom end step must be ${MAX_FIELD_LENGTH} characters or fewer` }
  }

  return {
    normalizedMainStep,
    normalizedCustom,
    error: null,
  }
}

function showCreateToast() {
  toast.success("추가 완료", {
    description: "새 조기 알림 설정이 저장되었습니다.",
    icon: <IconPlus className="h-5 w-5 text-[var(--normal-text)]" />,
    ...buildToastOptions({ intent: "success" }),
  })
}

function showUpdateToast() {
  toast.success("수정 완료", {
    description: "설정이 업데이트되었습니다.",
    icon: <IconDeviceFloppy className="h-5 w-5 text-[var(--normal-text)]" />,
    ...buildToastOptions({ intent: "success" }),
  })
}

function showJiraKeyToast() {
  toast.success("저장 완료", {
    description: "Jira project key가 저장되었습니다.",
    icon: <IconDeviceFloppy className="h-5 w-5 text-[var(--normal-text)]" />,
    ...buildToastOptions({ intent: "success" }),
  })
}

function showDeleteToast() {
  toast.warning("삭제 완료", {
    description: "설정이 제거되었습니다.",
    icon: <IconTrash className="h-5 w-5 text-[var(--normal-text)]" />,
    ...buildToastOptions({ intent: "warning" }),
  })
}

function showRequestErrorToast(message) {
  toast.error("요청 실패", {
    description: message || "요청 처리 중 오류가 발생했습니다.",
    icon: <IconX className="h-5 w-5 text-[var(--normal-text)]" />,
    ...buildToastOptions({ intent: "destructive", duration: 3200 }),
  })
}

function LineUserSdwtBadges({ lineId, values }) {
  if (!lineId) {
    return (
      <div className="inline-flex items-center gap-2 rounded-md bg-background px-2 py-1 text-[11px] text-muted-foreground">
        <AlertCircleIcon className="h-3 w-3" />
        라인을 선택하면 User SDWT 목록이 표시됩니다.
      </div>
    )
  }

  if (!values || values.length === 0) {
    return (
      <div className="inline-flex items-center gap-2 rounded-md bg-background px-2 py-1 text-[11px] text-muted-foreground">
        <AlertCircleIcon className="h-3 w-3" />
        등록된 User SDWT가 없습니다.
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="font-mono text-xs font-semibold text-foreground">{lineId} Line 분임조 : </span>
      {values.map((value) => (
        <Badge key={value} variant="secondary" className="gap-1 text-[11px] font-mono">
          <BadgeCheckIcon className="h-3 w-3" />
          {value}
        </Badge>
      ))}
    </div>
  )
}

export function LineSettingsPage({ lineId = "" }) {
  const { user } = useAuth()
  const [selectedUserSdwtProd, setSelectedUserSdwtProd] = React.useState("")
  const {
    entries,
    userSdwtValues,
    jiraKey,
    jiraKeyError,
    error,
    isLoading,
    isJiraKeyLoading,
    hasLoadedOnce,
    lastUpdatedLabel,
    refresh,
    createEntry,
    updateEntry,
    deleteEntry,
    updateJiraKey,
  } = useLineSettings({ lineId, userSdwtProd: selectedUserSdwtProd })

  const [formValues, setFormValues] = React.useState({ mainStep: "", customEndStep: "" })
  const [formError, setFormError] = React.useState(null)
  const [isCreating, setIsCreating] = React.useState(false)

  const [editingId, setEditingId] = React.useState(null)
  const [editDraft, setEditDraft] = React.useState({ mainStep: "", customEndStep: "" })
  const [rowErrors, setRowErrors] = React.useState({})
  const [savingMap, setSavingMap] = React.useState({})
  const [jiraKeyDraft, setJiraKeyDraft] = React.useState("")
  const [jiraKeyFormError, setJiraKeyFormError] = React.useState(null)
  const [isSavingJiraKey, setIsSavingJiraKey] = React.useState(false)

  const isSuperuser = Boolean(user?.is_superuser)
  const isRefreshing = isLoading && hasLoadedOnce

  const handleRefresh = React.useCallback(() => {
    if (!lineId) return
    refresh()
  }, [lineId, refresh])

  const handleFormChange = React.useCallback((key, value) => {
    setFormValues((prev) => ({ ...prev, [key]: value }))
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
    setJiraKeyDraft(jiraKey || "")
    setJiraKeyFormError(null)
  }, [jiraKey, lineId, selectedUserSdwtProd])

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

  const handleJiraKeySave = React.useCallback(
    async (event) => {
      event.preventDefault()
      if (!selectedUserSdwtProd) {
        setJiraKeyFormError("Select a user SDWT to update Jira key")
        return
      }

      const normalized = jiraKeyDraft.trim()
      if (normalized.length > MAX_JIRA_KEY_LENGTH) {
        setJiraKeyFormError(`Jira key must be ${MAX_JIRA_KEY_LENGTH} characters or fewer`)
        return
      }

      setIsSavingJiraKey(true)
      setJiraKeyFormError(null)

      try {
        await updateJiraKey({ jiraKey: normalized })
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
    [jiraKeyDraft, selectedUserSdwtProd, updateJiraKey],
  )

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

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col gap-3 overflow-hidden">
      {/* 헤더 */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-end gap-x-2 gap-y-1 text-lg font-semibold">
            <IconSettings className="size-5" />
            <span>{lineId ? `${lineId} ${LABELS.titleSuffix}` : LABELS.titleSuffix}</span>

            <div
              className="ml-0 md:ml-2 text-[10px] font-normal text-muted-foreground"
              aria-live="polite"
            >
              {LABELS.updated} {lastUpdatedLabel}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">{LABELS.subtitle}</p>
        </div>

        <div className="flex items-center gap-2 self-end">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={!lineId || isRefreshing}
            className="gap-1"
            aria-label={LABELS.refresh}
            title={LABELS.refresh}
          >
            <IconRefresh className={`size-3 ${isRefreshing ? "animate-spin" : ""}`} />
            {LABELS.refresh}
          </Button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      {/* 본문 */}
      <div className="grid flex-1 min-h-0 min-w-0 grid-rows-[auto_1fr] gap-3">
        {/* 상단 카드 */}
        <div className="grid min-w-0 grid-cols-[2fr_2fr_2fr] gap-3">
          {/* E-SOP End Step 추가 카드 */}
          <div className="rounded-lg border bg-background p-4 shadow-sm">
            <div className="flex flex-col gap-3">
              <div className="space-y-1">
                <h2 className="text-base font-medium">{LABELS.addTitle}</h2>
                <p className="text-xs text-muted-foreground">{LABELS.addDescription}</p>
              </div>

              {formError ? (
                <p className="text-xs text-destructive" role="alert">
                  {formError}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">&nbsp;</p>
              )}

              <form
                className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 lg:items-end"
                onSubmit={handleCreate}
              >
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="main-step-input">
                    {LABELS.mainStep}
                  </label>
                  <Input
                    id="main-step-input"
                    value={formValues.mainStep}
                    onChange={(event) => handleFormChange("mainStep", event.target.value)}
                    placeholder="ex) AB123456"
                    required
                    maxLength={MAX_FIELD_LENGTH}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="custom-step-input">
                    {LABELS.customEndStep}
                  </label>
                  <Input
                    id="custom-step-input"
                    value={formValues.customEndStep}
                    onChange={(event) => handleFormChange("customEndStep", event.target.value)}
                    placeholder="조기 알람 받을 스텝"
                    maxLength={MAX_FIELD_LENGTH}
                  />
                </div>

                <div className="flex sm:justify-end lg:justify-start">
                  <Button type="submit" disabled={isCreating || !lineId} className="w-full sm:w-auto">
                    <IconPlus className="mr-1 size-4" />
                    {LABELS.addButton}
                  </Button>
                </div>
              </form>
            </div>
          </div>

          {/* User SDWT 카드 */}
          <div className="rounded-lg border bg-background p-4 shadow-sm">
            <div className="space-y-1 pb-3">
              <h2 className="text-base font-medium">{LABELS.badgesTitle}</h2>
              <p className="text-xs text-muted-foreground">{LABELS.badgesDescription}</p>

            </div>

            <div className="pt-1">
              <LineUserSdwtBadges lineId={lineId} values={userSdwtValues} />
            </div>
          </div>

          {/* Jira 카드 */}
          <div className="rounded-lg border bg-background p-4 shadow-sm">
            <div className="space-y-1 pb-3">
              <h2 className="text-base font-medium">{LABELS.jiraTitle}</h2>
              <p className="text-xs text-muted-foreground">{LABELS.jiraDescription}</p>
              <p className="text-xs text-muted-foreground">{LABELS.jiraHelper}</p>
            </div>

            {jiraKeyFormError ? (
              <p className="text-xs text-destructive" role="alert">
                {jiraKeyFormError}
              </p>
            ) : jiraKeyError ? (
              <p className="text-xs text-destructive" role="alert">
                {jiraKeyError}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">&nbsp;</p>
            )}

            {isSuperuser ? (
              <form
                className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] gap-3"
                onSubmit={handleJiraKeySave}
              >
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="jira-user-sdwt-select">
                    {LABELS.jiraUserSdwtLabel}
                  </label>
                  <Select
                    value={selectedUserSdwtProd || undefined}
                    onValueChange={setSelectedUserSdwtProd}
                    disabled={!lineId || userSdwtValues.length === 0 || isJiraKeyLoading}
                  >
                    <SelectTrigger id="jira-user-sdwt-select" className="w-full">
                      <SelectValue placeholder={LABELS.jiraUserSdwtPlaceholder} />
                    </SelectTrigger>
                    <SelectContent>
                      {userSdwtValues.map((value) => (
                        <SelectItem key={value} value={value}>
                          {value}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="jira-key-input">
                    {LABELS.jiraTitle}
                  </label>
                  <Input
                    id="jira-key-input"
                    value={jiraKeyDraft}
                    onChange={(event) => setJiraKeyDraft(event.target.value)}
                    placeholder={LABELS.jiraPlaceholder}
                    maxLength={MAX_JIRA_KEY_LENGTH}
                    disabled={!selectedUserSdwtProd || isJiraKeyLoading || isSavingJiraKey}
                  />
                </div>

                <div className="flex items-end justify-end">
                  <Button
                    type="submit"
                    disabled={!selectedUserSdwtProd || isJiraKeyLoading || isSavingJiraKey}
                    className="w-auto"
                  >
                    <IconDeviceFloppy className="mr-1 size-4" />
                    {LABELS.jiraSave}
                  </Button>
                </div>
              </form>
            ) : (
              <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="jira-user-sdwt-select">
                    {LABELS.jiraUserSdwtLabel}
                  </label>
                  <Select
                    value={selectedUserSdwtProd || undefined}
                    onValueChange={setSelectedUserSdwtProd}
                    disabled={!lineId || userSdwtValues.length === 0 || isJiraKeyLoading}
                  >
                    <SelectTrigger id="jira-user-sdwt-select" className="w-full">
                      <SelectValue placeholder={LABELS.jiraUserSdwtPlaceholder} />
                    </SelectTrigger>
                    <SelectContent>
                      {userSdwtValues.map((value) => (
                        <SelectItem key={value} value={value}>
                          {value}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="jira-key-input">
                    {LABELS.jiraTitle}
                  </label>
                  <Input
                    id="jira-key-input"
                    value={jiraKeyDraft}
                    placeholder={LABELS.jiraPlaceholder}
                    maxLength={MAX_JIRA_KEY_LENGTH}
                    disabled
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 테이블 */}
        <div className="min-h-0 min-w-0 overflow-hidden rounded-lg border bg-background">
          <div className="h-full min-h-0 min-w-0 overflow-auto">
            <Table stickyHeader className="w-full table-fixed">
              <colgroup>
                <col className="w-30" />
                <col className="w-40" />
                <col className="w-40" />
                <col className="w-32" />
                <col className="w-40" />
                <col className="w-60" />
              </colgroup>

              <TableHeader className="sticky top-0 z-10 bg-muted">
                <TableRow>
                  <TableHead className="text-center">{LABELS.lineId}</TableHead>
                  <TableHead className="text-center">{LABELS.mainStep}</TableHead>
                  <TableHead className="text-center">{LABELS.customEndStep}</TableHead>
                  <TableHead className="text-center">{LABELS.updatedBy}</TableHead>
                  <TableHead className="text-center">{LABELS.updatedAt}</TableHead>
                  <TableHead className="text-right" />
                </TableRow>
              </TableHeader>

              <TableBody>
                {isLoading && !hasLoadedOnce && (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center text-sm text-muted-foreground">
                      {LABELS.loading}
                    </TableCell>
                  </TableRow>
                )}

                {!isLoading && entries.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center text-sm text-muted-foreground">
                      {lineId ? LABELS.empty : "Select a line to view overrides."}
                    </TableCell>
                  </TableRow>
                )}

                {entries.map((entry) => {
                  const isEditing = editingId === entry.id
                  const isSaving = Boolean(savingMap[entry.id])
                  const rowError = rowErrors[entry.id]

                  return (
                    <React.Fragment key={entry.id}>
                      <TableRow className={isSaving ? "opacity-60" : ""}>
                        <TableCell className="text-center font-light">{entry.lineId || "-"}</TableCell>

                        <TableCell className="text-center">
                          {isEditing ? (
                            <Input
                              value={editDraft.mainStep}
                              onChange={(event) => handleEditChange("mainStep", event.target.value)}
                              maxLength={MAX_FIELD_LENGTH}
                              disabled={isSaving}
                              className="text-center"
                            />
                          ) : (
                            <span className="font-light">{entry.mainStep}</span>
                          )}
                        </TableCell>

                        <TableCell className="text-center font-light">
                          {isEditing ? (
                            <Input
                              value={editDraft.customEndStep ?? ""}
                              onChange={(event) => handleEditChange("customEndStep", event.target.value)}
                              maxLength={MAX_FIELD_LENGTH}
                              disabled={isSaving}
                              className="text-center"
                            />
                          ) : entry.customEndStep && entry.customEndStep.trim().length > 0 ? (
                            entry.customEndStep
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>

                        <TableCell className="text-center text-xs text-muted-foreground">
                          {entry.updatedBy || "-"}
                        </TableCell>

                        <TableCell className="text-center text-xs text-muted-foreground">
                          {formatUpdatedAt(entry.updatedAt)}
                        </TableCell>

                        <TableCell className="text-end">
                          <div className="inline-flex items-center justify-end gap-2">
                            {isEditing ? (
                              <>
                                <Button size="sm" onClick={handleSave} disabled={isSaving} className="gap-1">
                                  <IconDeviceFloppy className="size-4" />
                                  Save
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={cancelEditing}
                                  disabled={isSaving}
                                  className="gap-1"
                                >
                                  <IconX className="size-4" />
                                  Cancel
                                </Button>
                              </>
                            ) : (
                              <>
                                <Button size="sm" variant="ghost" onClick={() => startEditing(entry)} className="gap-1">
                                  <IconPencil className="size-4" />
                                  Edit
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleDelete(entry)}
                                  className="gap-1 text-destructive"
                                >
                                  <IconTrash className="size-4" />
                                  Delete
                                </Button>
                              </>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>

                      {rowError && (
                        <TableRow>
                          <TableCell
                            colSpan={6}
                            className="bg-destructive/5 px-4 py-2 text-center text-xs text-destructive"
                          >
                            {rowError}
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>
    </section>
  )
}
