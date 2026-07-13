import { useEffect, useState } from "react"
import { toast } from "sonner"
import {
  AlertTriangle,
  Ban,
  Check,
  Clock3,
  Eye,
  History,
  MoreHorizontal,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useAuth } from "@/lib/auth"

import { AccountDataTable } from "../components/AccountDataTable"
import { AppPermissionMatrix } from "../components/AppPermissionMatrix"
import {
  useAccessAuditLogs,
  useAccessMatrix,
  useAccessPolicyRules,
  useAccessUserDecision,
  useAccessUsers,
  useCreateAccessPolicyRule,
  useDeleteAccessPolicyRule,
  useUpdateAccessPolicyRule,
} from "../hooks/useAccountData"
import { formatAccountDateValue } from "../utils/accountOverview"

const PAGE_SIZE = 20

const INITIAL_MATRIX_FILTERS = {
  search: "",
  department: "",
}

const INITIAL_MATRIX_FILTER_DRAFT = {
  search: "",
  department: "",
}

const INITIAL_POLICY_FORM = {
  value: "",
  role: "viewer",
  isActive: true,
}

const ROLE_OPTIONS = [
  { value: "viewer", label: "Portal 조회 역할" },
  { value: "member", label: "Portal 일반 역할" },
  { value: "manager", label: "Portal 운영 역할" },
  { value: "admin", label: "Portal 관리자 역할" },
]

const APP_SCOPE_LABELS = {
  "access-stats": "접속 현황",
  appstore: "Appstore",
  assistant: "Assistant",
  emails: "메일함",
  "l0-spider": "L0 Spider",
  "l1-spider": "L1 Spider",
  "l3-spider": "L3 Spider",
  "line-dashboard": "ESOP Dashboard",
  observer: "Observer",
  "pm-spider": "PM Spider",
  teamstaff: "Team",
  "tttm-spider": "TTTM Spider",
  voc: "VoE",
}

const ACTION_LABELS = {
  request: "승인 요청",
  approve: "승인",
  reject: "거절",
  grant: "직접 부여",
  revoke: "회수",
  reset_to_policy: "수동 설정 해제",
  change_role: "Portal 역할 변경",
  user_access_update: "접근 상태 변경",
  policy_create: "자동 규칙 추가",
  policy_update: "자동 규칙 수정",
  policy_delete: "자동 규칙 삭제",
  scope_create: "권한 범위 생성",
  scope_update: "권한 범위 수정",
  scope_delete: "권한 범위 삭제",
  access_manager_grant: "권한 관리자 지정",
  access_manager_revoke: "권한 관리자 해제",
}

const STATUS_LABELS = {
  allowed: "허용",
  pending: "대기",
  denied: "차단",
  not_requested: "미요청",
  inactive: "비활성",
}

const SOURCE_LABELS = {
  portal_access_required: "Portal 차단 우선",
  explicit_allowed: "개별 허용",
  explicit_denied: "개별 차단",
  explicit_pending: "개별 승인 대기",
  policy_department: "부서 자동 규칙",
  superuser_bypass: "슈퍼유저 우회",
  none: "결정 기준 없음",
  scope_inactive: "권한 범위 비활성",
  scope_not_found: "권한 범위 없음",
  admin: "슈퍼유저 우회",
}
const ROLE_LABELS = Object.fromEntries(ROLE_OPTIONS.map((option) => [option.value, option.label]))
const RULE_TYPE_LABELS = { department: "부서 일치" }

const MUTATION_ERROR_LABELS = {
  app_role_not_supported: "앱 권한은 허용 또는 차단으로만 변경할 수 있습니다.",
  duplicate_policy_rule: "동일한 자동 접근 규칙이 이미 등록되어 있습니다.",
  forbidden: "권한 관리 권한이 없습니다.",
  invalid_policy_rule: "적용 조건 형식을 확인해 주세요.",
  invalid_role: "지원하지 않는 권한입니다.",
  invalid_status_transition: "이미 상태가 변경되었습니다. 목록을 새로고침해 주세요.",
  role_required: "변경할 권한을 선택해 주세요.",
}

function isSuperuserBypass(access) {
  return access?.source === "superuser_bypass" || access?.source === "admin"
}

function getMutationErrorMessage(error, fallback) {
  const message = error?.message || ""
  if (MUTATION_ERROR_LABELS[message]) return MUTATION_ERROR_LABELS[message]
  if (!message || message.startsWith("Failed to") || /failed to fetch|networkerror/i.test(message)) {
    return fallback
  }
  return message
}

function getAuditIdentity(user) {
  return user?.knoxId || user?.username || user?.email || (user?.id ? `#${user.id}` : "-")
}

function formatAuditValue(field, value) {
  if (value === undefined || value === null || value === "") return "-"
  if (field === "status") return STATUS_LABELS[value] || value
  if (field === "role") return ROLE_LABELS[value] || value
  if (field === "defaultRole") return ROLE_LABELS[value] || value
  if (field === "ruleType") return RULE_TYPE_LABELS[value] || value
  if (field === "isActive") return value ? "사용" : "사용 안 함"
  if (field === "requestable") return value ? "가능" : "불가"
  if (field === "canManageAccess") return value ? "있음" : "없음"
  if (field === "source") return SOURCE_LABELS[value] || value
  return String(value)
}

function getAuditSnapshotValue(snapshot, field) {
  if (!snapshot || typeof snapshot !== "object") return undefined
  if (field === "status") return snapshot.status ?? snapshot.effectiveStatus
  return snapshot[field]
}

function getAuditChanges(row) {
  const fields = [
    "status",
    "role",
    "isActive",
    "ruleType",
    "value",
    "source",
    "key",
    "name",
    "scopeType",
    "requestable",
    "defaultRole",
    "canManageAccess",
  ]
  return fields.flatMap((field) => {
    const before = getAuditSnapshotValue(row.before, field)
    const after = getAuditSnapshotValue(row.after, field)
    if (before === undefined && after === undefined) return []
    if (before === after) return []
    const label = {
      status: "상태",
      role: "Portal 접근 역할",
      isActive: "사용 여부",
      ruleType: "적용 기준",
      value: "적용 조건",
      source: "결정 기준",
      key: "키",
      name: "이름",
      scopeType: "권한 범위 유형",
      requestable: "요청 가능",
      defaultRole: "기본 Portal 역할",
      canManageAccess: "권한 관리",
    }[field]
    return [`${label}: ${formatAuditValue(field, before)} -> ${formatAuditValue(field, after)}`]
  })
}

