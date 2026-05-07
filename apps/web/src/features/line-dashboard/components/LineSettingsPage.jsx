// 파일 경로: src/features/line-dashboard/components/LineSettingsPage.jsx
import * as React from "react"
import {
  IconDeviceFloppy,
  IconPencil,
  IconPlus,
  IconRefresh,
  IconSearch,
  IconSettings,
  IconTrash,
  IconUserPlus,
  IconUsers,
  IconX,
} from "@tabler/icons-react"
import { AlertCircleIcon, BadgeCheckIcon } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/common"
import { useAuth } from "@/lib/auth"
import { fetchAccountUserPool, fetchNotificationRecipientPermissions } from "../api"
import { useLineSettings } from "../hooks/useLineSettings"
import { buildToastOptions } from "../utils/toast"
import { formatUpdatedAt, isDuplicateMessage, normalizeDraft } from "../utils/lineSettings"

const LABELS = {
  titleSuffix: "Line E-SOP Settings",
  badgesTitle: "알림 Target",
  targetSelectLabel: "알림 Target",
  targetSelectPlaceholder: "알림 Target 선택",
  targetCreateLabel: "새 알림 Target",
  targetCreatePlaceholder: "ex) L1_NIGHT_SHIFT",
  targetCreate: "Target 추가",
  mailRecipientsTitle: "메일 수신인",
  mailRecipientsDescription: "선택한 알림 Target의 메일 수신인을 개별 사용자로 관리합니다.",
  mailRecipientsHelper: "소속에서 불러오기는 현재 소속 사용자를 한 번에 후보로 추가합니다.",
  recipientSourcePlaceholder: "소속 선택",
  recipientSearchPlaceholder: "이름/사번/Knox/email 검색",
  recipientSave: "수신인 저장",
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
const RECIPIENT_CHANNELS = [
  {
    channel: "mail",
    title: "메일 수신인",
    contactField: "email",
    countLabel: "메일 수신인",
    emptyText: "등록된 메일 수신인이 없습니다.",
    loadingText: "메일 수신인을 불러오는 중입니다.",
    permissionErrorText: "메일 수신인 변경 권한이 없습니다.",
    saveDescription: "메일 수신인 목록이 저장되었습니다.",
  },
  {
    channel: "messenger",
    title: "메신저 수신인",
    contactField: "knox_id",
    countLabel: "메신저 수신인",
    emptyText: "등록된 메신저 수신인이 없습니다.",
    loadingText: "메신저 수신인을 불러오는 중입니다.",
    permissionErrorText: "메신저 수신인 변경 권한이 없습니다.",
    saveDescription: "메신저 수신인 목록이 저장되었습니다.",
  },
]
const RECIPIENT_CHANNEL_CONFIG = RECIPIENT_CHANNELS.reduce((acc, config) => {
  acc[config.channel] = config
  return acc
}, {})

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
        라인을 선택하면 알림 Target 목록이 표시됩니다.
      </div>
    )
  }

  if (!values || values.length === 0) {
    return (
      <div className="inline-flex items-center gap-2 rounded-md bg-background px-2 py-1 text-[11px] text-muted-foreground">
        <AlertCircleIcon className="h-3 w-3" />
        등록된 알림 Target이 없습니다.
      </div>
    )
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-2 content-start gap-2 overflow-y-auto rounded-md border p-2">
      <span className="col-span-2 font-mono text-xs font-semibold text-foreground">{lineId} Line Target : </span>
      {values.map((value) => (
        <Badge key={value} variant="secondary" className="min-w-0 justify-start gap-1 text-[11px] font-mono">
          <BadgeCheckIcon className="h-3 w-3" />
          <span className="truncate">{value}</span>
        </Badge>
      ))}
    </div>
  )
}

function getRecipientPrimaryText(user) {
  return user?.displayName || user?.username || user?.knoxId || user?.sabun || `User ${user?.userId || user?.id}`
}

