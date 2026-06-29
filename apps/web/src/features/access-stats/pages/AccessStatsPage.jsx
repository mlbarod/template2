import { useMemo, useState } from "react"
import {
  AlertTriangle,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  ClipboardPaste,
  FileSpreadsheet,
  Layers3,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
  Users,
} from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
  useManualAppAccessCommitMutation,
  useManualAppAccessPreviewMutation,
} from "../hooks/useAccessStatsQueries"

const RANGE_OPTIONS = [
  { key: "today", label: "오늘", days: 1 },
  { key: "7d", label: "7일", days: 7 },
  { key: "30d", label: "30일", days: 30 },
]

const PERIOD_OPTIONS = [
  { key: "day", label: "일별" },
  { key: "week", label: "주별" },
  { key: "month", label: "월별" },
]

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

const MANUAL_PASTE_SAMPLE =
  "date\tapp_id\tapp_name\taccess_count\tunique_user_count\tmemo\n" +
  "2026-06-29\texternal-foo\t외부 Foo\t120\t55\t외부 서버 리포트 기준"

function getKstDateString(offsetDays = 0) {
  const now = new Date()
  const kst = new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60 * 1000)
  kst.setDate(kst.getDate() + offsetDays)
  const year = kst.getFullYear()
  const month = String(kst.getMonth() + 1).padStart(2, "0")
  const day = String(kst.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function buildRange(days) {
  const to = getKstDateString()
  const from = getKstDateString(-(days - 1))
  return { from, to }
}

function buildStatsParams(range, period) {
  return { ...range, period }
}

function formatNumber(value) {
  return new Intl.NumberFormat("ko-KR").format(Number(value) || 0)
}

function formatAverage(value) {
  return new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: 1,
  }).format(Number(value) || 0)
}

function formatDateTime(value) {
  if (!value) return "-"
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value))
}

