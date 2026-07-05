// 파일 경로: src/features/line-dashboard/pages/LineDashboardDroneTargetAdminPage.jsx
// superuser 전용 drone_sop_target 관리 화면입니다.
import * as React from "react"
import {
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldAlert,
  Trash2,
  X,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useAuth } from "@/lib/auth"

import { useDroneTargetAdmin } from "../hooks/useDroneTargetAdmin"

const EMPTY_DRAFT = { lineId: "", targetUserSdwtProd: "" }
const EMPTY_TARGETS = []

function normalizeDraftValue(value) {
  return typeof value === "string" ? value.trim() : ""
}

function buildMutationError(error, fallback) {
  return error instanceof Error && error.message ? error.message : fallback
}

function formatDateTime(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

function buildRelatedSummary(target) {
  if (!target) return ""
  const parts = [
    `mapping ${target.mappingCount}`,
    `recipient ${target.recipientCount}`,
    `channel ${target.channelConfigCount}`,
    `dispatch ${target.dispatchCount}`,
  ]
  if (target.hasNeedToSendRule) parts.push("rule 1")
  return parts.join(" · ")
}

function hasRelatedRows(target) {
  return Boolean(
    target &&
      (target.mappingCount > 0 ||
        target.recipientCount > 0 ||
        target.channelConfigCount > 0 ||
        target.dispatchCount > 0 ||
        target.hasNeedToSendRule),
  )
}

function RelatedCountBadges({ target }) {
  return (
    <div className="flex flex-wrap gap-1">
      <Badge variant="secondary">Mapping {target.mappingCount}</Badge>
      <Badge variant="secondary">Recipient {target.recipientCount}</Badge>
      <Badge variant="secondary">Channel {target.channelConfigCount}</Badge>
      <Badge variant="secondary">Dispatch {target.dispatchCount}</Badge>
      {target.hasNeedToSendRule ? <Badge variant="outline">Need rule</Badge> : null}
    </div>
  )
}

export function LineDashboardDroneTargetAdminPage() {
  const { user } = useAuth()
  const isSuperuser = Boolean(user?.is_superuser)
  const {
    targetsQuery,
    createMutation,
    updateMutation,
    deleteMutation,
  } = useDroneTargetAdmin({ enabled: isSuperuser })
  const [createDraft, setCreateDraft] = React.useState(EMPTY_DRAFT)
  const [editId, setEditId] = React.useState(null)
  const [editDraft, setEditDraft] = React.useState(EMPTY_DRAFT)
  const [deleteTarget, setDeleteTarget] = React.useState(null)
  const [search, setSearch] = React.useState("")
  const [formError, setFormError] = React.useState("")
  const [actionError, setActionError] = React.useState("")

  const targets = targetsQuery.data?.targets || EMPTY_TARGETS
  const normalizedSearch = search.trim().toLowerCase()
  const filteredTargets = React.useMemo(() => {
    if (!normalizedSearch) return targets
    return targets.filter((target) => {
      const lineId = target.lineId.toLowerCase()
      const targetValue = target.targetUserSdwtProd.toLowerCase()
      return lineId.includes(normalizedSearch) || targetValue.includes(normalizedSearch)
    })
  }, [normalizedSearch, targets])

  const isCreating = createMutation.isPending
  const isUpdating = updateMutation.isPending
  const isDeleting = deleteMutation.isPending

  const handleCreateSubmit = async (event) => {
    event.preventDefault()
    const lineId = normalizeDraftValue(createDraft.lineId)
    const targetUserSdwtProd = normalizeDraftValue(createDraft.targetUserSdwtProd)
    if (!lineId || !targetUserSdwtProd) {
      setFormError("Line ID와 Target 값을 모두 입력하세요.")
      return
    }

    setFormError("")
    setActionError("")
    try {
      await createMutation.mutateAsync({ lineId, targetUserSdwtProd })
      setCreateDraft(EMPTY_DRAFT)
    } catch (error) {
      setFormError(buildMutationError(error, "Target 생성에 실패했습니다."))
    }
  }

  const handleStartEdit = (target) => {
    setEditId(target.id)
    setEditDraft({
      lineId: target.lineId,
      targetUserSdwtProd: target.targetUserSdwtProd,
    })
    setActionError("")
  }

  const handleCancelEdit = () => {
    setEditId(null)
    setEditDraft(EMPTY_DRAFT)
    setActionError("")
  }

  const handleSaveEdit = async (target) => {
    const lineId = normalizeDraftValue(editDraft.lineId)
    const targetUserSdwtProd = normalizeDraftValue(editDraft.targetUserSdwtProd)
    if (!lineId || !targetUserSdwtProd) {
      setActionError("Line ID와 Target 값을 모두 입력하세요.")
      return
    }

    setActionError("")
    try {
      await updateMutation.mutateAsync({ id: target.id, lineId, targetUserSdwtProd })
      handleCancelEdit()
    } catch (error) {
      setActionError(buildMutationError(error, "Target 수정에 실패했습니다."))
    }
  }

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return
    setActionError("")
    try {
      await deleteMutation.mutateAsync({ id: deleteTarget.id })
      setDeleteTarget(null)
      if (editId === deleteTarget.id) handleCancelEdit()
    } catch (error) {
      setActionError(buildMutationError(error, "Target 삭제에 실패했습니다."))
    }
  }

  if (!isSuperuser) {
    return (
      <div className="flex h-full min-h-0 items-start px-6 py-4">
        <section className="w-full rounded-lg border bg-card p-6">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 size-5 text-destructive" aria-hidden="true" />
            <div className="space-y-1">
              <h1 className="text-base font-semibold">Superuser 권한 필요</h1>
              <p className="text-sm text-muted-foreground">
                drone_sop_target 관리는 superuser 계정에서만 사용할 수 있습니다.
              </p>
            </div>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="shrink-0 border-b px-6 py-4">
        <div className="flex min-w-0 items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight">Drone Target 관리</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              superuser 전용 drone_sop_target 기준 정보 관리
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => targetsQuery.refetch()}
            disabled={targetsQuery.isFetching}
          >
            <RefreshCw className={targetsQuery.isFetching ? "mr-2 size-4 animate-spin" : "mr-2 size-4"} />
            새로고침
          </Button>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-rows-[auto,1fr] gap-4 overflow-hidden px-6 py-4">
        <section className="rounded-lg border bg-card">
          <form className="grid grid-cols-[220px,1fr,auto] items-end gap-3 p-4" onSubmit={handleCreateSubmit}>
            <div className="space-y-1.5">
              <label htmlFor="drone-target-line" className="text-xs font-medium text-muted-foreground">
                Line ID
              </label>
              <Input
                id="drone-target-line"
                value={createDraft.lineId}
                maxLength={50}
                placeholder="L1"
                onChange={(event) => setCreateDraft((draft) => ({ ...draft, lineId: event.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="drone-target-value" className="text-xs font-medium text-muted-foreground">
                Target
              </label>
              <Input
                id="drone-target-value"
                value={createDraft.targetUserSdwtProd}
                maxLength={64}
                placeholder="TARGET_USER_SDWT"
                onChange={(event) => setCreateDraft((draft) => ({ ...draft, targetUserSdwtProd: event.target.value }))}
              />
            </div>
            <Button type="submit" disabled={isCreating}>
              <Plus className="mr-2 size-4" />
              추가
            </Button>
          </form>
          {formError ? (
            <p className="border-t px-4 py-2 text-sm text-destructive" role="alert">
              {formError}
            </p>
          ) : null}
        </section>

        <section className="grid min-h-0 grid-rows-[auto,auto,1fr] rounded-lg border bg-card">
          <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold">Target 목록</h2>
              <p className="text-xs text-muted-foreground">
                {filteredTargets.length} / {targets.length} rows
              </p>
            </div>
            <div className="relative w-[320px]">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input
                value={search}
                placeholder="Line 또는 Target 검색"
                className="pl-8"
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
          </div>

          {actionError ? (
            <p className="border-b px-4 py-2 text-sm text-destructive" role="alert">
              {actionError}
            </p>
          ) : null}

          <div className="min-h-0 overflow-y-auto">
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-card">
                <TableRow>
                  <TableHead className="w-[90px]">ID</TableHead>
                  <TableHead className="w-[220px]">Line ID</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead className="w-[360px]">Related</TableHead>
                  <TableHead className="w-[190px]">Updated</TableHead>
                  <TableHead className="w-[160px] text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {targetsQuery.isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-28 text-center text-sm text-muted-foreground">
                      Target 목록을 불러오는 중입니다.
                    </TableCell>
                  </TableRow>
                ) : null}
                {targetsQuery.isError ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-28 text-center text-sm text-destructive">
                      {buildMutationError(targetsQuery.error, "Target 목록을 불러오지 못했습니다.")}
                    </TableCell>
                  </TableRow>
                ) : null}
                {!targetsQuery.isLoading && !targetsQuery.isError && filteredTargets.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-28 text-center text-sm text-muted-foreground">
                      표시할 target이 없습니다.
                    </TableCell>
                  </TableRow>
                ) : null}
                {filteredTargets.map((target) => {
                  const isEditing = editId === target.id
                  return (
                    <TableRow key={target.id} className={isEditing ? "bg-muted/40" : ""}>
                      <TableCell className="font-mono text-xs text-muted-foreground">{target.id}</TableCell>
                      <TableCell>
                        {isEditing ? (
                          <Input
                            value={editDraft.lineId}
                            maxLength={50}
                            onChange={(event) => setEditDraft((draft) => ({ ...draft, lineId: event.target.value }))}
                          />
                        ) : (
                          <span className="font-mono text-sm">{target.lineId || "-"}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {isEditing ? (
                          <Input
                            value={editDraft.targetUserSdwtProd}
                            maxLength={64}
                            onChange={(event) => (
                              setEditDraft((draft) => ({ ...draft, targetUserSdwtProd: event.target.value }))
                            )}
                          />
                        ) : (
                          <span className="font-mono text-sm font-medium">{target.targetUserSdwtProd}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <RelatedCountBadges target={target} />
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDateTime(target.updatedAt)}
                      </TableCell>
                      <TableCell className="text-right">
                        {isEditing ? (
                          <div className="flex justify-end gap-1.5">
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => handleSaveEdit(target)}
                              disabled={isUpdating}
                            >
                              <Save className="mr-1 size-3" />
                              저장
                            </Button>
                            <Button type="button" size="sm" variant="outline" onClick={handleCancelEdit}>
                              <X className="mr-1 size-3" />
                              취소
                            </Button>
                          </div>
                        ) : (
                          <div className="flex justify-end gap-1.5">
                            <Button type="button" size="sm" variant="outline" onClick={() => handleStartEdit(target)}>
                              <Pencil className="mr-1 size-3" />
                              수정
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="destructive"
                              onClick={() => setDeleteTarget(target)}
                            >
                              <Trash2 className="mr-1 size-3" />
                              삭제
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </section>
      </main>

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Target 삭제</DialogTitle>
            <DialogDescription>
              {deleteTarget ? `${deleteTarget.targetUserSdwtProd} target을 삭제합니다.` : "Target을 삭제합니다."}
            </DialogDescription>
          </DialogHeader>
          {deleteTarget && hasRelatedRows(deleteTarget) ? (
            <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
              연결 데이터: {buildRelatedSummary(deleteTarget)}
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>
              취소
            </Button>
            <Button type="button" variant="destructive" onClick={handleConfirmDelete} disabled={isDeleting}>
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
