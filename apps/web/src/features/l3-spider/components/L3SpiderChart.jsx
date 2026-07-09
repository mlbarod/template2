import { useMemo, useRef, useState } from "react"
import { BarChart3, Camera, Download, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import TrellisChart from "./TrellisChart"

function downloadCSV(rows) {
  if (!rows.length) return
  const headers = Object.keys(rows[0])
  const escape = (v) => {
    if (v == null) return ''
    const s = String(v)
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s
  }
  const csv = [headers.join(','), ...rows.map(r => headers.map(h => escape(r[h])).join(','))].join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `l3_spider_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export function L3SpiderChart({
  rows,
  isLoading,
  error,
  groupBy,
  xAxisMode,
  onXAxisModeChange,
  scrollContainerRef,
  outerScrollTop,
  outerViewportHeight,
}) {
  const trellisRef = useRef(null)
  const [lassoMode, setLassoMode] = useState('off')
  const [lassoShape, setLassoShape] = useState('box')
  const [eqcTimeTrellisMode, setEqcTimeTrellisMode] = useState('step')
  const [highlightFirst, setHighlightFirst] = useState(false)
  const [isCapturing, setIsCapturing] = useState(false)
  const [captureProgress, setCaptureProgress] = useState(0)

  const trellisLabel = groupBy === 'bin' ? 'Bin' : 'EQPCH'

  const trellisCount = useMemo(() => {
    if (!rows.length) return 0
    if (groupBy === 'bin') return new Set(rows.map(r => r.binName)).size
    if (groupBy === 'eqc') return new Set(rows.map(r => r.eqc)).size
    return new Set(rows.map(r => `${r.stepSeq}|||${r.binName}`)).size
  }, [rows, groupBy])

  const handleCaptureAll = async () => {
    if (!trellisRef.current || isCapturing || !rows.length) return
    setIsCapturing(true)
    setCaptureProgress(0)
    try {
      await trellisRef.current.captureAll((done, total) => {
        setCaptureProgress(total > 0 ? Math.round((done / total) * 100) : 0)
      })
    } finally {
      setIsCapturing(false)
      setCaptureProgress(0)
    }
  }

  return (
    <Card className="grid min-w-0 gap-0 overflow-hidden rounded-lg py-0">
      <CardHeader className="border-b bg-muted/50 px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-sm">Scatter Plot — Trellis by {trellisLabel}</CardTitle>
            {rows.length > 0 && (
              <>
                <Badge variant="outline">{rows.length.toLocaleString()} rows</Badge>
                <Badge variant="secondary">{trellisCount} {trellisLabel}</Badge>
              </>
            )}
            <div className="flex items-center gap-3 pl-1">
              {xAxisMode === 'eqc_tkin_time' ? (
                <>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <span className="text-[10px] font-bold leading-none" style={{ color: '#dc2626' }}>★</span>
                    High Risk
                  </span>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <span className="inline-block size-2.5 rounded-full" style={{ background: '#ea580c' }} />
                    Warning
                  </span>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <span className="inline-block size-2.5 rounded-full border-2" style={{ borderColor: '#4b5563' }} />
                    Normal
                  </span>
                </>
              ) : (
                <>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <span className="inline-block size-2.5 rounded-full" style={{ background: '#dc2626' }} />
                    High Risk
                  </span>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <span className="inline-block size-2.5 rounded-full border-2" style={{ borderColor: '#ea580c' }} />
                    Warning
                  </span>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <span className="inline-block size-2.5 rounded-full border-2" style={{ borderColor: '#4b5563' }} />
                    Normal
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">Chart Order</span>
              <div className="flex items-center gap-1 rounded-md border bg-muted/40 p-0.5">
                <Button
                  type="button"
                  variant={!highlightFirst ? 'default' : 'ghost'}
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setHighlightFirst(false)}
                >
                  기본 순서
                </Button>
                <Button
                  type="button"
                  variant={highlightFirst ? 'default' : 'ghost'}
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setHighlightFirst(true)}
                >
                  High Risk 먼저
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">X Axis</span>
              <div className="flex items-center gap-1 rounded-md border bg-muted/40 p-0.5">
                <Button
                  type="button"
                  variant={xAxisMode === 'tkin_time' ? 'default' : 'ghost'}
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => onXAxisModeChange('tkin_time')}
                >
                  Time
                </Button>
                <Button
                  type="button"
                  variant={xAxisMode === 'tkin_time_wafer_id' ? 'default' : 'ghost'}
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => onXAxisModeChange('tkin_time_wafer_id')}
                >
                  Time·Wafer
                </Button>
                <Button
                  type="button"
                  variant={xAxisMode === 'eqc_tkin_time' ? 'default' : 'ghost'}
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => onXAxisModeChange('eqc_tkin_time')}
                >
                  EQPCH·Time
                </Button>
              </div>
            </div>
            {xAxisMode === 'eqc_tkin_time' && (
              <div className="flex items-center gap-1 rounded-md border bg-muted/40 p-0.5">
                <Button
                  type="button"
                  variant={eqcTimeTrellisMode === 'step' ? 'default' : 'ghost'}
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setEqcTimeTrellisMode('step')}
                >
                  by Step
                </Button>
                <Button
                  type="button"
                  variant={eqcTimeTrellisMode === 'step_ppid' ? 'default' : 'ghost'}
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setEqcTimeTrellisMode('step_ppid')}
                >
                  by Step+PPID
                </Button>
              </div>
            )}
            <div className="h-5 w-px bg-border" />
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 gap-1.5 px-2.5 text-xs"
              onClick={() => downloadCSV(rows)}
              disabled={!rows.length}
            >
              <Download className="size-3.5" />
              Raw Data
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 gap-1.5 px-2.5 text-xs"
              onClick={handleCaptureAll}
              disabled={isCapturing || !rows.length}
            >
              {isCapturing ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" />
                  {captureProgress}%
                </>
              ) : (
                <>
                  <Camera className="size-3.5" />
                  All Charts
                </>
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="flex h-full min-h-64 items-center justify-center text-sm text-muted-foreground">
            차트 데이터를 불러오는 중입니다.
          </div>
        ) : error ? (
          <div className="flex h-full min-h-64 items-center justify-center text-sm text-destructive">
            {error.message || "차트 데이터를 불러오지 못했습니다."}
          </div>
        ) : rows.length === 0 ? (
          <div className="flex h-full min-h-64 flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
            <BarChart3 className="size-6" aria-hidden="true" />
            <p>EQPCH 또는 Bin Name을 선택하면 차트가 표시됩니다.</p>
          </div>
        ) : (
          <TrellisChart
            ref={trellisRef}
            data={rows}
            trellisBy={groupBy}
            xAxisMode={xAxisMode}
            highlightFirst={highlightFirst}
            lassoMode={lassoMode}
            lassoShape={lassoShape}
            eqcTimeTrellisMode={eqcTimeTrellisMode}
            onLassoModeChange={setLassoMode}
            onLassoShapeChange={setLassoShape}
            scrollContainerRef={scrollContainerRef}
            outerScrollTop={outerScrollTop}
            outerViewportHeight={outerViewportHeight}
          />
        )}
      </CardContent>
    </Card>
  )
}
