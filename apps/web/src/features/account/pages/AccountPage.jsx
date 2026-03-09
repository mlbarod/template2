import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/lib/auth"

import { AccountProfileCard } from "../components/AccountProfileCard"
import { AffiliationCard } from "../components/AffiliationCard"
import { AffiliationHistoryCard } from "../components/AffiliationHistoryCard"
import { ManageableGroupsCard } from "../components/ManageableGroupsCard"
import { useAccountOverview, useAffiliation, useUpdateAffiliation } from "../hooks/useAccountData"

const REQUEST_STATUS_LABELS = {
  PENDING: { label: "대기", variant: "secondary" },
  APPROVED: { label: "승인", variant: "default" },
  REJECTED: { label: "거절", variant: "destructive" },
  SUPERSEDED: { label: "취소(대체됨)", variant: "outline" },
}

function formatDate(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"
  return date.toLocaleString("ko-KR")
}

function AffiliationRequestStatusCard({ latestRequest }) {
  if (!latestRequest) {
    return (
      <Card className="h-full">
        <CardHeader className="pb-2">
          <CardTitle>요청 상태</CardTitle>
          <CardDescription>최근 소속 변경 요청의 상태를 확인합니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">소속 변경 요청 이력이 없습니다.</p>
        </CardContent>
      </Card>
    )
  }

  const status = REQUEST_STATUS_LABELS[latestRequest.status] || {
    label: latestRequest.status || "미지정",
    variant: "outline",
  }
  const fromValue = latestRequest.fromUserSdwtProd || "-"
  const toValue = latestRequest.toUserSdwtProd || "-"
  const orgValue =
    latestRequest.department || latestRequest.line
      ? `${latestRequest.department || "미지정"} / ${latestRequest.line || "미지정"}`
      : "-"

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>요청 상태</CardTitle>
        <CardDescription>최근 소속 변경 요청의 상태를 확인합니다.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={status.variant}>{status.label}</Badge>
          <span className="text-xs text-muted-foreground">
            요청 시각: {formatDate(latestRequest.requestedAt)}
          </span>
        </div>
        <div className="grid gap-3 rounded-lg border p-3">
          <div className="grid gap-2 md:grid-cols-2">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">변경</span>
              <span className="text-sm text-foreground">{`${fromValue} → ${toValue}`}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">조직</span>
              <span className="text-sm text-foreground">{orgValue}</span>
            </div>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">처리 시각</span>
              <span className="text-sm text-foreground">
                {formatDate(latestRequest.approvedAt)}
              </span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">처리자</span>
              <span className="text-sm text-foreground">
                {latestRequest.approvedBy?.username || "-"}
              </span>
            </div>
          </div>
        </div>
        {latestRequest.status === "REJECTED" && latestRequest.rejectionReason ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            거절 사유: {latestRequest.rejectionReason}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

export default function AccountPage() {
  const { user } = useAuth()
  const {
    data: overviewData,
    isLoading: overviewLoading,
    error: overviewError,
  } = useAccountOverview()
  const {
    data: affiliationData,
    isLoading: affiliationLoading,
    error: affiliationError,
  } = useAffiliation()
  const updateAffiliationMutation = useUpdateAffiliation()
  const [submitMessage, setSubmitMessage] = useState("")
  const [submitError, setSubmitError] = useState("")

  const pageTitle = user?.username ? `내 계정 · ${user.username}` : "내 계정"
  const profile = overviewData?.user
  const affiliation = overviewData?.affiliation
  const reconfirm = overviewData?.affiliationReconfirm
  const history = overviewData?.affiliationHistory || []
  const manageableGroups = overviewData?.manageableGroups?.groups || []
  const latestRequest =
    history.find((item) => item.status === "PENDING") || history[0] || null
  const pendingRequests = history.filter((item) => item.status === "PENDING").length

  const handleAffiliationSubmit = async (payload, onComplete) => {
    setSubmitMessage("")
    setSubmitError("")
    try {
      await updateAffiliationMutation.mutateAsync(payload)
      setSubmitMessage("소속 변경 요청이 접수되었습니다. 승인 결과는 상태/이력에서 확인할 수 있습니다.")
      onComplete?.()
    } catch (error) {
      setSubmitError(error?.message || "소속 변경 요청에 실패했습니다.")
    }
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold text-foreground">{pageTitle}</h2>
        <p className="text-sm text-muted-foreground">
          계정 소속, 접근 권한, 승인 히스토리를 한 번에 확인합니다.
        </p>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Badge variant="secondary">현재 소속: {affiliation?.currentUserSdwtProd || "미지정"}</Badge>
          <Badge variant="outline">요청 이력 {history.length}건</Badge>
          <Badge variant={pendingRequests > 0 ? "destructive" : "secondary"}>
            대기 {pendingRequests}건
          </Badge>
        </div>
      </div>

      {overviewError ? (
        <div className="rounded-lg border bg-card p-4">
          <p className="text-destructive text-sm">
            {overviewError?.message || "계정 정보를 불러오지 못했습니다."}
          </p>
        </div>
      ) : overviewLoading ? (
        <div className="grid min-h-0 min-w-0 grid-cols-1 gap-4">
          <section className="grid min-h-0 min-w-0 grid-cols-1 gap-4 md:grid-cols-12 md:auto-rows-fr">
            <Skeleton className="h-64 w-full md:col-span-8" />
            <Skeleton className="h-64 w-full md:col-span-4" />
          </section>
          <section className="grid min-h-0 min-w-0 grid-cols-1 gap-4 md:grid-cols-12">
            <Skeleton className="h-80 w-full md:col-span-7" />
            <Skeleton className="h-80 w-full md:col-span-5" />
          </section>
          <Skeleton className="h-96 w-full" />
        </div>
      ) : (
        <div className="grid min-h-0 min-w-0 grid-cols-1 gap-4">
          <section className="grid min-h-0 min-w-0 grid-cols-1 gap-4 md:grid-cols-12 md:auto-rows-fr">
            <div className="min-h-0 min-w-0 md:col-span-6">
              <AccountProfileCard
                profile={profile}
                affiliation={affiliation}
                reconfirm={reconfirm}
              />
            </div>
            <div className="min-h-0 min-w-0 md:col-span-6">
              <AffiliationRequestStatusCard latestRequest={latestRequest} />
            </div>
          </section>

          <section className="grid min-h-0 min-w-0 grid-cols-1 gap-4 md:grid-cols-12">
            <div className="min-h-0 min-w-0 md:col-span-7">
              {affiliationLoading ? (
                <Skeleton className="h-80 w-full" />
              ) : affiliationError ? (
                <div className="rounded-lg border bg-card p-4">
                  <p className="text-destructive text-sm">
                    {affiliationError?.message || "소속 정보를 불러오지 못했습니다."}
                  </p>
                </div>
              ) : (
                <AffiliationCard
                  data={affiliationData}
                  onSubmit={handleAffiliationSubmit}
                  isSubmitting={updateAffiliationMutation.isPending}
                  error={submitError}
                  successMessage={submitMessage}
                />
              )}
            </div>
            <div className="min-h-0 min-w-0 md:col-span-5">
              <ManageableGroupsCard groups={manageableGroups} />
            </div>
          </section>

          <div className="min-h-0 min-w-0">
            <AffiliationHistoryCard history={history} />
          </div>
        </div>
      )}
    </div>
  )
}