function getRecipientUserId(user) {
  const userId = Number.parseInt(user?.userId ?? user?.id, 10)
  return Number.isFinite(userId) && userId > 0 ? userId : null
}

function getRecipientSecondaryText(user) {
  const parts = [user?.userSdwtProd, user?.email, user?.knoxId].filter(Boolean)
  return parts.length ? parts.join(" · ") : "연락처 정보 없음"
}

function getRecipientListText(user) {
  const name =
    user?.displayName ||
    user?.username ||
    user?.sabun ||
    user?.knoxId ||
    `User ${user?.userId || user?.id}`
  const knoxId = user?.knoxId || ""
  const userSdwtProd = user?.userSdwtProd || ""
  const nameWithKnox = knoxId && name !== knoxId ? `${name}(${knoxId})` : name
  return userSdwtProd ? `${nameWithKnox}-${userSdwtProd}` : nameWithKnox
}

function mergeRecipientUsers(currentUsers, nextUsers) {
  const byId = new Map()
  for (const user of currentUsers || []) {
    const userId = getRecipientUserId(user)
    if (userId) {
      byId.set(userId, { ...user, userId, id: userId })
    }
  }
  for (const user of nextUsers || []) {
    const userId = getRecipientUserId(user)
    if (userId) {
      byId.set(userId, { ...user, userId, id: userId })
    }
  }
  return Array.from(byId.values()).sort((a, b) =>
    `${a.userSdwtProd || ""}${getRecipientPrimaryText(a)}`.localeCompare(
      `${b.userSdwtProd || ""}${getRecipientPrimaryText(b)}`,
    ),
  )
}

function sameUserSdwtProd(left, right) {
  return String(left || "").trim().toLowerCase() === String(right || "").trim().toLowerCase()
}

function getRecipientPickerUsers(results) {
  return mergeRecipientUsers(results?.group || [], results?.search || [])
}

function RecipientPickerUserList({
  users,
  selectedIds,
  isLoading,
  loadingText,
  emptyText,
  onToggleUser,
  onToggleAll,
}) {
  const visibleUserIds = users.map(getRecipientUserId).filter(Boolean)
  const selectedVisibleCount = visibleUserIds.filter((userId) => selectedIds.includes(userId)).length
  const allChecked = visibleUserIds.length > 0 && selectedVisibleCount === visibleUserIds.length
  const checked = allChecked ? true : selectedVisibleCount > 0 ? "indeterminate" : false

  if (isLoading) {
    return (
      <div className="rounded-md border px-3 py-8 text-center text-xs text-muted-foreground">
        {loadingText}
      </div>
    )
  }

  if (users.length === 0) {
    return (
      <div className="rounded-md border px-3 py-8 text-center text-xs text-muted-foreground">
        {emptyText}
      </div>
    )
  }

  return (
    <div className="grid min-h-0 grid-rows-[auto,1fr] overflow-hidden rounded-md border">
      <label className="flex items-center gap-2 border-b px-3 py-2 text-xs font-medium">
        <Checkbox
          checked={checked}
          onCheckedChange={(nextChecked) => onToggleAll(nextChecked === true)}
        />
        현재 결과 전체 선택
      </label>
      <div className="min-h-0 overflow-y-auto">
        {users.map((user) => {
          const userId = getRecipientUserId(user)
          if (!userId) return null
          return (
            <label
              key={userId}
              className="flex min-w-0 cursor-pointer items-center gap-3 border-b px-3 py-2 last:border-b-0"
            >
              <Checkbox
                checked={selectedIds.includes(userId)}
                onCheckedChange={(nextChecked) => onToggleUser(userId, nextChecked === true)}
              />
              <div className="min-w-0">
                <div className="truncate text-xs font-medium">{getRecipientListText(user)}</div>
                <div className="truncate text-[11px] text-muted-foreground">
                  {getRecipientSecondaryText(user)}
                </div>
              </div>
            </label>
          )
        })}
      </div>
    </div>
  )
}

