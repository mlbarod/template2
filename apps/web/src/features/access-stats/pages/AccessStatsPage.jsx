import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  ClipboardPaste,
  Download,
  FileSpreadsheet,
  Layers3,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
} from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Slider } from "@/components/ui/slider"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"

import {
  useAppAccessStatsQuery,
  useExternalAppUsageSyncMutation,
  useManualAppAccessCommitMutation,
  useManualAppAccessPreviewMutation,
} from "../hooks/useAccessStatsQueries"

const PERIOD_OPTIONS = [
  { key: "day", label: "일별" },
  { key: "week", label: "주별" },
  { key: "month", label: "월별" },
]

const MIN_ACCESS_DATE_OFFSET_DAYS = -365
const MAX_ACCESS_DATE_OFFSET_DAYS = 0
const DEFAULT_ACCESS_DATE_OFFSET_DAYS = -6

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

const CHART_BG_CLASSES = [
  "bg-[var(--chart-1)]",
  "bg-[var(--chart-2)]",
  "bg-[var(--chart-3)]",
  "bg-[var(--chart-4)]",
  "bg-[var(--chart-5)]",
]

const MANUAL_TEMPLATE_HEADERS = [
  "date",
  "appName",
  "accessCount",
  "uniqueUserCount",
  "memo",
]

const MANUAL_TEMPLATE_FILENAME = "external-app-access-template.csv"