function formatCount(value) {
  return Number(value || 0).toLocaleString("ko-KR")
}

function buildAccessScopeOptions(appAccess) {
  const appScopeOptions = Object.keys(appAccess || {})
    .sort((left, right) => (APP_SCOPE_LABELS[left] || left).localeCompare(APP_SCOPE_LABELS[right] || right, "ko"))
    .map((scopeKey) => ({ value: scopeKey, label: APP_SCOPE_LABELS[scopeKey] || scopeKey }))
  return [{ value: "portal", label: "Portal" }, ...appScopeOptions]
}

function getStatusVariant(status) {
  if (status === "allowed") return "default"
  if (status === "pending") return "secondary"
  if (status === "denied") return "destructive"
  return "outline"
}

function getSummaryToneClass(tone) {
  if (tone === "primary") return "bg-primary/10 text-primary"
  if (tone === "destructive") return "bg-destructive/10 text-destructive"
  if (tone === "secondary") return "bg-secondary text-secondary-foreground"
  return "bg-muted text-muted-foreground"
}

function SummaryTile({ icon: Icon, label, value, detail, tone = "muted", isLoading = false }) {
  return (
    <div className="min-w-0 rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          {isLoading ? (
            <Skeleton className="mt-2 h-7 w-20" />
          ) : (
            <p className="mt-1 truncate text-2xl font-semibold tabular-nums text-foreground">
              {formatCount(value)}
            </p>
          )}
        </div>
        <div className={`flex size-10 shrink-0 items-center justify-center rounded-md ${getSummaryToneClass(tone)}`}>
          <Icon className="size-4" />
        </div>
      </div>
      {detail ? <p className="mt-2 truncate text-xs text-muted-foreground">{detail}</p> : null}
    </div>
  )
}

function DesktopSummaryMetric({ icon: Icon, label, value, detail, tone = "muted", isLoading = false }) {
  return (
    <div className="flex min-w-0 items-center gap-3 border-r px-4 py-3 last:border-r-0">
      <div className={`flex size-9 shrink-0 items-center justify-center rounded-md ${getSummaryToneClass(tone)}`}>
        <Icon className="size-4" />
      </div>
      <div className="min-w-0">
        <p className="truncate text-xs font-medium text-muted-foreground">{label}</p>
        <p className="truncate text-xs text-muted-foreground">{detail}</p>
      </div>
      {isLoading ? (
        <Skeleton className="ml-auto h-7 w-14 shrink-0" />
      ) : (
        <p className="ml-auto shrink-0 text-xl font-semibold tabular-nums text-foreground">
          {formatCount(value)}
        </p>
      )}
    </div>
  )
}

function Pager({ pagination, onPageChange, disabled = false }) {
  const page = pagination?.page || 1
  const pageSize = pagination?.pageSize || PAGE_SIZE
  const total = pagination?.total || 0
  const totalPages = pagination?.totalPages || 1
  const canPrevious = page > 1
  const canNext = page < totalPages
  const start = total > 0 ? (page - 1) * pageSize + 1 : 0
  const end = total > 0 ? Math.min(page * pageSize, total) : 0

  return (
    <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
      <p className="text-xs text-muted-foreground">
        표시 {formatCount(start)}-{formatCount(end)} / 총 {formatCount(total)}
      </p>
      <Pagination className="mx-0 w-auto justify-end">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              href="#"
              aria-label="이전 페이지"
              title="이전 페이지"
              aria-disabled={!canPrevious || disabled}
              tabIndex={!canPrevious || disabled ? -1 : undefined}
              className={`xl:size-8 xl:p-0 xl:[&>span]:hidden ${
                !canPrevious || disabled ? "pointer-events-none opacity-50" : ""
              }`}
              onClick={(event) => {
                event.preventDefault()
                if (canPrevious && !disabled) onPageChange(page - 1)
              }}
            />
          </PaginationItem>
          <PaginationItem>
            <PaginationNext
              href="#"
              aria-label="다음 페이지"
              title="다음 페이지"
              aria-disabled={!canNext || disabled}
              tabIndex={!canNext || disabled ? -1 : undefined}
              className={`xl:size-8 xl:p-0 xl:[&>span]:hidden ${
                !canNext || disabled ? "pointer-events-none opacity-50" : ""
              }`}
              onClick={(event) => {
                event.preventDefault()
                if (canNext && !disabled) onPageChange(page + 1)
              }}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  )
}

function ErrorState({ error, onRetry }) {
  const message = error?.message === "forbidden" ? "권한 관리 권한이 없습니다." : "데이터를 불러오지 못했습니다."
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-4" role="alert">
      <p className="text-sm text-destructive">{message}</p>
      {onRetry ? (
        <Button type="button" size="sm" variant="outline" onClick={() => onRetry()}>
          <RefreshCw className="size-4" />
          다시 시도
        </Button>
      ) : null}
    </div>
  )
}

function AccessStatusBadge({ access }) {
  const status = access?.effectiveStatus || "not_requested"
  return <Badge variant={getStatusVariant(status)}>{STATUS_LABELS[status] || status}</Badge>
}

function AccessSourceMeta({ access }) {
  const source = access?.source
  const policy = access?.policy
  const policyLabel =
    policy?.matched && policy?.ruleType
      ? `${RULE_TYPE_LABELS[policy.ruleType] || policy.ruleType} / ${policy.value || "-"}`
      : ""

  return (
    <span className="inline-flex min-w-0 items-center gap-1.5">
      <Badge variant="outline">{SOURCE_LABELS[source] || source || "-"}</Badge>
      {policyLabel ? (
        <span className="max-w-56 truncate text-xs text-muted-foreground" title={policyLabel}>
          {policyLabel}
        </span>
      ) : null}
    </span>
  )
}

