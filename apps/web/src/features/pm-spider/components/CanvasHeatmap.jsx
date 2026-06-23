import { useEffect, useMemo, useRef } from "react"

import { cn } from "@/lib/utils"

function finiteValues(values) {
  return values.filter((value) => Number.isFinite(Number(value))).map(Number)
}

function extent(values, fallback = [0, 1]) {
  const clean = finiteValues(values)
  if (!clean.length) return fallback
  const min = Math.min(...clean)
  const max = Math.max(...clean)
  if (min === max) return [min - 1, max + 1]
  return [min, max]
}

function hslToRgb(h, s, l) {
  const sat = s / 100
  const light = l / 100
  const c = (1 - Math.abs(2 * light - 1)) * sat
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = light - c / 2
  let r = 0
  let g = 0
  let b = 0
  if (h < 60) [r, g, b] = [c, x, 0]
  else if (h < 120) [r, g, b] = [x, c, 0]
  else if (h < 180) [r, g, b] = [0, c, x]
  else if (h < 240) [r, g, b] = [0, x, c]
  else if (h < 300) [r, g, b] = [x, 0, c]
  else [r, g, b] = [c, 0, x]
  return [
    Math.round((r + m) * 255),
    Math.round((g + m) * 255),
    Math.round((b + m) * 255),
  ]
}

function intensityRgb(value, min, max) {
  if (!Number.isFinite(value)) return [9, 9, 28]
  const span = max - min || 1
  const t = Math.max(0, Math.min(1, (value - min) / span))
  return hslToRgb(Math.round(270 - t * 210), Math.round(70 + t * 20), Math.round(15 + t * 60))
}

function divergingRgb(value, absMax) {
  if (!Number.isFinite(value)) return [224, 224, 224]
  const t = Math.max(-1, Math.min(1, value / (absMax || 1)))
  if (t >= 0) return hslToRgb(0, Math.round(t * 85), Math.round(95 - t * 45))
  return hslToRgb(240, Math.round(-t * 80), Math.round(95 + t * 40))
}

function HeatmapCanvas({ title, values, width, height, wavelengths, selectedWavelength, onSelectWavelength, colorMode }) {
  const canvasRef = useRef(null)
  const domain = useMemo(() => extent(values), [values])
  const absMax = useMemo(() => Math.max(0.01, ...finiteValues(values).map((value) => Math.abs(value))), [values])
  const firstWavelength = Math.round(Number(wavelengths?.[0]))
  const lastWavelength = Math.round(Number(wavelengths?.[wavelengths.length - 1]))

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !width || !height) return
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext("2d")
    const image = ctx.createImageData(width, height)
    for (let index = 0; index < width * height; index += 1) {
      const rawValue = values?.[index]
      const value = rawValue == null ? NaN : Number(rawValue)
      const [r, g, b] = colorMode === "diverging"
        ? divergingRgb(value, absMax)
        : intensityRgb(value, domain[0], domain[1])
      const offset = index * 4
      image.data[offset] = r
      image.data[offset + 1] = g
      image.data[offset + 2] = b
      image.data[offset + 3] = 255
    }
    ctx.putImageData(image, 0, 0)
    if (selectedWavelength != null && wavelengths?.length) {
      let nearestIndex = 0
      let nearestDistance = Infinity
      wavelengths.forEach((wavelength, index) => {
        const distance = Math.abs(Number(wavelength) - Number(selectedWavelength))
        if (distance < nearestDistance) {
          nearestDistance = distance
          nearestIndex = index
        }
      })
      ctx.strokeStyle = "rgba(255,255,255,0.9)"
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(nearestIndex + 0.5, 0)
      ctx.lineTo(nearestIndex + 0.5, height)
      ctx.stroke()
    }
  }, [absMax, colorMode, domain, height, selectedWavelength, values, wavelengths, width])

  const selectAt = (event) => {
    if (!wavelengths?.length) return
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
    const index = Math.max(0, Math.min(wavelengths.length - 1, Math.floor(ratio * wavelengths.length)))
    onSelectWavelength?.(wavelengths[index])
  }

  return (
    <div className="grid min-w-0 gap-1">
      <p className="text-center text-[10px] font-semibold text-muted-foreground">{title}</p>
      <button
        type="button"
        onClick={selectAt}
        className="block h-36 min-w-0 overflow-hidden rounded border bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`${title} wavelength 선택`}
      >
        <canvas ref={canvasRef} className="block size-full" />
      </button>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center text-[9px] text-muted-foreground">
        <span>{Number.isFinite(firstWavelength) ? `${firstWavelength} nm` : "-"}</span>
        <span>wavelength</span>
        <span className="text-right">{Number.isFinite(lastWavelength) ? `${lastWavelength} nm` : "-"}</span>
      </div>
    </div>
  )
}

export function CanvasHeatmap({ heatmap, selectedWavelength, onSelectWavelength, className }) {
  const width = Number(heatmap?.width || 0)
  const height = Number(heatmap?.height || 0)
  const wavelengths = Array.isArray(heatmap?.wavelengths) ? heatmap.wavelengths : []
  if (!width || !height || !wavelengths.length) {
    return (
      <div className="flex min-h-[180px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        Heatmap 데이터가 없습니다
      </div>
    )
  }

  return (
    <div className={cn("grid min-w-0 gap-3", className)}>
      <div className="grid min-w-0 gap-3 lg:grid-cols-3">
        <HeatmapCanvas
          title="REF"
          values={heatmap.ref ?? []}
          width={width}
          height={height}
          wavelengths={wavelengths}
          selectedWavelength={selectedWavelength}
          onSelectWavelength={onSelectWavelength}
        />
        <HeatmapCanvas
          title="COMP"
          values={heatmap.comp ?? []}
          width={width}
          height={height}
          wavelengths={wavelengths}
          selectedWavelength={selectedWavelength}
          onSelectWavelength={onSelectWavelength}
        />
        <HeatmapCanvas
          title="OOB (C-R)"
          values={heatmap.oob ?? []}
          width={width}
          height={height}
          wavelengths={wavelengths}
          selectedWavelength={selectedWavelength}
          onSelectWavelength={onSelectWavelength}
          colorMode="diverging"
        />
      </div>
      {heatmap?.sourcePointCount ? (
        <p className="text-[10px] text-muted-foreground">
          {Number(heatmap.sourcePointCount).toLocaleString()} points → {width.toLocaleString()} x {height.toLocaleString()} matrix
        </p>
      ) : null}
    </div>
  )
}
