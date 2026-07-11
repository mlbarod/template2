import { RefreshCw, RotateCcw, Search } from "lucide-react"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"

import { AccountDataTablePagination } from "./AccountDataTable"

function isSuperuserBypass(access) {
  return access?.source === "superuser_bypass" || access?.source === "admin"
}

function getCellValue(access) {
  if (isSuperuserBypass(access)) return "allowed"
  if (access?.explicitStatus === "pending") return "pending"
  if (access?.explicitStatus === "denied") return "denied"
  if (access?.explicitStatus === "allowed") return "allowed"
  return "inherit"
}

function getInheritedLabel(access) {
  if (access?.source === "policy_department") {
    return "자동 허용"
  }
  return "미지정"
}

function getAccessMeta(access) {
  if (isSuperuserBypass(access)) return "슈퍼유저"
  if (access?.explicitStatus === "pending") return "승인 대기"
  if (access?.explicitStatus === "denied") return "수동 차단"
  if (access?.explicitStatus === "allowed") return "수동 부여"
  if (access?.source === "policy_department") return "부서 자동 규칙"
  return "자동 규칙 없음"
}

function AppPermissionCell({ user, scope, access, pendingCell, onChange }) {
  const cellKey = `${user.id}:${scope.key}`
  const value = getCellValue(access)
  const hasSuperuserBypass = isSuperuserBypass(access)
  const isPending = pendingCell === cellKey
  const inheritedLabel = getInheritedLabel(access)

  return (
    <div className="grid min-w-36 gap-1">
      <Select
        value={value}
        onValueChange={(nextValue) => onChange({ user, scope, access, nextValue })}
        disabled={hasSuperuserBypass || isPending}
      >
        <SelectTrigger
          className="h-8 w-36 text-xs"
          aria-label={`${user.knoxId || user.sabun || user.id} ${scope.name} 권한`}
        >
          {isPending ? <RefreshCw className="size-3.5 animate-spin" /> : null}
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="inherit">{inheritedLabel}</SelectItem>
          {value === "pending" ? <SelectItem value="pending">승인 대기</SelectItem> : null}
          <SelectItem value="allowed">허용</SelectItem>
          <SelectItem value="denied">차단</SelectItem>
        </SelectContent>
      </Select>
      <span className="truncate text-[11px] text-muted-foreground" title={getAccessMeta(access)}>
        {getAccessMeta(access)}
      </span>
    </div>
  )
}

export function AppPermissionMatrix({
  query,
  filters,
  filterDraft,
  setFilterDraft,
  onApplyFilters,
  onResetFilters,
  onPageChange,
  onAccessChange,
  pendingCell,
}) {
  const scopes = query.data?.scopes || []
  const rows = query.data?.results || []
  const pagination = query.data?.pagination || {}
  const hasFilters = Boolean(filters.search || filters.department)

  return (
    <Card className="grid min-w-0 grid-rows-[auto_auto_minmax(0,1fr)_auto] overflow-hidden py-0 xl:h-full xl:min-h-0">
      <CardHeader className="border-b px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">앱별 권한 매트릭스</CardTitle>
            <CardDescription>사용자별 앱 접근을 허용하거나 차단하면 즉시 반영됩니다.</CardDescription>
          </div>
          <Badge variant="secondary">앱 {scopes.length.toLocaleString("ko-KR")}개</Badge>
        </div>
      </CardHeader>

      <form
        className="grid gap-3 border-b p-4 xl:grid-cols-[minmax(220px,1fr)_minmax(220px,1fr)_auto] xl:px-4 xl:py-3"
        onSubmit={(event) => {
          event.preventDefault()
          onApplyFilters()
        }}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="app-permission-user-search">사용자 ID</Label>
          <Input
            id="app-permission-user-search"
            value={filterDraft.search}
            onChange={(event) => setFilterDraft((current) => ({ ...current, search: event.target.value }))}
            placeholder="Knox ID, 사번, 이름"
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="app-permission-department-search">부서</Label>
          <Input
            id="app-permission-department-search"
            value={filterDraft.department}
            onChange={(event) => setFilterDraft((current) => ({ ...current, department: event.target.value }))}
            placeholder="정확한 부서명"
          />
        </div>
        <div className="flex items-end gap-2">
          <Button type="submit">
            <Search className="size-4" />
            검색
          </Button>
          <Button type="button" variant="outline" onClick={onResetFilters} disabled={!hasFilters && !filterDraft.search && !filterDraft.department}>
            <RotateCcw className="size-4" />
            초기화
          </Button>
        </div>
      </form>

      <CardContent className="min-h-0 min-w-0 overflow-auto p-0" aria-busy={query.isFetching}>
        {query.isPending ? (
          <div className="grid gap-3 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={`app-permission-matrix-${index}`} className="h-14 w-full" />
            ))}
          </div>
        ) : query.error ? (
          <div className="flex min-h-40 flex-col items-center justify-center gap-3 p-6" role="alert">
            <p className="text-sm text-destructive">앱 권한 목록을 불러오지 못했습니다.</p>
            <Button type="button" size="sm" variant="outline" onClick={() => query.refetch()}>
              <RefreshCw className="size-4" />
              다시 시도
            </Button>
          </div>
        ) : !scopes.length ? (
          <div className="flex min-h-40 items-center justify-center p-6 text-sm text-muted-foreground">
            활성화된 앱 scope가 없습니다.
          </div>
        ) : !rows.length ? (
          <div className="flex min-h-40 items-center justify-center p-6 text-sm text-muted-foreground">
            표시할 사용자가 없습니다.
          </div>
        ) : (
          <Table stickyHeader className="w-max min-w-full" aria-label="사용자별 앱 접근 권한 매트릭스">
            <TableHeader>
              <TableRow className="h-14 hover:bg-transparent">
                <TableHead className="sticky left-0 z-30 min-w-64 border-r bg-muted px-4 text-xs font-medium text-muted-foreground">
                  사용자 ID
                </TableHead>
                {scopes.map((scope) => (
                  <TableHead key={scope.key} className="min-w-44 bg-muted/30 px-4 align-middle">
                    <span className="block whitespace-nowrap text-xs font-medium text-foreground">{scope.name}</span>
                    <span className="block whitespace-nowrap text-[11px] font-normal text-muted-foreground">{scope.key}</span>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const identifier = row.user.knoxId || row.user.sabun || `#${row.user.id}`
                return (
                  <TableRow key={row.user.id} className="group h-16 hover:bg-muted/40">
                    <TableCell className="sticky left-0 z-20 min-w-64 border-r bg-card px-4 group-hover:bg-muted">
                      <span className="block truncate text-sm font-medium">{identifier}</span>
                      <span className="block max-w-56 truncate text-xs text-muted-foreground">
                        {row.user.displayName || "이름 없음"} · {row.user.department || "부서 없음"}
                      </span>
                    </TableCell>
                    {scopes.map((scope) => (
                      <TableCell key={scope.key} className="min-w-44 px-4 py-2">
                        <AppPermissionCell
                          user={row.user}
                          scope={scope}
                          access={row.accesses?.[scope.key]}
                          pendingCell={pendingCell}
                          onChange={onAccessChange}
                        />
                      </TableCell>
                    ))}
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <AccountDataTablePagination
        page={pagination.page || 1}
        pageSize={pagination.pageSize || 20}
        total={pagination.total || 0}
        totalPages={pagination.totalPages || 1}
        disabled={query.isFetching}
        onPageChange={onPageChange}
      />
    </Card>
  )
}
