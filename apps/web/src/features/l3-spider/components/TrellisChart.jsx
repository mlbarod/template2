import { forwardRef, memo, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState } from 'react'
import Plotly from 'plotly.js-dist-min'
import { CHART_MARKER_SIZE, EQC_TIME_STATUS_MARKER, STATUS_MARKER, STATUS_ORDER } from '../utils/chartStatus'
import './TrellisChart.css'

const NCOLS = 3
const EQC_TIME_NCOLS = 1
const SUBPLOT_H = 340
const SUBPLOT_H_WAFER = 420
const AXIS_FONT_SIZE = 12
const SUBPLOT_TITLE_FONT_SIZE = 13
const AXIS_TITLE_FONT_SIZE = 12
const RISK_TITLE_MARKER = '<span style="color:#be123c;font-size:19px">▌</span>'
const RISK_BADGE_XSHIFT = -62
const RISK_TITLE_START_X = 0.16
const X_JITTER_OFFSET = 0.28
const MAX_X_TICKS_PER_SUBPLOT = 12
const MAX_POINTS_PER_SUBPLOT = 900
const OVERSCAN_ROWS = 3
const DEFAULT_VIEWPORT_H = 1200
// idle 스케줄러(정상 마커 fill-in을 유휴 시점으로 미룸). requestIdleCallback 미지원 시 setTimeout 폴백.
const scheduleIdle = (typeof window !== 'undefined' && window.requestIdleCallback)
  ? (cb) => window.requestIdleCallback(cb, { timeout: 250 })
  : (cb) => window.setTimeout(cb, 32)
const cancelIdle = (typeof window !== 'undefined' && window.cancelIdleCallback)
  ? (h) => window.cancelIdleCallback(h)
  : (h) => window.clearTimeout(h)
const LASSO_KEY_SEPARATOR = '\u0000'
const HIGHLIGHT_COLOR = '#14DBFF'
const HIGHLIGHT_GLOW = 'rgba(20, 219, 255, 0.28)'
const HIGHLIGHT_SHINE = '#89FCFF'
const HOVER_LABEL = { align: 'left' }
const EQC_COLOR_PALETTE = [
  '#2563eb', '#16a34a', '#f97316', '#7c3aed', '#0891b2',
  '#db2777', '#65a30d', '#9333ea', '#0f766e', '#ca8a04',
  '#1d4ed8', '#be123c',
]

const ACTIVE_MODEBAR_TITLES = new Set(['Pan', 'Box select wafer', 'Box select lot'])
const PRESERVE_ACTIVE_MODEBAR_TITLES = new Set(['Autoscale', 'Reset axes'])

const HAND_PAN_ICON = {
  width: 512, height: 512,
  path: 'M176 232V96c0-22 18-40 40-40s40 18 40 40v120h16V56c0-22 18-40 40-40s40 18 40 40v176h16V88c0-22 18-40 40-40s40 18 40 40v184h16V144c0-22 18-40 40-40s40 18 40 40v176c0 93-75 168-168 168h-56c-56 0-108-28-139-75L48 334c-13-20-8-47 12-60s47-8 60 12l40 60V232c0-22 18-40 40-40s40 18 40 40z',
}

const LASSO_WAFER_ICON = {
  width: 512, height: 512,
  path: 'M254 72c104 0 188 57 188 128s-84 128-188 128S66 271 66 200 150 72 254 72zm0 52c-72 0-132 35-132 76s60 76 132 76 132-35 132-76-60-76-132-76zm-34 252h68v68h-68z',
}

const LASSO_LOT_ICON = {
  width: 512, height: 512,
  path: 'M254 72c104 0 188 57 188 128s-84 128-188 128S66 271 66 200 150 72 254 72zm0 52c-72 0-132 35-132 76s60 76 132 76 132-35 132-76-60-76-132-76zM154 366h58v58h-58zm73 0h58v58h-58zm73 0h58v58h-58z',
}

function getActiveModebarTitle(dragMode, lassoMode, lassoShape) {
  if (dragMode === 'pan') return 'Pan'
  if (dragMode === 'select' && lassoShape === 'box') {
    if (lassoMode === 'wafer') return 'Box select wafer'
    if (lassoMode === 'lot') return 'Box select lot'
  }
  return null
}

function syncModebarActiveButtons(plotEl, activeTitle) {
  plotEl.querySelectorAll('.modebar-btn[data-title]').forEach(button => {
    const title = button.getAttribute('data-title')
    if (!title || !ACTIVE_MODEBAR_TITLES.has(title)) return
    const active = title === activeTitle
    button.classList.toggle('active', active)
    button.setAttribute('aria-pressed', active ? 'true' : 'false')
  })
}

function parseTimeMs(value) {
  const ms = new Date(value).getTime()
  return Number.isFinite(ms) ? ms : 0
}

