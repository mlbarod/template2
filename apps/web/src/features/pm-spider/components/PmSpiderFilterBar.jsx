import { Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { hasRequiredPmFilters, normalizeOptions } from "../utils/format"

function Field({ id, label, children }) {
  return (
    <div className="grid min-w-0 gap-1.5">
      <Label htmlFor={id} className="text-xs font-medium text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  )
}

function MetaSelect({ id, value, onChange, options, placeholder, disabled }) {
  const items = normalizeOptions(options)
  return (
    <Select value={value || ""} onValueChange={onChange} disabled={disabled || !items.length}>
      <SelectTrigger id={id} className="h-9 w-full bg-background">
        <SelectValue placeholder={items.length ? placeholder : "데이터 없음"} />
      </SelectTrigger>
      <SelectContent>
        {items.map((item) => (
          <SelectItem key={item} value={item}>
            {item}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

const RESET_FIELDS_BY_KEY = {
  lineId: ["eqpId", "fdcBin", "pmTimestamp"],
  eqpId: ["fdcBin", "pmTimestamp"],
  fdcBin: ["pmTimestamp"],
}

export function PmSpiderFilterBar({
  form,
  meta,
  isMetaLoading,
  isResultFetching,
  onFormChange,
  onSubmit,
}) {
  const canSubmit = hasRequiredPmFilters(form) && !isResultFetching

  const setField = (key, value) => {
    const nextForm = { ...form, [key]: value }
    for (const resetKey of RESET_FIELDS_BY_KEY[key] || []) {
      nextForm[resetKey] = ""
    }
    onFormChange(nextForm)
  }

  const submit = (event) => {
    event.preventDefault()
    if (!canSubmit) return
    onSubmit()
  }

  return (
    <section className="shrink-0 border-b bg-card">
      <form onSubmit={submit} className="px-4 py-3 md:px-6">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-[repeat(4,minmax(0,1fr))_auto]">
          <Field id="pm-line-id" label="Line ID *">
            <MetaSelect
              id="pm-line-id"
              value={form.lineId}
              onChange={(v) => setField("lineId", v)}
              options={meta?.lineIds}
              placeholder="Line 선택"
              disabled={isMetaLoading}
            />
          </Field>

          <Field id="pm-eqp-id" label="EQP ID *">
            <MetaSelect
              id="pm-eqp-id"
              value={form.eqpId}
              onChange={(v) => setField("eqpId", v)}
              options={meta?.eqpIds}
              placeholder="EQP 선택"
              disabled={isMetaLoading}
            />
          </Field>

          <Field id="pm-fdc-bin" label="FDC Bin *">
            <MetaSelect
              id="pm-fdc-bin"
              value={form.fdcBin}
              onChange={(v) => setField("fdcBin", v)}
              options={meta?.fdcBins}
              placeholder="Bin 선택"
              disabled={isMetaLoading}
            />
          </Field>

          <Field id="pm-timestamp" label="PM 시점 *">
            <MetaSelect
              id="pm-timestamp"
              value={form.pmTimestamp}
              onChange={(v) => setField("pmTimestamp", v)}
              options={meta?.pmDates}
              placeholder="날짜 선택"
              disabled={isMetaLoading}
            />
          </Field>

          <div className="flex items-end">
            <Button type="submit" disabled={!canSubmit} className="h-9 w-full lg:w-auto">
              <Search className="size-4" />
              조회
            </Button>
          </div>
        </div>
      </form>
    </section>
  )
}