function getKstDateString(offsetDays = 0) {
  const now = new Date()
  const kst = new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60 * 1000)
  kst.setDate(kst.getDate() + offsetDays)
  const year = kst.getFullYear()
  const month = String(kst.getMonth() + 1).padStart(2, "0")
  const day = String(kst.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function clampAccessDateOffset(value) {
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return DEFAULT_ACCESS_DATE_OFFSET_DAYS
  return Math.min(
    Math.max(Math.round(numericValue), MIN_ACCESS_DATE_OFFSET_DAYS),
    MAX_ACCESS_DATE_OFFSET_DAYS
  )
}

function buildRangeFromOffset(offsetDays) {
  const from = getKstDateString(clampAccessDateOffset(offsetDays))
  const to = getKstDateString()
  return { from, to }
}

function formatAccessDateOffsetLabel(offsetDays) {
  const clampedOffset = clampAccessDateOffset(offsetDays)
  if (clampedOffset === 0) return "오늘"
  return `${Math.abs(clampedOffset)}일 전`
}

function formatStatsRangeLabel(range) {
  if (range.from === range.to) return range.from
  return `${range.from} ~ ${range.to}`
}

function buildStatsParams(range, period) {
  return { ...range, period }
}

function formatNumber(value) {
  return new Intl.NumberFormat("ko-KR").format(Number(value) || 0)
}

function formatSourceLabel(app) {
  if (app?.sourceType === "internal") return "AX Portal"
  if (app?.sourceType === "manual") return "수동"
  if (app?.sourceType === "mixed") return "복합"
  return app?.sourceName || "-"
}

function buildManualTemplateExampleRow() {
  return [getKstDateString(), "AIO", "120", "55", "외부 서버 리포트 기준"]
}

function escapeCsvCell(value) {
  const text = String(value ?? "")
  if (!/[",\n\r]/.test(text)) return text
  return `"${text.replaceAll('"', '""')}"`
}

function buildCsvText(rows) {
  return `${rows.map((row) => row.map(escapeCsvCell).join(",")).join("\n")}\n`
}

function buildManualPasteSample() {
  return buildCsvText([MANUAL_TEMPLATE_HEADERS, buildManualTemplateExampleRow()]).trimEnd()
}

function downloadManualTemplateCsv() {
  const csvText = buildCsvText([MANUAL_TEMPLATE_HEADERS, buildManualTemplateExampleRow()])
  const blob = new Blob([`\ufeff${csvText}`], { type: "text/csv;charset=utf-8" })
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = href
  anchor.download = MANUAL_TEMPLATE_FILENAME
  anchor.click()
  URL.revokeObjectURL(href)
}

function parseDateString(value) {
  if (typeof value !== "string") return null
  const [year, month, day] = value.split("-").map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function formatDateString(value) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const day = String(value.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function getPeriodStartDate(value, period) {
  const date = new Date(value)
  if (period === "week") {
    const mondayOffset = (date.getDay() + 6) % 7
    date.setDate(date.getDate() - mondayOffset)
    return date
  }
  if (period === "month") {
    date.setDate(1)
    return date
  }
  return date
}

function addPeriod(value, period) {
  const next = new Date(value)
  if (period === "week") {
    next.setDate(next.getDate() + 7)
  } else if (period === "month") {
    next.setMonth(next.getMonth() + 1)
  } else {
    next.setDate(next.getDate() + 1)
  }
  return next
}

function buildDateKeys({ from, to }, period) {
  const start = parseDateString(from)
  const end = parseDateString(to)
  if (!start || !end || start > end) return []

  const dates = []
  let cursor = getPeriodStartDate(start, period)
  const endBucket = getPeriodStartDate(end, period)
  while (cursor <= endBucket) {
    dates.push(formatDateString(cursor))
    cursor = addPeriod(cursor, period)
  }
  return dates
}

function formatDateTick(value, period) {
  if (typeof value !== "string") return value
  if (period === "month") return value.slice(0, 7).replace("-", ".")
  if (period === "week") return `${value.slice(5).replace("-", "/")} 주`
  return value.slice(5).replace("-", "/")
}

function buildChartRows(series, apps, range, period) {
  const topApps = apps.slice(0, 5)
  const topIds = new Set(topApps.map((app) => app.appId))
  const rows = new Map(
    buildDateKeys(range, period).map((date) => [
      date,
      Object.fromEntries([["date", date], ...topApps.map((app) => [app.appId, 0])]),
    ])
  )

  series
    .filter((row) => topIds.has(row.appId))
    .forEach((row) => {
      if (!rows.has(row.date)) {
        rows.set(row.date, Object.fromEntries([["date", row.date], ...topApps.map((app) => [app.appId, 0])]))
      }
      rows.get(row.date)[row.appId] = Number(row.accessCount) || 0
    })

  return Array.from(rows.values())
}

function KpiCard({ title, value, description, icon: Icon, isLoading }) {
  return (
    <Card className="h-full min-h-0 gap-0.5 rounded-lg px-3 py-1.5 shadow-none items-start justify-start p-4 gap-2">
      <div className="flex min-w-0 items-start justify-between gap-2">
        <span className="truncate text-xs font-medium leading-none text-muted-foreground">{title}</span>
        <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      </div>
      {isLoading ? (
        <Skeleton className="h-5 w-20" />
      ) : (
        <div className="truncate text-base font-semibold leading-5 tabular-nums tracking-tight">{value}</div>
      )}
      <p className="truncate text-[11px] leading-3 text-muted-foreground">{description}</p>
    </Card>
  )
}
function StatePanel({ icon: Icon, title, description, action }) {
  return (
    <div className="flex h-full min-h-64 items-center justify-center rounded-lg border bg-card p-8 text-center">
      <div className="grid max-w-md justify-items-center gap-3">
        <Icon className="size-8 text-muted-foreground" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold">{title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        {action}
      </div>
    </div>
  )
}

function hasPreviewErrors(preview) {
  if (!preview) return false
  if (Array.isArray(preview.errors) && preview.errors.length > 0) return true
  return preview.rows?.some((row) => row.errors?.length > 0) ?? false
}

function ManualPastePanel({ onCommitted }) {
  const [pastedText, setPastedText] = useState("")
  const [sourceName, setSourceName] = useState("manual")
  const [preview, setPreview] = useState(null)
  const previewMutation = useManualAppAccessPreviewMutation({
    onSuccess: (payload) => setPreview(payload),
  })
  const commitMutation = useManualAppAccessCommitMutation({
    onSuccess: (payload) => {
      setPreview(payload)
      onCommitted?.()
    },
  })

  const errorPreview = commitMutation.error?.payload?.preview ?? null
  const visiblePreview = errorPreview ?? preview
  const previewHasErrors = hasPreviewErrors(visiblePreview)
  const previewRows = visiblePreview?.rows ?? []
  const canPreview = pastedText.trim().length > 0 && !previewMutation.isPending
  const canCommit =
    pastedText.trim().length > 0 &&
    visiblePreview &&
    previewRows.length > 0 &&
    !previewHasErrors &&
    !commitMutation.isPending

  function handlePreview() {
    previewMutation.mutate({ pastedText, sourceName })
  }

  function handleCommit() {
    commitMutation.mutate({ pastedText, sourceName })
  }

  function handleTextChange(value) {
    setPastedText(value)
    setPreview(null)
    previewMutation.reset()
    commitMutation.reset()
  }

  function handlePaste(event) {
    const nextText = event.clipboardData?.getData("text") ?? ""
    if (!nextText.trim()) return

    event.preventDefault()
    handleTextChange(nextText)
    previewMutation.mutate({ pastedText: nextText, sourceName })
  }

  return (
    <div className="grid gap-4">
      {visiblePreview ? (
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge variant={previewHasErrors ? "destructive" : "secondary"}>
            오류 {formatNumber(visiblePreview.summary?.errorRows)}
          </Badge>
          <Badge variant="outline">유효 {formatNumber(visiblePreview.summary?.validRows)}행</Badge>
        </div>
      ) : null}

      <div className="rounded-lg border bg-card">
        <div className="grid gap-4 p-4">
          <div className="grid gap-4 lg:grid-cols-[220px,1fr]">
            <div className="grid content-start gap-2">
              <Label htmlFor="manual-source-name">출처</Label>
              <Input
                id="manual-source-name"
                value={sourceName}
                onChange={(event) => {
                  setSourceName(event.target.value)
                  setPreview(null)
                  previewMutation.reset()
                  commitMutation.reset()
                }}
                placeholder="manual"
              />
              <p className="text-xs leading-5 text-muted-foreground">
                같은 앱/날짜/출처는 기존 값을 덮어씁니다.
              </p>
            </div>
            <div className="grid min-w-0 gap-2">
              <Label htmlFor="manual-paste-text">붙여넣기 데이터</Label>
              <Textarea
                id="manual-paste-text"
                value={pastedText}
                onChange={(event) => handleTextChange(event.target.value)}
                onPaste={handlePaste}
                placeholder={buildManualPasteSample()}
                className="min-h-28 font-mono text-xs"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              필수 컬럼: date, appName, accessCount, uniqueUserCount
            </p>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" onClick={downloadManualTemplateCsv}>
                <Download className="size-4" />
                템플릿 CSV
              </Button>
              <Button type="button" variant="outline" onClick={handlePreview} disabled={!canPreview}>
                <ClipboardPaste className={cn("size-4", previewMutation.isPending && "animate-pulse")} />
                미리보기
              </Button>
              <Button type="button" onClick={handleCommit} disabled={!canCommit}>
                <CheckCircle2 className="size-4" />
                반영
              </Button>
            </div>
          </div>

          {previewMutation.error ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {previewMutation.error.message}
            </div>
          ) : null}
          {commitMutation.error ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {commitMutation.error.message}
            </div>
          ) : null}
          {commitMutation.data?.commit ? (
            <div className="rounded-md border bg-muted px-3 py-2 text-sm text-muted-foreground">
              신규 {formatNumber(commitMutation.data.commit.createdRows)}건, 수정{" "}
              {formatNumber(commitMutation.data.commit.updatedRows)}건을 반영했습니다.
            </div>
          ) : null}

          {visiblePreview?.errors?.length ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {visiblePreview.errors.join(", ")}
            </div>
          ) : null}

          {visiblePreview ? (
            <div className="min-h-0 min-w-0 overflow-auto rounded-md border">
              <Table>
                <TableHeader className="bg-card">
                  <TableRow>
                    <TableHead className="w-16 px-4">행</TableHead>
                    <TableHead>날짜</TableHead>
                    <TableHead>앱</TableHead>
                    <TableHead className="text-right">접속횟수</TableHead>
                    <TableHead className="text-right">접속 사용자</TableHead>
                    <TableHead>상태</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previewRows.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                        미리보기할 데이터 행이 없습니다.
                      </TableCell>
                    </TableRow>
                  ) : (
                    previewRows.map((row) => {
                      const rowHasErrors = row.errors?.length > 0
                      return (
                        <TableRow key={row.rowNumber}>
                          <TableCell className="px-4 text-muted-foreground tabular-nums">
                            {row.rowNumber}
                          </TableCell>
                          <TableCell className="tabular-nums">{row.values?.date || "-"}</TableCell>
                          <TableCell>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">{row.values?.appName || "-"}</p>
                              <p className="text-xs text-muted-foreground">{row.values?.appId || "-"}</p>
                            </div>
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatNumber(row.values?.accessCount)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatNumber(row.values?.uniqueUserCount)}
                          </TableCell>
                          <TableCell>
                            {rowHasErrors ? (
                              <span className="text-sm text-destructive">{row.errors.join(", ")}</span>
                            ) : (
                              <Badge variant="secondary">정상</Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      )
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function AccessDateSlider({ value, onChange }) {
  const normalizedValue = clampAccessDateOffset(value)
  const [draftValue, setDraftValue] = useState(normalizedValue)
  const selectedDate = getKstDateString(draftValue)
  const selectedLabel = formatAccessDateOffsetLabel(draftValue)

  useEffect(() => {
    setDraftValue(normalizedValue)
  }, [normalizedValue])

  function handleValueChange(nextValue) {
    setDraftValue(clampAccessDateOffset(nextValue[0]))
  }

  function handleValueCommit(nextValue) {
    const nextOffset = clampAccessDateOffset(nextValue[0])
    setDraftValue(nextOffset)
    onChange?.(nextOffset)
  }

  return (
    <div className="flex h-9 min-w-[252px] max-w-[420px] flex-1 items-center gap-2 rounded-md border-border bg-card px-2">
      <span className="mt-5 shrink-0 text-[11px] text-muted-foreground">-365일</span>
      <div className="relative min-w-[120px] flex-1 pt-5">
        <span className="absolute left-1/2 top-0 -translate-x-1/2 whitespace-nowrap text-[11px] font-medium text-muted-foreground">
          {selectedDate} ({selectedLabel})
        </span>
        <Slider
          className="[&>span:first-child]:h-2 [&>span:first-child]:bg-primary [&>span:first-child>span]:bg-muted [&_[role=slider]]:size-3 [&_[role=slider]]:shadow-sm"
          min={MIN_ACCESS_DATE_OFFSET_DAYS}
          max={MAX_ACCESS_DATE_OFFSET_DAYS}
          step={1}
          value={[draftValue]}
          onValueChange={handleValueChange}
          onValueCommit={handleValueCommit}
          aria-label="접속 통계 날짜 선택"
        />
      </div>
      <span className="mt-5 shrink-0 text-[11px] text-muted-foreground">오늘</span>
    </div>
  )
}

function ChartPanel({
  apps,
  chartRows,
  isLoading,
  error,
  period,
  dateOffset,
  onDateOffsetChange,
  periodKey,
  onPeriodChange,
}) {
  const [hiddenAppIds, setHiddenAppIds] = useState(() => new Set())
  const chartApps = apps.slice(0, 5)
  const visibleChartApps = chartApps.filter((app) => !hiddenAppIds.has(app.appId))
  const chartConfig = Object.fromEntries(
    chartApps.map((app, index) => [
      app.appId,
      { label: app.appName, color: CHART_COLORS[index % CHART_COLORS.length] },
    ])
  )

  function toggleChartApp(appId) {
    setHiddenAppIds((current) => {
      const next = new Set(current)
      if (next.has(appId)) {
        next.delete(appId)
      } else {
        next.add(appId)
      }
      return next
    })
  }

  return (
    <Card className="flex h-full min-h-0 min-w-0 flex-col gap-0 overflow-hidden rounded-lg py-0 shadow-none">
      <div className="flex h-12 shrink-0 items-center border-b px-4">
        <div className="flex w-full min-w-0 items-center justify-between gap-3">
          <CardTitle className="flex self-stretch items-center text-sm font-semibold leading-none">
            앱별 접속 추이
          </CardTitle>
          <div className="flex shrink-0 items-center gap-2">
            <AccessDateSlider value={dateOffset} onChange={onDateOffsetChange} />
            <div className="flex items-center rounded-md border bg-background p-0.5">
              {PERIOD_OPTIONS.map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  size="sm"
                  variant={periodKey === option.key ? "default" : "ghost"}
                  className="h-6 px-2 text-xs"
                  onClick={() => onPeriodChange(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </div>
      <CardContent className="min-h-0 flex-1 px-4 py-2">
        {isLoading ? (
          <div className="grid h-full min-h-72 gap-3">
            <Skeleton className="h-full min-h-64 w-full" />
          </div>
        ) : error ? (
          <StatePanel
            icon={AlertTriangle}
            title="차트를 불러오지 못했습니다."
            description={error.message || "접속 통계 요청 중 오류가 발생했습니다."}
          />
        ) : chartRows.length === 0 || chartApps.length === 0 ? (
          <StatePanel
            icon={BarChart3}
            title="접속 기록이 없습니다."
            description="선택한 기간에 기록된 앱 접속 이벤트가 없습니다."
          />
        ) : (
          <div className="flex h-full min-h-72 min-w-0 gap-4">
            <ChartContainer config={chartConfig} className="h-full min-h-0 min-w-0 flex-1">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartRows}
                  margin={{ top: 16, right: 16, left: 0, bottom: 28 }}
                  barCategoryGap="24%"
                >
                  <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => formatDateTick(value, period)}
                    tickLine={false}
                    axisLine={{ stroke: "var(--border)" }}
                    tick={{ fontSize: 12 }}
                    angle={-45}
                    textAnchor="end"
                    tickMargin={6}
                    height={44}
                    minTickGap={16}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={{ stroke: "var(--border)" }}
                    tick={{ fontSize: 12 }}
                    tickMargin={6}
                    allowDecimals={false}
                    width={52}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  {visibleChartApps.map((app) => {
                    const colorIndex = chartApps.findIndex((item) => item.appId === app.appId)
                    return (
                      <Bar
                        key={app.appId}
                        dataKey={app.appId}
                        name={app.appName}
                        stackId="access"
                        fill={CHART_COLORS[colorIndex % CHART_COLORS.length]}
                        maxBarSize={44}
                      />
                    )
                  })}
                </BarChart>
              </ResponsiveContainer>
            </ChartContainer>
            <div className="flex w-40 shrink-0 flex-col justify-center gap-2">
              {chartApps.map((app, index) => {
                const isHidden = hiddenAppIds.has(app.appId)
                return (
                  <button
                    key={app.appId}
                    type="button"
                    className={cn(
                      "flex min-w-0 items-center gap-2 rounded-sm text-left text-xs text-muted-foreground outline-none transition-opacity hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
                      isHidden && "opacity-40"
                    )}
                    onClick={() => toggleChartApp(app.appId)}
                    aria-pressed={!isHidden}
                  >
                    <span
                      className={cn("size-2.5 shrink-0 rounded-full", CHART_BG_CLASSES[index % CHART_BG_CLASSES.length])}
                      aria-hidden="true"
                    />
                    <span className="truncate whitespace-nowrap">{app.appName}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AppTable({ apps, isLoading }) {
  return (
    <Card className="flex h-full min-h-0 min-w-0 flex-col gap-0 overflow-hidden rounded-lg py-0 shadow-none">
      <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b px-4">
        <CardTitle className="text-sm font-semibold">앱별 접속 순위 및 상세 현황</CardTitle>
        <Badge variant="secondary" className="h-5 px-1.5 py-0 text-[11px]">
          {formatNumber(apps.length)} apps
        </Badge>
      </div>
      <CardContent className="flex min-h-0 min-w-0 flex-1 flex-col items-stretch justify-start overflow-auto px-0 py-0">
        {isLoading ? (
          <div className="grid gap-2 p-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-9 w-full" />
            ))}
          </div>
        ) : (
          <Table className="table-fixed">
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow className="hover:bg-transparent">
                <TableHead className="h-12 w-1/2 px-4 text-left">앱명</TableHead>
                <TableHead className="h-12 w-1/4 text-center">출처</TableHead>
                <TableHead className="h-12 w-1/4 px-4 text-center">접속횟수</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {apps.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="h-32 text-center text-muted-foreground">
                    선택한 기간에 접속 기록이 없습니다.
                  </TableCell>
                </TableRow>
              ) : (
                apps.map((app, index) => (
                  <TableRow key={app.appId}>
                    <TableCell className="w-1/2 px-4">
                      <div className="flex min-w-0 items-center gap-2">
                        <span
                          className={cn(
                            "inline-flex size-6 shrink-0 items-center justify-center rounded-md border bg-muted text-xs font-medium tabular-nums",
                            index < 3 && "border-primary/30 bg-primary/10 text-primary"
                          )}
                        >
                          {index + 1}
                        </span>
                        <span className="min-w-0 truncate font-medium">{app.appName}</span>
                      </div>
                    </TableCell>
                    <TableCell className="w-1/4 text-center">
                      <Badge variant={app.sourceType === "manual" ? "outline" : "secondary"}>
                        {formatSourceLabel(app)}
                      </Badge>
                    </TableCell>
                    <TableCell className="w-1/4 px-4 text-center tabular-nums">
                      {formatNumber(app.accessCount)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

function KpiActionCard({ onManualInput, onExternalSync, canManualInput, isSyncing, syncLabel }) {
  return (
    <Card className="h-full min-h-0 justify-center gap-2 rounded-lg px-3 py-2 shadow-none">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-8 justify-start text-[11px]"
        onClick={onManualInput}
        disabled={!canManualInput}
      >
        <FileSpreadsheet className="size-4" />
        외부 앱 수동입력
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-8 justify-start text-[11px]"
        onClick={onExternalSync}
        disabled={isSyncing}
      >
        <RefreshCw className={cn("size-4", isSyncing && "animate-spin")} />
        {syncLabel}
      </Button>
    </Card>
  )
}

export function AccessStatsPage() {
  const { user } = useAuth()
  const [dateOffset, setDateOffset] = useState(DEFAULT_ACCESS_DATE_OFFSET_DAYS)
  const [periodKey, setPeriodKey] = useState("day")
  const [isManualDialogOpen, setIsManualDialogOpen] = useState(false)
  const params = useMemo(
    () => buildStatsParams(buildRangeFromOffset(dateOffset), periodKey),
    [dateOffset, periodKey]
  )
  const statsQuery = useAppAccessStatsQuery(params, { enabled: Boolean(user) })
  const externalSyncMutation = useExternalAppUsageSyncMutation()
  const payload = statsQuery.data
  const summary = payload?.summary ?? {}
  const responsePeriod = payload?.period || periodKey
  const apps = useMemo(() => (Array.isArray(payload?.apps) ? payload.apps : []), [payload?.apps])
  const series = useMemo(() => (Array.isArray(payload?.series) ? payload.series : []), [payload?.series])
  const chartRows = useMemo(
    () => buildChartRows(series, apps, params, responsePeriod),
    [apps, params, responsePeriod, series]
  )
  const externalSyncLabel = externalSyncMutation.data?.skipped
    ? "최근 동기화됨"
    : externalSyncMutation.data?.synced
      ? "동기화 완료"
      : "외부 API 동기화"

  if (!user) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6">
        <StatePanel
          icon={ShieldAlert}
          title="로그인이 필요합니다."
          description="접속 현황은 로그인 후 볼 수 있습니다."
        />
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-muted/30">
      <Dialog open={isManualDialogOpen} onOpenChange={setIsManualDialogOpen}>
        <DialogContent className="max-h-[88vh] max-w-5xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>외부 앱 수동 입력</DialogTitle>
            <DialogDescription>
              엑셀/스프레드시트에서 헤더 포함 영역을 복사해 붙여넣고 미리보기 후 반영합니다.
            </DialogDescription>
          </DialogHeader>
          <ManualPastePanel onCommitted={() => statsQuery.refetch()} />
        </DialogContent>
      </Dialog>

      <main className="flex-1 min-h-0 min-w-0 overflow-y-auto px-6 py-4">
        <div className="grid min-h-full min-w-0 grid-cols-4 gap-4">
          <section className="col-span-3 flex min-h-0 min-w-0 flex-col gap-4">
            <div className="grid h-24 shrink-0 grid-cols-7 gap-4">
              <div className="col-span-2 min-w-0">
                <KpiCard
                  title="전체 앱 개수"
                  value={formatNumber(summary.activeAppCount)}
                  description="접속 기록이 있는 앱"
                  icon={Layers3}
                  isLoading={statsQuery.isLoading}
                />
              </div>
              <div className="col-span-2 min-w-0">
                <KpiCard
                  title="전체 접속횟수"
                  value={formatNumber(summary.totalAccessCount)}
                  description={formatStatsRangeLabel(params)}
                  icon={TrendingUp}
                  isLoading={statsQuery.isLoading}
                />
              </div>
              <div className="col-span-2 min-w-0">
                <KpiCard
                  title="최다 접속 앱"
                  value={summary.topApp?.appName || "-"}
                  description={
                    summary.topApp
                      ? `${formatNumber(summary.topApp.accessCount)}회`
                      : "접속 기록 없음"
                  }
                  icon={CalendarDays}
                  isLoading={statsQuery.isLoading}
                />
              </div>
              <div className="col-span-1 min-w-0">
                <KpiActionCard
                  onManualInput={() => setIsManualDialogOpen(true)}
                  onExternalSync={() => externalSyncMutation.mutate()}
                  canManualInput={Boolean(user?.is_superuser)}
                  isSyncing={externalSyncMutation.isPending}
                  syncLabel={externalSyncLabel}
                />
              </div>
            </div>

            {statsQuery.error ? (
              <StatePanel
                icon={AlertTriangle}
                title="접속 통계를 불러오지 못했습니다."
                description={statsQuery.error.message || "잠시 후 다시 시도하세요."}
                action={
                  <Button type="button" variant="outline" onClick={() => statsQuery.refetch()}>
                    <RefreshCw className="size-4" />
                    다시 시도
                  </Button>
                }
              />
            ) : (
              <div className="min-h-0 min-w-0 flex-1">
                <ChartPanel
                  apps={apps}
                  chartRows={chartRows}
                  isLoading={statsQuery.isLoading}
                  error={statsQuery.error}
                  period={responsePeriod}
                  dateOffset={dateOffset}
                  onDateOffsetChange={setDateOffset}
                  periodKey={periodKey}
                  onPeriodChange={setPeriodKey}
                />
              </div>
            )}
          </section>

          <section className="col-span-1 min-h-[420px] min-w-0">
            <AppTable apps={apps} isLoading={statsQuery.isLoading} />
          </section>
        </div>
      </main>
    </div>
  )
}
