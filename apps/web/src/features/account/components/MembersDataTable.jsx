import {
  Check,
  Clock3,
  Crown,
  Eye,
  Search,
  ShieldQuestion,
  X,
  UserRound,
  Users,
} from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import { AccountDataTable } from "./AccountDataTable"

const MEMBER_ROLE_OPTIONS = [
  { value: "all", label: "전체 멤버 권한" },
  { value: "manager", label: "운영 권한" },
  { value: "member", label: "일반 권한" },
  { value: "viewer", label: "조회 권한" },
]

const MEMBER_ROLE_LABELS = {
  viewer: "조회 권한",
  member: "일반 권한",
  manager: "운영 권한",
}

const MEMBER_ROLE_DESCRIPTIONS = {
  viewer: "멤버 목록을 확인할 수 있습니다.",
  member: "멤버 확인과 소속 변경 요청 처리가 가능합니다.",
  manager: "소속 멤버와 변경 요청을 운영 권한으로 관리합니다.",
}

const TAB_OPTIONS = [
  { value: "all", label: "전체" },
  { value: "members", label: "현재 멤버" },
  { value: "requests", label: "승인 대기" },
]

function getInitials(row) {
  const label = row.name || row.knoxId || "?"
  const parts = label.trim().split(/\s+/).filter(Boolean)
  if (parts.length > 1) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return label.slice(0, 2).toUpperCase()
}

function formatDate(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"
  return date.toLocaleString("ko-KR")
}

function MemberRole({ role }) {
  const normalizedRole = MEMBER_ROLE_LABELS[role] ? role : "viewer"
  const Icon = normalizedRole === "manager" ? Crown : normalizedRole === "member" ? UserRound : Eye
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="inline-flex cursor-help items-center gap-2 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
          <span className="text-sm">{MEMBER_ROLE_LABELS[normalizedRole]}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-64">
        {MEMBER_ROLE_DESCRIPTIONS[normalizedRole]}
      </TooltipContent>
    </Tooltip>
  )
}

function RequestActions({ row, isMutating, onApprove, onReject }) {
  if (row.type !== "request") return <span className="text-sm text-muted-foreground">-</span>

  const isPending = row.status === "PENDING"
  const canApprove = row.approvalRole === "member" || row.approvalRole === "manager"
  const disabled = !isPending || !canApprove || isMutating

  return (
    <div className="flex items-center justify-end gap-1.5">
      <Button
        type="button"
        size="sm"
        onClick={() => onApprove(row)}
        disabled={disabled}
        aria-label={`${row.name} 소속 변경 승인`}
      >
        <Check className="size-4" />
        승인
      </Button>
      <Button
        type="button"
        size="sm"
        variant="destructive"
        onClick={() => onReject(row)}
        disabled={disabled}
        aria-label={`${row.name} 소속 변경 거절`}
      >
        <X className="size-4" />
        거절
      </Button>
      {!canApprove ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <ShieldQuestion className="size-4" aria-hidden="true" />
            </span>
          </TooltipTrigger>
          <TooltipContent side="top">일반 권한 또는 운영 권한이 필요합니다.</TooltipContent>
        </Tooltip>
      ) : null}
    </div>
  )
}

