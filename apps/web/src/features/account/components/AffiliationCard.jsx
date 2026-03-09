import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"

function optionKey(opt) {
  return `${opt.department}||${opt.line}||${opt.user_sdwt_prod}`
}

function formatDateTimeLocal(date) {
  const pad = (value) => String(value).padStart(2, "0")
  const year = date.getFullYear()
  const month = pad(date.getMonth() + 1)
  const day = pad(date.getDate())
  const hours = pad(date.getHours())
  const minutes = pad(date.getMinutes())
  return `${year}-${month}-${day}T${hours}:${minutes}`
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
  const [effectiveFrom, setEffectiveFrom] = useState(() => formatDateTimeLocal(new Date()))

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
    if (effectiveFrom) {
      payload.effectiveFrom = effectiveFrom
    }
    onSubmit(payload, () => {
      setSelectedKey("")
    })
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>소속 변경 요청</CardTitle>
        <CardDescription>
          소속 변경은 승인 이후에만 적용됩니다. 메일 재분류는 선택한 기준 시각 이후 수신분부터 반영됩니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 rounded-lg border p-3">
          <div className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">현재 소속 :
              <span className="text-lg font-semibold text-foreground"> {(data?.currentDepartment || "미지정") + " / " + (data?.currentLine || "미지정") + " / " + (data?.currentUserSdwtProd || "미지정")}</span>
            </span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="grid gap-3">
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

          <div className="grid gap-2">
            <Label htmlFor="effectiveFromInput">소속 변경 기준 시각 (KST)</Label>
            <input
              id="effectiveFromInput"
              type="datetime-local"
              className="bg-background border-input focus-visible:ring-ring/50 focus-visible:ring-[3px] h-10 rounded-md border px-3 text-sm outline-none"
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
            />
          </div>

          <div className="grid gap-1 rounded-md border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            <p>관리자 승인 후 소속이 변경됩니다.</p>
            <p>승인 완료 후 메일함과 RAG 인덱스가 반영됩니다.</p>
          </div>

          {error ? (
            <p className="text-destructive text-sm">{error}</p>
          ) : null}
          {successMessage ? <p className="text-sm text-primary">{successMessage}</p> : null}

          <div className="flex justify-end">
            <Button type="submit" disabled={isSubmitting || !options.length || !selectedKey}>
              {isSubmitting ? "요청 중..." : "변경 신청"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
