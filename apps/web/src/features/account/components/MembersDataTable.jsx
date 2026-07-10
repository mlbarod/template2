import {
  Check,
  Clock3,
  Crown,
  Eye,
  MoreHorizontal,
  UserRound,
  Users,
} from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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
    <span className="inline-flex items-center gap-2">
      <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
      <span className="text-sm">{MEMBER_ROLE_LABELS[normalizedRole]}</span>
    </span>
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
      <DropdownMenu>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                disabled={disabled}
                aria-label={`${row.name} 추가 작업`}
              >
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent side="top">추가 작업</TooltipContent>
        </Tooltip>
        <DropdownMenuContent align="end">
          <DropdownMenuItem variant="destructive" onSelect={() => onReject(row)}>
            거절
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

export function MembersDataTable({
  rows,
  activeTab,
  onActiveTabChange,
  memberTotal,
  requestTotal,
  roleFilter,
  onRoleFilterChange,
  page,
  pageSize,
  totalPages,
  onPageChange,
  onPageSizeChange,
  isLoading,
  isFetching,
  error,
  emptyMessage,
  onRetry,
  isMutating,
  showApprovalNotice,
  onApprove,
  onReject,
}) {
  const safeRows = Array.isArray(rows) ? rows : []
  const filteredRows = roleFilter === "all"
    ? safeRows
    : safeRows.filter((row) => row.type === "request" || row.memberRole === roleFilter)
  const displayedMemberCount = filteredRows.filter((row) => row.type === "member").length
  const requestStart = requestTotal > 0 ? (page - 1) * pageSize + 1 : 0
  const requestEnd = requestTotal > 0 ? Math.min(page * pageSize, requestTotal) : 0
  const requestPagination = activeTab !== "members"
  const paginationSummary = activeTab === "all"
    ? `멤버 ${displayedMemberCount.toLocaleString("ko-KR")}명 · 요청 ${requestStart.toLocaleString("ko-KR")}-${requestEnd.toLocaleString("ko-KR")} / 총 ${requestTotal.toLocaleString("ko-KR")}건`
    : activeTab === "requests"
      ? `요청 ${requestStart.toLocaleString("ko-KR")}-${requestEnd.toLocaleString("ko-KR")} / 총 ${requestTotal.toLocaleString("ko-KR")}건`
      : `총 ${filteredRows.length.toLocaleString("ko-KR")}명`

  const columns = [
    {
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
            <div className="flex min-w-0 flex-col">
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
    },
    {
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
    },
    {
      accessorKey: "affiliationLabel",
      header: "소속",
      cell: ({ row }) => (
        <span className="block max-w-72 truncate text-sm text-muted-foreground" title={row.original.affiliationLabel}>
          {row.original.affiliationLabel || "-"}
        </span>
      ),
      meta: {
        headerClassName: "min-w-56",
        cellClassName: "min-w-56",
      },
    },
    {
      id: "memberRole",
      header: "멤버 권한",
      cell: ({ row }) => row.original.type === "member"
        ? <MemberRole role={row.original.memberRole} />
        : <span className="text-sm text-muted-foreground">-</span>,
      meta: {
        headerClassName: "min-w-36",
        cellClassName: "min-w-36",
      },
    },
    {
      accessorKey: "requestedAt",
      header: "요청 시각",
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">{formatDate(row.original.requestedAt)}</span>
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
        <RequestActions
          row={row.original}
          isMutating={isMutating}
          onApprove={onApprove}
          onReject={onReject}
        />
      ),
      meta: {
        headerClassName: "sticky right-0 z-20 min-w-36 bg-muted/30 text-right",
        cellClassName: "sticky right-0 z-10 min-w-36 bg-card text-right group-hover:bg-muted/40",
      },
    },
  ]

  const toolbar = (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold">필터</h3>
        {isFetching && !isLoading ? <span className="text-xs text-muted-foreground">새로고침 중...</span> : null}
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <div className="grid gap-1.5">
          <Label htmlFor="members-list-filter">목록 구분</Label>
          <Select value={activeTab} onValueChange={onActiveTabChange}>
            <SelectTrigger id="members-list-filter" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">전체 목록</SelectItem>
              <SelectItem value="members">현재 멤버 ({memberTotal.toLocaleString("ko-KR")})</SelectItem>
              <SelectItem value="requests">승인 대기 ({requestTotal.toLocaleString("ko-KR")})</SelectItem>
            </SelectContent>
          </Select>
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

        <div className="grid gap-1.5">
          <Label htmlFor="members-page-size">페이지 크기</Label>
          <Select
            value={String(pageSize)}
            onValueChange={(value) => onPageSizeChange(Number(value))}
            disabled={activeTab === "members"}
          >
            <SelectTrigger id="members-page-size" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[10, 20, 50].map((value) => (
                <SelectItem key={value} value={String(value)}>
                  {value}개씩
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
      emptyMessage={emptyMessage}
      onRetry={onRetry}
      pagination={{
        page: requestPagination ? page : 1,
        pageSize: requestPagination ? pageSize : Math.max(filteredRows.length, 1),
        total: requestPagination ? requestTotal : filteredRows.length,
        totalPages: requestPagination ? totalPages : 1,
        summary: paginationSummary,
        showControls: requestPagination && totalPages > 1,
        onPageChange,
      }}
      className="h-full"
      tableClassName="min-w-[1080px]"
      ariaLabel="소속 사용자 목록"
    />
  )
}
