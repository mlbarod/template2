import { RefreshCw, RotateCcw, Search } from "lucide-react"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

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

function getInheritedLabel() {
  return "자동"
}

function getEffectiveLabel(access) {
  if (access?.allowed) return "허용"
  if (access?.effectiveStatus === "pending") return "승인 대기"
  if (access?.effectiveStatus === "denied") return "차단"
  if (access?.effectiveStatus === "inactive") return "비활성"
  return "차단"
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

function getSourceDescription(access) {
  if (isSuperuserBypass(access)) return "슈퍼유저 권한으로 접근이 허용됩니다."
  if (access?.source === "portal_access_required") return "Portal 권한이 없어 앱 접근이 막힌 상태입니다."
  if (access?.source === "scope_inactive") return "권한 범위가 비활성화되어 접근할 수 없습니다."
  if (access?.source === "scope_not_found") return "권한 범위를 찾을 수 없습니다."
  if (access?.explicitStatus === "pending") return "사용자가 요청했고 아직 승인되지 않았습니다."
  if (access?.explicitStatus === "denied") return "관리자가 직접 차단했습니다."
  if (access?.explicitStatus === "allowed") return "관리자가 직접 허용했습니다."
  if (access?.source === "policy_department") return "사용자의 부서가 자동 규칙과 일치합니다."
  return "수동 설정이 없고 적용되는 자동 규칙도 없습니다."
}

function getPolicyDescription(access) {
  const policy = access?.policy
  if (access?.policyMatched || policy?.matched) {
    const ruleType = policy?.ruleType === "department" ? "부서" : policy?.ruleType || "규칙"
    const value = policy?.value || access?.department || "-"
    return `${ruleType}: ${value}`
  }
  return "적용 규칙 없음"
}

function getVisibleLabel(value, inheritedLabel) {
  if (value === "inherit") return inheritedLabel
  if (value === "pending") return "승인 대기"
  if (value === "denied") return "차단"
  return "허용"
}

function AccessTooltipContent({ access, scope, visibleLabel }) {
  const effectiveLabel = getEffectiveLabel(access)
  const metaLabel = getAccessMeta(access)
  const policyLabel = getPolicyDescription(access)
  const role = scope.scopeType === "portal" && access?.role ? access.role : ""

  return (
    <div className="grid max-w-72 gap-2 text-xs">
      <div className="font-medium text-popover-foreground">{scope.name}</div>
      <div className="grid gap-1">
        <div className="flex items-center justify-between gap-4">
          <span className="text-muted-foreground">선택값</span>
          <span className="font-medium">{visibleLabel}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-muted-foreground">최종 결과</span>
          <span className="font-medium">{effectiveLabel}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-muted-foreground">설정 방식</span>
          <span className="font-medium">{metaLabel}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-muted-foreground">자동 규칙</span>
          <span className="max-w-44 truncate font-medium" title={policyLabel}>{policyLabel}</span>
        </div>
        {access?.blockedByPortal ? (
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Portal 영향</span>
            <span className="font-medium">Portal 차단 우선</span>
          </div>
        ) : null}
        {role ? (
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">내부 role</span>
            <span className="font-medium">{role}</span>
          </div>
        ) : null}
      </div>
      <p className="leading-5 text-muted-foreground">{getSourceDescription(access)}</p>
    </div>
  )
}

function AppPermissionCell({ user, scope, access, pendingCell, isMutating, onChange }) {
  const cellKey = `${user.id}:${scope.key}`
  const value = getCellValue(access)
  const hasSuperuserBypass = isSuperuserBypass(access)
  const isScopeUnavailable = ["scope_inactive", "scope_not_found"].includes(access?.source)
  const isPending = pendingCell === cellKey
  const inheritedLabel = getInheritedLabel()
  const visibleLabel = getVisibleLabel(value, inheritedLabel)
  const tooltipLabel = `${visibleLabel}, 최종 ${getEffectiveLabel(access)}, ${getAccessMeta(access)}`

  return (
    <div className="flex w-40 min-w-40 max-w-40 items-center justify-center gap-1 overflow-visible">
      <Select
        value={value}
        onValueChange={(nextValue) => onChange({ user, scope, access, nextValue })}
        disabled={hasSuperuserBypass || isScopeUnavailable || isPending || isMutating}
      >
        <Tooltip>
          <TooltipTrigger asChild>
            <SelectTrigger
              className="h-8 w-24 shrink-0 text-center text-xs"
              aria-label={`${user.knoxId || user.sabun || user.id} ${scope.name} 권한, ${tooltipLabel}`}
            >
              {isPending ? <RefreshCw className="size-3.5 animate-spin" /> : null}
              <SelectValue />
            </SelectTrigger>
          </TooltipTrigger>
          <TooltipContent side="top" align="center" className="p-3">
            <AccessTooltipContent access={access} scope={scope} visibleLabel={visibleLabel} />
          </TooltipContent>
        </Tooltip>
        <SelectContent>
          <SelectItem value="inherit">{inheritedLabel}</SelectItem>
          {value === "pending" ? <SelectItem value="pending">승인 대기</SelectItem> : null}
          <SelectItem value="allowed">허용</SelectItem>
          <SelectItem value="denied">차단</SelectItem>
        </SelectContent>
      </Select>
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
              <TableRow className="h-12 bg-muted hover:bg-muted">
                <TableHead className="sticky left-0 z-40 w-44 min-w-44 max-w-44 bg-muted px-2 text-center text-xs font-medium text-muted-foreground shadow-[inset_0_-1px_0_hsl(var(--border))]">
                  이름
                </TableHead>
                <TableHead className="sticky left-44 z-40 w-40 min-w-40 max-w-40 bg-muted px-2 text-center text-[11px] font-medium text-muted-foreground shadow-[inset_0_-1px_0_hsl(var(--border))]">
                  사용자 ID (Knox ID)
                </TableHead>
                <TableHead className="sticky left-84 z-40 w-40 min-w-40 max-w-40 border-r bg-muted px-2 text-center text-xs font-medium text-muted-foreground shadow-[inset_0_-1px_0_hsl(var(--border))]">
                  부서
                </TableHead>
                {scopes.map((scope) => {
                  return (
                    <TableHead
                      key={scope.key}
                      className="z-30 w-44 min-w-44 max-w-44 bg-muted px-2 text-center align-middle shadow-[inset_0_-1px_0_hsl(var(--border))]"
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
