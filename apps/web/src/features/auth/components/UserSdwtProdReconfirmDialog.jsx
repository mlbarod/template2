import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

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
import { Skeleton } from "@/components/ui/skeleton"
import { buildBackendUrl } from "@/lib/api"

import { fetchJson } from "../utils/fetchJson"

const AFFILIATION_QUERY_KEY = ["account", "affiliation"]
const RECONFIRM_QUERY_KEY = ["account", "affiliationReconfirm"]

function isBlank(value) {
  return !value || (typeof value === "string" && !value.trim())
}

function optionKey(option) {
  return `${option.department}||${option.line}||${option.user_sdwt_prod}`
}

async function fetchAffiliationOverview() {
  const endpoint = buildBackendUrl("/api/v1/account/affiliation")
  const result = await fetchJson(endpoint, { cache: "no-store" })
  if (result.ok) return result.data
  const message =
    (result.data && typeof result.data === "object" && result.data.error) ||
    "소속 정보를 불러오지 못했습니다."
  throw new Error(message)
}

async function fetchReconfirmStatus() {
  const endpoint = buildBackendUrl("/api/v1/account/affiliation/reconfirm")
  const result = await fetchJson(endpoint, { cache: "no-store" })
  if (result.ok) return result.data
  const message =
    (result.data && typeof result.data === "object" && result.data.error) ||
    "재확인 상태를 불러오지 못했습니다."
  throw new Error(message)
}

async function submitReconfirm(payload) {
  const endpoint = buildBackendUrl("/api/v1/account/affiliation/reconfirm")
  const result = await fetchJson(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (result.ok) return result.data
  const message =
    (result.data && typeof result.data === "object" && result.data.error) ||
    "재확인 처리에 실패했습니다."
  throw new Error(message)
}

export function UserSdwtProdReconfirmDialog({ user, onCompleted }) {
  const [selectedKey, setSelectedKey] = useState("")
  const [dismissed, setDismissed] = useState(false)
  const [submitError, setSubmitError] = useState("")
  const queryClient = useQueryClient()

  const hasPendingAffiliation = Boolean(
    user && (user.has_pending_affiliation ?? !isBlank(user.pending_user_sdwt_prod)),
  )
  const hasAffiliation = Boolean(user && !isBlank(user.user_sdwt_prod))
  const canCheck = Boolean(user && hasAffiliation && !hasPendingAffiliation)

  const reconfirmQuery = useQuery({
    queryKey: RECONFIRM_QUERY_KEY,
    queryFn: fetchReconfirmStatus,
    enabled: canCheck,
  })

  const needsReconfirm = Boolean(reconfirmQuery.data?.requiresReconfirm)
  const predictedUserSdwtProd = reconfirmQuery.data?.predictedUserSdwtProd || ""

  useEffect(() => {
    if (!needsReconfirm) {
      setDismissed(false)
      setSelectedKey("")
      setSubmitError("")
    }
  }, [needsReconfirm])

  const open = canCheck && needsReconfirm && !dismissed

  const affiliationQuery = useQuery({
    queryKey: AFFILIATION_QUERY_KEY,
    queryFn: fetchAffiliationOverview,
    enabled: open,
  })

  const allOptions = affiliationQuery.data?.affiliationOptions || []
  const predictedOption = allOptions.find(
    (option) => option.user_sdwt_prod === predictedUserSdwtProd,
  )
  const predictedMissing = Boolean(predictedUserSdwtProd) && !predictedOption
  const options = allOptions

  useEffect(() => {
    if (predictedOption) {
      setSelectedKey(optionKey(predictedOption))
    }
  }, [predictedOption])

  const selected = options.find((option) => optionKey(option) === selectedKey)

  const handleRetry = () => {
    reconfirmQuery.refetch()
    affiliationQuery.refetch()
  }

  const mutation = useMutation({
    mutationFn: submitReconfirm,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: RECONFIRM_QUERY_KEY })
      await queryClient.invalidateQueries({ queryKey: AFFILIATION_QUERY_KEY })
      await onCompleted?.()
    },
  })

  const handleKeep = async () => {
    setSubmitError("")
    try {
      await mutation.mutateAsync({ accepted: false })
    } catch (error) {
      setSubmitError(error?.message || "재확인 처리에 실패했습니다.")
    }
  }

  const handleApply = async (event) => {
    event.preventDefault()
    if (!selected) return
    setSubmitError("")
    try {
      await mutation.mutateAsync({
        accepted: true,
        user_sdwt_prod: selected.user_sdwt_prod,
      })
    } catch (error) {
      setSubmitError(error?.message || "재확인 처리에 실패했습니다.")
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) setDismissed(true)
      }}
    >
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>소속 재확인</DialogTitle>
          <DialogDescription>
            외부 예측 소속이 변경되었습니다. 최신 소속으로 변경할지, 기존 소속을 유지할지
            선택해 주세요.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="rounded-lg border bg-card p-3">
            <p className="text-sm text-muted-foreground">현재 소속</p>
            <p className="text-sm font-medium text-foreground">
              {(user?.department || "미지정") +
                " / " +
                (user?.line || "미지정") +
                " / " +
                (user?.user_sdwt_prod || "미지정")}
            </p>
          </div>

          {reconfirmQuery.isLoading || affiliationQuery.isLoading ? (
            <div className="grid gap-2">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-32" />
            </div>
          ) : reconfirmQuery.isError || affiliationQuery.isError ? (
            <div className="grid gap-2 rounded-lg border bg-card p-3">
              <p className="text-sm text-destructive">
                {reconfirmQuery.error?.message ||
                  affiliationQuery.error?.message ||
                  "재확인 정보를 불러오지 못했습니다."}
              </p>
              <div className="flex justify-end">
                <Button type="button" variant="outline" onClick={handleRetry}>
                  다시 시도
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleApply} className="grid gap-3">
              <div className="grid gap-2">
                <Label htmlFor="reconfirmAffiliationSelect">
                  최신 소속 (Department / Line / user_sdwt_prod)
                </Label>
                <select
                  id="reconfirmAffiliationSelect"
                  className="bg-background border-input focus-visible:ring-ring/50 focus-visible:ring-[3px] h-10 rounded-md border px-3 text-sm outline-none"
                  value={selectedKey}
                  onChange={(event) => setSelectedKey(event.target.value)}
                  required
                  disabled={!options.length || mutation.isPending}
                >
                  <option value="" disabled>
                    최신 소속을 선택하세요
                  </option>
                  {options.map((option) => (
                    <option key={optionKey(option)} value={optionKey(option)}>
                      {option.department} / {option.line} / {option.user_sdwt_prod}
                    </option>
                  ))}
                </select>
                {!options.length ? (
                  <p className="text-sm text-destructive">
                    선택 가능한 소속이 없습니다. 관리자에게 문의하세요.
                  </p>
                ) : predictedMissing ? (
                  <p className="text-sm text-muted-foreground">
                    최신 예측 소속이 목록에 없습니다. 선택한 소속은 승인 대기 요청으로 처리됩니다.
                  </p>
                ) : null}
              </div>

              {submitError ? <p className="text-sm text-destructive">{submitError}</p> : null}

              <DialogFooter className="gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleKeep}
                  disabled={mutation.isPending}
                >
                  기존 유지
                </Button>
                <Button
                  type="submit"
                  disabled={!selected || !options.length || mutation.isPending}
                >
                  {mutation.isPending ? "적용 중..." : "최신 소속 적용"}
                </Button>
              </DialogFooter>
            </form>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