function formatAxisTime(value) {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return value
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${month}-${day}`
}

function getWaferJitterOffset(waferId) {
  const waferNo = Number.parseInt(waferId, 10)
  if (Number.isFinite(waferNo)) {
    const clamped = Math.max(1, Math.min(25, waferNo))
    return ((clamped - 13) / 12) * X_JITTER_OFFSET
  }
  let hash = 0
  for (let i = 0; i < waferId.length; i += 1) hash = (hash * 31 + waferId.charCodeAt(i)) % 997
  return ((hash / 996) * 2 - 1) * X_JITTER_OFFSET
}

function buildTimeXAxis(subData) {
  const xByRow = new Map()
  subData.forEach(d => xByRow.set(d, d.tkinTime))
  const times = subData.map(d => d.tkinTime)
  const lineMin = times.reduce((a, b) => a < b ? a : b)
  const lineMax = times.reduce((a, b) => a > b ? a : b)
  return {
    axis: {
      title: { text: 'eqp_tkin_time', font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 10 },
      type: 'date',
      tickformat: '%m-%d',
      nticks: MAX_X_TICKS_PER_SUBPLOT,
      tickangle: -90,
    },
    xByRow, lineMin, lineMax,
  }
}

function buildWaferXAxis(subData) {
  const sorted = [...subData].sort((a, b) => {
    const byTime = parseTimeMs(a.tkinTime) - parseTimeMs(b.tkinTime)
    if (byTime !== 0) return byTime
    return a.waferId.localeCompare(b.waferId, undefined, { numeric: true })
  })
  const xByRow = new Map()
  sorted.forEach((d, idx) => xByRow.set(d, idx + getWaferJitterOffset(d.waferId)))
  const step = Math.max(1, Math.ceil(sorted.length / MAX_X_TICKS_PER_SUBPLOT))
  const sampled = sorted.filter((_, idx) => idx % step === 0)
  return {
    axis: {
      title: { text: 'eqp_tkin_time, wafer_id', font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 12 },
      type: 'linear',
      tickmode: 'array',
      tickangle: -90,
      range: [-0.7, Math.max(sorted.length - 0.3, 0.7)],
      tickvals: sampled.map(d => sorted.indexOf(d)),
      ticktext: sampled.map(d => `${formatAxisTime(d.tkinTime)}_${d.waferId}`),
    },
    xByRow,
    lineMin: -0.5,
    lineMax: Math.max(sorted.length - 0.5, 0.5),
  }
}

function buildXAxis(subData, mode) {
  return mode === 'tkin_time_wafer_id' ? buildWaferXAxis(subData) : buildTimeXAxis(subData)
}

function buildEqcTimeXAxis(subData) {
  const sorted = [...subData].sort((a, b) => {
    const byEqc = a.eqc.localeCompare(b.eqc, undefined, { numeric: true })
    if (byEqc !== 0) return byEqc
    const byTime = parseTimeMs(a.tkinTime) - parseTimeMs(b.tkinTime)
    if (byTime !== 0) return byTime
    return a.waferId.localeCompare(b.waferId, undefined, { numeric: true })
  })
  const xByRow = new Map()
  const eqcOrder = [...new Set(sorted.map(d => d.eqc))]
  const eqcColor = new Map(eqcOrder.map((eqc, idx) => [eqc, EQC_COLOR_PALETTE[idx % EQC_COLOR_PALETTE.length]]))
  const boundaries = []
  const tickvals = []
  const ticktext = []

  let cursor = 0
  eqcOrder.forEach((eqc, eqcIdx) => {
    const rows = sorted.filter(d => d.eqc === eqc)
    const start = cursor
    rows.forEach((row, idx) => xByRow.set(row, start + idx))
    cursor += rows.length
    const end = cursor - 1
    tickvals.push((start + end) / 2)
    ticktext.push(eqc)
    if (eqcIdx < eqcOrder.length - 1) boundaries.push(end + 0.5)
  })

  return {
    axis: {
      title: { text: 'eqpch, tkin_time', font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 12 },
      type: 'linear',
      tickmode: 'array',
      tickangle: -45,
      range: [-0.7, Math.max(sorted.length - 0.3, 0.7)],
      tickvals,
      ticktext,
    },
    xByRow,
    lineMin: -0.5,
    lineMax: Math.max(sorted.length - 0.5, 0.5),
    eqcOrder,
    eqcColor,
    boundaries,
  }
}

function sortHighlightFirst(keys, hasHighlight) {
  return [...keys].sort((a, b) => {
    const aRisk = hasHighlight(a)
    const bRisk = hasHighlight(b)
    if (aRisk === bRisk) return 0
    return aRisk ? -1 : 1
  })
}

function getBinNameAxisTitle(subData) {
  const binNames = [...new Set(subData.map(d => d.binName))].sort()
  return binNames.length > 0 ? binNames.join(', ') : ''
}

function sampleRowsForPlot(rows, maxPoints = MAX_POINTS_PER_SUBPLOT) {
  if (rows.length <= maxPoints) return rows
  const anomalyRows = rows.filter(d => d.displayStatus === 'High Risk Chamber' || d.displayStatus === 'Warning')
  const anomalySet = new Set(anomalyRows)
  const remainingBudget = Math.max(maxPoints - anomalyRows.length, Math.floor(maxPoints * 0.35))
  const normalRows = rows.filter(d => !anomalySet.has(d))
  const sampledNormal = []
  const step = normalRows.length / remainingBudget
  for (let i = 0; i < remainingBudget; i += 1) {
    const idx = Math.min(Math.floor(i * step), normalRows.length - 1)
    if (normalRows[idx]) sampledNormal.push(normalRows[idx])
  }
  return [...anomalyRows, ...sampledNormal]
}

function getWaferLassoKey(row) {
  return `${row.rootLotId}${LASSO_KEY_SEPARATOR}${row.waferId}`
}

function getLotLassoKey(row) {
  return row.lotId
}

function escapeHoverText(value) {
  if (!value) return ''
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function isLassoHighlighted(row, selection) {
  if (!selection) return false
  if (selection.mode === 'wafer') return selection.keys.has(getWaferLassoKey(row))
  return selection.keys.has(getLotLassoKey(row))
}

function getSelectedPointKeys(points, mode) {
  const keys = new Set()
  points.forEach(point => {
    const customdata = point.customdata
    if (!Array.isArray(customdata)) return
    const [rootLotId, lotId, waferId] = customdata
    if (mode === 'wafer' && rootLotId !== undefined && waferId !== undefined) {
      keys.add(`${rootLotId}${LASSO_KEY_SEPARATOR}${waferId}`)
    }
    if (mode === 'lot' && lotId !== undefined) keys.add(String(lotId))
  })
  return keys
}

function makeHighlightTrace(rows, xAxis, xRef, yRef, customdata, hovertemplate, layer) {
  const common = {
    type: 'scatter',
    mode: 'markers',
    x: rows.map(d => xAxis.xByRow.get(d) ?? 0),
    y: rows.map(d => d.binValue),
    customdata,
    xaxis: xRef,
    yaxis: yRef,
    showlegend: false,
    hovertemplate,
  }

  if (layer === 'glow') {
    return {
      ...common,
      marker: {
        color: HIGHLIGHT_GLOW,
        size: CHART_MARKER_SIZE + 12,
        symbol: 'circle',
        opacity: 0.9,
        line: { color: 'rgba(20, 219, 255, 0)', width: 0 },
      },
      hoverinfo: 'skip',
    }
  }

  if (layer === 'shine') {
    return {
      ...common,
      marker: {
        color: HIGHLIGHT_SHINE,
        size: Math.max(CHART_MARKER_SIZE - 2, 5),
        symbol: 'circle',
        opacity: 0.92,
        line: { color: 'rgba(137, 252, 255, 0)', width: 0 },
      },
      hoverinfo: 'skip',
    }
  }

  return {
    ...common,
    marker: {
      color: HIGHLIGHT_COLOR,
      size: CHART_MARKER_SIZE + 7,
      symbol: 'circle',
      opacity: 1,
      line: { color: 'rgba(20, 219, 255, 0)', width: 0 },
    },
    name: 'selected highlight',
  }
}

function makePointCustomData(rows, includeEqc = false) {
  return rows.map(d => [
    d.rootLotId,
    d.lotId,
    d.waferId,
    d.tkinTime,
    escapeHoverText(d.comment),
    ...(includeEqc ? [d.eqc] : []),
  ])
}

function getStepPpidTitle(rows) {
  const stepSeqs = [...new Set(rows.map(d => d.stepSeq))].sort()
  const ppids = [...new Set(rows.map(d => d.ppid))].sort()
  return `${stepSeqs.length > 0 ? stepSeqs.join(', ') : '-'} / ${ppids.length > 0 ? ppids.join(', ') : '-'}`
}

function getUniqueText(values) {
  const unique = [...new Set(values)].sort()
  return unique.length > 0 ? unique.join(', ') : '-'
}

function getSharedYRange(rows) {
  if (!rows.length) return null
  const vals = rows.map(d => d.binValue)
  const limits = rows
    .map(d => d.propOver50 < 0.5 ? d.usl : d.lsl)
    .filter(v => v !== null && v !== undefined)
  const allY = [...vals, ...limits]
  const yMin = Math.min(...allY)
  const yMax = Math.max(...allY)
  const pad = Math.max((yMax - yMin) * 0.1, 1)
  return [yMin - pad, yMax + pad]
}

function getLimitInfoFromRows(rows) {
  if (!rows.length) return { value: null, label: '', color: '' }
  const r = rows[0]
  const isMso = r.propOver50 < 0.5
  const val = isMso ? r.usl : r.lsl
  return { value: val ?? null, label: isMso ? 'USL' : 'LSL', color: '#dc2626' }
}

function getBaseXAxis() {
  return {
    color: '#6b7394',
    showgrid: false,
    zeroline: false,
    linecolor: '#000000',
    linewidth: 1,
    mirror: true,
    tickfont: { size: AXIS_FONT_SIZE, color: '#6b7394' },
    ticks: 'outside',
    ticklen: 5,
    tickwidth: 1,
    tickcolor: '#000000',
    showticklabels: true,
    automargin: true,
    showline: true,
  }
}

function getBaseYAxis() {
  return {
    color: '#6b7394',
    showgrid: true,
    gridcolor: '#c7c7c7',
    griddash: 'dot',
    zeroline: false,
    linecolor: '#000000',
    linewidth: 1,
    mirror: true,
    tickfont: { size: AXIS_FONT_SIZE, color: '#6b7394' },
    ticks: 'outside',
    ticklen: 5,
    tickwidth: 1,
    tickcolor: '#000000',
    title: { font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 8 },
    showticklabels: true,
    nticks: 12,
    automargin: true,
    showline: true,
  }
}

function buildSingleEqcTimeChart(key, subData, lassoSelection) {
  const plotData = []
  const shapes = []
  const annotations = []
  const xAxis = buildEqcTimeXAxis(subData)
  const plotRows = sampleRowsForPlot(
    subData,
    Math.max(MAX_POINTS_PER_SUBPLOT * xAxis.eqcOrder.length, MAX_POINTS_PER_SUBPLOT),
  )
  const title = getStepPpidTitle(subData)
  const yRange = getSharedYRange(subData)

  xAxis.boundaries.forEach(x => {
    shapes.push({
      type: 'line', xref: 'x', yref: 'y',
      x0: x, x1: x,
      y0: yRange?.[0] ?? 0,
      y1: yRange?.[1] ?? 1,
      line: { color: '#94a3b8', dash: 'dot', width: 1 },
    })
  })

  STATUS_ORDER.forEach(status => {
    xAxis.eqcOrder.forEach(eqc => {
      const pts = plotRows.filter(d => d.displayStatus === status && d.eqc === eqc)
      if (pts.length === 0) return

      const highlightedPts = lassoSelection
        ? subData.filter(d => d.displayStatus === status && d.eqc === eqc && isLassoHighlighted(d, lassoSelection))
        : []
      const markerStyle = EQC_TIME_STATUS_MARKER[status]
      const eqcColor = xAxis.eqcColor.get(eqc) ?? '#2563eb'
      const hovertemplate =
        `<b>${title}</b><br>` +
        `eqc: %{customdata[5]}<br>` +
        `Time: %{customdata[3]}<br>` +
        `Value: %{y:.4f}<br>` +
        `root_lot_id: %{customdata[0]}<br>` +
        `lot_id: %{customdata[1]}<br>` +
        `wafer_id: %{customdata[2]}<br>` +
        `comment: %{customdata[4]}<br>` +
        `${status}<extra></extra>`
      const customdata = makePointCustomData(pts, true)

      plotData.push({
        type: 'scatter', mode: 'markers',
        x: pts.map(d => xAxis.xByRow.get(d) ?? 0),
        y: pts.map(d => d.binValue),
        customdata,
        marker: { color: eqcColor, size: CHART_MARKER_SIZE, symbol: markerStyle.symbol, opacity: 0.95, line: { color: eqcColor, width: 1.4 } },
        name: markerStyle.label,
        legendgroup: status,
        showlegend: false,
        hovertemplate,
      })

      if (highlightedPts.length > 0) {
        const highlightCustomData = makePointCustomData(highlightedPts, true)
        plotData.push(
          makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'glow'),
          makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'sphere'),
          makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'shine'),
        )
      }
    })
  })

  const limit = getLimitInfoFromRows(subData)
  if (limit.value !== null) {
    shapes.push({
      type: 'line', xref: 'x', yref: 'y',
      x0: xAxis.lineMin, x1: xAxis.lineMax,
      y0: limit.value, y1: limit.value,
      line: { color: limit.color, dash: 'dot', width: 1.5 },
    })
    annotations.push({
      xref: 'x domain', yref: 'y',
      x: 1, y: limit.value,
      text: `<b>${limit.label}</b>`,
      showarrow: false,
      font: { size: 9, color: limit.color },
      xanchor: 'right', yanchor: 'bottom',
    })
  }

  annotations.push({
    xref: 'x domain', yref: 'y domain',
    x: 0.5, y: 1.065,
    text: `<b>${title}</b>`,
    showarrow: false,
    font: { size: SUBPLOT_TITLE_FONT_SIZE, color: '#1a2044' },
    xanchor: 'center', yanchor: 'bottom',
  })

  return {
    key,
    plotData,
    plotLayout: {
      xaxis: { ...getBaseXAxis(), ...xAxis.axis },
      yaxis: {
        ...getBaseYAxis(),
        title: { text: getBinNameAxisTitle(subData), font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 8 },
        ...(yRange !== null ? { range: yRange.slice(), autorange: false } : { autorange: true }),
      },
      height: SUBPLOT_H_WAFER,
      autosize: true,
      paper_bgcolor: '#ffffff',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#6b7394', size: AXIS_FONT_SIZE },
      margin: { l: 62, r: 20, t: 55, b: 115 },
      shapes, annotations,
      hoverlabel: HOVER_LABEL,
      showlegend: false,
    },
  }
}

function buildSingleStandardChart(key, subData, title, limit, sharedYRange, xAxisMode, lassoSelection) {
  const plotData = []
  const baseData = []  // 이상(비정상) 트레이스만 — progressive draw의 1단계
  const shapes = []
  const annotations = []
  const hasRisk = subData.some(d => d.displayStatus === 'High Risk Chamber')
  const xAxis = buildXAxis(subData, xAxisMode)
  const plotRows = sampleRowsForPlot(subData)

  STATUS_ORDER.forEach(status => {
    const pts = plotRows.filter(d => d.displayStatus === status)
    if (pts.length === 0) return

    const highlightedPts = lassoSelection
      ? subData.filter(d => d.displayStatus === status && isLassoHighlighted(d, lassoSelection))
      : []
    const markerStyle = STATUS_MARKER[status]
    const hovertemplate =
      `<b>${title}</b><br>` +
      `Time: %{customdata[3]}<br>` +
      `Value: %{y:.4f}<br>` +
      `root_lot_id: %{customdata[0]}<br>` +
      `lot_id: %{customdata[1]}<br>` +
      `wafer_id: %{customdata[2]}<br>` +
      `comment: %{customdata[4]}<br>` +
      `${status}<extra></extra>`
    const customdata = makePointCustomData(pts)

    const isAnomaly = status !== 'Normal (Ref)'
    const mainTrace = {
      type: 'scatter', mode: 'markers',
      x: pts.map(d => xAxis.xByRow.get(d) ?? 0),
      y: pts.map(d => d.binValue),
      customdata,
      marker: { color: markerStyle.color, size: CHART_MARKER_SIZE, symbol: markerStyle.symbol, opacity: 0.95, line: { color: markerStyle.color, width: 1.2 } },
      name: markerStyle.label,
      legendgroup: status,
      showlegend: false,
      hovertemplate,
    }
    plotData.push(mainTrace)
    if (isAnomaly) baseData.push(mainTrace)

    if (highlightedPts.length > 0) {
      const highlightCustomData = makePointCustomData(highlightedPts)
      const highlightTraces = [
        makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'glow'),
        makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'sphere'),
        makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'shine'),
      ]
      plotData.push(...highlightTraces)
      if (isAnomaly) baseData.push(...highlightTraces)
    }
  })

  if (limit.value !== null) {
    shapes.push({
      type: 'line', xref: 'x', yref: 'y',
      x0: xAxis.lineMin, x1: xAxis.lineMax,
      y0: limit.value, y1: limit.value,
      line: { color: limit.color, dash: 'dot', width: 1.5 },
    })
    annotations.push({
      xref: 'x domain', yref: 'y',
      x: 1, y: limit.value,
      text: `<b>${limit.label}</b>`,
      showarrow: false,
      font: { size: 9, color: limit.color },
      xanchor: 'right', yanchor: 'bottom',
    })
  }

  if (hasRisk) {
    annotations.push({
      xref: 'paper', yref: 'paper',
      x: 0, y: 1.065,
      text: `${RISK_TITLE_MARKER} <b><span style="color:#be123c">High Risk</span></b>`,
      showarrow: false,
      font: { size: SUBPLOT_TITLE_FONT_SIZE, color: '#be123c' },
      xshift: RISK_BADGE_XSHIFT,
      xanchor: 'left', yanchor: 'bottom',
    })
  }

  annotations.push({
    xref: 'x domain', yref: 'y domain',
    x: hasRisk ? RISK_TITLE_START_X : 0.5,
    y: 1.065,
    text: `<b>${title}</b>`,
    showarrow: false,
    font: { size: SUBPLOT_TITLE_FONT_SIZE, color: '#1a2044' },
    xanchor: hasRisk ? 'left' : 'center', yanchor: 'bottom',
  })

  return {
    key,
    plotData,
    // progressive draw: 이상 트레이스가 있고 정상 트레이스도 있을 때만 1단계용 baseData 제공.
    // (전부 정상이거나 전부 이상이면 나눌 필요 없어 undefined → 전체를 즉시 그림)
    baseData: (baseData.length > 0 && baseData.length < plotData.length) ? baseData : undefined,
    plotLayout: {
      xaxis: { ...getBaseXAxis(), ...xAxis.axis },
      yaxis: {
        ...getBaseYAxis(),
        title: { text: getBinNameAxisTitle(subData), font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 8 },
        // sharedYRange는 모든 subplot이 공유하는 배열이다. Plotly가 layout을 in-place로 변형
        // (확대 시 range 덮어쓰기)하므로, 복사본을 넘겨 한 차트의 줌이 다른 차트로 새지 않게 한다.
        ...(sharedYRange !== null ? { range: sharedYRange.slice(), autorange: false } : { autorange: true }),
      },
      height: xAxisMode === 'tkin_time_wafer_id' ? SUBPLOT_H_WAFER : SUBPLOT_H,
      autosize: true,
      paper_bgcolor: '#ffffff',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#6b7394', size: AXIS_FONT_SIZE },
      margin: { l: 70, r: 20, t: 50, b: xAxisMode === 'tkin_time_wafer_id' ? 130 : 75 },
      shapes, annotations,
      hoverlabel: HOVER_LABEL,
      showlegend: false,
    },
  }
}

const FacetPlot = memo(function FacetPlot({ chart, lassoMode, lassoShape, dragMode, onSelected, onPanRequest, onLassoRequest, onModebarNeutralRequest }) {
  const plotRef = useRef(null)
  const initializedRef = useRef(false)
  const selectedHandlerRef = useRef(null)
  const deferHandleRef = useRef(0)
  const axisSigRef = useRef(null)
  const activeModebarTitle = getActiveModebarTitle(dragMode, lassoMode, lassoShape)

  useEffect(() => {
    const plotEl = plotRef.current
    if (!plotEl) return

    let disposed = false
    const syncActiveModebar = () => {
      if (!disposed) syncModebarActiveButtons(plotEl, activeModebarTitle)
    }
    const scheduleActiveModebarSync = () => {
      window.requestAnimationFrame(syncActiveModebar)
      window.setTimeout(syncActiveModebar, 0)
      window.setTimeout(syncActiveModebar, 80)
    }
    const modebarClickHandler = (event) => {
      if (!(event.target instanceof Element)) return
      const button = event.target.closest('.modebar-btn[data-title]')
      if (!button || !plotEl.contains(button)) return
      const title = button.getAttribute('data-title')
      if (title && ACTIVE_MODEBAR_TITLES.has(title)) return
      if (!title || !PRESERVE_ACTIVE_MODEBAR_TITLES.has(title)) {
        onModebarNeutralRequest()
        syncModebarActiveButtons(plotEl, null)
        return
      }
      scheduleActiveModebarSync()
    }

    const plotConfig = {
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ['pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d'],
      modeBarButtonsToAdd: [
        {
          name: 'pan-hand',
          title: 'Pan',
          icon: HAND_PAN_ICON,
          click: (gd) => {
            onPanRequest()
            Plotly.relayout(gd, { dragmode: 'pan' })
            syncModebarActiveButtons(gd, 'Pan')
          },
        },
        {
          name: 'lasso-wafer',
          title: 'Box select wafer',
          icon: LASSO_WAFER_ICON,
          click: (gd) => {
            onLassoRequest('wafer')
            Plotly.relayout(gd, { dragmode: 'select' })
            syncModebarActiveButtons(gd, 'Box select wafer')
          },
        },
        {
          name: 'lasso-lot',
          title: 'Box select lot',
          icon: LASSO_LOT_ICON,
          click: (gd) => {
            onLassoRequest('lot')
            Plotly.relayout(gd, { dragmode: 'select' })
            syncModebarActiveButtons(gd, 'Box select lot')
          },
        },
      ],
      displaylogo: false,
    }

    const layout = {
      ...chart.plotLayout,
      dragmode: dragMode,
      ...(dragMode === 'select' ? { selectdirection: 'd' } : {}),
    }

    // 사용자 줌 보존: 축 기준(xaxis 구성 + yaxis range)이 그대로인 재렌더(라쏘 선택/모드바 등)에서는
    // 현재 그래프의 실제 축 범위를 유지해 줌이 풀리지 않게 한다. 축 기준 자체가 바뀌면(데이터/xAxis
    // 모드 변경 등) chart.plotLayout의 기본 범위를 그대로 적용(리셋).
    const axisSig = JSON.stringify([
      chart.plotLayout.xaxis,
      chart.plotLayout.yaxis?.range ?? null,
      chart.plotLayout.yaxis?.autorange ?? null,
    ])
    const axisBaseChanged = axisSigRef.current !== axisSig
    axisSigRef.current = axisSig
    if (initializedRef.current && !axisBaseChanged && plotEl.layout) {
      const cur = plotEl.layout
      if (cur.yaxis) {
        layout.yaxis = { ...layout.yaxis, autorange: cur.yaxis.autorange }
        if (cur.yaxis.range) layout.yaxis.range = cur.yaxis.range.slice()
      }
      if (cur.xaxis) {
        layout.xaxis = { ...layout.xaxis, autorange: cur.xaxis.autorange }
        if (cur.xaxis.range) layout.xaxis.range = cur.xaxis.range.slice()
      }
    }

    // progressive draw는 '최초 그릴 때(newPlot)'에만 적용: 이상 트레이스만 먼저 그리고 정상은
    // idle에 채운다. 이후 재렌더(모드바/드래그모드/데이터 변경 등)는 전체를 한 번에 그려
    // 매번 정상점이 사라졌다 다시 생기는 깜빡임을 방지한다.
    const usePartial = !initializedRef.current && Boolean(chart.baseData)
    const firstData = usePartial ? chart.baseData : chart.plotData
    plotEl.addEventListener('click', modebarClickHandler, true)
    const plotPromise = initializedRef.current
      ? Plotly.react(plotEl, firstData, layout, plotConfig)
      : Plotly.newPlot(plotEl, firstData, layout, plotConfig)

    initializedRef.current = true
    plotPromise.finally(() => {
      if (disposed) return
      syncActiveModebar()
      // 2단계: 정상 마커까지 포함한 전체를 idle(유휴) 시점에 채운다. (최초 그릴 때만)
      // 스크롤/다른 subplot 마운트로 메인스레드가 바쁘면 자연히 뒤로 밀려 fling이 가벼워진다.
      if (usePartial) {
        deferHandleRef.current = scheduleIdle(() => {
          deferHandleRef.current = 0
          if (disposed) return
          Plotly.react(plotEl, chart.plotData, layout, plotConfig).finally(() => {
            if (!disposed) syncActiveModebar()
          })
        })
      }
      if (selectedHandlerRef.current) {
        plotEl.removeListener?.('plotly_selected', selectedHandlerRef.current)
        selectedHandlerRef.current = null
      }
      if (lassoMode === 'off') return
      const selectedHandler = (event) => {
        onSelected(Array.isArray(event?.points) ? event.points : [])
      }
      selectedHandlerRef.current = selectedHandler
      plotEl.on?.('plotly_selected', selectedHandler)
    })

    return () => {
      disposed = true
      if (deferHandleRef.current) {
        cancelIdle(deferHandleRef.current)
        deferHandleRef.current = 0
      }
      plotEl.removeEventListener('click', modebarClickHandler, true)
      if (selectedHandlerRef.current) {
        plotEl.removeListener?.('plotly_selected', selectedHandlerRef.current)
        selectedHandlerRef.current = null
      }
    }
  }, [chart.plotData, chart.baseData, chart.plotLayout, lassoMode, lassoShape, dragMode, activeModebarTitle, onSelected, onPanRequest, onLassoRequest, onModebarNeutralRequest])

  useEffect(() => () => {
    const plotEl = plotRef.current
    if (plotEl && initializedRef.current) Plotly.purge(plotEl)
  }, [])

  return <div ref={plotRef} className="tc-plot" />
})

const TrellisChart = forwardRef(function TrellisChart({
  data,
  trellisBy,
  xAxisMode,
  highlightFirst = false,
  lassoMode = 'off',
  lassoShape = 'box',
  eqcTimeTrellisMode = 'step',
  onLassoModeChange,
  onLassoShapeChange,
  scrollContainerRef,
  outerScrollTop = 0,
  outerViewportHeight = DEFAULT_VIEWPORT_H,
}, ref) {
  const scrollerRef = useRef(null)
  const spacerRef = useRef(null)
  const virtualWindowRef = useRef(null)
  const plotGridRef = useRef(null)
  const [chartAreaTop, setChartAreaTop] = useState(0)
  const [lassoSelection, setLassoSelection] = useState(null)
  const [plotDragMode, setPlotDragMode] = useState('zoom')

  const rowHeight = xAxisMode === 'tkin_time_wafer_id' || xAxisMode === 'eqc_tkin_time'
    ? SUBPLOT_H_WAFER
    : SUBPLOT_H
  const chartColumns = xAxisMode === 'eqc_tkin_time' ? EQC_TIME_NCOLS : NCOLS

  const chartPlan = useMemo(() => {
    if (data.length === 0) {
      return { keys: [], subtitle: '', sharedYRange: null, groupedData: new Map() }
    }

    if (xAxisMode === 'eqc_tkin_time') {
      const groupedData = new Map()
      data.forEach(row => {
        const key = eqcTimeTrellisMode === 'step_ppid'
          ? `${row.stepSeq}|||${row.ppid}`
          : row.stepSeq
        const rows = groupedData.get(key)
        if (rows) rows.push(row)
        else groupedData.set(key, [row])
      })
      const keys = [...groupedData.keys()].sort()
      const subtitleMode = eqcTimeTrellisMode === 'step_ppid' ? 'step_seq + ppid' : 'step_seq'
      return {
        keys,
        subtitle: `${new Set(data.map(d => d.eqc)).size} EQPCH · ${subtitleMode} trellis`,
        sharedYRange: getSharedYRange(data),
        groupedData,
      }
    }

    if (trellisBy === 'eqc') {
      const groupedData = new Map()
      data.forEach(row => {
        const rows = groupedData.get(row.eqc)
        if (rows) rows.push(row)
        else groupedData.set(row.eqc, [row])
      })
      const baseKeys = [...groupedData.keys()].sort()
      const riskEqpchs = new Set(data.filter(d => d.displayStatus === 'High Risk Chamber').map(d => d.eqc))
      const keys = highlightFirst
        ? sortHighlightFirst(baseKeys, eqc => riskEqpchs.has(eqc))
        : baseKeys
      const vals = data.map(d => d.binValue)
      const limits = data
        .map(d => d.propOver50 < 0.5 ? d.usl : d.lsl)
        .filter(v => v !== null && v !== undefined)
      const allY = [...vals, ...limits]
      const yMin = Math.min(...allY)
      const yMax = Math.max(...allY)
      const pad = Math.max((yMax - yMin) * 0.1, 1)
      return { keys, subtitle: `${keys.length} EQPCH · 공통 Y축`, sharedYRange: [yMin - pad, yMax + pad], groupedData }
    }

    if (trellisBy === 'bin') {
      const groupedData = new Map()
      data.forEach(row => {
        const rows = groupedData.get(row.binName)
        if (rows) rows.push(row)
        else groupedData.set(row.binName, [row])
      })
      const baseKeys = [...groupedData.keys()].sort()
      const riskBins = new Set(data.filter(d => d.displayStatus === 'High Risk Chamber').map(d => d.binName))
      const keys = highlightFirst
        ? sortHighlightFirst(baseKeys, key => riskBins.has(key))
        : baseKeys
      return { keys, subtitle: `${keys.length} bin_name · 독립 Y축`, sharedYRange: null, groupedData }
    }

    const groupedData = new Map()
    data.forEach(row => {
      const key = `${row.stepSeq}|||${row.binName}`
      const rows = groupedData.get(key)
      if (rows) rows.push(row)
      else groupedData.set(key, [row])
    })
    const baseKeys = [...groupedData.keys()].sort()
    const riskStepBins = new Set(
      data.filter(d => d.displayStatus === 'High Risk Chamber').map(d => `${d.stepSeq}|||${d.binName}`),
    )
    const keys = highlightFirst
      ? sortHighlightFirst(baseKeys, key => riskStepBins.has(key))
      : baseKeys
    return { keys, subtitle: `${keys.length} step·bin · 독립 Y축`, sharedYRange: null, groupedData }
  }, [data, trellisBy, highlightFirst, xAxisMode, eqcTimeTrellisMode])

  const keySignature = useMemo(() => chartPlan.keys.join('\u0001'), [chartPlan.keys])
  const totalRows = Math.ceil(chartPlan.keys.length / chartColumns)
  const totalHeight = Math.max(totalRows * rowHeight, 300)
  const viewportHeight = outerViewportHeight || DEFAULT_VIEWPORT_H
  const maxChartScrollTop = Math.max(totalHeight - viewportHeight, 0)
  const chartScrollTop = Math.min(Math.max(outerScrollTop - chartAreaTop, 0), maxChartScrollTop)
  const visibleRowStart = Math.max(Math.floor(chartScrollTop / rowHeight) - OVERSCAN_ROWS, 0)
  const visibleRowCount = Math.ceil(viewportHeight / rowHeight) + OVERSCAN_ROWS * 2
  const visibleRowEnd = Math.min(visibleRowStart + visibleRowCount, totalRows)
  const virtualOffset = visibleRowStart * rowHeight

  useLayoutEffect(() => {
    spacerRef.current?.style.setProperty('--tc-total-height', `${totalHeight}px`)
    // 스켈레톤 backdrop(빠른 스크롤 시 빈칸 채움)이 행 높이를 알 수 있게 spacer에도 설정
    spacerRef.current?.style.setProperty('--tc-row-height', `${rowHeight}px`)
    virtualWindowRef.current?.style.setProperty('--tc-virtual-offset', `${virtualOffset}px`)
    plotGridRef.current?.style.setProperty('--tc-chart-columns', String(chartColumns))
    plotGridRef.current?.style.setProperty('--tc-row-height', `${rowHeight}px`)
  }, [chartColumns, rowHeight, totalHeight, virtualOffset])

  const visibleKeys = useMemo(() => {
    const start = visibleRowStart * chartColumns
    const end = Math.min(visibleRowEnd * chartColumns, chartPlan.keys.length)
    return chartPlan.keys.slice(start, end)
  }, [chartPlan.keys, chartColumns, visibleRowStart, visibleRowEnd])

  const getGroupedRows = useCallback(
    (key) => chartPlan.groupedData.get(key) ?? [],
    [chartPlan.groupedData],
  )

  // 단일 key의 차트 객체를 빌드. 스크롤(visibleKeys)과 무관하고, 실제 입력
  // (데이터/축/trellis/공유Y/lasso)이 바뀔 때만 정체성이 바뀐다.
  const buildChartForKey = useCallback((key) => {
    const subData = getGroupedRows(key)
    if (xAxisMode === 'eqc_tkin_time') {
      return buildSingleEqcTimeChart(key, subData, lassoSelection)
    }
    if (trellisBy === 'eqc') {
      return buildSingleStandardChart(
        key, subData,
        `${key} / ${getStepPpidTitle(subData)}`,
        getLimitInfoFromRows(subData),
        chartPlan.sharedYRange,
        xAxisMode,
        lassoSelection,
      )
    }
    if (trellisBy === 'bin') {
      return buildSingleStandardChart(
        key, subData,
        `${key} / ${getUniqueText(subData.map(d => d.eqc))}`,
        getLimitInfoFromRows(subData),
        null,
        xAxisMode,
        lassoSelection,
      )
    }
    const [stepSeq, binName] = key.split('|||')
    return buildSingleStandardChart(
      key, subData,
      `${stepSeq} / ${getUniqueText(subData.map(d => d.ppid))} / ${binName}`,
      getLimitInfoFromRows(subData),
      null,
      xAxisMode,
      lassoSelection,
    )
  }, [getGroupedRows, xAxisMode, trellisBy, chartPlan.sharedYRange, lassoSelection])

  // key별 차트 객체 캐시: 스크롤로 visibleKeys가 바뀌어도 이미 만든 key는 같은 객체 참조를
  // 재사용한다. 그래야 FacetPlot의 plotData/plotLayout 참조가 유지되어 Plotly가 재그리기하지
  // 않는다(스크롤 시 보이는 차트를 매번 다시 그리던 것이 주 병목이었음).
  // buildChartForKey 정체성이 바뀌면(실제 입력 변경) 캐시를 비운다.
  const chartCacheRef = useRef({ build: null, map: new Map() })
  const visibleCharts = useMemo(() => {
    if (data.length === 0 || visibleKeys.length === 0) return []
    const cache = chartCacheRef.current
    if (cache.build !== buildChartForKey) {
      cache.build = buildChartForKey
      cache.map = new Map()
    }
    return visibleKeys.map(key => {
      let chart = cache.map.get(key)
      if (chart === undefined) {
        chart = buildChartForKey(key)
        cache.map.set(key, chart)
      }
      return chart
    })
  }, [data.length, visibleKeys, buildChartForKey])

  // ④ defer draw: 스크롤 중에는 새로 들어오는 subplot을 그리지 않고 placeholder만 두고,
  // 스크롤이 멈추면(≈140ms) 실제로 보이는 것만 그린다. 이미 그려진 subplot은 유지한다.
  // (subplot 행이 많아 viewport 밖에서 계속 새로 마운트되는 경우의 fling 히칭을 줄임)
  const [isScrolling, setIsScrolling] = useState(false)
  const prevScrollTopRef = useRef(outerScrollTop)
  useEffect(() => {
    if (prevScrollTopRef.current === outerScrollTop) return
    prevScrollTopRef.current = outerScrollTop
    setIsScrolling(true)
    const timer = setTimeout(() => setIsScrolling(false), 140)
    return () => clearTimeout(timer)
  }, [outerScrollTop])

  // 실제로 그릴(마운트할) key 집합. 멈춤 상태에선 보이는 것 전부, 스크롤 중엔
  // 화면 밖으로 나간 것만 제거하고 새 key는 추가하지 않는다(→ 새 것은 placeholder).
  const [drawnKeys, setDrawnKeys] = useState(() => new Set())
  useEffect(() => {
    if (!isScrolling) {
      setDrawnKeys(new Set(visibleKeys))
      return
    }
    setDrawnKeys(prev => {
      const visible = new Set(visibleKeys)
      let changed = false
      const next = new Set()
      prev.forEach(k => { if (visible.has(k)) next.add(k); else changed = true })
      return changed ? next : prev
    })
  }, [visibleKeys, isScrolling])

  const handleSelectedPoints = useCallback((points) => {
    if (lassoMode === 'off') return
    const keys = getSelectedPointKeys(points, lassoMode)
    if (keys.size === 0) return
    setLassoSelection(prev => {
      if (!prev || prev.mode !== lassoMode) return { mode: lassoMode, keys }
      const nextKeys = new Set(prev.keys)
      keys.forEach(key => {
        if (nextKeys.has(key)) nextKeys.delete(key)
        else nextKeys.add(key)
      })
      return nextKeys.size > 0 ? { mode: lassoMode, keys: nextKeys } : null
    })
  }, [lassoMode])

  const handleModebarPan = useCallback(() => {
    setPlotDragMode('pan')
    onLassoModeChange?.('off')
  }, [onLassoModeChange])

  const handleModebarLasso = useCallback((mode) => {
    setPlotDragMode('select')
    onLassoShapeChange?.('box')
    onLassoModeChange?.(mode)
  }, [onLassoModeChange, onLassoShapeChange])

  const handleModebarNeutral = useCallback(() => {
    setPlotDragMode('zoom')
    onLassoModeChange?.('off')
  }, [onLassoModeChange])

  useEffect(() => {
    setLassoSelection(null)
  }, [data, keySignature, chartPlan.keys.length])

  useEffect(() => {
    // 줌/팬으로 빠져나갈 때(lassoMode='off')는 하이라이트를 유지한다. 새 라쏘 모드로
    // 들어갈 때만 이전 선택을 초기화(새 선택 시작).
    if (lassoMode === 'off') return
    setLassoSelection(null)
  }, [lassoMode])

  useEffect(() => {
    if (lassoMode === 'off') {
      setPlotDragMode(prev => prev === 'lasso' || prev === 'select' ? 'zoom' : prev)
      return
    }
    setPlotDragMode(lassoShape === 'freeform' ? 'lasso' : 'select')
  }, [lassoMode, lassoShape])

  useLayoutEffect(() => {
    const chartArea = scrollerRef.current
    const scrollContainer = scrollContainerRef?.current
    if (!chartArea || !scrollContainer) return undefined

    const updateChartAreaTop = () => {
      const chartRect = chartArea.getBoundingClientRect()
      const scrollRect = scrollContainer.getBoundingClientRect()
      setChartAreaTop(scrollContainer.scrollTop + chartRect.top - scrollRect.top)
    }

    updateChartAreaTop()
    const observer = new ResizeObserver(updateChartAreaTop)
    observer.observe(chartArea)
    observer.observe(scrollContainer)
    window.addEventListener('resize', updateChartAreaTop)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', updateChartAreaTop)
    }
  }, [scrollContainerRef, data.length, keySignature, rowHeight, totalHeight])

  // ── captureAll: 전체 차트를 PNG 한 장으로 합성 다운로드 ──────────────────
  useImperativeHandle(ref, () => ({
    async captureAll(onProgress) {
      const { keys, groupedData, sharedYRange } = chartPlan
      if (!keys.length) return

      const CAPTURE_W = 900
      const captureH = rowHeight

      // 모든 키에 대해 차트 객체 빌드 (가상화 무시)
      const allCharts = keys.map(key => {
        const subData = groupedData.get(key) ?? []
        if (xAxisMode === 'eqc_tkin_time') {
          return buildSingleEqcTimeChart(key, subData, null)
        }
        if (trellisBy === 'eqc') {
          return buildSingleStandardChart(
            key, subData,
            `${key} / ${getStepPpidTitle(subData)}`,
            getLimitInfoFromRows(subData), sharedYRange, xAxisMode, null,
          )
        }
        if (trellisBy === 'bin') {
          return buildSingleStandardChart(
            key, subData,
            `${key} / ${getUniqueText(subData.map(d => d.eqc))}`,
            getLimitInfoFromRows(subData), null, xAxisMode, null,
          )
        }
        const [stepSeq, binName] = key.split('|||')
        return buildSingleStandardChart(
          key, subData,
          `${stepSeq} / ${getUniqueText(subData.map(d => d.ppid))} / ${binName}`,
          getLimitInfoFromRows(subData), null, xAxisMode, null,
        )
      })

      // 차트별 Plotly → PNG (순차 처리로 메모리 안전)
      const imgUrls = []
      for (let i = 0; i < allCharts.length; i++) {
        onProgress?.(i, allCharts.length)
        const chart = allCharts[i]
        const el = document.createElement('div')
        el.style.cssText = `position:fixed;left:-9999px;top:0;width:${CAPTURE_W}px;height:${captureH}px;visibility:hidden;`
        document.body.appendChild(el)
        try {
          await Plotly.newPlot(
            el,
            chart.plotData,
            { ...chart.plotLayout, width: CAPTURE_W, height: captureH },
            { staticPlot: true, displayModeBar: false },
          )
          imgUrls.push(await Plotly.toImage(el, { format: 'png', width: CAPTURE_W, height: captureH }))
        } catch {
          imgUrls.push(null)
        } finally {
          Plotly.purge(el)
          document.body.removeChild(el)
        }
      }
      onProgress?.(allCharts.length, allCharts.length)

      // 그리드로 합성
      const cols = chartColumns
      const rowCount = Math.ceil(allCharts.length / cols)
      const canvas = document.createElement('canvas')
      canvas.width = CAPTURE_W * cols
      canvas.height = captureH * rowCount
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      await Promise.all(imgUrls.map((url, i) => {
        if (!url) return Promise.resolve()
        return new Promise(resolve => {
          const img = new Image()
          img.onload = () => {
            ctx.drawImage(img, (i % cols) * CAPTURE_W, Math.floor(i / cols) * captureH)
            resolve()
          }
          img.onerror = resolve
          img.src = url
        })
      }))

      await new Promise(resolve => {
        canvas.toBlob(blob => {
          if (!blob) { resolve(); return }
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `l3_spider_charts_${new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-')}.png`
          a.click()
          URL.revokeObjectURL(url)
          resolve()
        }, 'image/png')
      })
    },
  }), [chartPlan, xAxisMode, trellisBy, chartColumns, rowHeight])

  if (data.length === 0) {
    return (
      <div className="tc-empty">
        <div className="tc-empty-icon">📊</div>
        <div className="tc-empty-text">테이블에서 EQPCH 또는 bin_name을 클릭하세요</div>
      </div>
    )
  }

  const selectedCount = lassoSelection?.keys.size ?? 0

  return (
    <div className="tc-wrap">
      {selectedCount > 0 && (
        <button type="button" className="tc-clear-selection-float" onClick={() => setLassoSelection(null)}>
          선택 해제 ({selectedCount.toLocaleString()})
        </button>
      )}
      {visibleKeys.length === 0 && (
        <div className="tc-progress-placeholder">차트 준비 중…</div>
      )}
      <div
        ref={scrollerRef}
        className="tc-scroll"
      >
        <div ref={spacerRef} className="tc-spacer">
          <div ref={virtualWindowRef} className="tc-virtual-window">
            <div
              ref={plotGridRef}
              className="tc-plot-grid"
            >
              {visibleCharts.map(chart => {
                const draw = !isScrolling || drawnKeys.has(chart.key)
                return (
                  <div className="tc-plot-cell" key={chart.key}>
                    {draw ? (
                      <FacetPlot
                        chart={chart}
                        lassoMode={lassoMode}
                        lassoShape={lassoShape}
                        dragMode={plotDragMode}
                        onSelected={handleSelectedPoints}
                        onPanRequest={handleModebarPan}
                        onLassoRequest={handleModebarLasso}
                        onModebarNeutralRequest={handleModebarNeutral}
                      />
                    ) : (
                      <div className="tc-plot-defer" aria-hidden="true" />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
})

export default TrellisChart
