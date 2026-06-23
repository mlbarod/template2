import { useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
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

function formatTick(value) {
  if (!Number.isFinite(value)) return "-"
  if (Math.abs(value) >= 1000) return value.toFixed(0)
  if (Math.abs(value) >= 10) return value.toFixed(1)
  return value.toFixed(2)
}

function seriesColor(series, index) {
  const text = `${series?.label ?? ""} ${series?.meta?.phase ?? ""}`.toLowerCase()
  if (text.includes("ref")) return "hsl(217, 91%, 56%)"
  if (text.includes("comp")) return "hsl(24, 95%, 53%)"
  return `hsl(${(index * 47) % 360}, 72%, 45%)`
}

function seriesColorClass(series) {
  const text = `${series?.label ?? ""} ${series?.meta?.phase ?? ""}`.toLowerCase()
  if (text.includes("ref")) return "bg-primary"
  if (text.includes("comp")) return "bg-destructive"
  return "bg-muted-foreground"
}

function getChartDomains(series) {
  const xValues = series.flatMap((item) => finiteValues(item.x ?? []))
  const yValues = series.flatMap((item) => finiteValues(item.y ?? []))
  return {
    xDomain: extent(xValues),
    yDomain: extent(yValues),
  }
}

function useElementSize() {
  const ref = useRef(null)
  const [size, setSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const node = ref.current
    if (!node) return undefined
    const observer = new ResizeObserver(([entry]) => {
      const rect = entry.contentRect
      setSize({ width: rect.width, height: rect.height })
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return [ref, size]
}

export function CanvasLineChart({
  chart,
  height = 240,
  className,
  emptyLabel = "차트 데이터가 없습니다.",
}) {
  const canvasRef = useRef(null)
  const [wrapRef, size] = useElementSize()
  const [hiddenKeys, setHiddenKeys] = useState(() => new Set())
  const heightClass = height <= 180 ? "h-[180px]" : "h-[240px]"
  const series = useMemo(
    () => Array.isArray(chart?.series) ? chart.series : [],
    [chart?.series],
  )
  const visibleSeries = useMemo(
    () => series.filter((item) => !hiddenKeys.has(item.key)),
    [series, hiddenKeys],
  )
  const domains = useMemo(() => {
    const fallback = getChartDomains(visibleSeries)
    const xDomain = Array.isArray(chart?.xDomain) && chart.xDomain.every((value) => value != null)
      ? chart.xDomain.map(Number)
      : fallback.xDomain
    const yDomain = Array.isArray(chart?.yDomain) && chart.yDomain.every((value) => value != null)
      ? chart.yDomain.map(Number)
      : fallback.yDomain
    return { xDomain, yDomain }
  }, [chart, visibleSeries])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !size.width || !size.height) return
    const dpr = window.devicePixelRatio || 1
    const width = Math.max(1, Math.floor(size.width))
    const drawHeight = Math.max(1, Math.floor(size.height))
    canvas.width = Math.floor(width * dpr)
    canvas.height = Math.floor(drawHeight * dpr)
    const ctx = canvas.getContext("2d")
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, width, drawHeight)

    const margin = { top: 10, right: 10, bottom: 24, left: 46 }
    const plotWidth = Math.max(1, width - margin.left - margin.right)
    const plotHeight = Math.max(1, drawHeight - margin.top - margin.bottom)
    const [xMin, xMax] = domains.xDomain
    const [yMin, yMax] = domains.yDomain
    const xSpan = xMax - xMin || 1
    const ySpan = yMax - yMin || 1
    const xScale = (value) => margin.left + ((value - xMin) / xSpan) * plotWidth
    const yScale = (value) => margin.top + plotHeight - ((value - yMin) / ySpan) * plotHeight

    ctx.strokeStyle = "hsl(214, 20%, 88%)"
    ctx.lineWidth = 1
    ctx.font = "10px sans-serif"
    ctx.fillStyle = "hsl(215, 16%, 47%)"
    for (let index = 0; index <= 4; index += 1) {
      const y = margin.top + (plotHeight * index) / 4
      const value = yMax - (ySpan * index) / 4
      ctx.beginPath()
      ctx.moveTo(margin.left, y)
      ctx.lineTo(width - margin.right, y)
      ctx.stroke()
      ctx.fillText(formatTick(value), 4, y + 3)
    }
    for (let index = 0; index <= 4; index += 1) {
      const x = margin.left + (plotWidth * index) / 4
      const value = xMin + (xSpan * index) / 4
      ctx.fillText(formatTick(value), x - 10, drawHeight - 6)
    }

    visibleSeries.forEach((item, index) => {
      const xs = item.x ?? []
      const ys = item.y ?? []
      ctx.strokeStyle = seriesColor(item, index)
      ctx.lineWidth = item?.meta?.phase === "comp" ? 1.4 : 1
      ctx.beginPath()
      let started = false
      for (let pointIndex = 0; pointIndex < xs.length; pointIndex += 1) {
        const x = Number(xs[pointIndex])
        const y = Number(ys[pointIndex])
        if (!Number.isFinite(x) || !Number.isFinite(y)) {
          started = false
          continue
        }
        const px = xScale(x)
        const py = yScale(y)
        if (!started) {
          ctx.moveTo(px, py)
          started = true
        } else {
          ctx.lineTo(px, py)
        }
      }
      ctx.stroke()
    })
  }, [domains, size, visibleSeries])

  const toggleSeries = (key) => {
    setHiddenKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  if (!series.length) {
    return (
      <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        {emptyLabel}
      </div>
    )
  }

  return (
    <div className={cn("grid min-w-0 gap-2", className)}>
      <div ref={wrapRef} className={cn("min-w-0 rounded-md border bg-background", heightClass)}>
        <canvas ref={canvasRef} className="block size-full" />
      </div>
      <div className="flex max-h-16 flex-wrap gap-1 overflow-y-auto">
        {series.map((item) => {
          const muted = hiddenKeys.has(item.key)
          return (
            <Button
              key={item.key}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => toggleSeries(item.key)}
              className={cn("h-6 px-1.5 text-[10px]", muted && "opacity-45")}
              title={item.label}
            >
              <span
                className={cn("size-2 shrink-0 rounded-full", seriesColorClass(item))}
                aria-hidden="true"
              />
              <span className="max-w-28 truncate">{item.label}</span>
            </Button>
          )
        })}
      </div>
      {chart?.downsampled && (
        <p className="text-[10px] text-muted-foreground">
          {chart.sourcePointCount?.toLocaleString()} points → {chart.pointCount?.toLocaleString()} points로 축약 표시
        </p>
      )}
    </div>
  )
}
