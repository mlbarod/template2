import { useMemo, useState } from "react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Activity } from "lucide-react"

import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

import { formatNumber } from "../utils/format"

// ── 시맨틱 색상 (report.py 기준) ─────────────────────────────
export const C = {
  REF_LINE:    "rgba(37,99,235,0.22)",
  REF_MED:     "#2563eb",
  COMP_LINE:   "rgba(234,88,12,0.22)",
  COMP_MED:    "#ea580c",
  TUBE_FILL:   "rgba(37,99,235,0.08)",
  TUBE_STROKE: "#93c5fd",
  TUBE_Q50:    "#60a5fa",
}

// ── KDE helpers ────────────────────────────────────────────────
function _std(arr) {
  if (arr.length < 2) return 0
  const m = arr.reduce((s, v) => s + v, 0) / arr.length
  return Math.sqrt(arr.reduce((s, v) => s + (v - m) ** 2, 0) / (arr.length - 1))
}
function _median(arr) {
  if (!arr.length) return null
  const s = [...arr].sort((a, b) => a - b)
  return s[Math.floor(s.length / 2)]
}
function _gaussKde(data, bw) {
  return (x) =>
    data.reduce((s, v) => s + Math.exp(-0.5 * ((x - v) / bw) ** 2), 0) /
    (data.length * bw * Math.sqrt(2 * Math.PI))
}
function buildKdeData(refJ, compJ, nPts = 80) {
  if (!refJ.length && !compJ.length) return { data: [], refMed: null, compMed: null }
  const all = [...refJ, ...compJ]
  const lo = Math.min(...all), hi = Math.max(...all)
  const range = hi - lo
  if (range < 1e-10) return { data: [], refMed: null, compMed: null }
  const minBw = range * 0.05
  const bwRef  = Math.max(refJ.length  > 1 ? 1.06 * _std(refJ)  * refJ.length  ** -0.2 : 0, minBw)
  const bwComp = Math.max(compJ.length > 1 ? 1.06 * _std(compJ) * compJ.length ** -0.2 : 0, minBw)
  const kRef  = _gaussKde(refJ,  bwRef)
  const kComp = _gaussKde(compJ, bwComp)
  const xs = Array.from({ length: nPts }, (_, i) => lo - range * 0.1 + (range * 1.2 * i) / (nPts - 1))
  return {
    data: xs.map((x) => ({ x, ref: kRef(x), comp: kComp(x) })),
    refMed:  _median(refJ),
    compMed: _median(compJ),
  }
}

// ── Empty placeholder ──────────────────────────────────────────
function Empty({ label }) {
  return (
    <div className="flex min-h-44 flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-sm text-muted-foreground">
      <Activity className="size-5" />
      <span>{label}</span>
    </div>
  )
}

// ── 범례 칩 ────────────────────────────────────────────────────
function LegendChip({ color, label, bold }) {
  return (
    <span className="flex items-center gap-1 text-[10px]">
      <span
        className="inline-block rounded"
        style={{
          width: bold ? 20 : 16,
          height: bold ? 3 : 2,
          background: color,
          verticalAlign: "middle",
        }}
      />
      <span style={{ color }}>{label}</span>
    </span>
  )
}

// ── Raw signal chart ───────────────────────────────────────────
export function buildRawSeries(rows, chStep) {
  const filtered = rows.filter((r) => !chStep || String(r.chStep ?? r.ch_step ?? "") === chStep)
  const seriesMap = new Map()
  for (const r of filtered) {
    const group = r.group ?? "comp"
    const slot  = r.slotNo ?? r.slot_no ?? 0
    const key   = `${group}__${slot}`
    if (!seriesMap.has(key)) seriesMap.set(key, { group, slot, points: [] })
    seriesMap.get(key).points.push({ x: Number(r.stepTime ?? r.step_time ?? 0), y: Number(r.value) })
  }
  const series = Array.from(seriesMap.entries()).map(([key, s]) => ({
    key, group: s.group, slot: s.slot,
    points: s.points.sort((a, b) => a.x - b.x),
  }))
  if (!series.length) return { series: [], data: [] }
  const allX = Array.from(new Set(series.flatMap((s) => s.points.map((p) => p.x)))).sort((a, b) => a - b)
  const data = allX.map((x) => {
    const row = { x }
    for (const s of series) {
      const pt = s.points.find((p) => p.x === x)
      if (pt) row[s.key] = pt.y
    }
    return row
  })
  return { series, data }
}

