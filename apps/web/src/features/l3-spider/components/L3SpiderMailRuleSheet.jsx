import { useEffect, useRef, useState } from "react"
import { Clock3, Mail, Pencil, Plus, Save, Send, Trash2, Users, X } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

import {
  useCreateMailRule,
  useDeleteMailRule,
  useMailRules,
  useTestSendMailRule,
  useUpdateMailRule,
  useUpdateMailRulePermissions,
} from "../hooks/useL3SpiderMailRules"

const PATTERN_FIELDS = [
  { key: "lineId", api: "line_id", label: "Line ID" },
  { key: "processId", api: "process_id", label: "Process ID" },
  { key: "edsStep", api: "eds_step", label: "EDS Step" },
  { key: "stepSeq", api: "step_seq", label: "Step Seq" },
  { key: "ppid", api: "ppid", label: "PPID" },
  { key: "eqpch", api: "eqpch", label: "EQPCH" },
  { key: "binName", api: "bin_name", label: "Bin Name" },
]

const EMPTY_EDIT = {
  name: "L3 Spider 알림",
  severityMode: "high_risk",
  receiverEmailsText: "",
  scheduleType: "daily",
  sendTime: "09:00",
  timezone: "Asia/Seoul",
  isActive: true,
  lineId: "*",
  processId: "*",
  edsStep: "*",
  stepSeq: "*",
  ppid: "*",
  eqpch: "*",
  binName: "*",
  dateFrom: "",
  dateTo: "",
  memo: "",
}

const SEVERITY_LABELS = {
  high_risk: "High Risk",
  warning_or_high_risk: "Warning + High Risk",
}

const ACCESS_LABELS = {
  owner: "Owner",
  read: "Read",
  write: "Write",
}

