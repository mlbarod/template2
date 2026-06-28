import { useEffect, useRef, useState } from "react"
import { Filter, Plus, Save, Trash2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"

import {
  useCreateExclusionFilter,
  useDeleteExclusionFilter,
  useExclusionFilters,
  useUpdateExclusionFilter,
} from "../hooks/useL3SpiderExclusionFilters"

// ── 필드 정의 ────────────────────────────────────────────────────────────────
const PATTERN_FIELDS = [
  { key: "lineId",     api: "line_id",    label: "Line ID",    w: "w-24" },
  { key: "processId",  api: "process_id", label: "Process ID", w: "w-24" },
  { key: "edsStep",    api: "eds_step",   label: "EDS Step",   w: "w-28" },
  { key: "stepSeq",    api: "step_seq",   label: "Step Seq",   w: "w-24" },
  { key: "ppid",       api: "ppid",       label: "PPID",       w: "w-28" },
  { key: "eqpch",      api: "eqpch",      label: "EQPCH",      w: "w-24" },
  { key: "binName",    api: "bin_name",   label: "Bin Name",   w: "w-28" },
]

const EMPTY_EDIT = {
  lineId: "*", processId: "*", edsStep: "*", stepSeq: "*",
  ppid: "*", eqpch: "*", binName: "*",
  dateFrom: "", dateTo: "", memo: "", isActive: true,
}

function rowToEdit(row) {
  return {
    lineId:    row.lineId    ?? "*",
    processId: row.processId ?? "*",
    edsStep:   row.edsStep   ?? "*",
    stepSeq:   row.stepSeq   ?? "*",
    ppid:      row.ppid      ?? "*",
    eqpch:     row.eqpch     ?? "*",
    binName:   row.binName   ?? "*",
    dateFrom:  row.dateFrom  ?? "",
    dateTo:    row.dateTo    ?? "",
    memo:      row.memo      ?? "",
    isActive:  row.isActive  ?? true,
  }
}

function editToPayload(edit) {
  return {
    line_id:    edit.lineId    || "*",
    process_id: edit.processId || "*",
    eds_step:   edit.edsStep   || "*",
    step_seq:   edit.stepSeq   || "*",
    ppid:       edit.ppid      || "*",
    eqpch:      edit.eqpch     || "*",
    bin_name:   edit.binName   || "*",
    date_from:  edit.dateFrom  || null,
    date_to:    edit.dateTo    || null,
    memo:       edit.memo      || "",
    is_active:  edit.isActive,
  }
}

// ── 셀 표시 ──────────────────────────────────────────────────────────────────
function PatternCell({ value }) {
  const isWild = value === "*"
  return (
    <span className={cn("font-mono text-xs", isWild ? "text-muted-foreground/50" : "font-semibold text-foreground")}>
      {value}
    </span>
  )
}

// ── 편집 행 ──────────────────────────────────────────────────────────────────
function EditableRow({ initialEdit, onSave, onCancel, isSaving }) {
  const [edit, setEdit] = useState(initialEdit)
  const firstRef = useRef(null)

  useEffect(() => { firstRef.current?.focus() }, [])

  const set = (key, value) => setEdit((prev) => ({ ...prev, [key]: value }))

  return (
    <TableRow className="bg-primary/5">
      {/* 활성 */}
      <TableCell className="text-center">
        <Switch
          checked={edit.isActive}
          onCheckedChange={(v) => set("isActive", v)}
          disabled={isSaving}
        />
      </TableCell>

      {/* 패턴 7개 */}
      {PATTERN_FIELDS.map(({ key }, i) => (
        <TableCell key={key} className="px-1 py-1">
          <Input
            ref={i === 0 ? firstRef : undefined}
            value={edit[key]}
            onChange={(e) => set(key, e.target.value)}
            className="h-7 min-w-0 font-mono text-xs"
            placeholder="*"
            disabled={isSaving}
            onKeyDown={(e) => {
              if (e.key === "Escape") onCancel()
            }}
          />
        </TableCell>
      ))}

      {/* 날짜 범위 */}
      <TableCell className="px-1 py-1">
        <Input
          type="date"
          value={edit.dateFrom}
          onChange={(e) => set("dateFrom", e.target.value)}
          className="h-7 w-32 text-xs"
          disabled={isSaving}
        />
      </TableCell>
      <TableCell className="px-1 py-1">
        <Input
          type="date"
          value={edit.dateTo}
          onChange={(e) => set("dateTo", e.target.value)}
          className="h-7 w-32 text-xs"
          disabled={isSaving}
        />
      </TableCell>

      {/* 메모 */}
      <TableCell className="px-1 py-1">
        <Input
          value={edit.memo}
          onChange={(e) => set("memo", e.target.value)}
          placeholder="설명"
          className="h-7 min-w-0 text-xs"
          disabled={isSaving}
        />
      </TableCell>

      {/* 등록자/등록일: edit 중에는 빈 칸 */}
      <TableCell />
      <TableCell />

      {/* 저장/취소 */}
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-1">
          <Button
            type="button"
            size="icon"
            className="size-7"
            onClick={() => onSave(edit)}
            disabled={isSaving}
          >
            <Save className="size-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={onCancel}
            disabled={isSaving}
          >
            <X className="size-3.5" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

// ── 읽기 행 ──────────────────────────────────────────────────────────────────
function ReadRow({ row, onEdit, onDelete, onToggle, isUpdating }) {
  return (
    <TableRow className={cn(!row.isActive && "opacity-40")}>
      <TableCell className="text-center">
        <Switch
          checked={row.isActive}
          onCheckedChange={(v) => onToggle(v)}
          disabled={isUpdating}
        />
      </TableCell>
      {PATTERN_FIELDS.map(({ key }) => (
        <TableCell key={key}>
          <PatternCell value={row[key] ?? "*"} />
        </TableCell>
      ))}
      <TableCell className="text-xs text-muted-foreground">{row.dateFrom ?? "—"}</TableCell>
      <TableCell className="text-xs text-muted-foreground">{row.dateTo ?? "—"}</TableCell>
      <TableCell className="max-w-[120px] truncate text-xs text-muted-foreground" title={row.memo}>
        {row.memo || "—"}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">{row.createdBy ?? "—"}</TableCell>
      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{row.createdAt}</TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-1">
          <Button type="button" variant="ghost" size="icon" className="size-7" onClick={onEdit}>
            <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7 text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={onDelete}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

// ── 메인 시트 ─────────────────────────────────────────────────────────────────
export function L3SpiderExclusionSheet() {
  const { data: filters = [], isLoading } = useExclusionFilters()
  const createMutation = useCreateExclusionFilter()
  const updateMutation = useUpdateExclusionFilter()
  const deleteMutation = useDeleteExclusionFilter()

  const [editingId, setEditingId] = useState(null)   // null | "new" | number
  const [deleteConfirmId, setDeleteConfirmId] = useState(null)

  const isSaving = createMutation.isPending || updateMutation.isPending

  const activeCount = filters.filter((f) => f.isActive).length

  const handleSaveNew = (edit) => {
    createMutation.mutate(editToPayload(edit), {
      onSuccess: () => setEditingId(null),
    })
  }

  const handleSaveEdit = (id, edit) => {
    updateMutation.mutate({ id, ...editToPayload(edit) }, {
      onSuccess: () => setEditingId(null),
    })
  }

  const handleToggle = (row, isActive) => {
    updateMutation.mutate({ id: row.id, is_active: isActive })
  }

  const handleConfirmDelete = () => {
    deleteMutation.mutate(deleteConfirmId, {
      onSuccess: () => setDeleteConfirmId(null),
    })
  }

  return (
    <>
      <Sheet>
        <SheetTrigger asChild>
          <Button type="button" variant="outline" size="sm" className="h-8 gap-1.5 px-3 text-xs">
            <Filter className="size-3.5" />
            제외 필터
            {activeCount > 0 && (
              <Badge variant="destructive" className="ml-0.5 h-4 px-1.5 text-[10px]">
                {activeCount}
              </Badge>
            )}
          </Button>
        </SheetTrigger>

        <SheetContent side="right" className="flex w-full max-w-[98vw] flex-col gap-0 p-0 sm:max-w-[1400px]">
          <SheetHeader className="border-b px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <SheetTitle className="text-base">제외 필터 관리</SheetTitle>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  매칭 row를 차트·Stats에서 제외합니다.&nbsp;
                  <code className="rounded bg-muted px-1 font-mono">*</code> 전체&nbsp;·&nbsp;
                  <code className="rounded bg-muted px-1 font-mono">PP%</code> PP로 시작&nbsp;·&nbsp;
                  <code className="rounded bg-muted px-1 font-mono">%PP%</code> PP 포함
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                className="gap-1.5"
                onClick={() => setEditingId("new")}
                disabled={editingId === "new"}
              >
                <Plus className="size-3.5" />
                필터 추가
              </Button>
            </div>
          </SheetHeader>

          <div className="min-h-0 flex-1 overflow-auto px-4 py-3">
            {isLoading ? (
              <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">로딩 중…</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-14 text-center">활성</TableHead>
                    {PATTERN_FIELDS.map(({ label }) => (
                      <TableHead key={label}>{label}</TableHead>
                    ))}
                    <TableHead>날짜 시작</TableHead>
                    <TableHead>날짜 종료</TableHead>
                    <TableHead>메모</TableHead>
                    <TableHead>등록자</TableHead>
                    <TableHead>등록일</TableHead>
                    <TableHead className="w-20 text-right">작업</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {/* 새 필터 추가 행 */}
                  {editingId === "new" && (
                    <EditableRow
                      initialEdit={EMPTY_EDIT}
                      onSave={handleSaveNew}
                      onCancel={() => setEditingId(null)}
                      isSaving={isSaving}
                    />
                  )}

                  {filters.length === 0 && editingId !== "new" && (
                    <TableRow>
                      <TableCell colSpan={13} className="py-10 text-center text-sm text-muted-foreground">
                        <Filter className="mx-auto mb-2 size-6 opacity-30" />
                        등록된 필터가 없습니다. &quot;필터 추가&quot;를 클릭하세요.
                      </TableCell>
                    </TableRow>
                  )}

                  {filters.map((row) =>
                    editingId === row.id ? (
                      <EditableRow
                        key={row.id}
                        initialEdit={rowToEdit(row)}
                        onSave={(edit) => handleSaveEdit(row.id, edit)}
                        onCancel={() => setEditingId(null)}
                        isSaving={isSaving}
                      />
                    ) : (
                      <ReadRow
                        key={row.id}
                        row={row}
                        onEdit={() => setEditingId(row.id)}
                        onDelete={() => setDeleteConfirmId(row.id)}
                        onToggle={(v) => handleToggle(row, v)}
                        isUpdating={updateMutation.isPending}
                      />
                    )
                  )}
                </TableBody>
              </Table>
            )}
          </div>
        </SheetContent>
      </Sheet>

      {/* 삭제 확인 다이얼로그 */}
      <Dialog
        open={deleteConfirmId !== null}
        onOpenChange={(v) => { if (!v) setDeleteConfirmId(null) }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>필터 삭제</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">이 필터를 삭제하시겠습니까? 되돌릴 수 없습니다.</p>
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
              {deleteMutation.isPending ? "삭제 중…" : "삭제"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
