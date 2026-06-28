import { useEffect, useMemo, useRef, useState } from "react"
import { Activity, AlertTriangle, Search, Waves, X } from "lucide-react"
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import { usePmSpiderMeta, usePmSpiderDetailResult } from "../hooks/usePmSpiderQueries"
import { formatNumber } from "../utils/format"
import { CanvasHeatmap } from "./CanvasHeatmap"
import { CanvasLineChart } from "./CanvasLineChart"
import { buildJitterKde, buildRawSeries, buildShapeData, C as TC, StepSelector } from "./TraceSignalPanel"

// ──────────────────────────────────────────────────────────────
// 타입 탭 정의: NPW / PW
// ──────────────────────────────────────────────────────────────
const TYPE_TABS = [
  { id: "ag",      label: "NPW" },
  { id: "process", label: "PW"  },
]

function ChartCloseButton({ onClick, label = "차트 닫기" }) {
  if (!onClick) return null

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      onClick={onClick}
      className="size-7 text-muted-foreground hover:text-foreground"
      aria-label={label}
      title={label}
    >
      <X className="size-3.5" aria-hidden="true" />
    </Button>
  )
}

function formatWavelengthValue(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return ""
  if (Number.isInteger(numeric)) return String(numeric)
  return numeric.toFixed(3).replace(/0+$/, "").replace(/\.$/, "")
}

function nearestWavelength(value, wavelengths) {
  const numeric = Number(value)
  const candidates = Array.isArray(wavelengths)
    ? wavelengths.map(Number).filter(Number.isFinite)
    : []
  if (!Number.isFinite(numeric) || !candidates.length) return null
  return candidates.reduce((nearest, candidate) => (
    Math.abs(candidate - numeric) < Math.abs(nearest - numeric) ? candidate : nearest
  ), candidates[0])
}

function WavelengthInput({ value, wavelengths, onSelect, className }) {
  const [draft, setDraft] = useState(formatWavelengthValue(value))

  useEffect(() => {
    setDraft(formatWavelengthValue(value))
  }, [value])

  const commit = () => {
    const snapped = nearestWavelength(draft, wavelengths)
    if (snapped == null) {
      setDraft(formatWavelengthValue(value))
      return
    }
    onSelect?.(snapped)
    setDraft(formatWavelengthValue(snapped))
  }

  return (
    <label className={cn("flex items-center gap-1 text-[10px] text-muted-foreground", className)}>
      <span className="shrink-0">wavelength</span>
      <Input
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.currentTarget.blur()
          }
        }}
        inputMode="decimal"
        className="h-7 w-20 px-2 text-right text-[11px]"
        aria-label="OES wavelength 직접 입력"
      />
      <span className="shrink-0">nm</span>
    </label>
  )
}

function debugValue(value) {
  if (value == null || value === "") return "-"
  if (Array.isArray(value)) return value.length ? value.join(", ") : "[]"
  if (typeof value === "number") return Number.isFinite(value) ? formatNumber(value, 4) : "-"
  return String(value)
}

function OesDebugLine({ label, value }) {
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words font-mono text-foreground">{debugValue(value)}</dd>
    </div>
  )
}