function formatSourceLabel(app) {
  if (app?.sourceType === "internal") return "내부"
  if (app?.sourceType === "manual") return "수동"
  if (app?.sourceType === "mixed") return "복합"
  return app?.sourceName || "-"
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
    <Card className="gap-3 rounded-lg py-4 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between gap-3 px-4 py-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
      </CardHeader>
      <CardContent className="px-4">
        {isLoading ? (
          <Skeleton className="h-8 w-28" />
        ) : (
          <div className="text-2xl font-semibold tabular-nums tracking-tight">{value}</div>
        )}
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      </CardContent>
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
                onChange={(event) => {
                  setPastedText(event.target.value)
                  setPreview(null)
                  previewMutation.reset()
                  commitMutation.reset()
                }}
                placeholder={MANUAL_PASTE_SAMPLE}
                className="min-h-28 font-mono text-xs"
              />
            </div>
          </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            필수 컬럼: date, app_id, access_count, unique_user_count
          </p>
          <div className="flex items-center gap-2">
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

function ChartPanel({ apps, chartRows, isLoading, error, period }) {
  const chartApps = apps.slice(0, 5)
  const chartConfig = Object.fromEntries(
    chartApps.map((app, index) => [
      app.appId,
      { label: app.appName, color: CHART_COLORS[index % CHART_COLORS.length] },
    ])
  )

  return (
    <Card className="grid h-full min-h-0 min-w-0 grid-rows-[auto,1fr] gap-0 overflow-hidden rounded-lg py-0 shadow-none">
      <CardHeader className="border-b px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm font-semibold">앱별 접속 추이</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{PERIOD_OPTIONS.find((option) => option.key === period)?.label ?? "일별"}</Badge>
            <Badge variant="outline">Top {Math.min(apps.length, 5)}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 px-4 py-4">
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
          <ChartContainer config={chartConfig} className="h-full min-h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartRows}
                margin={{ top: 16, right: 16, left: 0, bottom: 8 }}
                barCategoryGap="24%"
              >
                <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(value) => formatDateTick(value, period)}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border)" }}
                  tickMargin={8}
                  minTickGap={16}
                />
                <YAxis
                  tickLine={false}
                  axisLine={{ stroke: "var(--border)" }}
                  tickMargin={8}
                  allowDecimals={false}
                  width={52}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Legend verticalAlign="top" height={28} iconType="circle" />
                {chartApps.map((app, index) => (
                  <Bar
                    key={app.appId}
                    dataKey={app.appId}
                    name={app.appName}
                    stackId="access"
                    fill={CHART_COLORS[index % CHART_COLORS.length]}
                    maxBarSize={44}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  )
}

function AppTable({ apps, isLoading }) {
  return (
    <Card className="grid h-full min-h-0 min-w-0 grid-rows-[auto,1fr] gap-0 overflow-hidden rounded-lg py-0 shadow-none">
      <CardHeader className="border-b px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm font-semibold">앱별 접속 순위 및 상세 현황</CardTitle>
          <Badge variant="secondary">{formatNumber(apps.length)} apps</Badge>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 min-w-0 overflow-auto px-0 py-0">
        {isLoading ? (
          <div className="grid gap-2 p-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-9 w-full" />
            ))}
          </div>
        ) : (
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow>
                <TableHead className="w-20 px-4">순위</TableHead>
                <TableHead className="px-4">앱명</TableHead>
                <TableHead>출처</TableHead>
                <TableHead className="text-right">접속횟수</TableHead>
                <TableHead className="text-right">접속 사용자</TableHead>
                <TableHead className="text-right">사용자당 평균</TableHead>
                <TableHead className="px-4 text-right">마지막 접속</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {apps.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    선택한 기간에 접속 기록이 없습니다.
                  </TableCell>
                </TableRow>
              ) : (
                apps.map((app, index) => (
                  <TableRow key={app.appId}>
                    <TableCell className="px-4">
                      <span
                        className={cn(
                          "inline-flex size-7 items-center justify-center rounded-md border bg-muted text-xs font-medium tabular-nums",
                          index < 3 && "border-primary/30 bg-primary/10 text-primary"
                        )}
                      >
                        {index + 1}
                      </span>
                    </TableCell>
                    <TableCell className="px-4 font-medium">{app.appName}</TableCell>
                    <TableCell>
                      <Badge variant={app.sourceType === "manual" ? "outline" : "secondary"}>
                        {formatSourceLabel(app)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(app.accessCount)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(app.uniqueUserCount)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatAverage(app.avgAccessPerUser)}</TableCell>
                    <TableCell className="px-4 text-right tabular-nums text-muted-foreground">
                      {formatDateTime(app.lastAccessedAt)}
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

export function AccessStatsPage() {
  const { user } = useAuth()
  const [rangeKey, setRangeKey] = useState("7d")
  const [periodKey, setPeriodKey] = useState("day")
  const [isManualDialogOpen, setIsManualDialogOpen] = useState(false)
  const selectedRange = RANGE_OPTIONS.find((option) => option.key === rangeKey) ?? RANGE_OPTIONS[1]
  const params = useMemo(
    () => buildStatsParams(buildRange(selectedRange.days), periodKey),
    [periodKey, selectedRange.days]
  )
  const statsQuery = useAppAccessStatsQuery(params, { enabled: Boolean(user?.is_superuser) })
  const payload = statsQuery.data
  const summary = payload?.summary ?? {}
  const responsePeriod = payload?.period || periodKey
  const apps = useMemo(() => (Array.isArray(payload?.apps) ? payload.apps : []), [payload?.apps])
  const series = useMemo(() => (Array.isArray(payload?.series) ? payload.series : []), [payload?.series])
  const chartRows = useMemo(
    () => buildChartRows(series, apps, params, responsePeriod),
    [apps, params, responsePeriod, series]
  )

  if (!user?.is_superuser) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6">
        <StatePanel
          icon={ShieldAlert}
          title="접속 통계 권한이 없습니다."
          description="이 화면은 슈퍼유저만 볼 수 있습니다."
        />
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-muted/30">
      <header className="shrink-0 border-b bg-card px-6 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">앱별 접속 현황</h1>
              <Badge variant="outline">KST</Badge>
              <Badge variant="secondary">Superuser</Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              내부 앱 화면 진입 이벤트와 외부 앱 수동 입력 집계를 기준으로 앱별 접속횟수를 집계합니다.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={() => setIsManualDialogOpen(true)}>
              <FileSpreadsheet className="size-4" />
              외부 앱 수동입력
            </Button>
            <div className="flex items-center rounded-md border bg-background p-1">
              {RANGE_OPTIONS.map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  size="sm"
                  variant={rangeKey === option.key ? "default" : "ghost"}
                  className="h-8"
                  onClick={() => setRangeKey(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
            <div className="flex items-center rounded-md border bg-background p-1">
              {PERIOD_OPTIONS.map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  size="sm"
                  variant={periodKey === option.key ? "default" : "ghost"}
                  className="h-8"
                  onClick={() => setPeriodKey(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => statsQuery.refetch()}
              disabled={statsQuery.isFetching}
            >
              <RefreshCw className={cn("size-4", statsQuery.isFetching && "animate-spin")} />
              새로고침
            </Button>
          </div>
        </div>
      </header>

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
        <div className="grid min-h-full grid-rows-[auto,minmax(360px,0.8fr),minmax(300px,0.7fr)] gap-4">
          <section className="grid grid-cols-4 gap-4">
            <KpiCard
              title="전체 접속횟수"
              value={formatNumber(summary.totalAccessCount)}
              description={`${params.from} ~ ${params.to}`}
              icon={TrendingUp}
              isLoading={statsQuery.isLoading}
            />
            <KpiCard
              title="접속 사용자"
              value={formatNumber(summary.uniqueUserCount)}
              description="knox_id 기준 중복 제거"
              icon={Users}
              isLoading={statsQuery.isLoading}
            />
            <KpiCard
              title="접속 앱 수"
              value={formatNumber(summary.activeAppCount)}
              description="접속 기록이 있는 앱"
              icon={Layers3}
              isLoading={statsQuery.isLoading}
            />
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
          </section>

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
            <section className="min-h-0 min-w-0">
              <ChartPanel
                apps={apps}
                chartRows={chartRows}
                isLoading={statsQuery.isLoading}
                error={statsQuery.error}
                period={responsePeriod}
              />
            </section>
          )}

          <section className="min-h-0 min-w-0">
            <AppTable apps={apps} isLoading={statsQuery.isLoading} />
          </section>
        </div>
      </main>
    </div>
  )
}
