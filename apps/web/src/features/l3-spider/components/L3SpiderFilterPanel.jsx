import { useMemo, useState } from "react"
import { ChevronRight, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import { sortedValues } from "../utils/selection"

function SelectRow({ label, hint, selected, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex h-9 w-full min-w-0 items-center justify-between gap-3 rounded-md border border-transparent px-3 text-left transition",
        "hover:border-border hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected && "border-primary/30 bg-primary/10 text-primary shadow-sm",
      )}
    >
      <span
        className={cn(
          "min-w-0 flex-1 truncate text-[13px] font-medium leading-5 text-foreground",
          selected && "text-primary",
        )}
      >
        {label}
      </span>
      {hint != null && (
        <span className="shrink-0 text-[11px] text-muted-foreground">
          {hint}
        </span>
      )}
      <ChevronRight className="size-3 shrink-0 text-muted-foreground" aria-hidden="true" />
    </button>
  )
}

function ColumnCard({ title, badge, disabled, placeholder, isActive, isLoading, children }) {
  const [query, setQuery] = useState("")

  return (
    <Card
      className={cn(
        "grid min-h-0 grid-rows-[48px_40px_minmax(0,1fr)] gap-0 overflow-hidden rounded-xl border bg-card py-0 shadow-sm transition-all",
        isActive && "ring-2 ring-primary/50",
      )}
    >
      <div
        className={cn(
          "flex h-12 items-center border-b px-4",
          isActive ? "bg-primary/10" : "bg-muted/40",
        )}
      >
        <div className="flex h-full min-w-0 flex-1 items-center justify-between gap-2">
          <CardTitle
            className={cn(
              "truncate text-sm font-semibold leading-5",
              disabled && "text-muted-foreground",
              isActive && "text-primary",
            )}
          >
            {title}
          </CardTitle>
          {isLoading ? (
            <Loader2 className="size-3.5 shrink-0 animate-spin text-muted-foreground" />
          ) : badge != null ? (
            <Badge variant={isActive ? "default" : "secondary"} className="shrink-0 text-[11px]">
              {badge}
            </Badge>
          ) : null}
        </div>
      </div>
      <div className="border-b px-2 py-1.5">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="검색…"
          className="h-7 text-xs"
          disabled={disabled}
        />
      </div>
      <CardContent className="min-h-0 overflow-y-auto bg-background/60 p-2">
        {disabled ? (
          <div className="flex h-full min-h-16 items-center justify-center text-center text-sm text-muted-foreground">
            {placeholder}
          </div>
        ) : (
          <div className="grid content-start gap-1.5">
            {children(query)}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function applyQuery(items, query) {
  const q = query.trim().toLowerCase()
  return q ? items.filter((item) => item.toLowerCase().includes(q)) : items
}

export function L3SpiderFilterPanel({
  edsStepSeqs,
  edsStepPpids,         // dict: eds_step|||step_seq → [ppids]
  ppidLastTkinTime,     // dict: eds_step|||step_seq|||ppid → "YYYY-MM-DD HH:mm"
  selectedEdsSteps,     // Set<string> — DataSelector에서 선택된 EDS Steps
  eqcHighRiskBins,      // null(로딩/미선택) | dict: eqc → [high_risk_bins] (candidates)
  isCandidatesLoading,
  checkedStep,          // string | null — 복합키: "eds_step|||step_seq"
  checkedPpid,          // string | null
  checkedEqc,           // string | null — EQPCH 모드 (단일)
  checkedBin,           // string | null — Bin 모드 (단일)
  onCheckedStepChange,
  onCheckedPpidChange,
  onCheckedEqcChange,
  onCheckedBinChange,
  onAnalysisModeChange,
}) {
  // EDS Step별로 step_seq 그룹핑 (같은 step_seq가 다른 EDS Step에 있을 수 있음)
  const groupedSteps = useMemo(
    () => sortedValues(selectedEdsSteps ?? [])
      .map((eds) => ({ eds, steps: sortedValues(edsStepSeqs?.[eds] ?? []) }))
      .filter(({ steps }) => steps.length > 0),
    [selectedEdsSteps, edsStepSeqs],
  )

  const totalStepCount = useMemo(
    () => groupedSteps.reduce((sum, { steps }) => sum + steps.length, 0),
    [groupedSteps],
  )

  // 복합키 "eds_step|||step_seq" 기반으로 ppid 조회
  const visiblePpids = useMemo(
    () => checkedStep ? sortedValues(edsStepPpids?.[checkedStep] ?? []) : [],
    [checkedStep, edsStepPpids],
  )

  // candidate 로드 완료 시점에만 표시 (null = 로딩 중 또는 ppid 미선택)
  const visibleEqcs = useMemo(
    () => (checkedPpid && eqcHighRiskBins != null)
      ? sortedValues(Object.keys(eqcHighRiskBins))
      : [],
    [checkedPpid, eqcHighRiskBins],
  )

  // 해당 EQPCH에서 high risk가 발생한 bin_name만 표시
  const visibleBins = useMemo(
    () => (checkedEqc && eqcHighRiskBins != null)
      ? sortedValues(eqcHighRiskBins[checkedEqc] ?? [])
      : [],
    [checkedEqc, eqcHighRiskBins],
  )

  const selectStep = (step) => {
    const next = checkedStep === step ? null : step
    onCheckedStepChange(next)
    onCheckedPpidChange(null)
    onCheckedEqcChange(null)
    onCheckedBinChange(null)
  }

  const selectPpid = (ppid) => {
    const next = checkedPpid === ppid ? null : ppid
    onCheckedPpidChange(next)
    onCheckedEqcChange(null)
    onCheckedBinChange(null)
  }

  const selectEqc = (eqc) => {
    const next = checkedEqc === eqc ? null : eqc
    onCheckedEqcChange(next)
    onCheckedBinChange(null)
    if (next !== null) onAnalysisModeChange("eqpch")
  }

  const selectBin = (bin) => {
    const next = checkedBin === bin ? null : bin
    onCheckedBinChange(next)
    onAnalysisModeChange(next !== null ? "bin" : "eqpch")
  }

  return (
    <section className="grid h-[320px] grid-cols-4 gap-4">
      <ColumnCard
        title="Step Seq"
        badge={totalStepCount > 0 ? `${totalStepCount}` : null}
        disabled={!selectedEdsSteps || selectedEdsSteps.size === 0}
        placeholder="EDS Step을 먼저 선택하세요"
        isActive={checkedStep !== null}
      >
        {(query) => {
          const q = query.trim().toLowerCase()
          return groupedSteps.map(({ eds, steps }) => {
            const filtered = q ? steps.filter((s) => s.toLowerCase().includes(q)) : steps
            if (filtered.length === 0) return null
            return (
              <div key={eds}>
                <div className="px-2 pb-0.5 pt-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground first:pt-0">
                  {eds}
                </div>
                {filtered.map((step) => {
                  const compositeKey = `${eds}|||${step}`
                  return (
                    <SelectRow
                      key={compositeKey}
                      label={step}
                      selected={checkedStep === compositeKey}
                      onClick={() => selectStep(compositeKey)}
                    />
                  )
                })}
              </div>
            )
          })
        }}
      </ColumnCard>

      <ColumnCard
        title="PPID"
        badge={visiblePpids.length > 0 ? `${visiblePpids.length}` : null}
        disabled={!checkedStep}
        placeholder="Step Seq를 먼저 선택하세요"
        isActive={checkedPpid !== null}
      >
        {(query) =>
          applyQuery(visiblePpids, query).map((ppid) => {
            const tkinKey = checkedStep ? `${checkedStep}|||${ppid}` : null
            const lastTkin = tkinKey ? (ppidLastTkinTime?.[tkinKey] ?? null) : null
            return (
              <SelectRow
                key={ppid}
                label={ppid}
                hint={lastTkin}
                selected={checkedPpid === ppid}
                onClick={() => selectPpid(ppid)}
              />
            )
          })
        }
      </ColumnCard>

      <ColumnCard
        title="EQPCH"
        badge={visibleEqcs.length > 0 ? `${visibleEqcs.length}` : null}
        disabled={!checkedPpid || isCandidatesLoading}
        placeholder={isCandidatesLoading ? "로딩 중…" : "PPID를 먼저 선택하세요"}
        isActive={checkedEqc !== null}
        isLoading={isCandidatesLoading}
      >
        {(query) =>
          applyQuery(visibleEqcs, query).map((eqc) => {
            const highRiskBinCount = eqcHighRiskBins?.[eqc]?.length ?? 0
            return (
              <SelectRow
                key={eqc}
                label={eqc}
                hint={highRiskBinCount > 0 ? String(highRiskBinCount) : null}
                selected={checkedEqc === eqc}
                onClick={() => selectEqc(eqc)}
              />
            )
          })
        }
      </ColumnCard>

      <ColumnCard
        title="Bin Name"
        badge={visibleBins.length > 0 ? `${visibleBins.length}` : null}
        disabled={!checkedEqc}
        placeholder="EQPCH를 먼저 선택하세요"
        isActive={checkedBin !== null}
      >
        {(query) =>
          applyQuery(visibleBins, query).map((bin) => (
            <SelectRow
              key={bin}
              label={bin}
              selected={checkedBin === bin}
              onClick={() => selectBin(bin)}
            />
          ))
        }
      </ColumnCard>
    </section>
  )
}