function RecipientPickerDialog({
  open,
  activeTab,
  config,
  selectedUserSdwtProd,
  canManageRecipients,
  accountUserSdwtValues,
  sourceSdwt,
  onOpenChange,
  onTabChange,
  onSourceSdwtChange,
  isLoadingSourceUsers,
  onLoadSourceRecipients,
  searchValue,
  onSearchChange,
  isSearchingRecipients,
  onSearch,
  results,
  selectedIds,
  onToggleUser,
  onToggleAll,
  onApply,
  error,
}) {
  const groupUsers = results?.group || []
  const searchUsers = results?.search || []
  const selectableUsers = getRecipientPickerUsers(results)
  const selectedCount = selectableUsers.filter((user) => {
    const userId = getRecipientUserId(user)
    return userId && selectedIds.includes(userId)
  }).length

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[85vh] w-[min(760px,calc(100%-2rem))] max-w-[min(760px,calc(100%-2rem))] grid-rows-[auto,1fr,auto] overflow-hidden">
        <DialogHeader>
          <DialogTitle>{config.title} 선택</DialogTitle>
          <DialogDescription>
            {selectedUserSdwtProd || "알림 Target"}에 추가할 수신인을 선택한 뒤 적용합니다.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={onTabChange} className="min-h-0">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="group">소속에서 불러오기</TabsTrigger>
            <TabsTrigger value="search">이름 · KnoxID 검색</TabsTrigger>
          </TabsList>

          <TabsContent value="group" className="grid min-h-0 grid-rows-[auto,1fr] gap-3">
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
              <Select
                value={sourceSdwt || undefined}
                onValueChange={onSourceSdwtChange}
                disabled={!canManageRecipients || accountUserSdwtValues.length === 0}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={LABELS.recipientSourcePlaceholder} />
                </SelectTrigger>
                <SelectContent>
                  {accountUserSdwtValues.map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                type="button"
                variant="outline"
                onClick={onLoadSourceRecipients}
                disabled={!canManageRecipients || !sourceSdwt || isLoadingSourceUsers}
                className="gap-1"
              >
                <IconUsers className="size-4" />
                불러오기
              </Button>
            </div>

            <RecipientPickerUserList
              users={groupUsers}
              selectedIds={selectedIds}
              isLoading={isLoadingSourceUsers}
              loadingText="소속 사용자를 불러오는 중입니다."
              emptyText="소속을 선택하고 불러오기를 누르세요."
              onToggleUser={onToggleUser}
              onToggleAll={(checked) => onToggleAll(groupUsers, checked)}
            />
          </TabsContent>

          <TabsContent value="search" className="grid min-h-0 grid-rows-[auto,1fr] gap-3">
            <form className="grid grid-cols-[minmax(0,1fr)_auto] gap-2" onSubmit={onSearch}>
              <Input
                value={searchValue}
                onChange={(event) => onSearchChange(event.target.value)}
                placeholder={LABELS.recipientSearchPlaceholder}
                disabled={!canManageRecipients || isSearchingRecipients}
              />
              <Button
                type="submit"
                variant="outline"
                disabled={!canManageRecipients || isSearchingRecipients}
                className="gap-1"
              >
                <IconSearch className="size-4" />
                검색
              </Button>
            </form>

            <RecipientPickerUserList
              users={searchUsers}
              selectedIds={selectedIds}
              isLoading={isSearchingRecipients}
              loadingText="사용자를 검색하는 중입니다."
              emptyText="검색어를 입력하고 검색을 누르세요."
              onToggleUser={onToggleUser}
              onToggleAll={(checked) => onToggleAll(searchUsers, checked)}
            />
          </TabsContent>
        </Tabs>

        <DialogFooter className="items-center gap-2 sm:justify-between">
          <div className="min-w-0 text-xs text-muted-foreground">
            {error ? <span className="text-destructive">{error}</span> : `${selectedCount}명 선택됨`}
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              취소
            </Button>
            <Button type="button" onClick={onApply} disabled={!canManageRecipients || selectedCount === 0}>
              <IconUserPlus className="mr-1 size-4" />
              선택 인원 적용
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function RecipientChannelCard({
  config,
  selectedUserSdwtProd,
  canManageRecipients,
  recipients,
  isLoadingRecipients,
  onRemoveUser,
  onSave,
  onOpenPicker,
  isDraftCurrent,
  isSavingRecipients,
  error,
}) {
  const saveDisabled = !selectedUserSdwtProd || !canManageRecipients
  const pickerDisabled = !selectedUserSdwtProd

  return (
    <div className="flex h-full min-h-0 flex-col rounded-lg border bg-background p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3 pb-3">
        <div className="min-w-0 space-y-1">
          <h2 className="text-base font-medium">{config.title}</h2>
          {error ? (
            <p className="text-xs text-destructive" role="alert">
              {error}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              {selectedUserSdwtProd
                ? `${selectedUserSdwtProd} ${recipients.length}명`
                : "알림 Target을 선택하세요."}
              {selectedUserSdwtProd && !canManageRecipients ? " · 변경 권한 없음" : ""}
            </p>
          )}
        </div>
        <Button
          type="button"
          size="sm"
          onClick={() => onSave(config.channel)}
          disabled={saveDisabled || !isDraftCurrent || isSavingRecipients || isLoadingRecipients}
          className="shrink-0 gap-1"
        >
          <IconDeviceFloppy className="size-4" />
          {LABELS.recipientSave}
        </Button>
      </div>

      <div className="flex flex-1 min-h-0 flex-col gap-3">
        <Button
          type="button"
          variant="outline"
          onClick={() => onOpenPicker(config.channel)}
          disabled={pickerDisabled}
          className="justify-start gap-1"
        >
          <IconUserPlus className="size-4" />
          수신인 검색/추가
        </Button>

        <div className="min-h-64 flex-1 overflow-y-auto rounded-md border">
          {isLoadingRecipients ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">{config.loadingText}</div>
          ) : recipients.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">{config.emptyText}</div>
          ) : (
            recipients.map((recipient) => (
              <div
                key={recipient.userId}
                className="flex min-w-0 items-center justify-between gap-2 border-b px-3 py-2 last:border-b-0"
              >
                <div className="min-w-0">
                  <div className="truncate text-xs font-medium">{getRecipientListText(recipient)}</div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => onRemoveUser(config.channel, recipient)}
                  disabled={!canManageRecipients}
                  className="h-7 shrink-0 text-destructive"
                >
                  제거
                </Button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

export function LineSettingsPage({ lineId = "" }) {
  const { user } = useAuth()
  const [selectedUserSdwtProd, setSelectedUserSdwtProd] = React.useState("")
  const [isGlobalOperator, setIsGlobalOperator] = React.useState(false)
  const {
    entries,
    userSdwtValues,
    mailRecipients,
    mailRecipientsTargetUserSdwtProd,
    messengerRecipients,
    messengerRecipientsTargetUserSdwtProd,
    mailRecipientsError,
    messengerRecipientsError,
    error,
    isLoading,
    isMailRecipientsLoading,
    isMessengerRecipientsLoading,
    hasLoadedOnce,
    lastUpdatedLabel,
    refresh,
    createEntry,
    updateEntry,
    deleteEntry,
    createTarget,
    updateMailRecipients,
    updateMessengerRecipients,
  } = useLineSettings({
    lineId,
    userSdwtProd: selectedUserSdwtProd,
    loadRecipients: isGlobalOperator,
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
  const [recipientSourceSdwt, setRecipientSourceSdwt] = React.useState({ mail: "", messenger: "" })
  const [accountUserSdwtValues, setAccountUserSdwtValues] = React.useState([])
  const [recipientActionErrors, setRecipientActionErrors] = React.useState({ mail: null, messenger: null })
  const [isSearchingRecipients, setIsSearchingRecipients] = React.useState({ mail: false, messenger: false })
  const [isLoadingSourceUsers, setIsLoadingSourceUsers] = React.useState({ mail: false, messenger: false })
  const [isSavingRecipients, setIsSavingRecipients] = React.useState({ mail: false, messenger: false })
  const recipientContextRef = React.useRef({ lineId, selectedUserSdwtProd })
  const sourceLoadRequestRef = React.useRef({ mail: 0, messenger: 0 })
  recipientContextRef.current = { lineId, selectedUserSdwtProd }

  const isRefreshing = isLoading && hasLoadedOnce
  const canManageRecipients = Boolean(selectedUserSdwtProd && isGlobalOperator)
  const canCreateTarget = Boolean(lineId && isGlobalOperator)
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

  const handleRefresh = React.useCallback(() => {
    if (!lineId) return
    refresh()
  }, [lineId, refresh])

  const handleFormChange = React.useCallback((key, value) => {
    setFormValues((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleRecipientSourceSdwtChange = React.useCallback((channel, value) => {
    setRecipientSourceSdwt((prev) => ({ ...prev, [channel]: value }))
  }, [])

  const handleRecipientSearchChange = React.useCallback((channel, value) => {
    setRecipientSearches((prev) => ({ ...prev, [channel]: value }))
  }, [])

  const handleRecipientPickerOpenChange = React.useCallback((channel, open) => {
    setRecipientPickerOpen((prev) => ({ ...prev, [channel]: open }))
  }, [])

  const handleRecipientPickerTabChange = React.useCallback((channel, value) => {
    setRecipientPickerTabs((prev) => ({ ...prev, [channel]: value }))
  }, [])

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
    },
    [canManageRecipients, selectedUserSdwtProd],
  )

  const handleRecipientPickerUserToggle = React.useCallback((channel, userId, checked) => {
    setRecipientPickerSelectedIds((prev) => {
      const current = new Set(prev[channel] || [])
      if (checked) {
        current.add(userId)
      } else {
        current.delete(userId)
      }
      return { ...prev, [channel]: Array.from(current) }
    })
  }, [])

  const handleRecipientPickerAllToggle = React.useCallback((channel, users, checked) => {
    setRecipientPickerSelectedIds((prev) => {
      const current = new Set(prev[channel] || [])
      for (const user of users || []) {
        const userId = getRecipientUserId(user)
        if (!userId) continue
        if (checked) {
          current.add(userId)
        } else {
          current.delete(userId)
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

  React.useEffect(() => {
    sourceLoadRequestRef.current.mail += 1
    sourceLoadRequestRef.current.messenger += 1
    setRecipientDrafts({ mail: [], messenger: [] })
    setRecipientDraftTargets({ mail: selectedUserSdwtProd || "", messenger: selectedUserSdwtProd || "" })
    setRecipientActionErrors({ mail: null, messenger: null })
    setRecipientPickerOpen({ mail: false, messenger: false })
    setRecipientPickerResults({ mail: { group: [], search: [] }, messenger: { group: [], search: [] } })
    setRecipientPickerSelectedIds({ mail: [], messenger: [] })
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

    async function loadRecipientOptions() {
      try {
        const [{ userSdwtProds }, permissionContext] = await Promise.all([
          fetchAccountUserPool({ limit: 1 }),
          fetchNotificationRecipientPermissions(),
        ])
        if (isActive) {
          setAccountUserSdwtValues(userSdwtProds || [])
          setIsGlobalOperator(Boolean(permissionContext?.isOperator))
        }
      } catch (requestError) {
        if (isActive) {
          const message =
            requestError instanceof Error ? requestError.message : "Failed to load user groups"
          setIsGlobalOperator(false)
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
    if (normalized.length > 64) {
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
        toast.success("Target 추가 완료", {
          description: `${target.targetUserSdwtProd} 알림 Target이 추가되었습니다.`,
          icon: <IconPlus className="h-5 w-5 text-[var(--normal-text)]" />,
          ...buildToastOptions({ intent: "success" }),
        })
      }
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to create target"
      setTargetFormError(message)
      showRequestErrorToast(message)
    } finally {
      setIsCreatingTarget(false)
    }
  }, [canCreateTarget, createTarget, lineId, newTargetDraft])

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
        })
        const previousSearchIds = new Set(
          (recipientPickerResults[channel]?.search || []).map(getRecipientUserId).filter(Boolean),
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
    const removeId = Number.parseInt(userToRemove?.userId ?? userToRemove?.id, 10)
    if (!Number.isFinite(removeId)) return
    setRecipientDrafts((prev) => ({
      ...prev,
      [channel]: prev[channel].filter((item) => Number.parseInt(item?.userId ?? item?.id, 10) !== removeId),
    }))
  }, [canManageRecipients])

  const handleLoadSourceRecipients = React.useCallback(async (channel) => {
    const config = RECIPIENT_CHANNEL_CONFIG[channel]
    const sourceSdwt = recipientSourceSdwt[channel]
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
      (recipientPickerResults[channel]?.group || []).map(getRecipientUserId).filter(Boolean),
    )
    const isCurrentLoad = () =>
      sourceLoadRequestRef.current[channel] === requestId &&
      isCurrentRecipientContext(requestLineId, requestTarget)
    try {
      const { results } = await fetchAccountUserPool({
        userSdwtProd: requestSourceSdwt,
        contactField: config.contactField,
        limit: "all",
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
        const current = new Set((prev[channel] || []).filter((userId) => !previousGroupIds.has(userId)))
        for (const user of loadedUsers) {
          const userId = getRecipientUserId(user)
          if (userId) current.add(userId)
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
      const userId = getRecipientUserId(user)
      return userId && selectedIds.has(userId)
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
    toast.success("수신인 후보 추가", {
      description: `${selectedUsers.length}명을 수신인 목록에 추가했습니다.`,
      icon: <IconUsers className="h-5 w-5 text-[var(--normal-text)]" />,
      ...buildToastOptions({ intent: "success" }),
    })
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
        .map((item) => Number.parseInt(item?.userId ?? item?.id, 10))
        .filter((value) => Number.isFinite(value) && value > 0)
      const updater = channel === "messenger" ? updateMessengerRecipients : updateMailRecipients
      const result = await updater({ userIds })
      if (result?.stale) {
        return
      }
      toast.success("저장 완료", {
        description: config.saveDescription,
        icon: <IconDeviceFloppy className="h-5 w-5 text-[var(--normal-text)]" />,
        ...buildToastOptions({ intent: "success" }),
      })
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
    selectedUserSdwtProd,
    updateMailRecipients,
    updateMessengerRecipients,
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
        <div className="grid min-w-0 grid-cols-1 gap-3 xl:grid-cols-2">
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

          {/* 알림 Target 카드 */}
          <div className="grid h-full min-h-0 grid-cols-2 grid-rows-[auto,auto,1fr] gap-3 rounded-lg border bg-background p-4 shadow-sm">
            <div className="space-y-1 pb-3">
              <h2 className="text-base font-medium">{LABELS.badgesTitle}</h2>
            </div>

            {targetFormError ? (
              <p className="text-xs text-destructive" role="alert">
                {targetFormError}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">&nbsp;</p>
            )}

            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="target-user-sdwt-select">
                {LABELS.targetSelectLabel}
              </label>
              <Select
                value={selectedUserSdwtProd || undefined}
                onValueChange={setSelectedUserSdwtProd}
                disabled={!lineId || userSdwtValues.length === 0}
              >
                <SelectTrigger id="target-user-sdwt-select" className="w-full">
                  <SelectValue placeholder={LABELS.targetSelectPlaceholder} />
                </SelectTrigger>
                <SelectContent>
                  {userSdwtValues.map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <label className="pt-2 text-xs font-medium text-muted-foreground" htmlFor="target-create-input">
                {LABELS.targetCreateLabel}
              </label>
              <div className="flex gap-2">
                <Input
                  id="target-create-input"
                  value={newTargetDraft}
                  onChange={(event) => setNewTargetDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault()
                      void handleCreateTarget()
                    }
                  }}
                  placeholder={LABELS.targetCreatePlaceholder}
                  maxLength={64}
                  disabled={!lineId || !canCreateTarget || isCreatingTarget}
                  className="h-8 text-xs"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleCreateTarget}
                  disabled={!lineId || !canCreateTarget || isCreatingTarget || !newTargetDraft.trim()}
                  className="h-8 shrink-0"
                >
                  <IconPlus className="mr-1 size-3" />
                  {LABELS.targetCreate}
                </Button>
              </div>
              {!canCreateTarget ? (
                <p className="text-[11px] text-muted-foreground">
                  알림 Target 추가는 operator 권한과 선택된 line이 필요합니다.
                </p>
              ) : null}
            </div>

            <div className="col-start-2 row-span-3 row-start-1 h-full min-h-0 min-w-0">
              <LineUserSdwtBadges lineId={lineId} values={userSdwtValues} />
            </div>
          </div>
        </div>

        {/* 수신인 및 테이블 카드 */}
        <div className="grid min-h-0 min-w-0 grid-cols-1 gap-3 xl:grid-cols-4">
          {RECIPIENT_CHANNELS.map((config) => (
            <React.Fragment key={config.channel}>
              <RecipientChannelCard
                config={config}
                selectedUserSdwtProd={selectedUserSdwtProd}
                canManageRecipients={canManageRecipients}
                recipients={currentRecipientDrafts[config.channel] || []}
                isLoadingRecipients={
                  config.channel === "messenger" ? isMessengerRecipientsLoading : isMailRecipientsLoading
                }
                onRemoveUser={handleRemoveRecipientUser}
                onSave={handleRecipientsSave}
                onOpenPicker={handleOpenRecipientPicker}
                isDraftCurrent={Boolean(isRecipientDraftCurrent[config.channel])}
                isSavingRecipients={Boolean(isSavingRecipients[config.channel])}
                error={
                  recipientActionErrors[config.channel] ||
                  (config.channel === "messenger" ? messengerRecipientsError : mailRecipientsError)
                }
              />
              <RecipientPickerDialog
                open={Boolean(recipientPickerOpen[config.channel])}
                activeTab={recipientPickerTabs[config.channel] || "group"}
                config={config}
                selectedUserSdwtProd={selectedUserSdwtProd}
                canManageRecipients={canManageRecipients}
                accountUserSdwtValues={accountUserSdwtValues}
                sourceSdwt={recipientSourceSdwt[config.channel] || ""}
                onOpenChange={(open) => handleRecipientPickerOpenChange(config.channel, open)}
                onTabChange={(value) => handleRecipientPickerTabChange(config.channel, value)}
                onSourceSdwtChange={(value) => handleRecipientSourceSdwtChange(config.channel, value)}
                isLoadingSourceUsers={Boolean(isLoadingSourceUsers[config.channel])}
                onLoadSourceRecipients={() => handleLoadSourceRecipients(config.channel)}
                searchValue={recipientSearches[config.channel] || ""}
                onSearchChange={(value) => handleRecipientSearchChange(config.channel, value)}
                isSearchingRecipients={Boolean(isSearchingRecipients[config.channel])}
                onSearch={(event) => handleRecipientSearch(config.channel, event)}
                results={recipientPickerResults[config.channel] || { group: [], search: [] }}
                selectedIds={recipientPickerSelectedIds[config.channel] || []}
                onToggleUser={(userId, checked) =>
                  handleRecipientPickerUserToggle(config.channel, userId, checked)
                }
                onToggleAll={(users, checked) =>
                  handleRecipientPickerAllToggle(config.channel, users, checked)
                }
                onApply={() => handleApplyRecipientPicker(config.channel)}
                error={recipientActionErrors[config.channel]}
              />
            </React.Fragment>
          ))}

          {/* 테이블 */}
          <div className="min-h-0 min-w-0 overflow-hidden rounded-lg border bg-background xl:order-first xl:col-span-2">
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
      </div>
    </section>
  )
}
