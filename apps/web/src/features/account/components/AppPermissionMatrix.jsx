import { RefreshCw, RotateCcw, Search, SlidersHorizontal } from "lucide-react"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

const ROLE_LABELS = {
  viewer: "Portal 조회 역할",
  member: "Portal 일반 역할",
  manager: "Portal 운영 역할",
  admin: "Portal 관리자 역할",
}

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
  if (access?.policyMatched || access?.policy?.matched) {
    return "자동 허용"
  }
  return "미지정"
}

function getAccessMeta(access) {
  if (isSuperuserBypass(access)) return "슈퍼유저"
  if (access?.source === "portal_access_required") return "Portal 차단"
  if (access?.source === "scope_inactive") return "권한 범위 비활성"
  if (access?.source === "scope_not_found") return "권한 범위 없음"
  if (access?.explicitStatus === "pending") return "승인 대기"
  if (access?.explicitStatus === "denied") return "수동 차단"
  if (access?.explicitStatus === "allowed") return "수동 부여"
  if (access?.source === "policy_department") return "부서 자동 규칙"
  return "자동 규칙 없음"
}

function AppPermissionCell({ user, scope, access, pendingCell, isMutating, onChange, onRoleChange }) {
  const cellKey = `${user.id}:${scope.key}`
  const value = getCellValue(access)
  const hasSuperuserBypass = isSuperuserBypass(access)
  const isPortal = scope.scopeType === "portal"
  const isScopeUnavailable = ["scope_inactive", "scope_not_found"].includes(access?.source)
  const isPending = pendingCell === cellKey
  const inheritedLabel = getInheritedLabel(access)
  const roleLabel = ROLE_LABELS[access?.role] || access?.role || scope.defaultRole || "Portal 조회 역할"

  return (
    <div className="flex w-40 min-w-40 max-w-40 items-center justify-center gap-1 overflow-hidden">
      <Select
        value={value}
        onValueChange={(nextValue) => onChange({ user, scope, access, nextValue })}
        disabled={hasSuperuserBypass || isScopeUnavailable || isPending || isMutating}
      >
        <SelectTrigger
          className="h-8 w-24 shrink-0 text-center text-xs"
          aria-label={`${user.knoxId || user.sabun || user.id} ${scope.name} 권한`}
        >
          {isPending ? <RefreshCw className="size-3.5 animate-spin" /> : null}
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="inherit">{inheritedLabel}</SelectItem>
          {value === "pending" ? <SelectItem value="pending">승인 대기</SelectItem> : null}
          <SelectItem value="allowed">{access?.blockedByPortal ? "허용 설정" : "허용"}</SelectItem>
          <SelectItem value="denied">차단</SelectItem>
        </SelectContent>
      </Select>
      {!hasSuperuserBypass ? (
        <span className="min-w-0 flex-1 truncate text-center text-[11px] text-muted-foreground" title={getAccessMeta(access)}>
          {getAccessMeta(access)}
        </span>
      ) : null}
      {!hasSuperuserBypass && isPortal && access?.allowed ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              className="size-7 shrink-0 text-muted-foreground"
              onClick={() => onRoleChange({ user, scope, access })}
              disabled={isPending || isMutating}
              aria-label={`${user.knoxId || user.sabun || user.id} ${scope.name} ${roleLabel} 변경`}
            >
              <SlidersHorizontal className="size-3" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">{roleLabel} 변경</TooltipContent>
        </Tooltip>
      ) : null}
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
  onAccessChange,
  onRoleChange,
  pendingCell,
  isMutating = false,
}) {
  const scopes = query.data?.scopes || []
  const rows = query.data?.results || []
  const hasFilters = Boolean(filters.search || filters.department)
  const isBusy = isMutating || query.isFetching
  const handleScroll = (event) => {
    if (!query.hasNextPage || query.isFetching || query.isFetchingNextPage) return
    const { scrollTop, scrollHeight, clientHeight } = event.target
    if (scrollHeight - scrollTop - clientHeight <= 96) {
      query.fetchNextPage()
    }
  }

  return (
    <Card className="grid min-w-0 grid-rows-[auto_minmax(0,1fr)] overflow-hidden py-0 xl:h-full xl:min-h-0">
      <form
        className="grid gap-3 border-b p-4 md:grid-cols-[minmax(180px,240px)_minmax(180px,240px)_auto] md:items-end xl:px-4 xl:py-3"
        onSubmit={(event) => {
          event.preventDefault()
          onApplyFilters()
        }}
      >
        <div className="grid min-w-0 gap-1.5">
          <Label htmlFor="app-permission-user-search">사용자 ID</Label>
          <Input
            id="app-permission-user-search"
            className="w-full"
            value={filterDraft.search}
            onChange={(event) => setFilterDraft((current) => ({ ...current, search: event.target.value }))}
            placeholder="Knox ID, 사번, 이름"
          />
        </div>
        <div className="grid min-w-0 gap-1.5">
          <Label htmlFor="app-permission-department-search">부서</Label>
          <Input
            id="app-permission-department-search"
            className="w-full"
            value={filterDraft.department}
            onChange={(event) => setFilterDraft((current) => ({ ...current, department: event.target.value }))}
            placeholder="정확한 부서명"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button type="submit" disabled={query.isFetching}>
            <Search className="size-4" />
            검색
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onResetFilters}
            disabled={query.isFetching || (!hasFilters && !filterDraft.search && !filterDraft.department)}
          >
            <RotateCcw className="size-4" />
            초기화
          </Button>
        </div>
      </form>

      <CardContent
        className="min-h-0 min-w-0 overflow-auto p-0"
        aria-busy={query.isFetching}
        onScrollCapture={handleScroll}
      >
        {query.isPending ? (
          <div className="grid gap-3 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={`app-permission-matrix-${index}`} className="h-14 w-full" />
            ))}
          </div>
        ) : query.error && !rows.length ? (
          <div className="flex min-h-40 flex-col items-center justify-center gap-3 p-6" role="alert">
            <p className="text-sm text-destructive">권한 매트릭스를 불러오지 못했습니다.</p>
            <Button type="button" size="sm" variant="outline" onClick={() => query.refetch()}>
              <RefreshCw className="size-4" />
              다시 시도
            </Button>
          </div>
        ) : !scopes.length ? (
          <div className="flex min-h-40 items-center justify-center p-6 text-sm text-muted-foreground">
            표시할 권한 범위가 없습니다.
          </div>
        ) : !rows.length ? (
          <div className="flex min-h-40 items-center justify-center p-6 text-sm text-muted-foreground">
            표시할 사용자가 없습니다.
          </div>
        ) : (
          <Table stickyHeader className="w-max min-w-full" aria-label="사용자별 접근 권한 매트릭스">
            <TableHeader>
              <TableRow className="h-12 hover:bg-transparent">
                <TableHead className="sticky left-0 z-30 w-44 min-w-44 max-w-44 bg-muted px-2 text-center text-xs font-medium text-muted-foreground">
                  이름
                </TableHead>
                <TableHead className="sticky left-44 z-30 w-40 min-w-40 max-w-40 bg-muted px-2 text-center text-[11px] font-medium text-muted-foreground">
                  사용자 ID (Knox ID)
                </TableHead>
                <TableHead className="sticky left-84 z-30 w-40 min-w-40 max-w-40 border-r bg-muted px-2 text-center text-xs font-medium text-muted-foreground">
                  부서
                </TableHead>
                {scopes.map((scope) => {
                  const isPortal = scope.scopeType === "portal"
                  return (
                    <TableHead
                      key={scope.key}
                      className={isPortal ? "w-44 min-w-44 max-w-44 bg-muted/60 px-2 text-center align-middle" : "w-44 min-w-44 max-w-44 bg-muted/30 px-2 text-center align-middle"}
                    >
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span
                            className="mx-auto block w-fit rounded-sm whitespace-nowrap text-xs font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            tabIndex={0}
                            aria-label={`${scope.name}, ${scope.key}`}
                          >
                            {scope.name}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top">{scope.key}</TooltipContent>
                      </Tooltip>
                    </TableHead>
                  )
                })}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const name = row.user.displayName || "이름 없음"
                const knoxId = row.user.knoxId || "-"
                const department = row.user.department || "부서 없음"
                return (
                  <TableRow key={row.user.id} className="group h-12 hover:bg-muted/40">
                    <TableCell className="sticky left-0 z-20 w-44 min-w-44 max-w-44 overflow-hidden bg-card px-2 py-2 text-center group-hover:bg-muted">
                      <span className="flex min-w-0 items-center justify-center gap-1">
                        <span className="min-w-0 truncate text-sm font-medium" title={name}>{name}</span>
                        {row.user.isSuperuser ? (
                          <Badge variant="secondary" className="h-5 shrink-0 px-1.5 text-[10px]">
                            SuperUser
                          </Badge>
                        ) : null}
                      </span>
                    </TableCell>
                    <TableCell className="sticky left-44 z-20 w-40 min-w-40 max-w-40 overflow-hidden bg-card px-2 py-2 text-center group-hover:bg-muted">
                      <span className="block truncate text-sm" title={knoxId}>{knoxId}</span>
                    </TableCell>
                    <TableCell className="sticky left-84 z-20 w-40 min-w-40 max-w-40 overflow-hidden border-r bg-card px-2 py-2 text-center group-hover:bg-muted">
                      <span className="block truncate text-sm text-muted-foreground" title={department}>{department}</span>
                    </TableCell>
                    {scopes.map((scope) => {
                      const isPortal = scope.scopeType === "portal"
                      return (
                        <TableCell key={scope.key} className={isPortal ? "w-44 min-w-44 max-w-44 bg-muted/10 px-2 py-2 text-center" : "w-44 min-w-44 max-w-44 px-2 py-2 text-center"}>
                          <AppPermissionCell
                            user={row.user}
                            scope={scope}
                            access={row.accesses?.[scope.key]}
                            pendingCell={pendingCell}
                            isMutating={isBusy}
                            onChange={onAccessChange}
                            onRoleChange={onRoleChange}
                          />
                        </TableCell>
                      )
                    })}
                  </TableRow>
                )
              })}
              {query.isFetchingNextPage ? (
                <TableRow className="h-12 hover:bg-transparent">
                  <TableCell colSpan={scopes.length + 3} className="text-center text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-2">
                      <RefreshCw className="size-3.5 animate-spin" />
                      추가 사용자를 불러오는 중...
                    </span>
                  </TableCell>
                </TableRow>
              ) : null}
              {query.isFetchNextPageError ? (
                <TableRow className="h-12 hover:bg-transparent">
                  <TableCell colSpan={scopes.length + 3} className="text-center">
                    <Button type="button" size="sm" variant="ghost" onClick={() => query.fetchNextPage()}>
                      <RefreshCw className="size-3.5" />
                      추가 목록 다시 불러오기
                    </Button>
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
