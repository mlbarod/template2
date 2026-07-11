import { useState } from "react"
import { toast } from "sonner"

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
import { useAuth } from "@/lib/auth"

import { MembersDataTable } from "../components/MembersDataTable"
import {
  useAffiliationMembers,
  useAffiliationDecision,
  useInfiniteAffiliationRequests,
} from "../hooks/useAccountData"

const REQUEST_PAGE_SIZE = 20

export default function MembersPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState("all")
  const [roleFilter, setRoleFilter] = useState("all")
  const [rejectTarget, setRejectTarget] = useState(null)
  const [rejectReason, setRejectReason] = useState("")
  const userSdwtProd = (user?.user_sdwt_prod || "").trim()

  const {
    data: membersData,
    isPending: membersPending,
    error: membersError,
    refetch: refetchMembers,
  } = useAffiliationMembers({ userSdwtProd })

  const {
    data: requestsData,
    isPending: requestsPending,
    error: requestsError,
    isFetching: requestsFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch: refetchRequests,
  } = useInfiniteAffiliationRequests({
    pageSize: REQUEST_PAGE_SIZE,
    status: "pending",
    search: "",
    userSdwtProd,
  })

  const decisionMutation = useAffiliationDecision()

  const members = membersData?.members || []
  const requestPages = requestsData?.pages || []
  const requests = requestPages.flatMap((pageData) => pageData?.results || [])
  const latestRequestPage = requestPages[requestPages.length - 1]
  const requestTotal = latestRequestPage?.total || 0

  const handleDecision = async (changeId, decision, rejectionReason) => {
    try {
      await decisionMutation.mutateAsync({ changeId, decision, rejectionReason })
      toast.success(
        decision === "approve"
          ? "소속 변경 요청을 승인했습니다."
          : "소속 변경 요청을 거절했습니다.",
      )
      return true
    } catch (error) {
      toast.error(error?.message || "소속 변경 요청을 처리하지 못했습니다.")
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
    const memberAffiliation = member?.userSdwtProd || member?.user_sdwt_prod || ""
    const normalizedRole = (member?.role || "").toLowerCase()
    return {
      id: `member-${member.userId}`,
      type: "member",
      name: displayName,
      knoxId: member.knoxId || "-",
      email: member.email || "",
      affiliationLabel: [member.department, memberAffiliation].filter(Boolean).join(" / ") || "-",
      memberRole: ["viewer", "member", "manager"].includes(normalizedRole)
        ? normalizedRole
        : "viewer",
      approvalRole: null,
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
      email: change?.user?.email || "",
      affiliationLabel: targetLabel,
      memberRole: null,
      approvalRole: role,
      requestedAt: change.requestedAt,
      changeId: change.id,
      status: change.status || "PENDING",
    }
  })
  const combinedRows = [...requestRows, ...memberRows]
  const canApproveAny = requestRows.some(
    (row) => row.approvalRole === "member" || row.approvalRole === "manager",
  )
  const showApprovalNotice = requestTotal > 0 && !canApproveAny
  const activeRows =
    activeTab === "members"
      ? memberRows
      : activeTab === "requests"
        ? requestRows
        : combinedRows

  const isActiveLoading =
    activeTab === "members"
      ? Boolean(userSdwtProd) && membersPending
      : activeTab === "requests"
        ? Boolean(userSdwtProd) && requestsPending
        : Boolean(userSdwtProd) && (membersPending || requestsPending)

  const activeErrors =
    activeTab === "members"
      ? [membersError].filter(Boolean)
      : activeTab === "requests"
        ? [requestsError].filter(Boolean)
        : [membersError, requestsError].filter(Boolean)

  const activeEmptyMessage =
    activeTab === "members"
      ? "현재 표시할 멤버가 없습니다."
      : activeTab === "requests"
        ? "현재 표시할 소속 변경 요청이 없습니다."
        : "현재 표시할 멤버 또는 소속 변경 요청이 없습니다."

  const activeErrorMessage = activeErrors.length > 0
    ? activeErrors
      .map((errorItem) => errorItem?.message || "사용자 목록을 불러오지 못했습니다.")
      .join(" ")
    : ""

  const handleRetry = () => {
    if (activeTab !== "requests") refetchMembers()
    if (activeTab !== "members") refetchRequests()
  }

  const handleLoadMoreRequests = () => {
    if (activeTab === "members" || !hasNextPage || isFetchingNextPage) return
    fetchNextPage()
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-hidden">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-2">
          <h2 className="text-2xl font-semibold text-foreground">{pageTitle}</h2>
          <p className="text-sm text-muted-foreground">
            {userSdwtProd
              ? `${userSdwtProd} 소속 멤버와 소속 변경 요청을 확인할 수 있습니다.`
              : "user_sdwt_prod가 설정되어 있지 않습니다."}
          </p>
        </div>
      </div>

      <div className="min-h-0 min-w-0 flex-1">
        <MembersDataTable
          rows={activeRows}
          activeTab={activeTab}
          onActiveTabChange={setActiveTab}
          memberTotal={members.length}
          requestTotal={requestTotal}
          requestLoadedCount={requests.length}
          roleFilter={roleFilter}
          onRoleFilterChange={setRoleFilter}
          isLoading={isActiveLoading}
          isFetching={requestsFetching}
          isLoadingMore={isFetchingNextPage}
          hasMoreRequests={Boolean(hasNextPage)}
          onLoadMore={handleLoadMoreRequests}
          error={activeErrorMessage}
          emptyMessage={activeEmptyMessage}
          onRetry={handleRetry}
          isMutating={decisionMutation.isPending}
          showApprovalNotice={showApprovalNotice}
          onApprove={(row) => handleDecision(row.changeId, "approve")}
          onReject={handleRejectOpen}
        />
      </div>

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
