import { useMemo, useState } from "react"
import { Waves } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { formatNumber } from "../utils/format"

// delta → CSS hsl color (blue=0 → yellow=1 → red=3+)
function deltaColor(delta, maxDelta = 3) {
  const t = Math.min(1, Math.max(0, delta / maxDelta))
  const h = Math.round(240 - t * 240)
  const s = 75
  const l = Math.round(55 - t * 25)
  return `hsl(${h},${s}%,${l}%)`
}

function buildGrid(summaryRows) {
  const rows = Array.isArray(summaryRows) ? summaryRows : []
  const stepSet = new Set()
  const wlSet = new Set()
  const cellMap = new Map()

  for (const r of rows) {
    const step = r.step || r.itemName || ""
    const wl = Number(r.wavelength)
    const delta = Number(r.deltaSpectrum ?? r.delta_spectrum ?? 0)
    if (!step || !Number.isFinite(wl)) continue
    stepSet.add(step)
    wlSet.add(wl)
    const key = `${step}::${wl}`
    const prev = cellMap.get(key)
    if (!prev || delta > prev.delta) {
      cellMap.set(key, { step, wavelength: wl, delta, score: Number(r.score ?? 1) })
    }
  }

  const steps = Array.from(stepSet).sort()
  const wavelengths = Array.from(wlSet).sort((a, b) => a - b)
  const maxDelta = Math.max(0.1, ...Array.from(cellMap.values()).map((c) => c.delta))

  return { steps, wavelengths, cellMap, maxDelta }
}

// Tooltip shown on hover
function CellTooltip({ cell, style }) {
  if (!cell) return null
  return (
    <div
      className="pointer-events-none fixed z-50 rounded-md border bg-popover px-2.5 py-1.5 text-xs shadow-md"
      style={style}
    >
      <p className="font-semibold">
        {cell.step} / {formatNumber(cell.wavelength, 1)} nm
      </p>
      <p className="text-muted-foreground">
        Δspectrum: <span className="font-mono text-foreground">{formatNumber(cell.delta, 3)}</span>
      </p>
      <p className="text-muted-foreground">
        score: <span className="font-mono text-foreground">{formatNumber(cell.score, 3)}</span>
      </p>
    </div>
  )
}

export function OesHeatmap({
  title = "OES Heatmap",
  summaryRows,
  selectedStep,
  selectedWavelength,
  onCellClick,
  isLoading = false,
}) {
  const [tooltip, setTooltip] = useState({ cell: null, x: 0, y: 0 })
  const grid = useMemo(() => buildGrid(summaryRows), [summaryRows])

  if (isLoading) {
    return (
      <Card className="grid min-h-0 grid-rows-[auto,1fr] rounded-lg py-0">
        <CardHeader className="border-b bg-muted/50 px-3 py-2">
          <CardTitle className="text-sm">{title}</CardTitle>
        </CardHeader>
        <CardContent className="flex min-h-48 items-center justify-center p-3">
          <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
            <Waves className="size-6 animate-pulse" />
            <span>OES heatmap 데이터 조회 중...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!grid.steps.length) {
    return (
      <Card className="grid min-h-0 grid-rows-[auto,1fr] rounded-lg py-0">
        <CardHeader className="border-b bg-muted/50 px-3 py-2">
          <CardTitle className="text-sm">{title}</CardTitle>
        </CardHeader>
        <CardContent className="flex min-h-48 items-center justify-center p-3">
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            <Waves className="size-6" />
            <span>OES heatmap 데이터가 없습니다.</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Bin wavelengths every 10 nm for legible x-axis ticks
  const wlTickStep = grid.wavelengths.length > 60 ? 50 : grid.wavelengths.length > 30 ? 20 : 10
  const tickWls = grid.wavelengths.filter((wl) => Math.round(wl) % wlTickStep === 0)

  return (
    <Card className="grid min-h-0 grid-rows-[auto,1fr] rounded-lg py-0">
      <CardHeader className="border-b bg-muted/50 px-3 py-2">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 overflow-auto p-3">
        <div className="w-full min-w-[480px]">
          {/* Color scale legend */}
          <div className="mb-2 flex items-center gap-2 text-[10px] text-muted-foreground">
            <span>Δ 0</span>
            <div
              className="h-2.5 flex-1 rounded"
              style={{
                background: `linear-gradient(to right, ${deltaColor(0, grid.maxDelta)}, ${deltaColor(grid.maxDelta * 0.5, grid.maxDelta)}, ${deltaColor(grid.maxDelta, grid.maxDelta)})`,
              }}
            />
            <span>Δ {formatNumber(grid.maxDelta, 2)}</span>
          </div>

          {/* Grid */}
          <div className="flex flex-col gap-px">
            {grid.steps.map((step) => (
              <div key={step} className="flex items-center gap-px">
                {/* Step label */}
                <span className="w-10 shrink-0 text-right text-[10px] font-medium text-muted-foreground pr-1">
                  {step}
                </span>
                {/* Cells */}
                <div className="flex flex-1 gap-px">
                  {grid.wavelengths.map((wl) => {
                    const cell = grid.cellMap.get(`${step}::${wl}`)
                    const delta = cell?.delta ?? 0
                    const isSelected = step === selectedStep && wl === selectedWavelength
                    return (
                      <button
                        key={wl}
                        type="button"
                        title={`${step} / ${wl}nm`}
                        className={cn(
                          "h-5 flex-1 cursor-pointer rounded-[1px] transition-transform hover:scale-110 hover:z-10",
                          isSelected && "ring-2 ring-primary ring-offset-1 z-10",
                        )}
                        style={{ backgroundColor: cell ? deltaColor(delta, grid.maxDelta) : "var(--muted)" }}
                        onClick={() => onCellClick?.({ step, wavelength: wl })}
                        onMouseEnter={(e) =>
                          setTooltip({ cell: cell ?? { step, wavelength: wl, delta: 0, score: 1 }, x: e.clientX + 10, y: e.clientY + 10 })
                        }
                        onMouseLeave={() => setTooltip({ cell: null, x: 0, y: 0 })}
                      />
                    )
                  })}
                </div>
              </div>
            ))}

            {/* Wavelength axis labels */}
            <div className="flex items-center gap-px">
              <span className="w-10 shrink-0" />
              <div className="relative flex-1">
                <div className="flex">
                  {grid.wavelengths.map((wl) => (
                    <div key={wl} className="flex-1 text-center">
                      {tickWls.includes(wl) && (
                        <span className="text-[9px] text-muted-foreground">{Math.round(wl)}</span>
                      )}
                    </div>
                  ))}
                </div>
                <p className="mt-0.5 text-center text-[10px] text-muted-foreground">Wavelength (nm)</p>
              </div>
            </div>
          </div>
        </div>

        {/* Tooltip */}
        <CellTooltip cell={tooltip.cell} style={{ left: tooltip.x, top: tooltip.y }} />
      </CardContent>
    </Card>
  )
}