export function RawChart({ trendRows, chStep }) {
  const { series, data } = useMemo(() => buildRawSeries(trendRows, chStep), [trendRows, chStep])
  if (!data.length) return <Empty label="Raw signal 데이터가 없습니다." />
  const refSeries  = series.filter((s) => s.group === "ref")
  const compSeries = series.filter((s) => s.group === "comp")
  return (
    <div>
      <div className="mb-1.5 flex gap-3">
        <LegendChip color={C.REF_LINE}  label={`ref (${refSeries.length})`} />
        <LegendChip color={C.COMP_LINE} label={`comp (${compSeries.length})`} />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 4, right: 12, bottom: 22, left: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="x" type="number" domain={["auto","auto"]}
            tickFormatter={(v) => formatNumber(v, 1)}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            tickLine={false} axisLine={{ stroke: "var(--border)" }}
            label={{ value: "step time (s)", position: "insideBottom", offset: -8, fontSize: 10, fill: "var(--muted-foreground)" }}
          />
          <YAxis tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            tickLine={false} axisLine={{ stroke: "var(--border)" }} width={50} />
          <Tooltip formatter={(v, n) => [formatNumber(v, 2), n]}
            labelFormatter={(v) => `t = ${formatNumber(v, 2)} s`}
            contentStyle={{ fontSize: 11 }} />
          {refSeries.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key}
              stroke={C.REF_LINE} strokeWidth={1}
              dot={false} connectNulls activeDot={false}
              legendType="none" isAnimationActive={false} />
          ))}
          {compSeries.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key}
              stroke={C.COMP_LINE} strokeWidth={1.5}
              dot={false} connectNulls activeDot={false}
              legendType="none" isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Shape chart (tube band fill + comp median) ─────────────────
export function buildShapeData(rows, chStep) {
  const filtered = rows.filter((r) => !chStep || String(r.chStep ?? r.ch_step ?? "") === chStep)
  const tube = { q50: {}, usl: {}, lsl: {} }
  const wafers = new Map()

  for (const r of filtered) {
    const group = r.group ?? "comp"
    const phase = Number(r.normPhase ?? r.norm_phase ?? 0)
    const val   = Number(r.shape)
    if      (group === "tube_q50") tube.q50[phase] = val
    else if (group === "tube_usl") tube.usl[phase] = val
    else if (group === "tube_lsl") tube.lsl[phase] = val
    else {
      // group 형식: ref_{lot}_{slot} 또는 comp_{lot}_{slot}
      if (!wafers.has(group)) wafers.set(group, { group, pts: new Map() })
      wafers.get(group).pts.set(phase, val)
    }
  }

  const allPhases = new Set([
    ...Object.keys(tube.q50).map(Number),
    ...[...wafers.values()].flatMap((w) => [...w.pts.keys()]),
  ])
  const phases = Array.from(allPhases).sort((a, b) => a - b)
  if (!phases.length) return { data: [], waferSeries: [], compMedKey: null, hasTube: false }

  const hasTube    = Object.keys(tube.lsl).length > 0
  const compWafers = [...wafers.values()].filter((w) => w.group.startsWith("comp_") || w.group === "comp")
  const compMedKey = compWafers.length > 0 ? "comp__med" : null

  const data = phases.map((ph) => {
    const lsl  = tube.lsl[ph] ?? null
    const usl  = tube.usl[ph] ?? null
    const q50  = tube.q50[ph] ?? null
    const band = lsl != null && usl != null ? usl - lsl : null
    const row  = { x: ph, lsl, band, q50 }
    for (const [key, w] of wafers) row[key] = w.pts.get(ph) ?? null
    return row
  })

  // comp group median per phase
  if (compMedKey) {
    data.forEach((d, i) => {
      const vals = compWafers.map((w) => w.pts.get(phases[i])).filter((v) => v != null)
      if (vals.length) {
        const sorted = [...vals].sort((a, b) => a - b)
        d[compMedKey] = sorted[Math.floor(sorted.length / 2)]
      }
    })
  }

  const waferSeries = [...wafers.entries()].map(([key, w]) => ({ key, group: w.group }))
  return { data, waferSeries, compMedKey, hasTube }
}