function getUserInitials(user) {
  const label = user?.displayName || user?.username || user?.knoxId || "?"
  const parts = label.trim().split(/\s+/).filter(Boolean)
  if (parts.length > 1) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return label.slice(0, 2).toUpperCase()
}

function UserIdentity({ user }) {
  const name = user?.displayName || user?.username || user?.knoxId || "미지정"
  const identifier = user?.knoxId || user?.sabun || "-"
  return (
    <div className="flex min-w-0 items-center gap-3 whitespace-nowrap">
      <Avatar className="size-9 border">
        <AvatarFallback className="text-xs font-medium text-muted-foreground">
          {getUserInitials(user)}
        </AvatarFallback>
      </Avatar>
      <span className="flex min-w-0 items-center gap-1.5">
        <span className="truncate font-medium">{name}</span>
        <span className="text-xs text-muted-foreground">/</span>
        <span className="truncate text-xs text-muted-foreground">{identifier}</span>
      </span>
    </div>
  )
}

function RoleIndicator({ role }) {
  const Icon = role === "admin" || role === "manager" ? ShieldCheck : role === "member" ? Users : Eye
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <Icon className="size-4 text-muted-foreground" />
      <span>{ROLE_LABELS[role] || role || "-"}</span>
    </span>
  )
}

function DecisionDialog({ decision, onOpenChange, onSubmit, isSubmitting, errorMessage }) {
  const [role, setRole] = useState("viewer")
  const [reason, setReason] = useState("")

  useEffect(() => {
    setRole(decision?.role || "viewer")
    setReason("")
  }, [decision])

  if (!decision) return null

  const requiresRole = ["approve", "grant", "change_role"].includes(decision.action)
  const requiresReason = ["reject", "revoke"].includes(decision.action)
  const actionLabel = decision.label || ACTION_LABELS[decision.action] || decision.action
  const ActionIcon = {
    approve: Check,
    reject: Ban,
    grant: UserPlus,
    revoke: Ban,
    reset_to_policy: RotateCcw,
    change_role: SlidersHorizontal,
  }[decision.action] || Save

  const handleSubmit = async () => {
    if (isSubmitting) return
    await onSubmit({
      userId: decision.row.user.id,
      scope: decision.scope?.key,
      action: decision.action,
      role: requiresRole ? role : undefined,
      reason: requiresReason || reason.trim() ? reason.trim() : undefined,
    })
  }

  return (
    <Dialog
      open={Boolean(decision)}
      onOpenChange={(open) => {
        if (!isSubmitting) onOpenChange(open)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{actionLabel}</DialogTitle>
          <DialogDescription>
            <span>{decision.row.user.displayName || decision.row.user.knoxId}</span>
            {decision.scope ? (
              <span className="mt-1 block">권한 범위: {decision.scope.name}</span>
            ) : null}
            {decision.action === "reset_to_policy" ? (
              <span className="mt-1 hidden xl:block">
                직접 지정한 상태를 제거하고 자동 접근 규칙의 판정으로 전환합니다.
              </span>
            ) : null}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          {requiresRole ? (
            <div className="grid gap-2">
              <Label htmlFor="access-role">Portal 접근 역할</Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger id="access-role" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
          {requiresReason ? (
            <div className="grid gap-2">
              <Label htmlFor="access-reason">사유 (선택)</Label>
              <Textarea
                id="access-reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="사유를 입력하세요"
                maxLength={500}
              />
            </div>
          ) : null}
          {errorMessage ? (
            <p className="text-sm text-destructive" role="alert">
              {errorMessage}
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            취소
          </Button>
          <Button
            variant={["reject", "revoke"].includes(decision.action) ? "destructive" : "default"}
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <RefreshCw className="size-4 animate-spin" />
            ) : (
              <>
                <Save className="size-4 xl:hidden" />
                <ActionIcon className="hidden size-4 xl:block" />
              </>
            )}
            {isSubmitting ? (
              <>
                <span className="xl:hidden">저장 중</span>
                <span className="hidden xl:inline">처리 중</span>
              </>
            ) : (
              <>
                <span className="xl:hidden">저장</span>
                <span className="hidden xl:inline">{actionLabel}</span>
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ConfirmActionDialog({
  open,
  title,
  description,
  confirmLabel = "확인",
  isSubmitting,
  onOpenChange,
  onConfirm,
  errorMessage = "",
  confirmIcon: ConfirmIcon = Trash2,
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!isSubmitting) onOpenChange(nextOpen)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-destructive/10 text-destructive">
              <AlertTriangle className="size-5" />
            </div>
            <div className="min-w-0">
              <DialogTitle>{title}</DialogTitle>
              <DialogDescription className="mt-1">{description}</DialogDescription>
            </div>
          </div>
        </DialogHeader>
        {errorMessage ? (
          <p className="text-sm text-destructive" role="alert">
            {errorMessage}
          </p>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            취소
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isSubmitting}>
            {isSubmitting ? <RefreshCw className="size-4 animate-spin" /> : <ConfirmIcon className="size-4" />}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function UserActions({ row, onDecision, disabled = false }) {
  const access = row.access || {}
  const explicitStatus = access.explicitStatus
  const status = access.effectiveStatus
  const userLabel = row.user.displayName || row.user.knoxId || row.user.username || "사용자"

  if (isSuperuserBypass(access)) {
    return <span className="whitespace-nowrap text-xs text-muted-foreground">슈퍼유저 권한으로 허용</span>
  }

  const primaryAction = status === "pending"
    ? { action: "approve", label: "승인", icon: Check, variant: "default" }
    : status === "allowed"
      ? { action: "change_role", label: "Portal 역할 변경", icon: SlidersHorizontal, variant: "outline" }
      : ["denied", "not_requested"].includes(status)
        ? { action: "grant", label: "직접 부여", icon: UserPlus, variant: "default" }
        : null
  const PrimaryIcon = primaryAction?.icon
  const hasMoreActions = status === "pending" || status === "allowed" || Boolean(explicitStatus)

  return (
    <>
      <div className="flex items-center justify-end gap-2 whitespace-nowrap xl:hidden">
        {status === "pending" ? (
          <>
            <Button
              size="sm"
              onClick={() => onDecision(row, "approve")}
              disabled={disabled}
              aria-label={`${userLabel} 승인`}
            >
              <Check className="size-4" />
              승인
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => onDecision(row, "reject")}
              disabled={disabled}
              aria-label={`${userLabel} 거절`}
            >
              <Ban className="size-4" />
              거절
            </Button>
          </>
        ) : null}
        {status === "allowed" ? (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onDecision(row, "change_role")}
              disabled={disabled}
              aria-label={`${userLabel} 권한 변경`}
            >
              <SlidersHorizontal className="size-4" />
              권한 변경
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => onDecision(row, "revoke")}
              disabled={disabled}
              aria-label={`${userLabel} 권한 회수`}
            >
              <Ban className="size-4" />
              회수
            </Button>
          </>
        ) : null}
        {["denied", "not_requested"].includes(status) ? (
          <Button
            size="sm"
            onClick={() => onDecision(row, "grant")}
            disabled={disabled}
            aria-label={`${userLabel} 권한 직접 부여`}
          >
            <UserPlus className="size-4" />
            직접 부여
          </Button>
        ) : null}
        {explicitStatus ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onDecision(row, "reset_to_policy")}
            disabled={disabled}
            aria-label={`${userLabel} 수동 설정 해제`}
          >
            <RotateCcw className="size-4" />
            수동 설정 해제
          </Button>
        ) : null}
      </div>

      <div className="hidden items-center justify-end gap-1.5 xl:flex">
        {primaryAction ? (
          <Button
            size="sm"
            variant={primaryAction.variant}
            onClick={() => onDecision(row, primaryAction.action, primaryAction.label)}
            disabled={disabled}
            aria-label={`${userLabel} ${primaryAction.label}`}
          >
            <PrimaryIcon className="size-4" />
            {primaryAction.label}
          </Button>
        ) : null}
        {hasMoreActions ? (
          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    disabled={disabled}
                    aria-label={`${userLabel} 추가 작업`}
                  >
                    <MoreHorizontal className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent side="top">추가 작업</TooltipContent>
            </Tooltip>
            <DropdownMenuContent align="end">
              {status === "pending" ? (
                <DropdownMenuItem variant="destructive" onSelect={() => onDecision(row, "reject", "거절")}>
                  <Ban className="size-4" />
                  거절
                </DropdownMenuItem>
              ) : null}
              {status === "allowed" ? (
                <DropdownMenuItem variant="destructive" onSelect={() => onDecision(row, "revoke", "회수")}>
                  <Ban className="size-4" />
                  회수
                </DropdownMenuItem>
              ) : null}
              {explicitStatus ? (
                <DropdownMenuItem
                  onSelect={() => onDecision(row, "reset_to_policy", "수동 설정 해제")}
                >
                  <RotateCcw className="size-4" />
                  수동 설정 해제
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
    </>
  )
}

function AccessUsersTable({
  rows,
  isLoading,
  isFetching,
  error,
  onDecision,
  isMutating = false,
  onRetry,
  onEmptyReset,
  toolbar,
  pagination,
  onPageChange,
}) {
  const columns = [
    {
      id: "user",
      header: "사용자",
      cell: ({ row }) => <UserIdentity user={row.original.user} />,
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    },
    {
      id: "affiliation",
      header: "소속",
      cell: ({ row }) => (
        <div className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
          <span className="truncate text-sm">{row.original.user.department || "-"}</span>
          <span className="text-xs text-muted-foreground">/</span>
          <span className="truncate text-xs text-muted-foreground">
            {row.original.user.userSdwtProd || "-"}
          </span>
        </div>
      ),
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    },
    {
      id: "accessStatus",
      header: "접근 상태 / 결정 기준",
      cell: ({ row }) => (
        <div className="flex min-w-0 items-center gap-2 whitespace-nowrap">
          <AccessStatusBadge access={row.original.access || {}} />
          <AccessSourceMeta access={row.original.access || {}} />
        </div>
      ),
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    },
    {
      id: "accessRole",
      header: "Portal 접근 역할",
      cell: ({ row }) => <RoleIndicator role={row.original.access?.role} />,
      meta: {
        headerClassName: "min-w-36",
        cellClassName: "min-w-36",
      },
    },
    {
      id: "decidedAt",
      header: "최근 결정",
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {formatAccountDateValue(row.original.access?.decidedAt || row.original.access?.requestedAt)}
        </span>
      ),
      meta: {
        headerClassName: "min-w-44",
        cellClassName: "min-w-44",
      },
    },
    {
      id: "actions",
      header: "작업",
      cell: ({ row }) => (
        <UserActions row={row.original} onDecision={onDecision} disabled={isMutating || isFetching} />
      ),
      meta: {
        headerClassName: "sticky right-0 z-20 min-w-44 bg-muted/30 text-right",
        cellClassName: "sticky right-0 z-10 min-w-44 bg-card text-right group-hover:bg-muted/40",
      },
    },
  ]
  const errorMessage = error?.message === "forbidden"
    ? "권한 관리 권한이 없습니다."
    : error
      ? "사용자 목록을 불러오지 못했습니다."
      : ""

  return (
    <AccountDataTable
      data={rows}
      columns={columns}
      getRowId={(row) => String(row.user.id)}
      toolbar={toolbar}
      isLoading={isLoading}
      isFetching={isFetching}
      error={errorMessage}
      emptyMessage="표시할 사용자가 없습니다."
      emptyAction={onEmptyReset ? (
        <Button type="button" size="sm" variant="outline" onClick={onEmptyReset}>
          <RotateCcw className="size-4" />
          필터 초기화
        </Button>
      ) : null}
      onRetry={onRetry}
      pagination={{
        page: pagination?.page || 1,
        pageSize: pagination?.pageSize || PAGE_SIZE,
        total: pagination?.total || 0,
        totalPages: pagination?.totalPages || 1,
        onPageChange,
      }}
      className="h-full rounded-none border-0"
      tableClassName="min-w-[1100px]"
      ariaLabel="포털 접근 사용자 목록"
    />
  )
}

function PendingPanel({ query, onDecision, onPageChange, isMutating }) {
  return (
    <Card className="grid min-w-0 grid-rows-[auto_auto] overflow-hidden py-0 xl:h-full xl:min-h-0 xl:grid-rows-[min-content_minmax(0,1fr)] xl:gap-0">
      <CardHeader className="border-b px-4 py-3 xl:grid-rows-[auto] xl:content-start xl:pb-3!">
        <CardTitle className="text-base">승인 대기 요청</CardTitle>
        <CardDescription>{(query.data?.pagination?.total || 0).toLocaleString("ko-KR")}건</CardDescription>
      </CardHeader>
      <CardContent className="grid min-w-0 grid-rows-[auto] p-0 xl:min-h-0 xl:grid-rows-[minmax(0,1fr)]">
        <AccessUsersTable
          rows={query.data?.results || []}
          isLoading={query.isPending}
          isFetching={query.isFetching}
          error={query.error}
          onDecision={onDecision}
          isMutating={isMutating}
          onRetry={query.refetch}
          pagination={query.data?.pagination}
          onPageChange={onPageChange}
        />
      </CardContent>
    </Card>
  )
}

function PolicyPanel({ query, scope, scopeOptions, onScopeChange }) {
  const createMutation = useCreateAccessPolicyRule()
  const updateMutation = useUpdateAccessPolicyRule()
  const deleteMutation = useDeleteAccessPolicyRule()
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [mutationError, setMutationError] = useState("")
  const [form, setForm] = useState(INITIAL_POLICY_FORM)
  const rules = query.data?.results || []
  const isMutating = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending
  const isAppScope = scope !== "portal"
  const scopeLabel = scopeOptions.find((option) => option.value === scope)?.label || scope

  const resetForm = () => {
    setForm({ ...INITIAL_POLICY_FORM })
  }

  const createPolicy = async (payload) => {
    if (isMutating) return false
    setMutationError("")
    try {
      await createMutation.mutateAsync(payload)
      resetForm()
      toast.success("자동 접근 규칙을 추가했습니다.")
      return true
    } catch (error) {
      const message = getMutationErrorMessage(error, "자동 접근 규칙을 추가하지 못했습니다.")
      setMutationError(message)
      toast.error(message)
      return false
    }
  }

  const updatePolicyActive = async (rule, checked) => {
    if (isMutating) return false
    setMutationError("")
    try {
      await updateMutation.mutateAsync({ id: rule.id, isActive: checked })
      toast.success(checked ? "자동 접근 규칙을 사용합니다." : "자동 접근 규칙 사용을 중지했습니다.")
      return true
    } catch (error) {
      const message = getMutationErrorMessage(error, "자동 접근 규칙의 사용 여부를 변경하지 못했습니다.")
      setMutationError(message)
      toast.error(message)
      return false
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (isMutating) return

    const value = form.value.trim()
    if (!value) {
      const message = "대상 부서를 입력해 주세요."
      setMutationError(message)
      toast.error(message)
      return
    }

    const payload = {
      scope,
      ruleType: "department",
      value,
      ...(isAppScope ? {} : { role: form.role }),
      isActive: form.isActive,
    }
    await createPolicy(payload)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget || isMutating) return
    setMutationError("")
    try {
      await deleteMutation.mutateAsync({ id: deleteTarget.id })
      setDeleteTarget(null)
      toast.success("자동 접근 규칙을 삭제했습니다.")
    } catch (error) {
      const message = getMutationErrorMessage(error, "자동 접근 규칙을 삭제하지 못했습니다.")
      setMutationError(message)
      toast.error(message)
    }
  }

  const handlePolicyToggle = async (rule, checked) => {
    if (isMutating) return
    await updatePolicyActive(rule, checked)
  }

  return (
    <Card className="grid min-w-0 grid-rows-[auto_auto] overflow-hidden py-0 xl:h-full xl:min-h-0 xl:grid-rows-[min-content_minmax(0,1fr)] xl:gap-0">
      <CardHeader className="border-b px-4 py-3 xl:grid-rows-[auto] xl:content-start xl:pb-3!">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base">
              <span className="xl:hidden">자동 규칙</span>
              <span className="hidden xl:inline">자동 접근 규칙</span>
            </CardTitle>
            <CardDescription>{scopeLabel} · {formatCount(rules.length)}개 규칙</CardDescription>
          </div>
          <Select value={scope} onValueChange={onScopeChange} disabled={isMutating}>
            <SelectTrigger className="w-52" aria-label="자동 접근 규칙 권한 범위">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {scopeOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="grid min-w-0 grid-rows-[auto_auto] gap-4 p-4 xl:min-h-0 xl:grid-rows-[min-content_minmax(0,1fr)]">
        <form
          className="grid gap-3 border-b pb-4 xl:grid-cols-[11rem_9rem_8rem_auto] xl:items-end xl:justify-start"
          onSubmit={handleSubmit}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="access-policy-value">대상 부서</Label>
            <Input
              id="access-policy-value"
              value={form.value}
              onChange={(event) => setForm((current) => ({ ...current, value: event.target.value }))}
              placeholder="부서명"
              maxLength={150}
              required
              disabled={isMutating}
            />
          </div>
          {isAppScope ? (
            <div className="grid gap-1.5">
              <Label>적용 결과</Label>
              <div className="flex h-9 items-center rounded-md border bg-muted/40 px-3 text-sm">
                앱 접근 허용
              </div>
            </div>
          ) : (
            <div className="grid gap-1.5">
              <Label htmlFor="access-policy-role">Portal 접근 역할</Label>
              <Select
                value={form.role}
                onValueChange={(value) => setForm((current) => ({ ...current, role: value }))}
                disabled={isMutating}
              >
                <SelectTrigger id="access-policy-role" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid gap-1.5">
            <Label htmlFor="access-policy-active">사용 여부</Label>
            <div className="flex h-9 items-center gap-2">
              <Switch
                id="access-policy-active"
                checked={form.isActive}
                onCheckedChange={(checked) => setForm((current) => ({ ...current, isActive: checked }))}
                aria-label="자동 접근 규칙 사용"
                disabled={isMutating}
              />
              <span className="text-sm text-muted-foreground">{form.isActive ? "사용" : "사용 안 함"}</span>
            </div>
          </div>
          <Button
            type="submit"
            className="self-end justify-self-start whitespace-nowrap"
            disabled={isMutating || query.isPending || query.isError}
          >
            {createMutation.isPending ? <RefreshCw className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {createMutation.isPending ? "추가 중" : "규칙 추가"}
          </Button>
          {mutationError ? (
            <p className="text-sm text-destructive xl:col-span-4" role="alert">
              {mutationError}
            </p>
          ) : null}
        </form>

        {query.isPending ? (
          <Skeleton className="h-48 w-full" />
        ) : query.error ? (
          <ErrorState error={query.error} onRetry={query.refetch} />
        ) : !rules.length ? (
          <div className="rounded-md border p-4 text-sm text-muted-foreground">
            등록된 자동 접근 규칙이 없습니다.
          </div>
        ) : (
          <div className="min-w-0 overflow-x-auto rounded-md border xl:min-h-0 xl:overflow-auto">
            <Table stickyHeader>
              <TableHeader>
                <TableRow>
                  <TableHead>대상 부서</TableHead>
                  <TableHead>{isAppScope ? "적용 결과" : "Portal 접근 역할"}</TableHead>
                  <TableHead>사용 여부</TableHead>
                  <TableHead className="text-right">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => {
                  const isUpdating = updateMutation.isPending && updateMutation.variables?.id === rule.id
                  return (
                    <TableRow key={rule.id}>
                      <TableCell className="max-w-lg truncate">{rule.value || "-"}</TableCell>
                      <TableCell>{isAppScope ? "앱 접근 허용" : ROLE_LABELS[rule.role] || rule.role}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Switch
                            checked={Boolean(rule.isActive)}
                            onCheckedChange={(checked) => handlePolicyToggle(rule, checked)}
                            aria-label={`${rule.value || "부서"} 규칙 사용`}
                            disabled={isMutating}
                          />
                          <Badge variant={rule.isActive ? "secondary" : "outline"}>
                            {isUpdating ? "변경 중" : rule.isActive ? "사용 중" : "사용 안 함"}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => {
                            setMutationError("")
                            setDeleteTarget(rule)
                          }}
                          disabled={isMutating}
                        >
                          <Trash2 className="size-4" />
                          삭제
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
      <ConfirmActionDialog
        open={Boolean(deleteTarget)}
        title="자동 접근 규칙 삭제"
        description={
          deleteTarget
            ? `대상 부서: ${deleteTarget.value || "-"}`
            : ""
        }
        confirmLabel="삭제"
        isSubmitting={deleteMutation.isPending}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        onConfirm={handleDeleteConfirm}
        errorMessage={deleteTarget ? mutationError : ""}
      />
    </Card>
  )
}

function AuditPanel({ query, scope, scopeOptions, onScopeChange, onPageChange }) {
  const rows = query.data?.results || []

  return (
    <Card className="grid min-w-0 grid-rows-[auto_auto] overflow-hidden py-0 xl:h-full xl:min-h-0 xl:grid-rows-[min-content_minmax(0,1fr)] xl:gap-0">
      <CardHeader className="border-b px-4 py-3 xl:grid-rows-[auto] xl:content-start xl:pb-3!">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base">변경 이력</CardTitle>
            <CardDescription>{(query.data?.pagination?.total || 0).toLocaleString("ko-KR")}건</CardDescription>
          </div>
          <Select value={scope} onValueChange={onScopeChange}>
            <SelectTrigger className="w-48" aria-label="권한 범위 필터">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {scopeOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="grid min-w-0 grid-rows-[auto_auto] p-0 xl:min-h-0 xl:grid-rows-[minmax(0,1fr)_auto]">
        {query.isPending ? (
          <div className="grid gap-2 p-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : query.error ? (
          <div className="p-4"><ErrorState error={query.error} onRetry={query.refetch} /></div>
        ) : !rows.length ? (
          <div className="p-4 text-sm text-muted-foreground">표시할 변경 이력이 없습니다.</div>
        ) : (
          <div className="min-w-0 overflow-x-auto xl:min-h-0 xl:overflow-auto" aria-busy={query.isFetching}>
            <Table stickyHeader>
              <TableHeader>
                <TableRow>
                  <TableHead>시각</TableHead>
                  <TableHead>작업</TableHead>
                  <TableHead>대상</TableHead>
                  <TableHead>핵심 변경</TableHead>
                  <TableHead>작업자</TableHead>
                  <TableHead>사유</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const changes = getAuditChanges(row)
                  const target = row.targetUser
                    ? getAuditIdentity(row.targetUser)
                    : row.policyRule?.value || row.scope || row.after?.value || row.before?.value || "-"
                  return (
                    <TableRow key={row.id}>
                      <TableCell className="min-w-40 text-xs text-muted-foreground">
                        {formatAccountDateValue(row.createdAt)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{ACTION_LABELS[row.action] || row.action}</Badge>
                      </TableCell>
                      <TableCell className="min-w-36">{target}</TableCell>
                      <TableCell>
                        <div className="flex min-w-60 flex-col gap-1">
                          {changes.length ? changes.map((change) => (
                            <span key={change} className="text-xs text-muted-foreground">
                              {change}
                            </span>
                          )) : <span className="text-xs text-muted-foreground">-</span>}
                        </div>
                      </TableCell>
                      <TableCell className="min-w-32">{getAuditIdentity(row.actor)}</TableCell>
                      <TableCell className="max-w-sm whitespace-normal break-words text-sm text-muted-foreground">
                        {row.reason || "-"}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
        <Pager pagination={query.data?.pagination} onPageChange={onPageChange} disabled={query.isFetching} />
      </CardContent>
    </Card>
  )
}

export default function PermissionsPage() {
  const { user, isLoading } = useAuth()
  const canManage = Boolean(user?.portal_access?.canManage)
  const [activeTab, setActiveTab] = useState("matrix")
  const [pendingPage, setPendingPage] = useState(1)
  const [auditPage, setAuditPage] = useState(1)
  const [auditScope, setAuditScope] = useState("all")
  const [policyScope, setPolicyScope] = useState("portal")
  const [decision, setDecision] = useState(null)
  const [decisionError, setDecisionError] = useState("")
  const [matrixFilters, setMatrixFilters] = useState(INITIAL_MATRIX_FILTERS)
  const [matrixFilterDraft, setMatrixFilterDraft] = useState(INITIAL_MATRIX_FILTER_DRAFT)
  const [pendingMatrixCell, setPendingMatrixCell] = useState("")

  const pendingQuery = useAccessUsers({
    page: pendingPage,
    pageSize: PAGE_SIZE,
    status: "pending",
    enabled: canManage,
  })
  const policyQuery = useAccessPolicyRules({ scope: policyScope, enabled: canManage })
  const auditQuery = useAccessAuditLogs({
    page: auditPage,
    pageSize: PAGE_SIZE,
    scope: auditScope === "all" ? "" : auditScope,
    enabled: canManage && activeTab === "audit",
  })
  const matrixQuery = useAccessMatrix({
    pageSize: PAGE_SIZE,
    search: matrixFilters.search,
    department: matrixFilters.department,
    enabled: canManage,
  })
  const decisionMutation = useAccessUserDecision()
  const matrixRows = matrixQuery.data?.results || []
  const matrixTotal = matrixQuery.data?.pagination?.total ?? 0
  const matrixLoadedTotal = matrixRows.length
  const portalPolicyAllowed = matrixRows.filter(
    (row) => row.accesses?.portal?.source === "policy_department",
  ).length
  const pendingTotal = pendingQuery.data?.pagination?.total ?? 0
  const policyTotal = policyQuery.data?.results?.length ?? 0
  const accessScopeOptions = buildAccessScopeOptions(user?.app_access)
  const auditScopeOptions = [{ value: "all", label: "전체 권한 범위" }, ...accessScopeOptions]
  const policyScopeLabel = accessScopeOptions.find((option) => option.value === policyScope)?.label || policyScope
  const hasAppliedMatrixFilters = Boolean(matrixFilters.search || matrixFilters.department)
  const isMatrixReplacing = matrixQuery.isFetching && !matrixQuery.isFetchingNextPage
  const isRefreshing =
    pendingQuery.isFetching || policyQuery.isFetching || auditQuery.isFetching || matrixQuery.isFetching

  const handleDecisionOpen = (row, action, label, scope = null) => {
    if (decisionMutation.isPending) return
    setDecisionError("")
    setDecision({
      row,
      action,
      label,
      role: row.access?.role || "viewer",
      scope,
    })
  }

  const handleDecisionSubmit = async (payload) => {
    if (decisionMutation.isPending) return
    setDecisionError("")
    try {
      await decisionMutation.mutateAsync(payload)
      setDecision(null)
      toast.success("사용자 권한을 변경했습니다.")
    } catch (error) {
      const message = getMutationErrorMessage(error, "사용자 권한을 변경하지 못했습니다.")
      setDecisionError(message)
      toast.error(message)
    }
  }

  const handleApplyMatrixFilters = () => {
    setMatrixFilters({
      search: matrixFilterDraft.search.trim(),
      department: matrixFilterDraft.department.trim(),
    })
  }

  const handleResetMatrixFilters = () => {
    setMatrixFilterDraft({ ...INITIAL_MATRIX_FILTER_DRAFT })
    setMatrixFilters({ ...INITIAL_MATRIX_FILTERS })
  }

  const handleMatrixAccessChange = async ({ user: targetUser, scope, access, nextValue }) => {
    if (decisionMutation.isPending || isSuperuserBypass(access)) return

    if (scope.scopeType === "portal") {
      let action = ""
      if (nextValue === "inherit") {
        if (!access?.explicitStatus) return
        action = "reset_to_policy"
      } else if (nextValue === "denied") {
        action = access?.explicitStatus === "pending" ? "reject" : "revoke"
      } else if (nextValue === "allowed") {
        action = access?.explicitStatus === "pending" ? "approve" : "grant"
      } else {
        return
      }
      handleDecisionOpen(
        { user: targetUser, access: { ...access, role: "viewer" } },
        action,
        ACTION_LABELS[action],
        scope,
      )
      return
    }

    let action = ""
    if (nextValue === "inherit") {
      if (!access?.explicitStatus) return
      action = "reset_to_policy"
    } else if (nextValue === "denied") {
      if (access?.explicitStatus === "denied") return
      action = "revoke"
    } else if (nextValue === "allowed") {
      if (access?.explicitStatus === "allowed") return
      action = "grant"
    } else {
      return
    }

    const cellKey = `${targetUser.id}:${scope.key}`
    setPendingMatrixCell(cellKey)
    try {
      await decisionMutation.mutateAsync({
        userId: targetUser.id,
        scope: scope.key,
        action,
        reason: "권한 매트릭스에서 수동 변경",
      })
      toast.success(`${scope.name} 권한을 변경했습니다.`)
    } catch (error) {
      toast.error(getMutationErrorMessage(error, `${scope.name} 권한을 변경하지 못했습니다.`))
    } finally {
      setPendingMatrixCell("")
    }
  }

  const handleRefresh = () => {
    matrixQuery.refetch()
    pendingQuery.refetch()
    policyQuery.refetch()
    if (activeTab === "audit") auditQuery.refetch()
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-y-auto xl:overflow-hidden">
      <section className="flex shrink-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">권한 관리</h2>
            <Badge variant="outline">Portal + Apps</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Portal 접근 역할과 앱별 허용 여부 · 권한 관리 기능은 별도 부여
          </p>
        </div>
        <Button variant="outline" onClick={handleRefresh} disabled={!canManage || isRefreshing}>
          <RefreshCw className={isRefreshing ? "size-4 animate-spin" : "size-4"} />
          새로고침
        </Button>
      </section>

      <div className="min-w-0 xl:min-h-0 xl:flex-1 xl:overflow-hidden">
        {isLoading ? (
          <Skeleton className="h-full min-h-48 w-full" />
        ) : !canManage ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">접근 불가</CardTitle>
              <CardDescription>권한 관리 권한이 없습니다.</CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <div className="grid min-w-0 gap-4 xl:h-full xl:min-h-0 xl:grid-rows-[min-content_minmax(0,1fr)] xl:overflow-hidden">
            <section className="grid shrink-0 grid-cols-2 gap-3 xl:hidden">
              <SummaryTile
                icon={Users}
                label={hasAppliedMatrixFilters ? "필터 결과" : "전체 인원"}
                value={matrixTotal}
                detail={`불러온 사용자 ${formatCount(matrixLoadedTotal)}명`}
                tone="secondary"
                isLoading={isMatrixReplacing}
              />
              <SummaryTile
                icon={Clock3}
                label="승인 대기"
                value={pendingTotal}
                detail="처리 필요 요청"
                tone="destructive"
                isLoading={pendingQuery.isFetching}
              />
              <SummaryTile
                icon={ShieldCheck}
                label="자동 허용"
                value={portalPolicyAllowed}
                detail="불러온 사용자 기준"
                tone="primary"
                isLoading={isMatrixReplacing}
              />
              <SummaryTile
                icon={SlidersHorizontal}
                label="자동 규칙"
                value={policyTotal}
                detail={`${policyScopeLabel} · 사용/미사용`}
                isLoading={policyQuery.isFetching}
              />
            </section>

            <section className="hidden shrink-0 overflow-hidden rounded-lg border bg-card xl:grid xl:grid-cols-4">
              <DesktopSummaryMetric
                icon={Users}
                label={hasAppliedMatrixFilters ? "필터 결과" : "전체 사용자"}
                value={matrixTotal}
                detail={`불러온 사용자 ${formatCount(matrixLoadedTotal)}명`}
                tone="secondary"
                isLoading={isMatrixReplacing}
              />
              <DesktopSummaryMetric
                icon={Clock3}
                label="승인 대기"
                value={pendingTotal}
                detail="처리할 접근 요청"
                tone="destructive"
                isLoading={pendingQuery.isFetching}
              />
              <DesktopSummaryMetric
                icon={ShieldCheck}
                label="불러온 사용자 자동 허용"
                value={portalPolicyAllowed}
                detail="자동 접근 규칙 기준"
                tone="primary"
                isLoading={isMatrixReplacing}
              />
              <DesktopSummaryMetric
                icon={SlidersHorizontal}
                label="자동 접근 규칙"
                value={policyTotal}
                detail={`${policyScopeLabel} · 사용/미사용`}
                isLoading={policyQuery.isFetching}
              />
            </section>

            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="min-w-0 gap-4 xl:h-full xl:min-h-0 xl:overflow-hidden"
            >
              <div className="min-w-0 shrink-0 overflow-x-auto pb-1">
                <TabsList className="grid w-full shrink-0 grid-cols-4 xl:inline-flex xl:w-max">
                  <TabsTrigger value="matrix">
                    <SlidersHorizontal className="hidden size-4 xl:block" />
                    <span className="xl:hidden">매트릭스</span>
                    <span className="hidden xl:inline">권한 매트릭스</span>
                  </TabsTrigger>
                  <TabsTrigger value="pending">
                    <Clock3 className="hidden size-4 xl:block" />
                    승인 대기
                    <Badge
                      variant={pendingTotal > 0 ? "destructive" : "secondary"}
                      className="hidden min-w-5 justify-center px-1.5 tabular-nums xl:inline-flex"
                    >
                      {formatCount(pendingTotal)}
                    </Badge>
                  </TabsTrigger>
                  <TabsTrigger value="policies">
                    <SlidersHorizontal className="hidden size-4 xl:block" />
                    <span className="xl:hidden">자동 규칙</span>
                    <span className="hidden xl:inline">자동 접근 규칙</span>
                    <Badge
                      variant="outline"
                      className="hidden min-w-5 justify-center px-1.5 tabular-nums xl:inline-flex"
                    >
                      {formatCount(policyTotal)}
                    </Badge>
                  </TabsTrigger>
                  <TabsTrigger value="audit">
                    <History className="hidden size-4 xl:block" />
                    변경 이력
                  </TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="matrix" className="min-w-0 xl:min-h-0 xl:overflow-hidden">
                <AppPermissionMatrix
                  query={matrixQuery}
                  filters={matrixFilters}
                  filterDraft={matrixFilterDraft}
                  setFilterDraft={setMatrixFilterDraft}
                  onApplyFilters={handleApplyMatrixFilters}
                  onResetFilters={handleResetMatrixFilters}
                  onAccessChange={handleMatrixAccessChange}
                  pendingCell={pendingMatrixCell}
                  isMutating={decisionMutation.isPending}
                />
              </TabsContent>

              <TabsContent value="pending" className="min-w-0 xl:min-h-0 xl:overflow-hidden">
                <PendingPanel
                  query={pendingQuery}
                  onDecision={handleDecisionOpen}
                  onPageChange={setPendingPage}
                  isMutating={decisionMutation.isPending}
                />
              </TabsContent>
              <TabsContent value="policies" className="min-w-0 xl:min-h-0 xl:overflow-hidden">
                <PolicyPanel
                  key={policyScope}
                  query={policyQuery}
                  scope={policyScope}
                  scopeOptions={accessScopeOptions}
                  onScopeChange={setPolicyScope}
                />
              </TabsContent>
              <TabsContent value="audit" className="min-w-0 xl:min-h-0 xl:overflow-hidden">
                <AuditPanel
                  query={auditQuery}
                  scope={auditScope}
                  scopeOptions={auditScopeOptions}
                  onScopeChange={(value) => {
                    setAuditScope(value)
                    setAuditPage(1)
                  }}
                  onPageChange={setAuditPage}
                />
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>

      <DecisionDialog
        decision={decision}
        onOpenChange={(open) => {
          if (!open) setDecision(null)
        }}
        onSubmit={handleDecisionSubmit}
        isSubmitting={decisionMutation.isPending}
        errorMessage={decisionError}
      />
    </div>
  )
}
