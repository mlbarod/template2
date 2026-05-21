import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

import { sortedValues, toggleSetValue } from "../utils/selection"

function NativeCheck({ checked, indeterminate, label, onChange }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 px-2 py-1 text-xs hover:bg-muted/60">
      <input
        type="checkbox"
        checked={checked}
        ref={(node) => {
          if (node) node.indeterminate = Boolean(indeterminate)
        }}
        onChange={onChange}
        className="size-3.5 accent-primary"
      />
      <span className="min-w-0 truncate">{label}</span>
    </label>
  )
}

export function L3SpiderFilterPanel({
  stepPpids,
  bins,
  checkedPpids,
  checkedBins,
  onCheckedPpidsChange,
  onCheckedBinsChange,
  onClearChartFilter,
}) {
  const [stepQuery, setStepQuery] = useState("")
  const [binQuery, setBinQuery] = useState("")
  const steps = useMemo(() => sortedValues(Object.keys(stepPpids || {})), [stepPpids])
  const allPpids = useMemo(
    () => sortedValues(new Set(steps.flatMap((step) => stepPpids?.[step] ?? []))),
    [stepPpids, steps],
  )
  const visibleSteps = useMemo(() => {
    const query = stepQuery.trim().toLowerCase()
    if (!query) return steps
    return steps.filter(
      (step) =>
        step.toLowerCase().includes(query) ||
        (stepPpids?.[step] ?? []).some((ppid) => ppid.toLowerCase().includes(query)),
    )
  }, [stepPpids, stepQuery, steps])
  const visibleBins = useMemo(() => {
    const query = binQuery.trim().toLowerCase()
    return query ? bins.filter((bin) => bin.toLowerCase().includes(query)) : bins
  }, [binQuery, bins])

  const allPpidsChecked = allPpids.length > 0 && allPpids.every((ppid) => checkedPpids.has(ppid))
  const somePpidsChecked = allPpids.some((ppid) => checkedPpids.has(ppid)) && !allPpidsChecked
  const allBinsChecked = bins.length > 0 && bins.every((bin) => checkedBins.has(bin))
  const someBinsChecked = bins.some((bin) => checkedBins.has(bin)) && !allBinsChecked

  const toggleStep = (step) => {
    const ppids = stepPpids?.[step] ?? []
    const isAllChecked = ppids.length > 0 && ppids.every((ppid) => checkedPpids.has(ppid))
    const next = new Set(checkedPpids)
    ppids.forEach((ppid) => {
      if (isAllChecked) next.delete(ppid)
      else next.add(ppid)
    })
    onCheckedPpidsChange(next)
  }

  return (
    <aside className="grid min-h-0 grid-rows-[auto,1fr] border-r bg-card">
      <div className="border-b px-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">Filters</h2>
          <Button type="button" variant="ghost" size="sm" onClick={onClearChartFilter}>
            선택 해제
          </Button>
        </div>
      </div>
      <div className="min-h-0 overflow-y-auto py-2">
        <section className="border-b">
          <div className="flex items-center gap-2 px-3 py-2">
            <h3 className="flex-1 text-xs font-semibold text-foreground">step_seq / ppid</h3>
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
              {checkedPpids.size}/{allPpids.length}
            </span>
          </div>
          <div className="grid gap-1 px-3 pb-3">
            <Input
              value={stepQuery}
              onChange={(event) => setStepQuery(event.target.value)}
              placeholder="Search…"
              className="h-8"
            />
            <NativeCheck
              label="All"
              checked={allPpidsChecked}
              indeterminate={somePpidsChecked}
              onChange={() =>
                onCheckedPpidsChange(allPpidsChecked ? new Set() : new Set(allPpids))}
            />
            <div className="grid gap-1">
              {visibleSteps.map((step) => {
                const ppids = stepPpids?.[step] ?? []
                const checkedCount = ppids.filter((ppid) => checkedPpids.has(ppid)).length
                return (
                  <details key={step} className="border-t py-1" open>
                    <summary className="cursor-pointer px-2 text-xs font-semibold">
                      {step}{" "}
                      <span className="text-[10px] text-muted-foreground">
                        ({checkedCount}/{ppids.length})
                      </span>
                    </summary>
                    <NativeCheck
                      label={`${step} All`}
                      checked={ppids.length > 0 && checkedCount === ppids.length}
                      indeterminate={checkedCount > 0 && checkedCount < ppids.length}
                      onChange={() => toggleStep(step)}
                    />
                    {ppids.map((ppid) => (
                      <NativeCheck
                        key={`${step}-${ppid}`}
                        label={ppid}
                        checked={checkedPpids.has(ppid)}
                        onChange={() => onCheckedPpidsChange(toggleSetValue(checkedPpids, ppid))}
                      />
                    ))}
                  </details>
                )
              })}
            </div>
          </div>
        </section>
        <section className="border-b">
          <div className="flex items-center gap-2 px-3 py-2">
            <h3 className="flex-1 text-xs font-semibold text-foreground">bin_name</h3>
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
              {checkedBins.size}/{bins.length}
            </span>
          </div>
          <div className="grid gap-1 px-3 pb-3">
            <Input
              value={binQuery}
              onChange={(event) => setBinQuery(event.target.value)}
              placeholder="Search…"
              className="h-8"
            />
            <NativeCheck
              label="All"
              checked={allBinsChecked}
              indeterminate={someBinsChecked}
              onChange={() =>
                onCheckedBinsChange(allBinsChecked ? new Set() : new Set(bins))}
            />
            {visibleBins.map((bin) => (
              <NativeCheck
                key={bin}
                label={bin}
                checked={checkedBins.has(bin)}
                onChange={() => onCheckedBinsChange(toggleSetValue(checkedBins, bin))}
              />
            ))}
          </div>
        </section>
      </div>
    </aside>
  )
}
