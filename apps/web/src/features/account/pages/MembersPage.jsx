import { useEffect, useState } from "react"

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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { useAuth } from "@/lib/auth"

import {
  useAffiliationDecision,
  useAffiliationRequests,
  useMailboxMembers,
} from "../hooks/useAccountData"

const PAGE_SIZE_OPTIONS = [10, 20, 50]

function formatDate(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"
  return date.toLocaleString("ko-KR")
}

export default function MembersPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState("all")
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [rejectTarget, setRejectTarget] = useState(null)
  const [rejectReason, setRejectReason] = useState("")
  const userSdwtProd = (user?.user_sdwt_prod || "").trim()

  const {
    data: membersData,
    isPending: membersPending,
    error: membersError,
  } = useMailboxMembers({ userSdwtProd })

  const {
    data: requestsData,
    isPending: requestsPending,
    error: requestsError,
    isFetching: requestsFetching,
  } = useAffiliationRequests({
    page,
    pageSize,
    status: "pending",
    search: "",
    userSdwtProd,
  })

  const decisionMutation = useAffiliationDecision()

  useEffect(() => {
    setPage(1)
  }, [pageSize, userSdwtProd])

  useEffect(() => {
    if (requestsData?.page && requestsData.page !== page) {
      setPage(requestsData.page)
    }
  }, [requestsData?.page, page])

  const members = membersData?.members || []
  const requests = requestsData?.results || []
  const requestTotal = requestsData?.total || 0
  const totalPages = requestsData?.totalPages || 1
  const canPrevious = page > 1
  const canNext = page < totalPages
  const showPagination = activeTab === "all" || activeTab === "requests"

  const handleDecision = async (changeId, decision, rejectionReason) => {
    try {
      await decisionMutation.mutateAsync({ changeId, decision, rejectionReason })
      return true
    } catch {
      return false
    }
  }

  const handleRejectOpen = (row) => {
    setRejectTarget(row)
    setRejectReason("")
  }

  const handleRejectConfirm = async () => {
    if (!rejectTarget) return
    const normalizedReason = rejectReason.trim()
    const didComplete = await handleDecision(
      rejectTarget.changeId,
      "reject",
      normalizedReason ? normalizedReason : undefined,
    )
    if (didComplete) {
      setRejectTarget(null)
      setRejectReason("")
    }
  }

  const pageTitle = user?.username ? `Members · ${user.username}` : "Members"
  const memberRows = members.map((member) => {
    const displayName =
      member?.name?.trim() || member?.username?.trim() || member?.knoxId || "알 수 없음"
    const memberAffiliation = member?.userSdwtProd || member?.user_sdwt_prod || "-"
    return {
      id: `member-${member.userId}`,
      type: "member",
      name: displayName,
      knoxId: member.knoxId || "-",
      affiliationLabel: memberAffiliation,
      requestedAt: null,
      changeId: null,
      status: "MEMBER",
    }
  })
  const requestRows = requests.map((change) => {
    const requesterName = change?.user?.username || change?.user?.sabun || "알 수 없음"
    const requesterKnoxId = change?.user?.knoxId || "-"
    const targetParts = [
      change?.department,
      change?.line,
      change?.toUserSdwtProd || change?.to_user_sdwt_prod,
    ].filter(Boolean)
    const targetLabel =
      targetParts.length > 0 ? targetParts.join(" / ") : change?.toUserSdwtProd || "-"
    const normalizedRole = (change?.role || "").toLowerCase()
    const role = ["viewer", "member", "manager"].includes(normalizedRole)
      ? normalizedRole
      : "viewer"
    return {
      id: `request-${change.id}`,
      type: "request",
      name: requesterName,
      knoxId: requesterKnoxId,
      affiliationLabel: targetLabel,
      requestedAt: change.requestedAt,
      changeId: change.id,
      status: change.status || "PENDING",
      role,
    }
  })
  const combinedRows = [...requestRows, ...memberRows]
  const canApproveAny = requestRows.some(
    (row) => row.role === "member" || row.role === "manager",
  )
  const showApprovalNotice = requestTotal > 0 && !canApproveAny

  const renderRows = (rows) => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>이름</TableHead>
          <TableHead>Knox ID</TableHead>
          <TableHead>변경 소속</TableHead>
          <TableHead>상태</TableHead>
          <TableHead>요청 시각</TableHead>
          <TableHead className="text-right">작업</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => {
          const isRequest = row.type === "request"
          const isPendingStatus = isRequest && row.status === "PENDING"
          const canApprove = isRequest && (row.role === "member" || row.role === "manager")
          const statusLabel = isRequest
            ? row.status === "APPROVED"
              ? "승인"
              : row.status === "REJECTED"
                ? "거절"
                : row.status === "SUPERSEDED"
                  ? "취소(대체됨)"
                  : "소속 변경 요청"
            : "멤버"
          return (
            <TableRow key={row.id}>
              <TableCell className="text-sm font-medium text-foreground">{row.name}</TableCell>
              <TableCell className="text-sm text-muted-foreground">{row.knoxId}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {row.affiliationLabel || "-"}
              </TableCell>
              <TableCell>
                <Badge variant={isRequest ? "destructive" : "secondary"}>{statusLabel}</Badge>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {isRequest ? formatDate(row.requestedAt) : "-"}
              </TableCell>
              <TableCell className="text-right">
                {isRequest ? (
                  <div className="flex justify-end gap-2">
                    <Button
                      size="sm"
                      onClick={() => handleDecision(row.changeId, "approve")}
                      disabled={!isPendingStatus || !canApprove || decisionMutation.isPending}
                    >
                      승인
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRejectOpen(row)}
                      disabled={!isPendingStatus || !canApprove || decisionMutation.isPending}
                    >
                      거절
                    </Button>
                  </div>
                ) : (
                  <span className="text-sm text-muted-foreground">-</span>
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-2xl font-semibold text-foreground">{pageTitle}</h2>
          {requestsFetching && !requestsPending ? (
            <span className="text-xs text-muted-foreground">새로고침 중...</span>
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground">
          {userSdwtProd
            ? `${userSdwtProd} 소속 멤버와 소속 변경 요청을 확인할 수 있습니다.`
            : "user_sdwt_prod가 설정되어 있지 않습니다."}
        </p>
      </div>

      <section className="flex min-h-0 flex-col">
        <div className="flex min-h-0 flex-col rounded-lg border bg-card">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex min-h-0 flex-col"
          >
            <div className="flex flex-col gap-3 border-b p-4 md:flex-row md:items-center md:justify-between">
              <TabsList className="h-9">
                <TabsTrigger value="all">전체</TabsTrigger>
                <TabsTrigger value="members">
                  멤버
                  <Badge variant="secondary" className="ml-2">
                    {members.length}
                  </Badge>
                </TabsTrigger>
                <TabsTrigger value="requests">
                  소속 변경 요청
                  {requestTotal > 0 ? (
                    <Badge variant="destructive" className="ml-2">
                      {requestTotal}
                    </Badge>
                  ) : null}
                </TabsTrigger>
              </TabsList>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">페이지 크기</span>
                <Select
                  value={String(pageSize)}
                  onValueChange={(value) => setPageSize(Number(value))}
                  disabled={activeTab === "members"}
                >
                  <SelectTrigger className="h-8 w-[90px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PAGE_SIZE_OPTIONS.map((value) => (
                      <SelectItem key={value} value={String(value)}>
                        {value}개
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {showApprovalNotice ? (
                <div className="px-4 pt-3">
                  <p className="text-xs text-muted-foreground">
                    승인/거절은 멤버 또는 관리자만 가능합니다.
                  </p>
                </div>
              ) : null}
            </div>

            <div className="border-t bg-background">
              <TabsContent value="all" className="m-0">
                {membersError || requestsError ? (
                  <div className="p-4">
                    {membersError ? (
                      <p className="text-sm text-destructive">
                        멤버 목록을 불러오지 못했습니다.
                      </p>
                    ) : null}
                    {requestsError ? (
                      <p className="text-sm text-destructive">
                        소속 변경 요청을 불러오지 못했습니다.
                      </p>
                    ) : null}
                  </div>
                ) : membersPending || requestsPending ? (
                  <div className="grid gap-3 p-4">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <Skeleton key={`all-skeleton-${index}`} className="h-10 w-full" />
                    ))}
                  </div>
                ) : combinedRows.length === 0 ? (
                  <div className="p-4 text-center text-sm text-muted-foreground">
                    현재 표시할 멤버 또는 소속 변경 요청이 없습니다.
                  </div>
                ) : (
                  renderRows(combinedRows)
                )}
              </TabsContent>

              <TabsContent value="members" className="m-0">
                {membersError ? (
                  <div className="p-4">
                    <p className="text-sm text-destructive">
                      {membersError?.message || "멤버 목록을 불러오지 못했습니다."}
                    </p>
                  </div>
                ) : membersPending ? (
                  <div className="grid gap-3 p-4">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <Skeleton key={`member-skeleton-${index}`} className="h-10 w-full" />
                    ))}
                  </div>
                ) : memberRows.length === 0 ? (
                  <div className="p-4 text-center text-sm text-muted-foreground">
                    현재 표시할 멤버가 없습니다.
                  </div>
                ) : (
                  renderRows(memberRows)
                )}
              </TabsContent>

              <TabsContent value="requests" className="m-0">
                {requestsError ? (
                  <div className="p-4">
                    <p className="text-sm text-destructive">
                      {requestsError?.message || "소속 변경 요청을 불러오지 못했습니다."}
                    </p>
                  </div>
                ) : requestsPending ? (
                  <div className="grid gap-3 p-4">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <Skeleton key={`request-skeleton-${index}`} className="h-10 w-full" />
                    ))}
                  </div>
                ) : requestRows.length === 0 ? (
                  <div className="p-4 text-center text-sm text-muted-foreground">
                    현재 표시할 소속 변경 요청이 없습니다.
                  </div>
                ) : (
                  renderRows(requestRows)
                )}
              </TabsContent>
            </div>

            {showPagination ? (
              <div className="flex flex-col gap-2 border-t p-4 md:flex-row md:items-center md:justify-between">
                <p className="text-xs text-muted-foreground">
                  페이지 {page.toLocaleString("ko-KR")} / {totalPages.toLocaleString("ko-KR")}
                </p>
                <Pagination className="justify-end">
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious
                        href="#"
                        onClick={(event) => {
                          event.preventDefault()
                          if (canPrevious) setPage((prev) => prev - 1)
                        }}
                        className={!canPrevious ? "pointer-events-none opacity-50" : ""}
                      />
                    </PaginationItem>
                    <PaginationItem>
                      <PaginationNext
                        href="#"
                        onClick={(event) => {
                          event.preventDefault()
                          if (canNext) setPage((prev) => prev + 1)
                        }}
                        className={!canNext ? "pointer-events-none opacity-50" : ""}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            ) : null}
          </Tabs>
        </div>
      </section>

      <Dialog
        open={Boolean(rejectTarget)}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setRejectTarget(null)
            setRejectReason("")
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>거절 사유 입력</DialogTitle>
            <DialogDescription>
              {rejectTarget?.name
                ? `${rejectTarget.name}님의 소속 변경 요청을 거절합니다.`
                : "소속 변경 요청을 거절합니다."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="affiliationRejectReason">거절 사유 (선택)</Label>
            <textarea
              id="affiliationRejectReason"
              value={rejectReason}
              onChange={(event) => setRejectReason(event.target.value)}
              className="min-h-24 resize-y rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="사유를 입력하지 않아도 거절할 수 있습니다."
              maxLength={500}
            />
            <p className="text-xs text-muted-foreground">
              거절 사유는 신청자에게 그대로 표시됩니다.
            </p>
            {decisionMutation.error ? (
              <p className="text-xs text-destructive">
                {decisionMutation.error?.message || "거절 처리에 실패했습니다."}
              </p>
            ) : null}
          </div>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setRejectTarget(null)
                setRejectReason("")
              }}
              disabled={decisionMutation.isPending}
            >
              취소
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleRejectConfirm}
              disabled={decisionMutation.isPending}
            >
              거절 확정
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
