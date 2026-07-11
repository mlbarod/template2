import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"

function optionKey(opt) {
  return `${opt.department}||${opt.line}||${opt.user_sdwt_prod}`
}

const EMPTY_OPTIONS = []

export function AffiliationCard({
  data,
  onSubmit,
  isSubmitting,
  error,
  successMessage,
}) {
  const [selectedKey, setSelectedKey] = useState("")

  const options = data?.affiliationOptions ?? EMPTY_OPTIONS

  const selected = options.find((opt) => optionKey(opt) === selectedKey)

  // 기본 선택: 현재 소속과 일치하는 옵션이 있으면 자동 선택
  useEffect(() => {
    if (selectedKey || !options.length) return
    const current = options.find(
      (opt) =>
        opt.user_sdwt_prod === data?.currentUserSdwtProd &&
        opt.department === data?.currentDepartment &&
        opt.line === data?.currentLine,
    )
    if (current) {
      setSelectedKey(optionKey(current))
    }
  }, [selectedKey, options, data?.currentUserSdwtProd, data?.currentDepartment, data?.currentLine])

  const handleSubmit = (e) => {
    e.preventDefault()
    const target = selected || options.find((opt) => opt.user_sdwt_prod === data?.currentUserSdwtProd)
    if (!target) return
    const payload = {
      userSdwtProd: target.user_sdwt_prod,
      department: target.department,
      line: target.line,
    }
    onSubmit(payload, () => {
      setSelectedKey("")
    })
  }

  return (
    <Card className="h-full min-h-0 gap-0 overflow-hidden py-0">
      <CardHeader className="shrink-0 border-b px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="space-y-1">
            <CardTitle>소속 변경 요청</CardTitle>
          </div>
        </div>
        <CardDescription>
          소속 변경은 승인 이후에 적용됩니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-y-auto p-5">
        <form onSubmit={handleSubmit} className="grid gap-4">
          <div className="grid gap-8">
            <div className="grid gap-1 rounded-lg border bg-muted/30 p-3">
              <span className="text-xs font-medium text-muted-foreground">현재 소속</span>
              <span className="text-sm font-semibold text-foreground">
                {(data?.currentDepartment || "미지정") +
                  " / " +
                  (data?.currentLine || "미지정") +
                  " / " +
                  (data?.currentUserSdwtProd || "미지정")}
              </span>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="affiliationSelect">변경할 소속 (Department / Line / user_sdwt_prod)</Label>
              <select
                id="affiliationSelect"
                className="bg-background border-input focus-visible:ring-ring/50 focus-visible:ring-[3px] h-10 rounded-md border px-3 text-sm outline-none"
                value={selectedKey}
                onChange={(e) => setSelectedKey(e.target.value)}
                required
                disabled={!options.length}
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
          </div>

          <div className="grid gap-1 rounded-md border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            <p>관리자 승인 후 소속이 변경됩니다.</p>
            <p>승인 완료 후 메일함과 RAG 인덱스가 반영됩니다.</p>
          </div>

          {error ? (
            <p className="text-destructive text-sm">{error}</p>
          ) : null}
          {successMessage ? <p className="text-sm text-primary">{successMessage}</p> : null}

          <div className="flex justify-end border-t pt-4">
            <Button type="submit" disabled={isSubmitting || !options.length || !selectedKey}>
              {isSubmitting ? "요청 중..." : "변경 신청"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