function _groupClass(group) {
  if (group.startsWith("ref_") || group === "ref") return "ref"
  if (group.startsWith("comp_") || group === "comp") return "comp"
  return "comp"
}

function ShapeChart({ shapeRows, chStep }) {
  const { data, waferSeries, compMedKey, hasTube } = useMemo(
    () => buildShapeData(shapeRows, chStep),
    [shapeRows, chStep],
  )
  if (!data.length) return <Empty label="Processed shape 데이터가 없습니다." />
  const refSeries  = waferSeries.filter((s) => _groupClass(s.group) === "ref")
  const compSeries = waferSeries.filter((s) => _groupClass(s.group) === "comp")
  return (
    <div>
      <div className="mb-1.5 flex flex-wrap gap-3">
        {hasTube && (
          <>
            <span className="flex items-center gap-1 text-[10px]">
              <span className="inline-block h-3 w-5 rounded-sm border"
                style={{ background: C.TUBE_FILL, borderColor: C.TUBE_STROKE }} />
              <span className="text-muted-foreground">ref tube</span>
            </span>
            <span className="flex items-center gap-1 text-[10px]">
              <span className="inline-block w-4 border-t border-dashed" style={{ borderColor: C.TUBE_Q50 }} />
              <span className="text-muted-foreground">ref q50</span>
            </span>
          </>
        )}
        <LegendChip color={C.REF_LINE}  label={`ref (${refSeries.length})`} />
        <LegendChip color={C.COMP_LINE} label={`comp (${compSeries.length})`} />
        {compMedKey && <LegendChip color={C.COMP_MED} label="comp median" bold />}
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={data} margin={{ top: 4, right: 12, bottom: 22, left: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="x" type="number" domain={[0, 99]}
            tickFormatter={(v) => String(Math.round(v))}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            tickLine={false} axisLine={{ stroke: "var(--border)" }}
            label={{ value: "normalized phase", position: "insideBottom", offset: -8, fontSize: 10, fill: "var(--muted-foreground)" }}
          />
          <YAxis tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            tickLine={false} axisLine={{ stroke: "var(--border)" }} width={50} />
          <Tooltip formatter={(v, n) => [formatNumber(v, 3), n]}
            labelFormatter={(v) => `phase ${v}`} contentStyle={{ fontSize: 11 }} />

          {/* ── tube band: stacked areas (lsl 투명 base → band 채우기) ── */}
          {hasTube && (
            <>
              <Area type="monotone" dataKey="lsl" stackId="tube"
                fillOpacity={0} stroke="none"
                dot={false} connectNulls activeDot={false}
                legendType="none" isAnimationActive={false} />
              <Area type="monotone" dataKey="band" stackId="tube"
                fill={C.TUBE_FILL} fillOpacity={1}
                stroke={C.TUBE_STROKE} strokeWidth={0.8} strokeDasharray="3 2"
                dot={false} connectNulls activeDot={false}
                legendType="none" isAnimationActive={false} />
              <Line type="monotone" dataKey="q50"
                stroke={C.TUBE_Q50} strokeWidth={1.5} strokeDasharray="5 3"
                dot={false} connectNulls activeDot={false}
                legendType="none" isAnimationActive={false} />
            </>
          )}

          {/* ref wafer shapes (뒤) */}
          {refSeries.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key}
              stroke={C.REF_LINE} strokeWidth={0.8}
              dot={false} connectNulls activeDot={false}
              legendType="none" isAnimationActive={false} />
          ))}

          {/* comp wafer shapes */}
          {compSeries.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key}
              stroke={C.COMP_LINE} strokeWidth={0.8}
              dot={false} connectNulls activeDot={false}
              legendType="none" isAnimationActive={false} />
          ))}

          {/* comp group median (굵은 선) */}
          {compMedKey && (
            <Line type="monotone" dataKey={compMedKey}
              stroke={C.COMP_MED} strokeWidth={2.5}
              dot={false} connectNulls activeDot={false}
              legendType="none" isAnimationActive={false} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Jitter KDE 분포 차트 ───────────────────────────────────────
export function buildJitterKde(jitterRows, chStep) {
  const filtered = jitterRows.filter(
    (r) => !chStep || String(r.chStep ?? r.ch_step ?? "") === chStep,
  )
  const seen = new Map()
  for (const r of filtered) {
    const group  = r.group ?? "comp"
    const slot   = r.slotNo ?? r.slot_no ?? 0
    const lot    = r.lotId  ?? r.lot_id  ?? ""
    const key    = `${group}__${lot}__${slot}`
    const jitter = Number(r.jitterRms ?? r.jitter_rms ?? 0)
    if (!seen.has(key) || jitter > 0) seen.set(key, { group, jitter })
  }
  const refJ  = [...seen.values()].filter((d) => d.group === "ref").map((d) => d.jitter)
  const compJ = [...seen.values()].filter((d) => d.group === "comp").map((d) => d.jitter)
  return buildKdeData(refJ, compJ)
}

export function JitterChart({ jitterRows, chStep }) {
  const { data, refMed, compMed } = useMemo(
    () => buildJitterKde(jitterRows, chStep),
    [jitterRows, chStep],
  )
  if (!data.length) return <Empty label="Jitter 데이터가 없습니다." />
  return (
    <div>
      <div className="mb-1.5 flex gap-3">
        <span className="flex items-center gap-1 text-[10px]" style={{ color: C.REF_MED }}>
          <span className="inline-block h-2.5 w-4 rounded-sm"
            style={{ background: "rgba(37,99,235,0.15)", border: `1px solid ${C.REF_MED}` }} />
          ref{refMed != null ? ` (med: ${formatNumber(refMed, 4)})` : ""}
        </span>
        <span className="flex items-center gap-1 text-[10px]" style={{ color: C.COMP_MED }}>
          <span className="inline-block h-2.5 w-4 rounded-sm"
            style={{ background: "rgba(234,88,12,0.15)", border: `1px solid ${C.COMP_MED}` }} />
          comp{compMed != null ? ` (med: ${formatNumber(compMed, 4)})` : ""}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ top: 4, right: 12, bottom: 22, left: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="x" type="number" domain={["auto", "auto"]}
            tickFormatter={(v) => formatNumber(v, 3)}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            tickLine={false} axisLine={{ stroke: "var(--border)" }}
            label={{ value: "jitter RMS", position: "insideBottom", offset: -8, fontSize: 10, fill: "var(--muted-foreground)" }}
          />
          <YAxis tickFormatter={(v) => formatNumber(v, 2)}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            tickLine={false} axisLine={{ stroke: "var(--border)" }} width={50}
            label={{ value: "density", angle: -90, position: "insideLeft", offset: 10, fontSize: 10, fill: "var(--muted-foreground)" }}
          />
          <Tooltip formatter={(v, n) => [formatNumber(v, 5), n]}
            labelFormatter={(v) => `jitter = ${formatNumber(v, 4)}`}
            contentStyle={{ fontSize: 11 }} />
          <Area type="monotone" dataKey="ref"
            stroke={C.REF_MED} strokeWidth={2}
            fill="rgba(37,99,235,0.15)" fillOpacity={1}
            dot={false} connectNulls isAnimationActive={false} name="ref" />
          <Area type="monotone" dataKey="comp"
            stroke={C.COMP_MED} strokeWidth={2}
            fill="rgba(234,88,12,0.15)" fillOpacity={1}
            dot={false} connectNulls isAnimationActive={false} name="comp" />
          {refMed != null && (
            <ReferenceLine x={refMed} stroke={C.REF_MED} strokeWidth={1.5} strokeDasharray="4 3"
              label={{ value: "ref", fontSize: 9, fill: C.REF_MED, position: "insideTopRight" }} />
          )}
          {compMed != null && (
            <ReferenceLine x={compMed} stroke={C.COMP_MED} strokeWidth={1.5} strokeDasharray="4 3"
              label={{ value: "comp", fontSize: 9, fill: C.COMP_MED, position: "insideTopLeft" }} />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── OES trajectory chart ───────────────────────────────────────
function buildTrajSeries(trajectoryRows) {
  const seriesMap = new Map()
  for (const r of trajectoryRows) {
    const group = r.group ?? "comp"
    const slot  = r.slotNo ?? r.slot_no ?? 0
    const key   = `${group}__${slot}`
    if (!seriesMap.has(key)) seriesMap.set(key, { group, slot, points: [] })
    seriesMap.get(key).points.push({
      x: Number(r.trajPhase ?? r.traj_phase ?? 0),
      y: Number(r.value ?? r.intensity ?? 0),
    })
  }
  const series = Array.from(seriesMap.entries()).map(([key, s]) => ({
    key, group: s.group,
    points: s.points.sort((a, b) => a.x - b.x),
  }))
  if (!series.length) return { series: [], data: [] }
  const allX = Array.from(new Set(series.flatMap((s) => s.points.map((p) => p.x)))).sort((a, b) => a - b)
  const data = allX.map((x) => {
    const row = { x }
    for (const s of series) {
      const pt = s.points.find((p) => p.x === x)
      if (pt) row[s.key] = pt.y
    }
    return row
  })
  return { series, data }
}

export function OesTrajectoryChart({ trajectoryRows = [], title = "OES Trajectory", isLoading = false }) {
  const { series, data } = useMemo(() => buildTrajSeries(trajectoryRows), [trajectoryRows])
  if (isLoading) return <Empty label="OES trajectory 조회 중..." />
  if (!data.length) return <Empty label="클릭한 셀의 trajectory 데이터가 없습니다." />
  const refSeries  = series.filter((s) => s.group === "ref")
  const compSeries = series.filter((s) => s.group === "comp")
  return (
    <div>
      <div className="mb-1 flex items-center gap-3">
        <p className="text-xs font-medium text-muted-foreground">{title}</p>
        <div className="flex gap-2">
          {refSeries.length  > 0 && <LegendChip color={C.REF_LINE}  label={`ref (${refSeries.length})`}  />}
          {compSeries.length > 0 && <LegendChip color={C.COMP_LINE} label={`comp (${compSeries.length})`} />}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 4, right: 12, bottom: 22, left: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="x" type="number" domain={[0, 99]}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            tickLine={false} axisLine={{ stroke: "var(--border)" }}
            label={{ value: "phase", position: "insideBottom", offset: -8, fontSize: 10, fill: "var(--muted-foreground)" }}
          />
          <YAxis tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            tickLine={false} axisLine={{ stroke: "var(--border)" }} width={50}
            label={{ value: "intensity", angle: -90, position: "insideLeft", offset: 10, fontSize: 10, fill: "var(--muted-foreground)" }}
          />
          <Tooltip formatter={(v, n) => [formatNumber(v, 4), n]}
            labelFormatter={(v) => `phase ${v}`} contentStyle={{ fontSize: 11 }} />
          {refSeries.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key}
              stroke={C.REF_LINE} strokeWidth={1}
              dot={false} connectNulls activeDot={false}
              legendType="none" isAnimationActive={false} />
          ))}
          {compSeries.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key}
              stroke={C.COMP_LINE} strokeWidth={1.5}
              dot={false} connectNulls activeDot={false}
              legendType="none" isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── ch_step 필터 버튼 ──────────────────────────────────────────
export function StepSelector({ steps, value, onChange }) {
  if (!steps.length) return null
  return (
    <div className="flex flex-wrap gap-1">
      <button type="button" onClick={() => onChange("")}
        className={`rounded px-2 py-0.5 text-xs transition-colors ${!value ? "bg-primary text-primary-foreground" : "border bg-background hover:bg-muted"}`}>
        All
      </button>
      {steps.map((s) => (
        <button key={s} type="button" onClick={() => onChange(s)}
          className={`rounded px-2 py-0.5 text-xs transition-colors ${value === s ? "bg-primary text-primary-foreground" : "border bg-background hover:bg-muted"}`}>
          {s}
        </button>
      ))}
    </div>
  )
}

// ── Main export ────────────────────────────────────────────────
export function TraceSignalPanel({
  trendRows = [],
  shapeRows = [],
  jitterRows = [],
  paramName = "",
  isLoading = false,
  defaultTab = "raw",
  defaultStep = "",
}) {
  const [activeTab, setActiveTab] = useState(defaultTab)
  const [chStep, setChStep] = useState(defaultStep)

  const chSteps = useMemo(() => {
    const all = new Set([
      ...trendRows.map((r) => String(r.chStep ?? r.ch_step ?? "")).filter(Boolean),
      ...shapeRows.map((r) => String(r.chStep ?? r.ch_step ?? "")).filter(Boolean),
      ...jitterRows.map((r) => String(r.chStep ?? r.ch_step ?? "")).filter(Boolean),
    ])
    return Array.from(all).sort()
  }, [trendRows, shapeRows, jitterRows])

  if (isLoading) {
    return (
      <Card className="rounded-lg py-0">
        <CardContent className="flex min-h-48 items-center justify-center p-3 text-sm text-muted-foreground">
          <Activity className="mr-2 size-4 animate-pulse" /> 데이터 조회 중...
        </CardContent>
      </Card>
    )
  }

  const hasRaw    = trendRows.length > 0
  const hasShape  = shapeRows.length > 0
  const hasJitter = jitterRows.length > 0
  const header    = paramName ? `Trace · ${paramName}` : "Trace signal"

  if (!hasRaw && !hasShape) {
    return (
      <Card className="rounded-lg py-0">
        <CardContent className="p-3">
          <Empty label={`${header} — 파라미터를 선택하세요.`} />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="rounded-lg py-0">
      <CardHeader className="border-b bg-muted/50 px-3 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium">{header}</p>
          <StepSelector steps={chSteps} value={chStep} onChange={setChStep} />
        </div>
      </CardHeader>
      <CardContent className="p-3">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-3 h-7">
            <TabsTrigger value="raw"    className="h-6 px-3 text-xs" disabled={!hasRaw}>Raw signal</TabsTrigger>
            <TabsTrigger value="shape"  className="h-6 px-3 text-xs" disabled={!hasShape}>Processed shape</TabsTrigger>
            <TabsTrigger value="jitter" className="h-6 px-3 text-xs" disabled={!hasJitter}>Jitter</TabsTrigger>
          </TabsList>
          <TabsContent value="raw">
            <RawChart    trendRows={trendRows} chStep={chStep} />
          </TabsContent>
          <TabsContent value="shape">
            <ShapeChart  shapeRows={shapeRows} chStep={chStep} />
          </TabsContent>
          <TabsContent value="jitter">
            <JitterChart jitterRows={jitterRows} chStep={chStep} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