function OesEmptyDebugPanel({ category, selectedStep, detailResult, queryError }) {
  const oes = detailResult?.oes ?? {}
  const filters = detailResult?.filters ?? category?.payload ?? {}
  const warnings = Array.isArray(detailResult?.warnings) ? detailResult.warnings : []
  const stepRows = Array.isArray(oes?.stepRows) ? oes.stepRows : []
  const availableSteps = stepRows.map((row) => String(row.step ?? "")).filter(Boolean)
  const selectedStepText = String(selectedStep ?? "")
  const hasSelectedStep = availableSteps.includes(selectedStepText)
  const heatmap = oes?.heatmap ?? {}
  const queryMessage = queryError?.message || queryError?.response?.data?.error || ""
  const diagnosis = []

  if (!detailResult) diagnosis.push("detail API 응답이 아직 없습니다. Network 탭에서 compare 요청 실패 여부를 확인하세요.")
  if (Number(oes?.scoreFileCount || 0) === 0) diagnosis.push("OES score 파일을 읽지 못했습니다. result/score_data partition을 확인하세요.")
  if (Number(oes?.fileCount || 0) === 0) diagnosis.push("OES raw 파일 후보가 0개입니다. data 경로, dt/PM 시점, ppid/recipe_id, OES plain/Hive layout을 확인하세요.")
  if (Number(oes?.fileCount || 0) > 0 && Number(oes?.rowCount || 0) === 0) diagnosis.push("raw 파일은 읽었지만 선택 step/filter 후 남은 row가 없습니다. raw의 rcp_step/step_seq와 선택 step 값이 같은지 확인하세요.")
  if (stepRows.length > 0 && !hasSelectedStep) diagnosis.push("선택 step이 score step 목록에 없습니다. 랭킹 row의 step 문자열과 raw rcp_step 값의 대소문자/공백을 확인하세요.")
  if (Number(oes?.rowCount || 0) > 0 && (!heatmap?.width || !heatmap?.height)) diagnosis.push("row는 있지만 heatmap matrix가 비었습니다. wavelength/value 컬럼 변환 또는 traj_phase/time 컬럼을 확인하세요.")
  if (warnings.length) diagnosis.push("backend warnings가 있습니다. 아래 warning 메시지를 먼저 확인하세요.")
  if (queryMessage) diagnosis.push("detail API 요청 오류가 있습니다. 아래 query error를 확인하세요.")
  if (!diagnosis.length) diagnosis.push("count상 명확한 원인이 없습니다. Network response의 oes.detailRows, oes.heatmap 원문을 확인하세요.")

  const visibleStepRows = stepRows.slice(0, 12)

  return (
    <div className="grid w-full gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-left">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
        <div className="grid gap-1">
          <p className="text-sm font-semibold text-foreground">
            step <span className="font-mono">{selectedStepText}</span> intensity 데이터가 없습니다
          </p>
          <p className="text-xs text-muted-foreground">
            score/raw 조회 결과와 선택 조건을 아래에 표시합니다.
          </p>
        </div>
      </div>

      <div className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
        <p className="font-semibold text-foreground">원인 후보</p>
        <ul className="grid gap-1 text-muted-foreground">
          {diagnosis.map((message) => (
            <li key={message}>- {message}</li>
          ))}
        </ul>
      </div>

      <dl className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
        <OesDebugLine label="lineId" value={filters.lineId} />
        <OesDebugLine label="eqpId" value={filters.eqpId} />
        <OesDebugLine label="fdcBin" value={filters.fdcBin} />
        <OesDebugLine label="pmTimestamp" value={filters.pmTimestamp} />
        <OesDebugLine label="type" value={filters.type} />
        <OesDebugLine label="ppid" value={filters.ppid} />
        <OesDebugLine label="recipeId" value={filters.recipeId} />
        <OesDebugLine label="selectedStep" value={selectedStepText} />
        <OesDebugLine label="oesDataSource" value={filters.oesDataSource || "oes"} />
      </dl>

      <dl className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
        <OesDebugLine label="scoreFileCount" value={oes.scoreFileCount} />
        <OesDebugLine label="rawFileCount" value={oes.fileCount} />
        <OesDebugLine label="rowCount" value={oes.rowCount} />
        <OesDebugLine label="summaryRows" value={Array.isArray(oes.summaryRows) ? oes.summaryRows.length : 0} />
        <OesDebugLine label="stepRows" value={stepRows.length} />
        <OesDebugLine label="detailRows" value={Array.isArray(oes.detailRows) ? oes.detailRows.length : 0} />
        <OesDebugLine label="heatmap" value={`${heatmap?.width || 0} x ${heatmap?.height || 0}`} />
        <OesDebugLine label="wavelengthCount" value={Array.isArray(heatmap?.wavelengths) ? heatmap.wavelengths.length : 0} />
        <OesDebugLine label="sourcePointCount" value={heatmap?.sourcePointCount} />
      </dl>

      <div className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
        <p className="font-semibold text-foreground">사용 가능한 score step 후보</p>
        {visibleStepRows.length ? (
          <div className="grid gap-1">
            {visibleStepRows.map((row) => (
              <div
                key={`${row.step}-${row.minScore}-${row.maxScore}`}
                className={cn(
                  "grid grid-cols-[80px_1fr] gap-2 rounded px-1 py-0.5",
                  String(row.step) === selectedStepText && "bg-accent text-accent-foreground",
                )}
              >
                <span className="font-mono">{debugValue(row.step)}</span>
                <span className="text-muted-foreground">
                  wavelengths {debugValue(row.wavelengthCount)} · score {debugValue(row.minScore)} ~ {debugValue(row.maxScore)}
                </span>
              </div>
            ))}
            {stepRows.length > visibleStepRows.length ? (
              <p className="text-muted-foreground">외 {stepRows.length - visibleStepRows.length}개 step 생략</p>
            ) : null}
          </div>
        ) : (
          <p className="text-muted-foreground">score step 후보가 없습니다.</p>
        )}
      </div>

      {warnings.length || queryMessage ? (
        <div className="grid gap-1 rounded-md border bg-background p-2 text-[11px]">
          <p className="font-semibold text-foreground">warnings / query error</p>
          {queryMessage ? <p className="break-words text-destructive">{queryMessage}</p> : null}
          {warnings.map((warning) => (
            <p key={warning} className="break-words text-muted-foreground">{warning}</p>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function formatMetaValues(values) {
  const normalized = Array.isArray(values) ? values.filter(Boolean) : []
  return normalized.length ? normalized.join(", ") : "-"
}

function normalizeMetaValues(values) {
  return Array.isArray(values) ? values.filter(Boolean).map(String) : []
}

function sameMetaValues(left, right) {
  if (left.length !== right.length) return false
  return left.every((value, index) => value === right[index])
}

function buildRecipeMeta(meta) {
  const commonPpids = normalizeMetaValues(meta?.ppids)
  const commonRecipes = normalizeMetaValues(meta?.recipeIds)
  const refPpids = normalizeMetaValues(meta?.refPpids ?? meta?.refPPIDs ?? meta?.ref?.ppids)
  const refRecipes = normalizeMetaValues(meta?.refRecipeIds ?? meta?.ref?.recipeIds)
  const compPpids = normalizeMetaValues(meta?.compPpids ?? meta?.compPPIDs ?? meta?.comp?.ppids)
  const compRecipes = normalizeMetaValues(meta?.compRecipeIds ?? meta?.comp?.recipeIds)
  const ref = {
    ppids: refPpids.length ? refPpids : commonPpids,
    recipeIds: refRecipes.length ? refRecipes : commonRecipes,
  }
  const comp = {
    ppids: compPpids.length ? compPpids : commonPpids,
    recipeIds: compRecipes.length ? compRecipes : commonRecipes,
  }
  const same = sameMetaValues(ref.ppids, comp.ppids) && sameMetaValues(ref.recipeIds, comp.recipeIds)
  return { ref, comp, same }
}

function getRankModeLabel(mode) {
  return mode === "p2" ? "P2 비교" : "P3 비교"
}

function buildRecipeMetaSummary(recipeMeta) {
  const formatPair = ({ ppids, recipeIds }) => {
    const ppidText = formatMetaValues(ppids)
    const recipeText = formatMetaValues(recipeIds)
    if (ppidText === "-" && recipeText === "-") return "-"
    return `${ppidText}-${recipeText}`
  }

  if (recipeMeta.same) return formatPair(recipeMeta.ref)

  return `REF ${formatPair(recipeMeta.ref)} / COMP ${formatPair(recipeMeta.comp)}`
}

function ToggleButton({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "h-7 rounded border px-2 text-[11px] font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}

function RankingControlPanel({
  activeType,
  activeKind,
  activeMode,
  onTypeChange,
  onKindChange,
  onModeChange,
}) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="grid gap-2">
        <div className="grid grid-cols-3 gap-2">
          <div className="grid gap-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Type</p>
            <div className="flex gap-1">
              {TYPE_TABS.map((tab) => (
                <ToggleButton
                  key={tab.id}
                  active={activeType === tab.id}
                  onClick={() => onTypeChange(tab.id)}
                >
                  {tab.label}
                </ToggleButton>
              ))}
            </div>
          </div>
          <div className="grid gap-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Source</p>
            <div className="flex gap-1">
              <ToggleButton active={activeKind === "trace"} onClick={() => onKindChange("trace")}>TRACE</ToggleButton>
              <ToggleButton active={activeKind === "oes"} onClick={() => onKindChange("oes")}>OES</ToggleButton>
            </div>
          </div>
          <div className="grid gap-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Mode</p>
            <div className="flex gap-1">
              <ToggleButton active={activeMode === "p2"} onClick={() => onModeChange("p2")}>P2</ToggleButton>
              <ToggleButton active={activeMode === "p3"} onClick={() => onModeChange("p3")}>P3</ToggleButton>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────
// 랭킹 빌드 헬퍼
// ──────────────────────────────────────────────────────────────
function buildRankRows(category, panelType) {
  const rows = (category?.rows ?? []).filter(Boolean)
  if (category?.kind === "trace") {
    const sorted = [...rows].sort((a, b) =>
      panelType === "p2"
        ? Number(b.alarmPct ?? 0) - Number(a.alarmPct ?? 0)
        : Number(b.deltaShape ?? 0) - Number(a.deltaShape ?? 0)
    )
    return sorted.filter((r) => r.itemName || r.traceSensor)
  }
  const byStep = new Map()
  for (const row of rows) {
    const stepKey = row.step || row.itemName || ""
    if (!stepKey) continue
    const prev = byStep.get(stepKey)
    const metric = panelType === "p2" ? Number(row.flaggedWl ?? 0) : Number(row.deltaSpectrum ?? 0)
    const prevMetric = prev ? (panelType === "p2" ? Number(prev.flaggedWl ?? 0) : Number(prev.deltaSpectrum ?? 0)) : -1
    if (!prev || metric > prevMetric) byStep.set(stepKey, row)
  }
  return Array.from(byStep.values()).sort((a, b) =>
    panelType === "p2"
      ? Number(b.flaggedWl ?? 0) - Number(a.flaggedWl ?? 0)
      : Number(b.deltaSpectrum ?? 0) - Number(a.deltaSpectrum ?? 0)
  )
}

function getRowKey(category, row) {
  if (!row) return ""
  if (category?.kind === "trace") {
    const param = row.itemName || row.traceSensor || ""
    const step  = row.step || ""
    return step ? `${param}::${step}` : param
  }
  return row.step || row.itemName || ""
}

function parseTraceKey(key) {
  if (!key) return { paramName: "", step: "" }
  const idx = key.indexOf("::")
  if (idx === -1) return { paramName: key, step: "" }
  return { paramName: key.slice(0, idx), step: key.slice(idx + 2) }
}

function getRowLabel(category, row) {
  if (!row) return "-"
  if (category?.kind === "trace") return row.itemName || row.traceSensor || "-"
  return row.step || row.itemName || "-"
}

function getRowSubLabel(category, row) {
  if (category?.kind !== "trace") return null
  return row?.step ? `step ${row.step}` : null
}

function getMetricValue(category, row, panelType) {
  if (!row) return 0
  if (category?.kind === "trace") {
    return panelType === "p2" ? Number(row.alarmPct ?? 0) : Number(row.deltaShape ?? 0)
  }
  return panelType === "p2" ? Number(row.flaggedWl ?? 0) : Number(row.deltaSpectrum ?? 0)
}

function getMetricLabel(category, row, panelType) {
  if (!row) return "-"
  if (category?.kind === "trace") {
    return panelType === "p2"
      ? `${formatNumber(row.alarmPct ?? 0, 1)}%`
      : `Δ ${formatNumber(row.deltaShape ?? 0, 3)}`
  }
  return panelType === "p2"
    ? `${formatNumber(row.flaggedWl ?? 0, 0)} wl`
    : `Δ ${formatNumber(row.deltaSpectrum ?? 0, 3)}`
}

function filterRows(rows, category, query) {
  if (!query.trim()) return rows
  const q = query.toLowerCase()
  return rows.filter((row) => getRowLabel(category, row).toLowerCase().includes(q))
}

const BAR_WIDTHS = ["w-1/12","w-1/6","w-1/4","w-1/3","w-5/12","w-1/2","w-7/12","w-2/3","w-3/4","w-5/6","w-full"]
function getBarWidth(val, maxVal) {
  if (maxVal <= 0) return BAR_WIDTHS[BAR_WIDTHS.length - 1]
  const ratio = Math.min(1, val / maxVal)
  const idx = Math.max(0, Math.min(BAR_WIDTHS.length - 1, Math.ceil(ratio * (BAR_WIDTHS.length - 1))))
  return BAR_WIDTHS[idx]
}

// ──────────────────────────────────────────────────────────────
// 랭킹 패널
// ──────────────────────────────────────────────────────────────
function RankPanel({ panelType, category, selectedKeys, onSelectRow, onClearAll, search, onSearchChange }) {
  const isP2 = panelType === "p2"
  const rows = useMemo(() => buildRankRows(category, panelType), [category, panelType])
  const filtered = useMemo(() => filterRows(rows, category, search), [rows, category, search])
  const metricVals = filtered.map((r) => getMetricValue(category, r, panelType))
  const maxMetric = Math.max(0.001, ...metricVals)

  const searchPlaceholder = category?.kind === "trace" ? "파라미터 검색..." : "Step 검색..."

  return (
    <Card className="flex flex-col overflow-hidden rounded-lg py-0">
      <div className="shrink-0 border-b px-3 py-1">
        <div className="flex items-center gap-1.5">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={searchPlaceholder}
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              className="h-6 pl-6 text-xs"
            />
          </div>
          {onClearAll && selectedKeys.length > 0 && (
            <button
              type="button"
              onClick={onClearAll}
              className="h-6 shrink-0 rounded border px-1.5 text-[10px] text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              전체 해제
            </button>
          )}
        </div>
      </div>
      <div className="max-h-[320px] overflow-y-auto">
        {category?.isLoading ? (
          <div className="flex min-h-32 items-center justify-center text-sm text-muted-foreground">데이터 조회 중...</div>
        ) : !filtered.length ? (
          <div className="flex min-h-32 items-center justify-center text-sm text-muted-foreground">
            {rows.length ? "검색 결과 없음" : "데이터가 없습니다."}
          </div>
        ) : (
          <div className="divide-y">
            {filtered.map((row, idx) => {
              const key      = getRowKey(category, row)
              const subLabel = getRowSubLabel(category, row)
              const isSelected = selectedKeys.includes(key)
              const metric = getMetricValue(category, row, panelType)
              const barColor = isP2 ? "bg-blue-500" : "bg-orange-500"
              return (
                <button
                  key={`${key}-${idx}`}
                  type="button"
                  onClick={() => onSelectRow(key)}
                  className={cn(
                    "grid w-full gap-0.5 px-3 py-1.5 text-left transition-colors hover:bg-muted/50",
                    isSelected && "border-l-2 bg-accent/40",
                    isSelected && (isP2 ? "border-l-blue-500" : "border-l-orange-500"),
                  )}
                >
                  <div className="flex min-w-0 items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="flex size-5 shrink-0 items-center justify-center rounded bg-muted text-[10px] font-medium tabular-nums">
                        {idx + 1}
                      </span>
                      <div className="flex min-w-0 items-center gap-1.5">
                        <span className="truncate text-xs font-medium">{getRowLabel(category, row)}</span>
                        {subLabel && (
                          <span className="shrink-0 rounded border bg-muted/40 px-1 py-0 text-[9px] leading-4 text-muted-foreground">
                            {subLabel}
                          </span>
                        )}
                      </div>
                      {row.flag && row.flag !== "OK" && (
                        <Badge variant="outline" className="shrink-0 px-1 py-0 text-[9px]">
                          {row.flag}
                        </Badge>
                      )}
                    </div>
                    <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                      {getMetricLabel(category, row, panelType)}
                    </span>
                  </div>
                  <div className="h-1 overflow-hidden rounded-full bg-muted">
                    <div className={cn("h-full rounded-full", barColor, getBarWidth(metric, maxMetric))} />
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </Card>
  )
}

// ──────────────────────────────────────────────────────────────
// 차트 줌 훅 — div pixel 추적 기반 드래그 줌
// Recharts onMouseMove는 데이터 변경 후 불안정하므로 div native 이벤트를 사용합니다.
// yAxisWidth/marginRight는 차트 layout과 맞춰야 합니다.
// ──────────────────────────────────────────────────────────────
function useChartZoom(defaultDomain, yAxisWidth = 50, marginRight = 8) {
  const [domain, setDomain] = useState(defaultDomain)
  const [area, setArea]     = useState({ x1: null, x2: null })
  const selecting           = useRef(false)
  const x1Ref               = useRef(null)
  const x2Ref               = useRef(null)
  const x1PxRef             = useRef(null)  // mousedown 픽셀 X (드래그 거리 판별용)
  const wrapperRef          = useRef(null)

  useEffect(() => {
    const handleMouseUp = (e) => {
      if (!selecting.current) return
      selecting.current = false
      const x1 = x1Ref.current
      const x2 = x2Ref.current
      const dragPx = x1PxRef.current != null ? Math.abs(e.clientX - x1PxRef.current) : 0
      // 5px 미만은 클릭으로 처리 → 더블클릭 리셋이 발동할 수 있도록 줌 미적용
      if (x1 != null && x2 != null && x1 !== x2 && dragPx >= 5) {
        const [lo, hi] = [x1, x2].sort((a, b) => a - b)
        setDomain([lo, hi])
      }
      setArea({ x1: null, x2: null })
      x1Ref.current = null
      x2Ref.current = null
      x1PxRef.current = null
    }
    window.addEventListener("mouseup", handleMouseUp)
    return () => window.removeEventListener("mouseup", handleMouseUp)
  }, [])

  const pixelToData = (clientX, dataMin, dataMax) => {
    if (!wrapperRef.current || !isFinite(dataMin) || !isFinite(dataMax) || dataMin === dataMax) return null
    const rect = wrapperRef.current.getBoundingClientRect()
    const plotLeft  = yAxisWidth
    const plotRight = rect.width - marginRight
    const plotWidth = plotRight - plotLeft
    if (plotWidth <= 0) return null
    const relX = Math.max(0, Math.min(1, (clientX - rect.left - plotLeft) / plotWidth))
    return dataMin + relX * (dataMax - dataMin)
  }

  const onWrapperMouseDown = (e, dataMin, dataMax) => {
    selecting.current = true
    x1PxRef.current = e.clientX
    const v = pixelToData(e.clientX, dataMin, dataMax)
    x1Ref.current = v
    x2Ref.current = v
  }
  const onWrapperMouseMove = (e, dataMin, dataMax) => {
    if (!selecting.current) return
    const v = pixelToData(e.clientX, dataMin, dataMax)
    if (v == null) return
    if (x1Ref.current == null) x1Ref.current = v
    x2Ref.current = v
    setArea({ x1: x1Ref.current, x2: v })
  }
  const reset = () => {
    selecting.current = false
    setDomain(defaultDomain)
    setArea({ x1: null, x2: null })
    x1Ref.current = null
    x2Ref.current = null
    x1PxRef.current = null
  }
  const isZoomed = domain[0] !== defaultDomain[0] || domain[1] !== defaultDomain[1]
  const showArea = area.x1 != null && area.x2 != null && area.x1 !== area.x2

  return { domain, area, showArea, isZoomed, wrapperRef, onWrapperMouseDown, onWrapperMouseMove, reset }
}

// X 범위로 데이터 필터링 — Recharts domain prop보다 신뢰성이 높습니다.
function filterByXDomain(data, xKey, xDomain) {
  if (!data?.length) return data
  if (!Array.isArray(xDomain) || xDomain[0] === "auto" || xDomain[1] === "auto") return data
  const [lo, hi] = xDomain
  return data.filter(d => { const x = Number(d[xKey]); return isFinite(x) && x >= lo && x <= hi })
}

// 필터링된 데이터에서 Y min/max 계산 (여백 3%)
function computeYRange(data, yKeys, padFrac = 0.03) {
  if (!data?.length || !yKeys.length) return ["auto", "auto"]
  let mn = Infinity, mx = -Infinity
  for (const d of data) {
    for (const k of yKeys) { const v = Number(d[k]); if (isFinite(v)) { mn = Math.min(mn, v); mx = Math.max(mx, v) } }
  }
  if (!isFinite(mn) || mn === mx) return ["auto", "auto"]
  const pad = (mx - mn) * padFrac
  return [mn - pad, mx + pad]
}

// ──────────────────────────────────────────────────────────────
// 범례 패널 — 계층형 토글 패널 (그룹 + 개별 wafer)
// groups 형식: [{ groupKey, label, color, series: [{ key, label }] }]
// extras 형식: [{ key, label, colorStyle }]
// ──────────────────────────────────────────────────────────────
function LegendPanel({ vis, onToggle, onGroupToggle, groups = [], extras = [] }) {
  return (
    <div className="flex w-[150px] shrink-0 flex-col gap-0 overflow-y-auto rounded-lg border p-2" style={{ maxHeight: 300 }}>
      <p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">Legend</p>

      {groups.map(({ groupKey, label, color, series }) => {
        const allOn = series.every((s) => vis[s.key] !== false)
        const anyOn = series.some((s) => vis[s.key] !== false)
        return (
          <div key={groupKey}>
            {/* 그룹 헤더 — 전체 토글 */}
            <button
              type="button"
              onClick={() => onGroupToggle(groupKey, series)}
              className={cn(
                "flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-[10px] font-semibold transition-colors hover:bg-muted/50",
                !anyOn && "opacity-35",
              )}
            >
              <span
                className="size-3 shrink-0 rounded-sm border border-black/10"
                style={{ background: color, opacity: allOn ? 1 : anyOn ? 0.5 : 0.2 }}
              />
              <span className="truncate">{label}</span>
            </button>
            {/* 개별 wafer 행 */}
            {series.map((s) => {
              const on = vis[s.key] !== false
              return (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => onToggle(s.key)}
                  className={cn(
                    "flex w-full items-center gap-1 rounded py-[1px] pl-4 pr-1 text-left text-[10px] transition-colors hover:bg-muted/50",
                    !on && "opacity-35",
                  )}
                >
                  <span className="size-2 shrink-0 rounded-sm" style={{ background: color }} />
                  <span className="truncate font-mono">{s.label}</span>
                </button>
              )
            })}
          </div>
        )
      })}

      {/* 평면 항목 (median, tube 등) */}
      {extras.map(({ key, label, colorStyle }) => {
        const enabled = vis[key] !== false
        return (
          <button
            key={key}
            type="button"
            onClick={() => onToggle(key)}
            className={cn(
              "flex items-center gap-1.5 rounded px-1 py-0.5 text-left text-[10px] transition-colors hover:bg-muted/50",
              !enabled && "opacity-35",
            )}
          >
            <span className="size-3 shrink-0 rounded-sm border border-black/10" style={colorStyle} />
            <span className="truncate leading-tight">{label}</span>
          </button>
        )
      })}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────
// Trace 상세 — 원신호 / Shape / Jitter 탭 + 범례 + 줌
// ──────────────────────────────────────────────────────────────
function TraceDetailWithLegend({ category, selectedKey, refPmDates, onClose }) {
  const [vis, setVis]             = useState({ refMed: true, compMed: true, tube: true })
  const [chStep, setChStep]       = useState("")
  const [activeTab, setActiveTab] = useState("shape")

  const shapeZoom = useChartZoom([0, 99])

  const { paramName, step: defaultStep } = parseTraceKey(selectedKey)
  const queryRow    = paramName ? { itemName: paramName, traceSensor: paramName } : null
  const detailQuery = usePmSpiderDetailResult(category, queryRow, refPmDates)
  const traceLineChart = detailQuery.data?.trace?.lineChart
  const shapeRows = useMemo(
    () => detailQuery.data?.trace?.shapeRows ?? [],
    [detailQuery.data?.trace?.shapeRows],
  )
  const jitterRows = useMemo(
    () => detailQuery.data?.trace?.jitterRows ?? [],
    [detailQuery.data?.trace?.jitterRows],
  )
  const trendRows = useMemo(
    () => detailQuery.data?.trace?.trendRows ?? [],
    [detailQuery.data?.trace?.trendRows],
  )

  const chSteps = useMemo(() => {
    const all = new Set([
      ...shapeRows.map((r) => String(r.chStep ?? r.ch_step ?? "")).filter(Boolean),
      ...trendRows.map((r) => String(r.chStep ?? r.ch_step ?? "")).filter(Boolean),
      ...jitterRows.map((r) => String(r.chStep ?? r.ch_step ?? "")).filter(Boolean),
    ])
    return Array.from(all).sort()
  }, [shapeRows, trendRows, jitterRows])

  useEffect(() => { setChStep(defaultStep) }, [selectedKey, defaultStep])

  // 데이터 로드 완료 시 — shape 우선, 없으면 raw로 자동 전환
  useEffect(() => {
    if (detailQuery.isFetching || !detailQuery.data) return
    if (shapeRows.length > 0) setActiveTab("shape")
    else if (trendRows.length > 0) setActiveTab("raw")
  }, [detailQuery.isFetching, detailQuery.data, shapeRows.length, trendRows.length])

  const { data: shapeData, waferSeries, compMedKey, hasTube } = useMemo(
    () => buildShapeData(shapeRows, chStep), [shapeRows, chStep],
  )
  const { series: rawAllSeries } = useMemo(
    () => buildRawSeries(trendRows, chStep), [trendRows, chStep],
  )
  const { data: jitterData, refMed: jRefMed, compMed: jCompMed } = useMemo(
    () => buildJitterKde(jitterRows, chStep), [jitterRows, chStep],
  )

  // wafer series는 shape를 우선 사용하고, 없으면 raw에서 추출합니다.
  // group 형식은 ref_{lot}_{slot} / comp_{lot}_{slot}입니다.
  const shapeRef  = waferSeries.filter((s) => s.group.startsWith("ref_") || s.group === "ref")
  const shapeComp = waferSeries.filter((s) => s.group.startsWith("comp_") || s.group === "comp")
  const rawRef    = rawAllSeries.filter((s) => s.group === "ref").map((s) => ({ key: `ref__${s.slot}`,  group: "ref",  slot: s.slot }))
  const rawComp   = rawAllSeries.filter((s) => s.group === "comp").map((s) => ({ key: `comp__${s.slot}`, group: "comp", slot: s.slot }))
  const refBase   = shapeRef.length  > 0 ? shapeRef  : rawRef
  const compBase  = shapeComp.length > 0 ? shapeComp : rawComp

  const refSeries  = refBase.map((s)  => ({ ...s, label: s.key.replace(/^ref_/, "") }))
  const compSeries = compBase.map((s) => ({ ...s, label: s.key.replace(/^comp_/, "") }))

  const visibleShapeData = useMemo(() => filterByXDomain(shapeData, "x", shapeZoom.domain), [shapeData, shapeZoom.domain])

  const shapeYKeys = useMemo(() => [
    ...refSeries.map(s => s.key), ...compSeries.map(s => s.key),
    "q50", ...(compMedKey ? [compMedKey] : []), "lsl",
  ], [refSeries, compSeries, compMedKey])
  const shapeYDomain = useMemo(() => computeYRange(visibleShapeData, shapeYKeys), [visibleShapeData, shapeYKeys])

  // div 기반 pixel→data 변환을 위한 X 범위
  const shapeXRange = useMemo(() => {
    if (!visibleShapeData.length) return [0, 99]
    const xs = visibleShapeData.map(d => d.x).filter(isFinite)
    return xs.length ? [Math.min(...xs), Math.max(...xs)] : [0, 99]
  }, [visibleShapeData])
  const toggleVis   = (k) => setVis((p) => ({ ...p, [k]: p[k] !== false ? false : true }))
  const toggleGroup = (_gk, series) => {
    const allOn = series.every((s) => vis[s.key] !== false)
    setVis((p) => { const n = { ...p }; series.forEach((s) => { n[s.key] = !allOn }); return n })
  }

  const legendGroups = [
    { groupKey: "ref",  label: `REF (${refSeries.length})`,   color: TC.REF_LINE,  series: refSeries },
    { groupKey: "comp", label: `COMP (${compSeries.length})`, color: TC.COMP_LINE, series: compSeries },
  ]
  const shapeExtras = [
    { key: "refMed",  label: "REF med",       colorStyle: { background: TC.TUBE_Q50 } },
    ...(compMedKey ? [{ key: "compMed", label: "COMP med", colorStyle: { background: TC.COMP_MED } }] : []),
    ...(hasTube ? [{ key: "tube", label: "Tube (LSL–USL)", colorStyle: { background: TC.TUBE_FILL, border: `1px solid ${TC.TUBE_STROKE}` } }] : []),
  ]

  // jitter는 wafer별 토글 상태로 group KDE 표시를 제어합니다.
  const showJRef  = refSeries.some((s)  => vis[s.key] !== false)
  const showJComp = compSeries.some((s) => vis[s.key] !== false)

  const hasRaw    = Boolean(traceLineChart?.series?.length || trendRows.length)
  const hasShape  = shapeRows.length > 0
  const hasJitter = jitterRows.length > 0

  const TABS = [
    { id: "raw",    label: "원신호", disabled: !hasRaw },
    { id: "shape",  label: "Shape",  disabled: !hasShape },
    { id: "jitter", label: "Jitter", disabled: !hasJitter },
  ]

  if (detailQuery.isFetching && !detailQuery.data) {
    return (
      <Card className="relative rounded-lg py-0">
        <div className="absolute right-2 top-2 z-10">
          <ChartCloseButton onClick={onClose} label={`${paramName || selectedKey} 차트 닫기`} />
        </div>
        <CardContent className="flex min-h-48 items-center justify-center p-3 text-sm text-muted-foreground">
          <Activity className="mr-2 size-4 animate-pulse" /> 데이터 조회 중...
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="rounded-lg py-0">
      <CardContent className="p-3">
        {/* 헤더 */}
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium">Trace · {paramName || selectedKey}</p>
            <div className="flex gap-1">
              {TABS.map(({ id, label, disabled }) => (
                <button key={id} type="button" disabled={disabled}
                  onClick={() => setActiveTab(id)}
                  className={cn(
                    "rounded px-2 py-0.5 text-xs transition-colors",
                    activeTab === id ? "bg-primary text-primary-foreground" : "border bg-background hover:bg-muted",
                    disabled && "cursor-not-allowed opacity-40",
                  )}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* 줌 초기화 */}
            {activeTab === "shape" && shapeZoom.isZoomed && (
              <button type="button" onClick={shapeZoom.reset}
                className="rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted">
                확대 초기화
              </button>
            )}
            {chSteps.length > 0 && <StepSelector steps={chSteps} value={chStep} onChange={setChStep} />}
            <ChartCloseButton onClick={onClose} label={`${paramName || selectedKey} 차트 닫기`} />
          </div>
        </div>

        {/* ── 원신호 탭 ── */}
        {activeTab === "raw" && (
          !traceLineChart?.series?.length ? (
            <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
              원신호(raw trend) 데이터가 없습니다
            </div>
          ) : (
            <CanvasLineChart chart={traceLineChart} height={240} emptyLabel="원신호(raw trend) 데이터가 없습니다" />
          )
        )}

        {/* ── Shape 탭 ── */}
        {activeTab === "shape" && (
          !shapeData.length ? (
            <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
              {paramName || selectedKey} — shape 데이터가 없습니다
            </div>
          ) : (
            <div className="flex gap-3">
              <div ref={shapeZoom.wrapperRef} className="min-w-0 flex-1" style={{ cursor: "crosshair" }}
                onMouseDown={(e) => shapeZoom.onWrapperMouseDown(e, shapeXRange[0], shapeXRange[1])}
                onMouseMove={(e) => shapeZoom.onWrapperMouseMove(e, shapeXRange[0], shapeXRange[1])}
                onDoubleClick={shapeZoom.reset}>
                <ResponsiveContainer width="100%" height={240}>
                  <ComposedChart data={visibleShapeData} margin={{ top: 4, right: 8, bottom: 22, left: 0 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]}
                      tickFormatter={(v) => String(Math.round(v))}
                      tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                      tickLine={false} axisLine={{ stroke: "var(--border)" }}
                      label={{ value: "normalized phase", position: "insideBottom", offset: -8, fontSize: 10, fill: "var(--muted-foreground)" }} />
                    <YAxis domain={shapeYDomain} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                      tickLine={false} axisLine={{ stroke: "var(--border)" }} width={50}
                      tickFormatter={(v) => formatNumber(v, 3)} />
                    <Tooltip formatter={(v, n) => [formatNumber(v, 3), n]}
                      labelFormatter={(v) => `phase ${v}`} contentStyle={{ fontSize: 11 }} />
                    {vis.tube !== false && hasTube && (
                      <>
                        <Area type="monotone" dataKey="lsl" stackId="tube"
                          fillOpacity={0} stroke="none" dot={false} connectNulls activeDot={false}
                          legendType="none" isAnimationActive={false} />
                        <Area type="monotone" dataKey="band" stackId="tube"
                          fill={TC.TUBE_FILL} fillOpacity={1} stroke={TC.TUBE_STROKE} strokeWidth={0.5}
                          dot={false} connectNulls activeDot={false}
                          legendType="none" isAnimationActive={false} name="Tube" />
                      </>
                    )}
                    {refSeries.map((s) => vis[s.key] !== false && (
                      <Line key={s.key} type="monotone" dataKey={s.key}
                        stroke={TC.REF_LINE} strokeWidth={1}
                        dot={false} connectNulls activeDot={false}
                        legendType="none" isAnimationActive={false} />
                    ))}
                    {compSeries.map((s) => vis[s.key] !== false && (
                      <Line key={s.key} type="monotone" dataKey={s.key}
                        stroke={TC.COMP_LINE} strokeWidth={1}
                        dot={false} connectNulls activeDot={false}
                        legendType="none" isAnimationActive={false} />
                    ))}
                    {vis.refMed !== false && hasTube && (
                      <Line type="monotone" dataKey="q50"
                        stroke={TC.TUBE_Q50} strokeWidth={1.5} strokeDasharray="4 2"
                        dot={false} connectNulls isAnimationActive={false} name="REF med" />
                    )}
                    {vis.compMed !== false && compMedKey && (
                      <Line type="monotone" dataKey={compMedKey}
                        stroke={TC.COMP_MED} strokeWidth={2}
                        dot={false} connectNulls isAnimationActive={false} name="COMP med" />
                    )}
                    {shapeZoom.showArea && (
                      <ReferenceArea x1={shapeZoom.area.x1} x2={shapeZoom.area.x2}
                        fill="rgba(59,130,246,0.15)" stroke="rgba(59,130,246,0.4)" />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <LegendPanel vis={vis} onToggle={toggleVis} onGroupToggle={toggleGroup}
                groups={legendGroups} extras={shapeExtras} />
            </div>
          )
        )}

        {/* ── Jitter 탭 ── */}
        {activeTab === "jitter" && (
          !jitterData.length ? (
            <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
              Jitter 데이터가 없습니다
            </div>
          ) : (
            <div className="flex gap-3">
              <div className="min-w-0 flex-1">
                <ResponsiveContainer width="100%" height={240}>
                  <ComposedChart data={jitterData} margin={{ top: 4, right: 8, bottom: 22, left: 0 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]}
                      tickFormatter={(v) => formatNumber(v, 3)}
                      tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                      tickLine={false} axisLine={{ stroke: "var(--border)" }}
                      label={{ value: "jitter RMS", position: "insideBottom", offset: -8, fontSize: 10, fill: "var(--muted-foreground)" }} />
                    <YAxis tickFormatter={(v) => formatNumber(v, 2)}
                      tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                      tickLine={false} axisLine={{ stroke: "var(--border)" }} width={50}
                      label={{ value: "density", angle: -90, position: "insideLeft", offset: 10, fontSize: 10, fill: "var(--muted-foreground)" }} />
                    <Tooltip formatter={(v, n) => [formatNumber(v, 5), n]}
                      labelFormatter={(v) => `jitter = ${formatNumber(v, 4)}`}
                      contentStyle={{ fontSize: 11 }} />
                    {showJRef && (
                      <Area type="monotone" dataKey="ref"
                        stroke={TC.REF_MED} strokeWidth={2}
                        fill="rgba(37,99,235,0.15)" fillOpacity={1}
                        dot={false} connectNulls isAnimationActive={false} name="REF" />
                    )}
                    {showJComp && (
                      <Area type="monotone" dataKey="comp"
                        stroke={TC.COMP_MED} strokeWidth={2}
                        fill="rgba(234,88,12,0.15)" fillOpacity={1}
                        dot={false} connectNulls isAnimationActive={false} name="COMP" />
                    )}
                    {showJRef && jRefMed != null && (
                      <ReferenceLine x={jRefMed} stroke={TC.REF_MED} strokeWidth={1.5} strokeDasharray="4 3"
                        label={{ value: "ref", fontSize: 9, fill: TC.REF_MED, position: "insideTopRight" }} />
                    )}
                    {showJComp && jCompMed != null && (
                      <ReferenceLine x={jCompMed} stroke={TC.COMP_MED} strokeWidth={1.5} strokeDasharray="4 3"
                        label={{ value: "comp", fontSize: 9, fill: TC.COMP_MED, position: "insideTopLeft" }} />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <LegendPanel vis={vis} onToggle={toggleVis} onGroupToggle={toggleGroup}
                groups={legendGroups} extras={[]} />
            </div>
          )
        )}
      </CardContent>
    </Card>
  )
}

// ── OES: wavelength 선택 시 시계열 + 스펙트럼 탭 ──────────────
function OesWavelengthLineChart({
  category,
  selectedStep,
  selectedWl,
  wavelengths,
  refPmDates,
  spectrumChart,
  onWavelengthChange,
  onClose,
}) {
  const [activeTab, setActiveTab] = useState("시계열")
  const detailQuery = usePmSpiderDetailResult(
    category,
    { step: selectedStep, wavelength: selectedWl },
    refPmDates,
    { step: selectedStep, wavelength: selectedWl },
    {
      includeOesHeatmap: false,
      includeOesSpectrum: activeTab === "스펙트럼",
    },
  )
  const lineChart = detailQuery.data?.oes?.lineChart
  const fallbackSpectrum = detailQuery.data?.oes?.spectrumChart
  const activeSpectrum = spectrumChart?.series?.length ? spectrumChart : fallbackSpectrum
  const TABS = ["시계열", "스펙트럼"]

  return (
    <Card className="rounded-lg py-0">
      <CardContent className="p-3">
        <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold">
              OES · <span className="text-primary">{selectedWl != null ? `${formatWavelengthValue(selectedWl)} nm` : "전체"}</span>
            </p>
            <WavelengthInput
              value={selectedWl}
              wavelengths={wavelengths}
              onSelect={onWavelengthChange}
            />
            <div className="flex gap-1">
              {TABS.map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "rounded px-2 py-0.5 text-[10px] transition-colors",
                    activeTab === tab ? "bg-primary text-primary-foreground" : "border bg-background hover:bg-muted",
                  )}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
          <ChartCloseButton onClick={onClose} label="OES wavelength 차트 닫기" />
        </div>

        {activeTab === "시계열" && (
          detailQuery.isFetching && !lineChart ? (
            <div className="flex min-h-[180px] items-center justify-center rounded-lg border text-sm text-muted-foreground">
              <Waves className="mr-2 size-4 animate-pulse" /> wavelength trajectory 조회 중...
            </div>
          ) : (
            <CanvasLineChart
              chart={lineChart}
              height={180}
              emptyLabel={`${selectedWl} nm trajectory 데이터가 없습니다`}
            />
          )
        )}

        {activeTab === "스펙트럼" && (
          detailQuery.isFetching && !activeSpectrum?.series?.length ? (
            <div className="flex min-h-[180px] items-center justify-center rounded-lg border text-sm text-muted-foreground">
              <Waves className="mr-2 size-4 animate-pulse" /> spectrum 조회 중...
            </div>
          ) : (
            <CanvasLineChart
              chart={activeSpectrum}
              height={180}
              emptyLabel="스펙트럼 데이터가 없습니다"
            />
          )
        )}
      </CardContent>
    </Card>
  )
}

// ── OES intensity 히트맵 (REF / COMP / OOB) ─────────────────
function OesIntensityHeatmaps({
  category,
  heatmap,
  spectrumChart,
  selectedStep,
  refPmDates,
  detailResult,
  queryError,
  isLoading,
  onClose,
}) {
  const [selectedWl, setSelectedWl] = useState(null)
  const wavelengths = Array.isArray(heatmap?.wavelengths) ? heatmap.wavelengths : []

  if (!selectedStep) {
    return (
      <div className="flex min-h-[180px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        랭킹에서 rcp_step을 선택하면 intensity heatmap이 표시됩니다
      </div>
    )
  }
  if (isLoading) {
    return (
      <Card className="relative rounded-lg py-0">
        <div className="absolute right-2 top-2 z-10">
          <ChartCloseButton onClick={onClose} label={`OES step ${selectedStep} 차트 닫기`} />
        </div>
        <CardContent className="flex min-h-[180px] items-center justify-center p-3 text-sm text-muted-foreground">
          <Waves className="mr-2 size-4 animate-pulse" /> OES intensity 조회 중...
        </CardContent>
      </Card>
    )
  }
  if (!heatmap?.width || !heatmap?.height) {
    return (
      <Card className="relative rounded-lg border-dashed py-0">
        <div className="absolute right-2 top-2 z-10">
          <ChartCloseButton onClick={onClose} label={`OES step ${selectedStep} 차트 닫기`} />
        </div>
        <CardContent className="p-3 text-sm text-muted-foreground">
          <OesEmptyDebugPanel
            category={category}
            selectedStep={selectedStep}
            detailResult={detailResult}
            queryError={queryError}
          />
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <Card className="rounded-lg py-0">
        <CardContent className="p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold">
              OES Intensity Heatmap · step <span className="text-primary">{selectedStep}</span>
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <WavelengthInput
                value={selectedWl}
                wavelengths={wavelengths}
                onSelect={setSelectedWl}
              />
              <p className="text-[10px] text-muted-foreground">
                클릭/입력 → wavelength 선택 · x = wavelength · y = time(0→1)
              </p>
              <ChartCloseButton onClick={onClose} label={`OES step ${selectedStep} 차트 닫기`} />
            </div>
          </div>
          <CanvasHeatmap
            heatmap={heatmap}
            selectedWavelength={selectedWl}
            onSelectWavelength={setSelectedWl}
          />
        </CardContent>
      </Card>

      {selectedWl != null && (
        <OesWavelengthLineChart
          category={category}
          selectedStep={selectedStep}
          selectedWl={selectedWl}
          wavelengths={wavelengths}
          refPmDates={refPmDates}
          spectrumChart={spectrumChart}
          onWavelengthChange={setSelectedWl}
          onClose={() => setSelectedWl(null)}
        />
      )}
    </div>
  )
}

// ── OES step 개별 쿼리 + 히트맵 래퍼 ──────────────────────────
function OesStepDetail({ category, selectedStep, refPmDates, onRemove }) {
  const stepCell    = { step: selectedStep }
  const detailQuery = usePmSpiderDetailResult(
    category,
    stepCell,
    refPmDates,
    stepCell,
    {
      includeOesHeatmap: true,
      includeOesSpectrum: false,
      heatmapXBins: 1200,
      limit: 50,
    },
  )
  const heatmap = detailQuery.data?.oes?.heatmap
  const spectrumChart = detailQuery.data?.oes?.spectrumChart

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {category?.label ?? ""} · OES · step {selectedStep}
        </span>
      </div>
      <OesIntensityHeatmaps
        key={selectedStep}
        category={category}
        heatmap={heatmap}
        spectrumChart={spectrumChart}
        selectedStep={selectedStep}
        refPmDates={refPmDates}
        detailResult={detailQuery.data}
        queryError={detailQuery.error}
        isLoading={detailQuery.isFetching && !detailQuery.data}
        onClose={() => onRemove(selectedStep)}
      />
    </div>
  )
}

// ──────────────────────────────────────────────────────────────
// 메인 내보내기
// ──────────────────────────────────────────────────────────────
export function PmSpiderCategoryDashboard({
  categories,
  meta,
  selectedCategoryId,
  onSelectedCategoryChange,
  isFetching,
}) {
  const refPmDates = null

  // selectedCategoryId는 "ag" | "process"이며, legacy "ag-trace"는 "ag"로 처리합니다.
  const activeType = useMemo(() => {
    const raw = selectedCategoryId || "ag"
    if (raw === "ag" || raw === "process") return raw
    return raw.startsWith("process") ? "process" : "ag"
  }, [selectedCategoryId])

  const traceCategory = categories.find((c) => c.type === activeType && c.kind === "trace")
  const oesCategory   = categories.find((c) => c.type === activeType && c.kind === "oes")

  const [selectedTraceKeys, setSelectedTraceKeys] = useState([])
  const [selectedOesSteps,  setSelectedOesSteps]  = useState([])
  const [rankKind,      setRankKind]      = useState("trace")
  const [rankMode,      setRankMode]      = useState("p3")
  const [traceSearch,   setTraceSearch]   = useState("")
  const [oesSearch,     setOesSearch]     = useState("")

  const handleTypeChange = (type) => {
    onSelectedCategoryChange?.(type)
    setSelectedTraceKeys([])
    setSelectedOesSteps([])
    setTraceSearch("")
    setOesSearch("")
  }

  const toggleTraceKey = (key) =>
    setSelectedTraceKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    )
  const toggleOesStep = (step) =>
    setSelectedOesSteps((prev) =>
      prev.includes(step) ? prev.filter((s) => s !== step) : [...prev, step]
    )

  const activeRankCategory = rankKind === "trace" ? traceCategory : oesCategory
  const activeRankKeys = rankKind === "trace" ? selectedTraceKeys : selectedOesSteps
  const activeRankSearch = rankKind === "trace" ? traceSearch : oesSearch
  const activeRankIcon = rankKind === "trace" ? Activity : Waves
  const ActiveRankIcon = activeRankIcon
  const activeRankLabel = rankKind === "trace" ? "TRACE" : "OES"
  const handleRankSelect = rankKind === "trace" ? toggleTraceKey : toggleOesStep
  const handleRankClear = rankKind === "trace" ? () => setSelectedTraceKeys([]) : () => setSelectedOesSteps([])
  const handleRankSearchChange = rankKind === "trace" ? setTraceSearch : setOesSearch
  const rankMetaSelection = activeRankCategory?.payload
    ? { ...activeRankCategory.payload, traceDataSource: rankKind === "oes" ? "oes" : "trace" }
    : {}
  const rankMetaQuery = usePmSpiderMeta(rankMetaSelection)
  const activeRankMeta = rankMetaQuery.data || meta
  const activeRecipeMeta = buildRecipeMeta(activeRankMeta)
  const activeRankMetaSummary = buildRecipeMetaSummary(activeRecipeMeta)
  const activeRankHeaderSummary = `${activeRankLabel} RANKING - ${getRankModeLabel(rankMode)} - ${activeRankMetaSummary}`

  if (!categories.length) {
    return (
      <div className="flex min-h-96 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
        PM Spider category 데이터가 없습니다.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(280px,1fr)_minmax(0,2fr)]">
        <section className="grid min-w-0 content-start gap-3">
          <RankingControlPanel
            activeType={activeType}
            activeKind={rankKind}
            activeMode={rankMode}
            onTypeChange={handleTypeChange}
            onKindChange={setRankKind}
            onModeChange={setRankMode}
          />
          <div className="flex flex-col gap-1.5">
            <div className="flex min-w-0 items-center gap-1.5 px-0.5">
              <ActiveRankIcon className="size-3 shrink-0 text-muted-foreground" />
              <div
                className="min-w-0 overflow-x-auto whitespace-nowrap text-[11px] font-semibold"
                title={activeRankHeaderSummary}
              >
                <span className="uppercase tracking-wider text-muted-foreground">{activeRankLabel} RANKING</span>
                <span className="mx-1.5 text-muted-foreground">-</span>
                <span className="text-foreground">{getRankModeLabel(rankMode)}</span>
                <span className="mx-1.5 text-muted-foreground">-</span>
                <span className="text-muted-foreground">{activeRankMetaSummary}</span>
              </div>
            </div>
            <RankPanel
              panelType={rankMode}
              category={activeRankCategory}
              selectedKeys={activeRankKeys}
              onSelectRow={handleRankSelect}
              onClearAll={handleRankClear}
              search={activeRankSearch}
              onSearchChange={handleRankSearchChange}
            />
          </div>
        </section>

        <section className="min-w-0">
          <div className="flex min-w-0 flex-col gap-3">
            {selectedTraceKeys.map((key) => (
              <TraceDetailWithLegend
                key={key}
                category={traceCategory}
                selectedKey={key}
                refPmDates={refPmDates}
                onClose={() => toggleTraceKey(key)}
              />
            ))}

            {selectedOesSteps.map((step) => (
              <OesStepDetail
                key={step}
                category={oesCategory}
                selectedStep={step}
                refPmDates={refPmDates}
                onRemove={toggleOesStep}
              />
            ))}

            {!selectedTraceKeys.length && !selectedOesSteps.length && (
              <div className="flex min-h-[320px] items-center justify-center rounded-lg border border-dashed bg-card text-sm text-muted-foreground">
                랭킹에서 항목을 선택하면 상세 차트가 표시됩니다
              </div>
            )}
          </div>
        </section>
      </div>

      {isFetching && (
        <div className="pointer-events-none fixed bottom-4 right-4 rounded-md border bg-card px-3 py-2 text-xs text-muted-foreground shadow-sm">
          PM Spider 데이터 갱신 중...
        </div>
      )}
    </div>
  )
}