function splitReceivers(value) {
  return value
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function permissionsToEdit(row) {
  return (row?.permissions ?? []).map((permission) => ({
    user: permission.email || permission.username || permission.sabun || permission.user || "",
    accessLevel: permission.accessLevel || "read",
  }))
}

function permissionsToPayload(rows) {
  return rows
    .map((row) => ({
      user: row.user.trim(),
      access_level: row.accessLevel || "read",
    }))
    .filter((row) => row.user)
}

function rowToEdit(row) {
  return {
    name: row.name ?? "L3 Spider 알림",
    severityMode: row.severityMode ?? "high_risk",
    receiverEmailsText: (row.receiverEmails ?? []).join("\n"),
    scheduleType: row.scheduleType ?? "daily",
    sendTime: row.sendTime ?? "09:00",
    timezone: row.timezone ?? "Asia/Seoul",
    isActive: row.isActive ?? true,
    lineId: row.lineId ?? "*",
    processId: row.processId ?? "*",
    edsStep: row.edsStep ?? "*",
    stepSeq: row.stepSeq ?? "*",
    ppid: row.ppid ?? "*",
    eqpch: row.eqpch ?? "*",
    binName: row.binName ?? "*",
    dateFrom: row.dateFrom ?? "",
    dateTo: row.dateTo ?? "",
    memo: row.memo ?? "",
  }
}

function editToPayload(edit) {
  const payload = {
    name: edit.name || "L3 Spider 알림",
    severity_mode: edit.severityMode || "high_risk",
    receiver_emails: splitReceivers(edit.receiverEmailsText),
    schedule_type: "daily",
    send_time: edit.sendTime || "09:00",
    timezone: "Asia/Seoul",
    is_active: edit.isActive,
    date_from: edit.dateFrom || null,
    date_to: edit.dateTo || null,
    memo: edit.memo || "",
  }
  PATTERN_FIELDS.forEach(({ key, api }) => {
    payload[api] = edit[key] || "*"
  })
  return payload
}

function PatternSummary({ row }) {
  const activePatterns = PATTERN_FIELDS
    .map(({ key, label }) => ({ label, value: row[key] ?? "*" }))
    .filter((item) => item.value !== "*")

  if (!activePatterns.length && !row.dateFrom && !row.dateTo) {
    return <span className="text-xs text-muted-foreground">전체</span>
  }

  return (
    <div className="flex max-w-[360px] flex-wrap gap-1">
      {activePatterns.slice(0, 5).map(({ label, value }) => (
        <Badge key={label} variant="secondary" className="max-w-[160px] truncate rounded px-1.5 py-0 font-mono text-[10px]">
          {label}: {value}
        </Badge>
      ))}
      {activePatterns.length > 5 && (
        <Badge variant="outline" className="rounded px-1.5 py-0 text-[10px]">
          +{activePatterns.length - 5}
        </Badge>
      )}
      {(row.dateFrom || row.dateTo) && (
        <Badge variant="outline" className="rounded px-1.5 py-0 text-[10px]">
          {row.dateFrom || "*"} ~ {row.dateTo || "*"}
        </Badge>
      )}
    </div>
  )
}

function RuleFormDialog({ editTarget, isSaving, error, onClose, onSave }) {
  const [edit, setEdit] = useState(EMPTY_EDIT)

  useEffect(() => {
    setEdit(editTarget?.row ? rowToEdit(editTarget.row) : EMPTY_EDIT)
  }, [editTarget])

  const set = (key, value) => setEdit((prev) => ({ ...prev, [key]: value }))
  const receivers = splitReceivers(edit.receiverEmailsText)
  const open = Boolean(editTarget)

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => { if (!nextOpen) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editTarget?.mode === "edit" ? "메일 rule 수정" : "메일 rule 추가"}</DialogTitle>
        </DialogHeader>

        <div className="grid gap-5">
          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error.message}
            </div>
          ) : null}

          <div className="grid gap-3 md:grid-cols-[1.2fr_0.8fr_0.8fr]">
            <div className="grid gap-1.5">
              <Label htmlFor="l3-mail-rule-name">Rule 이름</Label>
              <Input
                id="l3-mail-rule-name"
                value={edit.name}
                onChange={(event) => set("name", event.target.value)}
                disabled={isSaving}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>메일 조건</Label>
              <Select
                value={edit.severityMode}
                onValueChange={(value) => set("severityMode", value)}
                disabled={isSaving}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="high_risk">High Risk만</SelectItem>
                  <SelectItem value="warning_or_high_risk">Warning + High Risk</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="l3-mail-rule-send-time">발송 시각</Label>
              <Input
                id="l3-mail-rule-send-time"
                type="time"
                value={edit.sendTime}
                onChange={(event) => set("sendTime", event.target.value)}
                disabled={isSaving}
              />
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="l3-mail-rule-receivers">수신자</Label>
            <Textarea
              id="l3-mail-rule-receivers"
              value={edit.receiverEmailsText}
              onChange={(event) => set("receiverEmailsText", event.target.value)}
              placeholder="name@samsung.com"
              className="min-h-24 font-mono text-xs"
              disabled={isSaving}
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>쉼표, 세미콜론, 줄바꿈 구분</span>
              <span>{receivers.length}명</span>
            </div>
          </div>

          <div className="grid gap-3 rounded-md border bg-muted/20 p-3">
            <div className="grid gap-3 md:grid-cols-4">
              {PATTERN_FIELDS.map(({ key, label }) => (
                <div key={key} className="grid gap-1.5">
                  <Label htmlFor={`l3-mail-rule-${key}`}>{label}</Label>
                  <Input
                    id={`l3-mail-rule-${key}`}
                    value={edit[key]}
                    onChange={(event) => set(key, event.target.value)}
                    placeholder="*"
                    className="font-mono text-xs"
                    disabled={isSaving}
                  />
                </div>
              ))}
              <div className="grid gap-1.5">
                <Label htmlFor="l3-mail-rule-date-from">날짜 시작</Label>
                <Input
                  id="l3-mail-rule-date-from"
                  type="date"
                  value={edit.dateFrom}
                  onChange={(event) => set("dateFrom", event.target.value)}
                  disabled={isSaving}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="l3-mail-rule-date-to">날짜 종료</Label>
                <Input
                  id="l3-mail-rule-date-to"
                  type="date"
                  value={edit.dateTo}
                  onChange={(event) => set("dateTo", event.target.value)}
                  disabled={isSaving}
                />
              </div>
            </div>
            <div className="text-xs text-muted-foreground">
              패턴은 제외 필터와 동일하게 <code className="rounded bg-background px-1">*</code>, <code className="rounded bg-background px-1">PP%</code>, <code className="rounded bg-background px-1">%PP%</code> 형식을 사용합니다.
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-[auto_1fr] md:items-center">
            <label className="flex items-center gap-2 text-sm font-medium">
              <Switch
                checked={edit.isActive}
                onCheckedChange={(value) => set("isActive", value)}
                disabled={isSaving}
              />
              활성
            </label>
            <Input
              value={edit.memo}
              onChange={(event) => set("memo", event.target.value)}
              placeholder="메모"
              disabled={isSaving}
            />
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
            <X className="size-4" />
            취소
          </Button>
          <Button
            type="button"
            onClick={() => onSave(editTarget, edit)}
            disabled={isSaving || receivers.length === 0}
          >
            <Save className="size-4" />
            저장
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function PermissionDialog({ target, isSaving, error, onClose, onSave }) {
  const [rows, setRows] = useState([])
  const nextRowId = useRef(0)
  const open = Boolean(target)

  useEffect(() => {
    setRows(permissionsToEdit(target?.row).map((row) => ({
      ...row,
      rowId: `permission-${nextRowId.current++}`,
    })))
  }, [target])

  const set = (index, key, value) => {
    setRows((prev) => prev.map((row, rowIndex) => (
      rowIndex === index ? { ...row, [key]: value } : row
    )))
  }

  const addRow = () => {
    setRows((prev) => [
      ...prev,
      { rowId: `permission-${nextRowId.current++}`, user: "", accessLevel: "read" },
    ])
  }

  const removeRow = (index) => {
    setRows((prev) => prev.filter((_, rowIndex) => rowIndex !== index))
  }

  const hasBlankUser = rows.some((row) => !row.user.trim())

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => { if (!nextOpen) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>메일 rule 공유 권한</DialogTitle>
        </DialogHeader>

        <div className="grid gap-4">
          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error.message}
            </div>
          ) : null}

          <div className="rounded-md border">
            <div className="grid grid-cols-[1fr_140px_44px] gap-2 border-b bg-muted/40 px-3 py-2 text-xs font-medium text-muted-foreground">
              <div>사용자</div>
              <div>권한</div>
              <div />
            </div>
            <div className="grid gap-2 p-3">
              {rows.length === 0 ? (
                <div className="py-6 text-center text-sm text-muted-foreground">
                  공유 권한이 없습니다.
                </div>
              ) : rows.map((row, index) => (
                <div key={row.rowId} className="grid grid-cols-[1fr_140px_44px] gap-2">
                  <Input
                    value={row.user}
                    onChange={(event) => set(index, "user", event.target.value)}
                    placeholder="email, username, sabun"
                    disabled={isSaving}
                  />
                  <Select
                    value={row.accessLevel}
                    onValueChange={(value) => set(index, "accessLevel", value)}
                    disabled={isSaving}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="read">Read</SelectItem>
                      <SelectItem value="write">Write</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeRow(index)}
                    disabled={isSaving}
                    aria-label="권한 행 삭제"
                  >
                    <X className="size-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          <Button type="button" variant="outline" className="w-fit gap-1.5" onClick={addRow} disabled={isSaving}>
            <Plus className="size-4" />
            권한 추가
          </Button>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
            취소
          </Button>
          <Button
            type="button"
            onClick={() => onSave(target, rows)}
            disabled={isSaving || hasBlankUser}
          >
            <Save className="size-4" />
            저장
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function MailRuleRow({ row, isUpdating, isTesting, onEdit, onDelete, onToggle, onPermissions, onTestSend }) {
  const receiverCount = row.receiverEmails?.length ?? 0
  const canWrite = Boolean(row.canWrite)
  const canManage = Boolean(row.canManage)
  return (
    <TableRow className={cn(!row.isActive && "opacity-45")}>
      <TableCell className="w-14 text-center">
        <Switch
          checked={row.isActive}
          onCheckedChange={onToggle}
          disabled={isUpdating || !canWrite}
          aria-label={`${row.name} 활성 여부`}
        />
      </TableCell>
      <TableCell className="min-w-48">
        <div className="font-medium">{row.name}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">{row.memo || "메모 없음"}</div>
      </TableCell>
      <TableCell>
        <Badge variant={row.accessLevel === "owner" ? "default" : "outline"} className="rounded">
          {ACCESS_LABELS[row.accessLevel] ?? "Read"}
        </Badge>
      </TableCell>
      <TableCell>
        <Badge variant={row.severityMode === "high_risk" ? "destructive" : "secondary"} className="rounded">
          {SEVERITY_LABELS[row.severityMode] ?? row.severityMode}
        </Badge>
      </TableCell>
      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <Clock3 className="size-3.5" />
          매일 {row.sendTime}
        </div>
      </TableCell>
      <TableCell className="max-w-[260px]">
        <div className="truncate text-xs" title={(row.receiverEmails ?? []).join(", ")}>
          {receiverCount ? row.receiverEmails.join(", ") : "수신자 없음"}
        </div>
        <div className="text-[11px] text-muted-foreground">{receiverCount}명</div>
      </TableCell>
      <TableCell>
        <PatternSummary row={row} />
      </TableCell>
      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
        {row.lastSentAt || "-"}
      </TableCell>
      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
        {row.lastCheckedAt || "-"}
      </TableCell>
      <TableCell className="w-32 text-right">
        <div className="flex items-center justify-end gap-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 gap-1 px-2 text-xs"
            onClick={onTestSend}
            disabled={isUpdating || isTesting || !canWrite}
            aria-label={`${row.name} 테스트 발송`}
          >
            <Send className="size-3.5" />
            Test
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={onEdit}
            disabled={!canWrite}
            aria-label={`${row.name} 수정`}
          >
            <Pencil className="size-3.5" />
          </Button>
          {canManage ? (
            <>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7"
                onClick={onPermissions}
                aria-label={`${row.name} 공유 권한 관리`}
              >
                <Users className="size-3.5" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7 text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={onDelete}
                aria-label={`${row.name} 삭제`}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </>
          ) : null}
        </div>
      </TableCell>
    </TableRow>
  )
}

export function L3SpiderMailRuleSheet() {
  const { data: rules = [], isLoading, error: loadError } = useMailRules()
  const createMutation = useCreateMailRule()
  const updateMutation = useUpdateMailRule()
  const deleteMutation = useDeleteMailRule()
  const permissionMutation = useUpdateMailRulePermissions()
  const testSendMutation = useTestSendMailRule()

  const [editTarget, setEditTarget] = useState(null)
  const [permissionTarget, setPermissionTarget] = useState(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState(null)

  const isSaving = createMutation.isPending || updateMutation.isPending
  const activeCount = rules.filter((rule) => rule.isActive).length
  const mutationError = createMutation.error || updateMutation.error

  const handleSave = (target, edit) => {
    const payload = editToPayload(edit)
    if (target?.mode === "edit") {
      updateMutation.mutate({ id: target.row.id, ...payload }, {
        onSuccess: () => setEditTarget(null),
      })
      return
    }
    createMutation.mutate(payload, {
      onSuccess: () => setEditTarget(null),
    })
  }

  const handleToggle = (row, isActive) => {
    if (!row.canWrite) return
    updateMutation.mutate({ id: row.id, is_active: isActive })
  }

  const handleSavePermissions = (target, rows) => {
    permissionMutation.mutate({
      id: target.row.id,
      permissions: permissionsToPayload(rows),
    }, {
      onSuccess: () => setPermissionTarget(null),
    })
  }

  const handleConfirmDelete = () => {
    deleteMutation.mutate(deleteConfirmId, {
      onSuccess: () => setDeleteConfirmId(null),
    })
  }

  const handleTestSend = (row) => {
    testSendMutation.mutate({ id: row.id }, {
      onSuccess: (result) => {
        if (result.status === "no_events") {
          toast.info("테스트 발송할 이벤트가 없습니다.")
          return
        }
        toast.success(`테스트 메일을 발송했습니다. (${result.sent}건)`)
      },
      onError: (sendError) => {
        toast.error(sendError.message || "테스트 메일 발송에 실패했습니다.")
      },
    })
  }

  return (
    <>
      <Sheet>
        <SheetTrigger asChild>
          <Button type="button" variant="outline" size="sm" className="h-8 gap-1.5 px-3 text-xs">
            <Mail className="size-3.5" />
            메일 설정
            {activeCount > 0 && (
              <Badge variant="secondary" className="ml-0.5 h-4 px-1.5 text-[10px]">
                {activeCount}
              </Badge>
            )}
          </Button>
        </SheetTrigger>

        <SheetContent side="right" className="flex w-full max-w-[98vw] flex-col gap-0 p-0 sm:max-w-[1500px]">
          <SheetHeader className="border-b py-4 pl-6 pr-16">
            <div className="flex items-center justify-between gap-3">
              <div>
                <SheetTitle className="text-base">메일 발송 설정</SheetTitle>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  사용자별 rule이 매일 지정 시각 이후 한 번 처리됩니다.
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                className="gap-1.5"
                onClick={() => setEditTarget({ mode: "new" })}
              >
                <Plus className="size-3.5" />
                Rule 추가
              </Button>
            </div>
          </SheetHeader>

          <div className="min-h-0 flex-1 overflow-auto px-4 py-3">
            {loadError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {loadError.message}
              </div>
            ) : isLoading ? (
              <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">로딩 중...</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-14 text-center">활성</TableHead>
                    <TableHead>Rule</TableHead>
                    <TableHead>접근</TableHead>
                    <TableHead>조건</TableHead>
                    <TableHead>주기</TableHead>
                    <TableHead>수신자</TableHead>
                    <TableHead>패턴</TableHead>
                    <TableHead>최근 발송</TableHead>
                    <TableHead>최근 확인</TableHead>
                    <TableHead className="w-32 text-right">작업</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rules.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={10} className="py-10 text-center text-sm text-muted-foreground">
                        <Mail className="mx-auto mb-2 size-6 opacity-30" />
                        등록된 메일 rule이 없습니다.
                      </TableCell>
                    </TableRow>
                  ) : (
                    rules.map((row) => (
                      <MailRuleRow
                        key={row.id}
                        row={row}
                        isUpdating={updateMutation.isPending}
                        isTesting={testSendMutation.isPending && testSendMutation.variables?.id === row.id}
                        onEdit={() => setEditTarget({ mode: "edit", row })}
                        onDelete={() => setDeleteConfirmId(row.id)}
                        onToggle={(value) => handleToggle(row, value)}
                        onPermissions={() => setPermissionTarget({ row })}
                        onTestSend={() => handleTestSend(row)}
                      />
                    ))
                  )}
                </TableBody>
              </Table>
            )}
          </div>
        </SheetContent>
      </Sheet>

      <RuleFormDialog
        editTarget={editTarget}
        isSaving={isSaving}
        error={mutationError}
        onClose={() => setEditTarget(null)}
        onSave={handleSave}
      />

      <PermissionDialog
        target={permissionTarget}
        isSaving={permissionMutation.isPending}
        error={permissionMutation.error}
        onClose={() => setPermissionTarget(null)}
        onSave={handleSavePermissions}
      />

      <Dialog
        open={deleteConfirmId !== null}
        onOpenChange={(open) => { if (!open) setDeleteConfirmId(null) }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>메일 rule 삭제</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">이 메일 rule을 삭제하시겠습니까? 되돌릴 수 없습니다.</p>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteConfirmId(null)}
              disabled={deleteMutation.isPending}
            >
              취소
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "삭제 중..." : "삭제"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
