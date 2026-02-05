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

function isBlank(value) {
  return !value || (typeof value === "string" && !value.trim())
}

function optionKey(opt) {
  return `${opt.department}||${opt.line}||${opt.user_sdwt_prod}`
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

async function updateAffiliation(payload) {
  const endpoint = buildBackendUrl("/api/v1/account/affiliation")
  const result = await fetchJson(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (result.ok) return result.data
  const message =
    (result.data && typeof result.data === "object" && result.data.error) ||
    "소속 설정에 실패했습니다."
  throw new Error(message)
}

export function UserSdwtProdOnboardingDialog({ user, onCompleted }) {
  const hasPendingAffiliation = Boolean(
    user && (user.has_pending_affiliation ?? !isBlank(user.pending_user_sdwt_prod)),
  )
  const needsOnboarding = Boolean(user && isBlank(user.user_sdwt_prod) && !hasPendingAffiliation)
  const queryClient = useQueryClient()
  const [selectedKey, setSelectedKey] = useState("")
  const [submitError, setSubmitError] = useState("")

  const affiliationQuery = useQuery({
    queryKey: AFFILIATION_QUERY_KEY,
    queryFn: fetchAffiliationOverview,
    enabled: needsOnboarding,
  })

  const mutation = useMutation({
    mutationFn: updateAffiliation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: AFFILIATION_QUERY_KEY })
      await onCompleted?.()
    },
  })

  const allOptions = affiliationQuery.data?.affiliationOptions || []
  const userDepartment = user?.department
  const departmentOptions = userDepartment
    ? allOptions.filter((opt) => opt.department === userDepartment)
    : []
  const options = departmentOptions.length ? departmentOptions : allOptions
  const snapshotUserSdwtProd = affiliationQuery.data?.snapshotUserSdwtProd
  const snapshotOption = snapshotUserSdwtProd
    ? options.find((opt) => opt.user_sdwt_prod === snapshotUserSdwtProd)
    : null
  const selected = options.find((opt) => optionKey(opt) === selectedKey)

  useEffect(() => {
    if (selectedKey || !options.length) return
    if (snapshotOption) {
      setSelectedKey(optionKey(snapshotOption))
      return
    }
    if (!user?.department || !user?.line || !user?.user_sdwt_prod) return
    const current = options.find(
      (opt) =>
        opt.department === user.department &&
        opt.line === user.line &&
        opt.user_sdwt_prod === user.user_sdwt_prod,
    )
    if (current) {
      setSelectedKey(optionKey(current))
    }
  }, [options, selectedKey, snapshotOption, user?.department, user?.line, user?.user_sdwt_prod])

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!selected) return

    setSubmitError("")
    try {
      await mutation.mutateAsync({
        userSdwtProd: selected.user_sdwt_prod,
        department: selected.department,
        line: selected.line,
      })
    } catch (error) {
      setSubmitError(error?.message || "소속 설정에 실패했습니다.")
    }
  }

  return (
    <Dialog open={needsOnboarding} onOpenChange={() => { }}>
      <DialogContent showCloseButton={false} className="sm:max-w-[calc(100%-70rem)]">
        <DialogHeader>
          <DialogTitle>소속 설정</DialogTitle>
          <DialogDescription>
            처음 로그인을 완료하려면 <span className="font-medium text-foreground">user_sdwt_prod</span> 소속을 선택해 주세요.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="rounded-lg border bg-card p-3">
            <p className="text-sm text-muted-foreground">현재 사용자</p>
            <p className="text-sm font-medium text-foreground">{user?.username || user?.email || "-"}</p>
            {user?.department ? (
              <p className="mt-1 text-xs text-muted-foreground">부서(Claim): {user.department}</p>
            ) : null}
          </div>

          {affiliationQuery.isLoading ? (
            <div className="grid gap-2">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-32" />
            </div>
          ) : affiliationQuery.isError ? (
            <div className="grid gap-2 rounded-lg border bg-card p-3">
              <p className="text-sm text-destructive">
                {affiliationQuery.error?.message || "소속 정보를 불러오지 못했습니다."}
              </p>
              <div className="flex justify-end">
                <Button type="button" variant="outline" onClick={() => affiliationQuery.refetch()}>
                  다시 시도
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="grid gap-3">
              <div className="grid gap-2">
                <Label htmlFor="onboardingAffiliationSelect">
                  선택 (Department / Line / user_sdwt_prod)
                </Label>
                <select
                  id="onboardingAffiliationSelect"
                  className="bg-background border-input focus-visible:ring-ring/50 focus-visible:ring-[3px] h-10 w-full min-w-0 rounded-md border px-3 text-sm outline-none"
                  value={selectedKey}
                  onChange={(e) => setSelectedKey(e.target.value)}
                  required
                  disabled={!options.length || mutation.isPending}
                >
                  <option value="" disabled>
                    소속을 선택하세요
                  </option>
                  {options.map((opt) => (
                    <option key={optionKey(opt)} value={optionKey(opt)}>
                      {opt.department} / {opt.line} / {opt.user_sdwt_prod}
                    </option>
                  ))}
                </select>
                {!options.length ? (
                  <p className="text-sm text-destructive">선택 가능한 소속이 없습니다. 관리자에게 문의하세요.</p>
                ) : null}
              </div>

              {submitError ? <p className="text-sm text-destructive">{submitError}</p> : null}

              <DialogFooter className="gap-2">
                <Button type="submit" disabled={!selectedKey || !options.length || mutation.isPending}>
                  {mutation.isPending ? "저장 중..." : "저장"}
                </Button>
              </DialogFooter>
            </form>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