export function MembersDataTable({
  rows,
  activeTab,
  onActiveTabChange,
  memberTotal,
  requestTotal,
  requestLoadedCount,
  roleFilter,
  onRoleFilterChange,
  searchTerm,
  onSearchTermChange,
  isLoading,
  isFetching,
  isLoadingMore,
  hasMoreRequests,
  onLoadMore,
  error,
  emptyMessage,
  onRetry,
  isMutating,
  showApprovalNotice,
  onApprove,
  onReject,
}) {
  const safeRows = Array.isArray(rows) ? rows : []
  const normalizedSearch = (searchTerm || "").trim().toLowerCase()
  const roleFilteredRows = roleFilter === "all"
    ? safeRows
    : safeRows.filter((row) => row.type === "request" || row.memberRole === roleFilter)
  const filteredRows = normalizedSearch
    ? roleFilteredRows.filter((row) => [
      row.name,
      row.knoxId,
      row.email,
      row.affiliationLabel,
      MEMBER_ROLE_LABELS[row.memberRole],
      row.status,
    ].some((value) => String(value || "").toLowerCase().includes(normalizedSearch)))
    : roleFilteredRows
  const displayedMemberCount = filteredRows.filter((row) => row.type === "member").length
  const displayedRequestCount = filteredRows.filter((row) => row.type === "request").length
  const loadedRequestCount = Number(requestLoadedCount) || 0
  const requestPagination = activeTab !== "members"
  const paginationSummary = activeTab === "all"
    ? `멤버 ${displayedMemberCount.toLocaleString("ko-KR")}명 · 요청 ${displayedRequestCount.toLocaleString("ko-KR")} / 로드 ${loadedRequestCount.toLocaleString("ko-KR")}건`
    : activeTab === "requests"
      ? `요청 ${displayedRequestCount.toLocaleString("ko-KR")} / 로드 ${loadedRequestCount.toLocaleString("ko-KR")} / 총 ${requestTotal.toLocaleString("ko-KR")}건`
      : `총 ${filteredRows.length.toLocaleString("ko-KR")}명`
  const paginationStatus = isLoadingMore
    ? `${paginationSummary} · 더 불러오는 중...`
    : hasMoreRequests && requestPagination
      ? `${paginationSummary} · 아래로 스크롤하면 더 불러옵니다.`
      : paginationSummary

  const userColumn = {
      id: "user",
      header: "사용자",
      cell: ({ row }) => {
        const item = row.original
        return (
          <div className="flex min-w-0 items-center gap-3">
            <Avatar className="size-9 border">
              <AvatarFallback className="text-xs font-medium text-muted-foreground">
                {getInitials(item)}
              </AvatarFallback>
            </Avatar>
            <div className="flex min-w-0 items-baseline gap-2">
              <span className="truncate text-sm font-medium text-foreground">{item.name}</span>
              <span className="truncate text-xs text-muted-foreground">
                {item.knoxId || item.email || "-"}
              </span>
            </div>
          </div>
        )
      },
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    }
  const listTypeColumn = {
      id: "listType",
      header: "목록 구분",
      cell: ({ row }) => row.original.type === "request" ? (
        <Badge variant="destructive">
          <Clock3 className="size-3" />
          승인 대기
        </Badge>
      ) : (
        <Badge variant="secondary">
          <Users className="size-3" />
          현재 멤버
        </Badge>
      ),
      meta: {
        headerClassName: "min-w-32",
        cellClassName: "min-w-32",
      },
    }
  const affiliationColumn = {
      accessorKey: "affiliationLabel",
      header: activeTab === "requests" ? "변경 대상" : "소속",
      cell: ({ row }) => (
        <span className="block max-w-72 truncate text-sm text-muted-foreground" title={row.original.affiliationLabel}>
          {row.original.affiliationLabel || "-"}
        </span>
      ),
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    }
  const memberRoleColumn = {
      id: "memberRole",
      header: "멤버 권한",
      cell: ({ row }) => row.original.type === "member"
        ? <MemberRole role={row.original.memberRole} />
        : <span className="text-sm text-muted-foreground">-</span>,
      meta: {
        headerClassName: "min-w-36",
        cellClassName: "min-w-36",
      },
    }
  const requestedAtColumn = {
      accessorKey: "requestedAt",
      header: "요청 시각",
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">{formatDate(row.original.requestedAt)}</span>
      ),
      meta: {
        headerClassName: "min-w-44",
        cellClassName: "min-w-44",
      },
    }
  const actionsColumn = {
      id: "actions",
      header: "작업",
      cell: ({ row }) => (
        <RequestActions
          row={row.original}
          isMutating={isMutating}
          onApprove={onApprove}
          onReject={onReject}
        />
      ),
      meta: {
        headerClassName: "sticky right-0 z-20 min-w-44 bg-muted/30 text-right",
        cellClassName: "sticky right-0 z-10 min-w-44 bg-card text-right group-hover:bg-muted/40",
      },
    }
  const columns = activeTab === "members"
    ? [userColumn, affiliationColumn, memberRoleColumn]
    : activeTab === "requests"
      ? [userColumn, affiliationColumn, requestedAtColumn, actionsColumn]
      : [userColumn, listTypeColumn, affiliationColumn, memberRoleColumn, requestedAtColumn, actionsColumn]

  const toolbar = (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-md border bg-muted p-1" role="tablist" aria-label="멤버 목록 구분">
          {TAB_OPTIONS.map((tab) => {
            const isActive = activeTab === tab.value
            const count =
              tab.value === "members"
                ? memberTotal
                : tab.value === "requests"
                  ? requestTotal
                  : memberTotal + requestTotal
            return (
              <Button
                key={tab.value}
                type="button"
                size="sm"
                variant={isActive ? "secondary" : "ghost"}
                className="h-8 px-3"
                role="tab"
                aria-selected={isActive}
                onClick={() => onActiveTabChange(tab.value)}
              >
                {tab.label}
                <span className="tabular-nums text-xs text-muted-foreground">
                  {count.toLocaleString("ko-KR")}
                </span>
              </Button>
            )
          })}
        </div>
        {isFetching && !isLoading ? <span className="text-xs text-muted-foreground">새로고침 중...</span> : null}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="grid gap-1.5">
          <Label htmlFor="members-search">검색</Label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              id="members-search"
              value={searchTerm}
              onChange={(event) => onSearchTermChange(event.target.value)}
              className="pl-9"
              placeholder="이름, Knox ID, 소속 검색"
            />
          </div>
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="members-role-filter">멤버 권한</Label>
          <Select
            value={roleFilter}
            onValueChange={onRoleFilterChange}
            disabled={activeTab === "requests"}
          >
            <SelectTrigger id="members-role-filter" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MEMBER_ROLE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {showApprovalNotice ? (
        <p className="text-xs text-muted-foreground">소속 변경 승인과 거절은 일반 권한 또는 운영 권한이 필요합니다.</p>
      ) : null}
    </div>
  )

  return (
    <AccountDataTable
      data={filteredRows}
      columns={columns}
      getRowId={(row) => row.id}
      toolbar={toolbar}
      isLoading={isLoading}
      isFetching={isFetching}
      error={error}
      emptyMessage={normalizedSearch ? "검색 조건에 맞는 항목이 없습니다." : emptyMessage}
      onRetry={onRetry}
      pagination={{
        page: 1,
        pageSize: Math.max(filteredRows.length, 1),
        total: requestPagination ? requestTotal : filteredRows.length,
        totalPages: 1,
        summary: paginationStatus,
        showControls: false,
      }}
      className="h-full"
      tableClassName={activeTab === "members" ? "min-w-[760px]" : activeTab === "requests" ? "min-w-[860px]" : "min-w-[1080px]"}
      onScrollEnd={requestPagination ? onLoadMore : undefined}
      ariaLabel="소속 사용자 목록"
    />
  )
}
