// src/features/line-dashboard/components/LineHistoryDashboard.jsx
import * as React from "react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts"
import { IconAlertCircle, IconRefresh } from "@tabler/icons-react"
import { CalendarIcon, FilterIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { DateRangeCalendar } from "@/components/common"
import { cn } from "@/lib/utils"
import { timeFormatter } from "../utils/formatters"
import { useLineHistoryData } from "../hooks/useLineHistoryData"

const DIMENSION_OPTIONS = [
  { value: "sdwt_prod", label: "SDWT Prod" },
  { value: "process", label: "Process" },
  { value: "main_step", label: "Step" },
  { value: "ppid", label: "PPID" },
  { value: "sdwt", label: "SDWT" },
  { value: "user_sdwt", label: "User SDWT" },
]

const DIMENSION_LABELS = DIMENSION_OPTIONS.reduce(
  (labels, option) => ({ ...labels, [option.value]: option.label }),
  {}
)

// API에서 넘어오는 컬럼명이 화면 옵션과 다른 경우를 보정하기 위한 매핑
const DIMENSION_ALIASES = {
  process: ["proc_id"],
  user_sdwt: ["user_sdwt_prod"],
  sdwt: ["sdwt_prod", "user_sdwt_prod"],
}

const METRIC_OPTIONS = [
  { value: "rowCount", label: "진행 건수" },
  { value: "sendJiraCount", label: "Send Jira" },
]

const METRIC_LABELS = METRIC_OPTIONS.reduce(
  (labels, option) => ({ ...labels, [option.value]: option.label }),
  {}
)

const BIN_OPTIONS = [
  { value: "hour", label: "시간별" },
  { value: "day", label: "일별" },
  { value: "week", label: "주별" },
  { value: "month", label: "월별" },
]

const BIN_LABELS = BIN_OPTIONS.reduce(
  (labels, option) => ({ ...labels, [option.value]: option.label }),
  {}
)

const DEFAULT_BIN = BIN_OPTIONS[0].value
const MS_PER_DAY = 24 * 60 * 60 * 1000
const KST_OFFSET = "+09:00"

const CATEGORY_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--primary)",
  "var(--secondary)",
  "var(--accent)",
  "var(--muted-foreground)",
  "var(--foreground)",
]

const GRID_STROKE = "var(--border)" // 테마 토큰 기반 선 색상
const GRID_OPACITY = 0.65
const LEGEND_PRESET_COLORS = [
  ...CATEGORY_COLORS,
  "var(--primary-foreground)",
  "var(--secondary-foreground)",
]
const THEME_LINE_COLOR = "var(--primary)"

const LABELS = {
  titleSuffix: "Line E-SOP History",
  updated: "Updated",
}

const totalsChartConfig = {
  rowCount: { label: "진행 건수", color: "var(--chart-1)" },
  sendJiraCount: { label: "Send Jira", color: "var(--chart-2)" },
}

// KST 기준, 2자리 연도 포맷터
const KST_FORMATTER = new Intl.DateTimeFormat("ko-KR", {
  year: "2-digit",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  hour12: false,
  timeZone: "Asia/Seoul",
})

const KST_PARTS_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  hour12: false,
})

const KST_DATE_LABEL_FORMATTER = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  month: "2-digit",
  day: "2-digit",
})

const KST_YEAR_MONTH_FORMATTER = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "2-digit",
  month: "2-digit",
})

const KST_FULL_DATE_FORMATTER = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "2-digit",
  month: "2-digit",
  day: "2-digit",
})

function parseDateTime(value) {
  if (!value) return null
  if (value instanceof Date) return value

  const normalized =
    typeof value === "string" && value.includes("T")
      ? value
      : typeof value === "string"
        ? value.replace(" ", "T")
        : String(value)

  const parsed = new Date(normalized)
  return Number.isFinite(parsed.getTime()) ? parsed : null
}

// X축 라벨용 (MM/DD HH:00)
function formatKstDateTimeLabel(value) {
  const date = parseDateTime(value)
  if (!date) return typeof value === "string" ? value : String(value ?? "")

  const parts = Object.fromEntries(
    KST_FORMATTER.formatToParts(date).map((part) => [part.type, part.value]),
  )
  const month = parts.month ?? ""
  const day = parts.day ?? ""
  const hour = parts.hour ?? ""

  return `${month}/${day} ${hour}:00`
}

// Tooltip 라벨용 (yy/mm/dd HH:00)
function formatKstTooltipTime(value) {
  const date = parseDateTime(value)
  if (!date) return typeof value === "string" ? value : String(value ?? "")

  const parts = Object.fromEntries(
    KST_FORMATTER.formatToParts(date).map((part) => [part.type, part.value]),
  )

  const year = parts.year ?? "" // "25" 같은 2자리 연도
  const month = parts.month ?? ""
  const day = parts.day ?? ""
  const hour = parts.hour ?? ""

  // yy/mm/dd 23:00 형식
  return `${year}/${month}/${day} ${hour}:00`
}

function pad2(value) {
  return String(value ?? "").padStart(2, "0")
}

function getKstParts(value) {
  const date = parseDateTime(value)
  if (!date) return null

  const parts = Object.fromEntries(
    KST_PARTS_FORMATTER.formatToParts(date).map((part) => [part.type, part.value]),
  )

  const year = Number(parts.year)
  const month = Number(parts.month)
  const day = Number(parts.day)
  const hour = Number(parts.hour)

  if (![year, month, day, hour].every((value) => Number.isFinite(value))) return null
  return { year, month, day, hour }
}

function buildKstIsoDate({ year, month, day, hour = 0 }) {
  return `${year}-${pad2(month)}-${pad2(day)}T${pad2(hour)}:00:00${KST_OFFSET}`
}

function getBucketInfo(value, bin = DEFAULT_BIN) {
  const parts = getKstParts(value)
  if (!parts) return null

  let { year, month, day, hour } = parts
  let startHour = bin === "hour" ? hour : 0

  if (bin === "week") {
    const baseDate = new Date(Date.UTC(year, month - 1, day))
    const dayOfWeek = baseDate.getUTCDay() // 0=Sunday
    const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek
    baseDate.setUTCDate(baseDate.getUTCDate() + diffToMonday)
    year = baseDate.getUTCFullYear()
    month = baseDate.getUTCMonth() + 1
    day = baseDate.getUTCDate()
  } else if (bin === "month") {
    day = 1
  }

  const bucketDate = buildKstIsoDate({ year, month, day, hour: startHour })
  const startDate = parseDateTime(bucketDate)
  if (!startDate) return null

  let endDate = startDate
  if (bin === "week") {
    endDate = new Date(startDate.getTime() + 6 * MS_PER_DAY)
  } else if (bin === "month") {
    const daysInMonth = new Date(year, month, 0).getDate()
    const endDateString = buildKstIsoDate({
      year,
      month,
      day: daysInMonth,
      hour: startHour,
    })
    endDate = parseDateTime(endDateString) ?? startDate
  }

  return { key: bucketDate, startDate, endDate }
}

const METRIC_KEYS = METRIC_OPTIONS.map((option) => option.value)

const sortByDateValue = (a, b) => {
  if (a?.date < b?.date) return -1
  if (a?.date > b?.date) return 1
  return 0
}

function aggregateTotalsByBin(records, bin = DEFAULT_BIN) {
  if (!Array.isArray(records)) return []
  if (bin === "hour") return [...records].sort(sortByDateValue)

  const bucketMap = new Map()
  for (const record of records) {
    const bucket = getBucketInfo(record?.date, bin)
    if (!bucket) continue
    const existing = bucketMap.get(bucket.key) ?? { date: bucket.key }
    for (const metricKey of METRIC_KEYS) {
      const value = Number(record?.[metricKey] ?? 0) || 0
      existing[metricKey] = (existing[metricKey] ?? 0) + value
    }
    bucketMap.set(bucket.key, existing)
  }

  return Array.from(bucketMap.keys())
    .sort()
    .map((key) => bucketMap.get(key))
}

function aggregateBreakdownRecordsByBin(records, bin = DEFAULT_BIN) {
  if (!Array.isArray(records)) return []
  if (bin === "hour") return [...records].sort(sortByDateValue)

  const bucketMap = new Map()

  for (const record of records) {
    const bucket = getBucketInfo(record?.date, bin)
    if (!bucket) continue
    const category =
      typeof record?.category === "string" && record.category.trim().length > 0
        ? record.category.trim()
        : "Unspecified"
    const bucketKey = `${bucket.key}__${category}`
    const existing = bucketMap.get(bucketKey) ?? {
      date: bucket.key,
      category,
    }

    for (const metricKey of METRIC_KEYS) {
      const value = Number(record?.[metricKey] ?? 0) || 0
      existing[metricKey] = (existing[metricKey] ?? 0) + value
    }

    bucketMap.set(bucketKey, existing)
  }

  return Array.from(bucketMap.values()).sort((a, b) => {
    if (a.date < b.date) return -1
    if (a.date > b.date) return 1
    return String(a.category).localeCompare(String(b.category))
  })
}

function aggregateBreakdownsByBin(breakdowns, bin = DEFAULT_BIN) {
  if (!breakdowns || typeof breakdowns !== "object") return {}
  if (bin === "hour") return breakdowns

  return Object.fromEntries(
    Object.entries(breakdowns).map(([dimensionKey, records]) => [
      dimensionKey,
      aggregateBreakdownRecordsByBin(records, bin),
    ]),
  )
}

function formatAxisLabelByBin(value, bin = DEFAULT_BIN) {
  if (bin === "hour") return formatKstDateTimeLabel(value)
  const bucket = getBucketInfo(value, bin)
  if (!bucket?.startDate) return typeof value === "string" ? value : String(value ?? "")

  if (bin === "day") {
    return KST_DATE_LABEL_FORMATTER.format(bucket.startDate)
  }

  if (bin === "week") {
    return `${KST_DATE_LABEL_FORMATTER.format(bucket.startDate)}~${KST_DATE_LABEL_FORMATTER.format(bucket.endDate)}`
  }

  if (bin === "month") {
    return KST_YEAR_MONTH_FORMATTER.format(bucket.startDate)
  }

  return formatKstDateTimeLabel(value)
}

function formatTooltipLabelByBin(value, bin = DEFAULT_BIN) {
  if (bin === "hour") return formatKstTooltipTime(value)
  const bucket = getBucketInfo(value, bin)
  if (!bucket?.startDate) return typeof value === "string" ? value : String(value ?? "")

  if (bin === "day") {
    return KST_FULL_DATE_FORMATTER.format(bucket.startDate)
  }

  if (bin === "week") {
    return `${KST_FULL_DATE_FORMATTER.format(bucket.startDate)} ~ ${KST_FULL_DATE_FORMATTER.format(bucket.endDate)}`
  }

  if (bin === "month") {
    const monthLabel = KST_YEAR_MONTH_FORMATTER.format(bucket.startDate)
    const rangeLabel = `${KST_DATE_LABEL_FORMATTER.format(bucket.startDate)}~${KST_DATE_LABEL_FORMATTER.format(bucket.endDate)}`
    return `${monthLabel} (${rangeLabel})`
  }

  return formatKstTooltipTime(value)
}

function getDefaultDateRange(days = 30) {
  const to = new Date()
  const from = new Date()
  from.setDate(to.getDate() - (Number.isFinite(days) ? days : 30) + 1)
  return { from, to }
}

function formatRangeLabel(range) {
  const { from, to } = range ?? {}
  if (!from || !to) return "날짜 범위 선택"
  const formatter = new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium" })
  return `${formatter.format(from)} ~ ${formatter.format(to)}`
}

/**
 * Tooltip 내용에서 label(시간)을 직접 포맷팅해 주는 래퍼
 */
function KstTooltipContent(props) {
  const { label, bin = DEFAULT_BIN, ...rest } = props
  const formattedLabel = formatTooltipLabelByBin(label, bin)
  return <ChartTooltipContent {...rest} label={formattedLabel} />
}

/**
 * 분류(차원)별 라인 시리즈 생성
 * - metrics.length === 1 인 경우: 레전드 라벨을 "카테고리 이름"만 사용 (지표는 차트 제목으로 구분)
 */
function buildBreakdownSeries(
  records,
  metrics,
  limit = 5,
  selectedCategories = [],
  dimensionKey = "",
  dimensionLabel = "",
  colorOverrides = {},
) {
  if (
    !Array.isArray(records) ||
    records.length === 0 ||
    !Array.isArray(metrics) ||
    metrics.length === 0
  ) {
    return { data: [], categories: [], config: {}, seriesKeys: [] }
  }

  // Recharts dataKey를 안전하게 만들기 위한 정규화
  const safeKeyCache = new Map()
  const getSafeKey = (raw) => {
    const key = String(raw ?? "")
    if (!safeKeyCache.has(key)) {
      const sanitized = key.replace(/[^A-Za-z0-9_-]/g, "_")
      if (sanitized && sanitized === key && sanitized.length <= 64) {
        safeKeyCache.set(key, sanitized)
      } else {
        const hash = Math.abs(
          Array.from(key).reduce(
            (acc, char) => (acc * 31 + char.charCodeAt(0)) | 0,
            0,
          ),
        ).toString(36)
        const trimmed = sanitized
          .slice(0, Math.max(12, 64 - hash.length - 1))
          .replace(/_+$/g, "")
        safeKeyCache.set(
          key,
          [trimmed || "series", hash].filter(Boolean).join("_"),
        )
      }
    }
    return safeKeyCache.get(key)
  }

  const totalsByCategory = new Map()
  const dateSet = new Set()
  const primaryMetric = metrics[0]

  for (const record of records) {
    const category =
      typeof record?.category === "string" && record.category.trim().length > 0
        ? record.category.trim()
        : "Unspecified"
    const value = Number(record?.[primaryMetric] ?? 0) || 0
    dateSet.add(record?.date)
    totalsByCategory.set(category, (totalsByCategory.get(category) ?? 0) + value)
  }

  const normalizedSelected = Array.isArray(selectedCategories)
    ? selectedCategories.filter(Boolean)
    : []

  let categories =
    normalizedSelected.length > 0
      ? normalizedSelected.filter((category) => totalsByCategory.has(category))
      : Array.from(totalsByCategory.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, limit)
        .map(([category]) => category)

  const sortedDates = Array.from(dateSet)
    .filter(Boolean)
    .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0))

  const seriesKeyMap = new Map()
  categories.forEach((category) => {
    metrics.forEach((metricKey) => {
      const rawKey = [dimensionKey || "dim", category, metricKey]
        .filter(Boolean)
        .join("__")
      seriesKeyMap.set(rawKey, getSafeKey(rawKey))
    })
  })

  const basePoints = sortedDates.map((date) => {
    const point = { date }
    for (const safeKey of seriesKeyMap.values()) {
      point[safeKey] = 0
    }
    return point
  })

  const pointsByDate = new Map(basePoints.map((point) => [point.date, point]))

  for (const record of records) {
    const category =
      typeof record?.category === "string" && record.category.trim().length > 0
        ? record.category.trim()
        : "Unspecified"
    if (!categories.includes(category)) continue

    const date = record?.date
    if (!date || !pointsByDate.has(date)) continue

    const point = pointsByDate.get(date)
    for (const metricKey of metrics) {
      const value = Number(record?.[metricKey] ?? 0) || 0
      const rawKey = [dimensionKey || "dim", category, metricKey]
        .filter(Boolean)
        .join("__")
      const safeKey = seriesKeyMap.get(rawKey) ?? getSafeKey(rawKey)
      point[safeKey] = (point[safeKey] ?? 0) + value
    }
  }

  const config = {}
  const seriesKeys = []
  categories.forEach((category, categoryIndex) => {
    metrics.forEach((metricKey, metricIndex) => {
      const rawKey = [dimensionKey || "dim", category, metricKey]
        .filter(Boolean)
        .join("__")
      const seriesKey = seriesKeyMap.get(rawKey) ?? getSafeKey(rawKey)
      const paletteIndex =
        (categoryIndex * metrics.length + metricIndex) % CATEGORY_COLORS.length
      const color =
        colorOverrides?.[category] ?? CATEGORY_COLORS[paletteIndex]
      const dimensionLabelText = dimensionLabel || dimensionKey || "분류"

      let label
      if (metrics.length === 1) {
        // 지표 하나일 때는 레전드에 카테고리 이름만
        label = String(category)
      } else {
        label = `${dimensionLabelText} · ${category} · ${METRIC_LABELS[metricKey] ?? metricKey
          }`
      }

      config[seriesKey] = { label, color, category }
      seriesKeys.push(seriesKey)
    })
  })

  return { data: basePoints, categories, config, seriesKeys }
}

function buildTotals(records) {
  const totals = new Map()
  for (const record of records) {
    const category =
      typeof record?.category === "string" && record.category.trim().length > 0
        ? record.category.trim()
        : "Unspecified"
    const value = Number(record?.rowCount ?? 0) || 0
    totals.set(category, (totals.get(category) ?? 0) + value)
  }
  return Array.from(totals.entries()).sort((a, b) => b[1] - a[1])
}

function resolveDimensionRecords(breakdownsByDimension, dimensionKey) {
  if (!breakdownsByDimension || typeof breakdownsByDimension !== "object") {
    return { key: dimensionKey, records: [] }
  }

  const candidates = [dimensionKey, ...(DIMENSION_ALIASES[dimensionKey] ?? [])].filter(
    Boolean,
  )
  const lowerCandidates = new Set(candidates.map((key) => key.toLowerCase()))

  for (const [rawKey, rawRecords] of Object.entries(breakdownsByDimension)) {
    if (!lowerCandidates.has(String(rawKey).toLowerCase())) continue
    if (Array.isArray(rawRecords)) return { key: rawKey, records: rawRecords }
  }

  for (const key of candidates) {
    const records = breakdownsByDimension?.[key]
    if (Array.isArray(records)) return { key, records }
  }

  return { key: dimensionKey, records: [] }
}

function LegendLabel({
  label,
  color,
  onSelectColor,
  onResetColor,
  hasOverride,
  disabled,
}) {
  const [open, setOpen] = React.useState(false)
  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild disabled={disabled}>
        <button
          type="button"
          onClick={(event) => event.stopPropagation()}
          className={cn(
            "inline-flex items-center gap-2 rounded-md px-2 py-1 ring-offset-background transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-1 ring-border",
          )}
          aria-label="레전드 색상 변경"
        >
          <span
            className="inline-flex h-3 w-3 rounded-full ring-1 ring-inset ring-border"
            style={{ backgroundColor: color }}
            aria-hidden="true"
          />
          <span className="whitespace-nowrap">{label}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="w-60"
        sideOffset={6}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="grid grid-cols-5 gap-2 p-2">
          {LEGEND_PRESET_COLORS.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                onSelectColor(preset)
                setOpen(false)
              }}
              className="h-8 rounded-md border ring-offset-background transition hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              style={{ backgroundColor: preset }}
              aria-label={`색상 ${preset}`}
            />
          ))}
        </div>
        {hasOverride && (
          <>
            <DropdownMenuSeparator />
            <button
              type="button"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                onResetColor?.()
                setOpen(false)
              }}
              className="w-full px-3 py-2 text-left text-xs text-muted-foreground hover:bg-muted"
            >
              기본 색상으로 되돌리기
            </button>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ColorLegend({ payload = [], seriesConfig, renderItem }) {
  if (!renderItem) return null
  return (
    <ul className="flex flex-wrap justify-end gap-3 text-[11px]">
      {payload.map((entry) => {
        const key = entry?.dataKey ?? entry?.value
        if (!key) return null
        const configEntry = seriesConfig?.[key]

        return (
          <li key={key}>
            {renderItem(
              key,
              configEntry && {
                ...configEntry,
                color: configEntry.color ?? entry?.color,
              },
            )}
          </li>
        )
      })}
    </ul>
  )
}

export function LineHistoryDashboard({ lineId, initialRangeDays = 30 }) {
  const defaultRange = React.useMemo(
    () => getDefaultDateRange(initialRangeDays),
    [initialRangeDays],
  )

  const today = React.useMemo(() => {
    const now = new Date()
    now.setHours(23, 59, 59, 999)
    return now
  }, [])

  // 날짜 범위 (일반적인 range UX)
  const [dateRange, setDateRange] = React.useState(defaultRange)

  // X축 집계 단위
  const [binMode, setBinMode] = React.useState(DEFAULT_BIN)

  // 날짜 선택 팝오버 열림 상태
  const [isCalendarOpen, setIsCalendarOpen] = React.useState(false)

  // 분류 기준(레전드 기준): 처음엔 null, 데이터 들어오면 첫 사용가능 차원으로 자동 설정
  const [activeDimension, setActiveDimension] = React.useState(null)

  // 차원별 카테고리 선택 상태 (차트에는 activeDimension만 적용)
  const [selectedCategoriesByDimension, setSelectedCategoriesByDimension] =
    React.useState(() =>
      DIMENSION_OPTIONS.reduce(
        (acc, option) => ({ ...acc, [option.value]: [] }),
        {},
      ),
    )

  const [legendColorOverrides, setLegendColorOverrides] = React.useState(() =>
    DIMENSION_OPTIONS.reduce(
      (acc, option) => ({ ...acc, [option.value]: {} }),
      {},
    ),
  )

  const calendarButtonRef = React.useRef(null)
  const calendarPopoverRef = React.useRef(null)

  const {
    data,
    isLoading,
    error,
    totalsData: rawTotalsData,
    breakdownRecordsByDimension: rawBreakdownRecordsByDimension,
    hasSendJiraData,
    refresh,
  } = useLineHistoryData({ lineId, dateRange })

  const totalsData = React.useMemo(
    () => aggregateTotalsByBin(rawTotalsData, binMode),
    [rawTotalsData, binMode],
  )

  const breakdownRecordsByDimension = React.useMemo(
    () => aggregateBreakdownsByBin(rawBreakdownRecordsByDimension, binMode),
    [rawBreakdownRecordsByDimension, binMode],
  )

  React.useEffect(() => {
    if (!isCalendarOpen) return
    const handleClick = (event) => {
      const target = event.target
      if (
        calendarPopoverRef.current?.contains(target) ||
        calendarButtonRef.current?.contains(target)
      ) {
        return
      }
      setIsCalendarOpen(false)
    }
    const handleKey = (event) => {
      if (event.key === "Escape") setIsCalendarOpen(false)
    }
    document.addEventListener("mousedown", handleClick)
    document.addEventListener("keydown", handleKey)
    return () => {
      document.removeEventListener("mousedown", handleClick)
      document.removeEventListener("keydown", handleKey)
    }
  }, [isCalendarOpen])

  const tooltipContent = React.useCallback(
    function HistoryTooltipContent(props) {
      return <KstTooltipContent {...props} bin={binMode} />
    },
    [binMode],
  )

  const axisTickFormatter = React.useCallback(
    (value) => formatAxisLabelByBin(value, binMode),
    [binMode],
  )

  // 차원별 레코드/토탈 계산
  const dimensionRecords = React.useMemo(() => {
    const resolved = {}
    for (const option of DIMENSION_OPTIONS) {
      resolved[option.value] = resolveDimensionRecords(
        breakdownRecordsByDimension,
        option.value,
      )
    }
    return resolved
  }, [breakdownRecordsByDimension])

  const dimensionTotals = React.useMemo(() => {
    const totals = {}
    for (const option of DIMENSION_OPTIONS) {
      const records = dimensionRecords?.[option.value]?.records
      totals[option.value] = Array.isArray(records) ? buildTotals(records) : []
    }
    return totals
  }, [dimensionRecords])

  // 선택된 카테고리 중, 실제 존재하지 않는 카테고리는 정리
  React.useEffect(() => {
    setSelectedCategoriesByDimension((prev) => {
      let changed = false
      const next = { ...prev }

      for (const option of DIMENSION_OPTIONS) {
        const current = prev[option.value] ?? []
        const available = new Set(
          (dimensionTotals[option.value] ?? []).map(([category]) => category),
        )
        const filtered = current.filter((category) => available.has(category))
        const isSameLength = filtered.length === current.length
        const isSameOrder = isSameLength && filtered.every((value, index) => value === current[index])

        next[option.value] = filtered
        if (!isSameOrder) changed = true
      }

      return changed ? next : prev
    })
  }, [dimensionTotals])

  // activeDimension이 없거나 데이터 없는 차원을 가리키면,
  // 데이터가 있는 첫 차원으로 자동 설정
  React.useEffect(() => {
    const hasActive =
      activeDimension &&
      Array.isArray(dimensionRecords?.[activeDimension]?.records) &&
      dimensionRecords[activeDimension].records.length > 0

    if (hasActive) return

    for (const option of DIMENSION_OPTIONS) {
      const records = dimensionRecords?.[option.value]?.records
      if (Array.isArray(records) && records.length > 0) {
        if (option.value !== activeDimension) {
          setActiveDimension(option.value)
        }
        return
      }
    }

    // 어떤 차원에도 데이터가 없으면 null 유지
    if (activeDimension !== null) {
      setActiveDimension(null)
    }
  }, [activeDimension, dimensionRecords])

  const activeDimensionLabel = activeDimension
    ? DIMENSION_LABELS[activeDimension] ?? activeDimension
    : "선택 안됨"

  const activeDimensionTotals = React.useMemo(
    () => (activeDimension ? dimensionTotals[activeDimension] ?? [] : []),
    [activeDimension, dimensionTotals],
  )

  const activeCategories = React.useMemo(
    () =>
      activeDimension ? selectedCategoriesByDimension[activeDimension] ?? [] : [],
    [activeDimension, selectedCategoriesByDimension],
  )

  const activeDimensionRecords = React.useMemo(
    () =>
      activeDimension
        ? dimensionRecords?.[activeDimension]?.records ?? []
        : [],
    [activeDimension, dimensionRecords],
  )

  const hasFilterSelection = React.useMemo(
    () => Array.isArray(activeCategories) && activeCategories.length > 0,
    [activeCategories],
  )

  const activeLegendOverrides = React.useMemo(
    () => (activeDimension ? legendColorOverrides[activeDimension] ?? {} : {}),
    [activeDimension, legendColorOverrides],
  )

  // 진행 건수 브레이크다운 시리즈
  const rowBreakdownSeries = React.useMemo(() => {
    if (
      !activeDimension ||
      !Array.isArray(activeDimensionRecords) ||
      activeDimensionRecords.length === 0 ||
      !Array.isArray(activeCategories) ||
      activeCategories.length === 0
    ) {
      return { data: [], seriesKeys: [], config: {} }
    }

    const resolvedKey = dimensionRecords?.[activeDimension]?.key ?? activeDimension
    const label = DIMENSION_LABELS[activeDimension] ?? activeDimension

    return buildBreakdownSeries(
      activeDimensionRecords,
      ["rowCount"],
      10,
      activeCategories,
      resolvedKey,
      label,
      activeLegendOverrides,
    )
  }, [
    activeDimension,
    activeDimensionRecords,
    activeCategories,
    dimensionRecords,
    activeLegendOverrides,
  ])

  // Send Jira 브레이크다운 시리즈
  const jiraBreakdownSeries = React.useMemo(() => {
    if (
      !hasSendJiraData ||
      !activeDimension ||
      !Array.isArray(activeDimensionRecords) ||
      activeDimensionRecords.length === 0 ||
      !Array.isArray(activeCategories) ||
      activeCategories.length === 0
    ) {
      return { data: [], seriesKeys: [], config: {} }
    }

    const resolvedKey = dimensionRecords?.[activeDimension]?.key ?? activeDimension
    const label = DIMENSION_LABELS[activeDimension] ?? activeDimension

    return buildBreakdownSeries(
      activeDimensionRecords,
      ["sendJiraCount"],
      10,
      activeCategories,
      resolvedKey,
      label,
      activeLegendOverrides,
    )
  }, [
    hasSendJiraData,
    activeDimension,
    activeDimensionRecords,
    activeCategories,
    dimensionRecords,
    activeLegendOverrides,
  ])

  const handleRefresh = React.useCallback(() => {
    if (!lineId) return
    refresh()
  }, [lineId, refresh])

  const handleDateRangeSelect = React.useCallback((range) => {
    setDateRange(range)
  }, [])

  const handleBinChange = React.useCallback((value) => {
    const isValid = BIN_OPTIONS.some((option) => option.value === value)
    setBinMode(isValid ? value : DEFAULT_BIN)
  }, [])

  // 카테고리 선택 토글
  const handleCategoryToggle = React.useCallback(
    (dimension, category, checked) => {
      setSelectedCategoriesByDimension((prev) => {
        const current = prev[dimension] ?? []
        const next =
          checked === true
            ? Array.from(new Set([...current, category]))
            : current.filter((item) => item !== category)
        return { ...prev, [dimension]: next }
      })
    },
    [],
  )

  // 레전드 색상 변경
  const handleLegendColorChange = React.useCallback(
    (dimension, category, color) => {
      if (!dimension || !category || !color) return
      setLegendColorOverrides((prev) => ({
        ...prev,
        [dimension]: {
          ...(prev[dimension] ?? {}),
          [category]: color,
        },
      }))
    },
    [],
  )

  const handleLegendColorReset = React.useCallback((dimension, category) => {
    setLegendColorOverrides((prev) => {
      const prevDimension = prev[dimension] ?? {}
      if (!prevDimension[category]) return prev
      const nextDimension = { ...prevDimension }
      delete nextDimension[category]
      return { ...prev, [dimension]: nextDimension }
    })
  }, [])

  const combinedLegendEntries = React.useMemo(() => {
    if (!hasFilterSelection) return []
    const entriesByCategory = new Map()

    const collectEntries = (series) => {
      if (!series || !Array.isArray(series.seriesKeys)) return
      for (const key of series.seriesKeys) {
        const configEntry = series.config?.[key]
        if (!configEntry?.category) continue
        if (entriesByCategory.has(configEntry.category)) continue
        entriesByCategory.set(configEntry.category, {
          key,
          label: configEntry.label ?? configEntry.category,
          category: configEntry.category,
          color: configEntry.color,
        })
      }
    }

    collectEntries(rowBreakdownSeries)
    collectEntries(jiraBreakdownSeries)

    return Array.from(entriesByCategory.values())
  }, [hasFilterSelection, rowBreakdownSeries, jiraBreakdownSeries])

  const renderLegendLabel = React.useCallback(
    (key, configEntry) => {
      if (!configEntry) return null
      const label = configEntry.label ?? key
      const category = configEntry.category
      const color = configEntry.color ?? "var(--chart-1)"
      const overrideColor = category ? activeLegendOverrides?.[category] : null

      return (
        <LegendLabel
          label={label}
          color={color}
          category={category}
          disabled={!activeDimension || !category}
          hasOverride={Boolean(overrideColor)}
          onResetColor={() =>
            handleLegendColorReset(activeDimension, category)
          }
          onSelectColor={(selected) =>
            handleLegendColorChange(activeDimension, category, selected)
          }
        />
      )
    },
    [
      activeDimension,
      activeLegendOverrides,
      handleLegendColorChange,
      handleLegendColorReset,
    ],
  )

  const lastUpdatedLabel = React.useMemo(() => {
    if (isLoading) return "Updating…"
    const generatedAt = data?.generatedAt
    if (!generatedAt) return "-"
    const parsed = new Date(generatedAt)
    if (Number.isNaN(parsed.getTime())) return "-"
    return timeFormatter.format(parsed)
  }, [data?.generatedAt, isLoading])

  const hasTotalsRowData = Array.isArray(totalsData) && totalsData.length > 0
  const hasTotalsJiraData =
    hasSendJiraData && Array.isArray(totalsData) && totalsData.length > 0

  // 전체 필터가 하나라도 변경되었는지 여부 (버튼 활성화용)
  const hasAnyActiveFilter = React.useMemo(() => {
    const toDateKey = (date) =>
      date instanceof Date ? date.toISOString().slice(0, 10) : null

    const currentFromKey = toDateKey(dateRange?.from)
    const currentToKey = toDateKey(dateRange?.to)
    const defaultFromKey = toDateKey(defaultRange?.from)
    const defaultToKey = toDateKey(defaultRange?.to)

    const hasDateFilter =
      !currentFromKey ||
      !currentToKey ||
      currentFromKey !== defaultFromKey ||
      currentToKey !== defaultToKey

    const hasCategoryFilter = Object.values(selectedCategoriesByDimension).some(
      (categories) => Array.isArray(categories) && categories.length > 0,
    )

    const hasBinSelection = binMode !== DEFAULT_BIN

    return hasDateFilter || hasCategoryFilter || hasBinSelection
  }, [binMode, dateRange, defaultRange, selectedCategoriesByDimension])

  // 필터 전체 초기화
  const handleResetAllFilters = React.useCallback(() => {
    // 날짜 범위 기본값
    setDateRange(defaultRange)

    // 집계 단위 기본값
    setBinMode(DEFAULT_BIN)

    // 달력 닫기
    setIsCalendarOpen(false)

    // 카테고리 필터 초기화
    setSelectedCategoriesByDimension(
      DIMENSION_OPTIONS.reduce(
        (acc, option) => ({ ...acc, [option.value]: [] }),
        {},
      ),
    )
  }, [defaultRange])

  // 진행 건수 차트 렌더러
  const renderRowChart = () => {
    if (!hasTotalsRowData && rowBreakdownSeries.data.length === 0) {
      return (
        <div className="flex h-full min-h-[180px] items-center justify-center rounded-lg border border-dashed text-xs text-muted-foreground">
          진행 건수 데이터가 없습니다.
        </div>
      )
    }

    const showBreakdown =
      hasFilterSelection && rowBreakdownSeries.data.length > 0

    if (showBreakdown) {
      return (
        <ChartContainer
          config={rowBreakdownSeries.config}
          className="flex-1 min-h-[180px]"
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={rowBreakdownSeries.data}
              margin={{ top: 16, right: 8, left: 0, bottom: 56 }}
            >
              <CartesianGrid
                horizontal
                vertical={false}              // 세로선은 숨기고
                stroke={GRID_STROKE}
                strokeDasharray="4 4"         // 가로선을 점선으로
                strokeOpacity={GRID_OPACITY}
              />
              <XAxis
                dataKey="date"
                tickFormatter={axisTickFormatter}
                tickMargin={12}
                minTickGap={12}
                angle={-45}
                textAnchor="end"
                height={60}
                tick={{ fontSize: 15 }}
              />
              <YAxis allowDecimals={false} width={64} />
              <ChartTooltip
                isAnimationActive={false}
                content={tooltipContent}
              />
              {rowBreakdownSeries.seriesKeys.map((seriesKey) => (
                <Line
                  key={seriesKey}
                  type="monotone"
                  dataKey={seriesKey}
                  name={
                    rowBreakdownSeries.config?.[seriesKey]?.label ?? seriesKey
                  }
                  stroke={
                    rowBreakdownSeries.config?.[seriesKey]?.color ??
                    "var(--chart-1)"
                  }
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartContainer>
      )
    }

    // 브레이크다운이 없으면 토탈 차트 (단일 라인)
    const rowTotalsConfig = {
      rowCount: hasFilterSelection
        ? totalsChartConfig.rowCount
        : { ...totalsChartConfig.rowCount, color: THEME_LINE_COLOR },
    }

    return (
      <ChartContainer
        config={rowTotalsConfig}
        className="flex-1 min-h-[180px]"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={totalsData}
            margin={{ top: 16, right: 8, left: 0, bottom: 56 }}
          >
            <CartesianGrid
              horizontal
              vertical={false}              // 세로선은 숨기고
              stroke={GRID_STROKE}
              strokeDasharray="4 4"         // 가로선을 점선으로
              strokeOpacity={GRID_OPACITY}
            />
            <XAxis
              dataKey="date"
              tickFormatter={axisTickFormatter}
              tickMargin={8}
              minTickGap={12}
              angle={-45}
              textAnchor="end"
              height={56}
              tick={{ fontSize: 15 }}
            />
            <YAxis allowDecimals={false} width={64} />
            <ChartTooltip
              isAnimationActive={false}
              content={tooltipContent}
            />
            <Line
              type="monotone"
              dataKey="rowCount"
              name={rowTotalsConfig.rowCount.label}
              stroke={rowTotalsConfig.rowCount.color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    )
  }

  // Send Jira 차트 렌더러
  const renderJiraChart = () => {
    if (!hasSendJiraData) {
      return (
        <div className="flex h-full min-h-[180px] items-center justify-center rounded-lg border border-dashed text-xs text-muted-foreground">
          Send Jira 데이터가 없습니다.
        </div>
      )
    }

    const showBreakdown =
      hasFilterSelection && jiraBreakdownSeries.data.length > 0

    if (showBreakdown) {
      return (
        <ChartContainer
          config={jiraBreakdownSeries.config}
          className="flex-1 min-h-[180px]"
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={jiraBreakdownSeries.data}
              margin={{ top: 16, right: 8, left: 0, bottom: 56 }}
            >
              <CartesianGrid
                horizontal
                vertical={false}              // 세로선은 숨기고
                stroke={GRID_STROKE}
                strokeDasharray="4 4"         // 가로선을 점선으로
                strokeOpacity={GRID_OPACITY}
              />
              <XAxis
                dataKey="date"
                tickFormatter={axisTickFormatter}
                tickMargin={16}
                minTickGap={12}
                angle={-45}
                textAnchor="end"
                height={56}
                tick={{ fontSize: 15 }}
              />
              <YAxis allowDecimals={false} width={64} />
              <ChartTooltip
                isAnimationActive={false}
                content={tooltipContent}
              />
              {jiraBreakdownSeries.seriesKeys.map((seriesKey) => (
                <Line
                  key={seriesKey}
                  type="monotone"
                  dataKey={seriesKey}
                  name={
                    jiraBreakdownSeries.config?.[seriesKey]?.label ?? seriesKey
                  }
                  stroke={
                    jiraBreakdownSeries.config?.[seriesKey]?.color ??
                    "var(--chart-2)"
                  }
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartContainer>
      )
    }

    if (!hasTotalsJiraData) {
      return (
        <div className="flex h-full min-h-[180px] items-center justify-center rounded-lg border border-dashed text-xs text-muted-foreground">
          Jira 인폼 데이터가 없습니다.
        </div>
      )
    }

    const jiraTotalsConfig = {
      sendJiraCount: hasFilterSelection
        ? totalsChartConfig.sendJiraCount
        : { ...totalsChartConfig.sendJiraCount, color: THEME_LINE_COLOR },
    }

    return (
      <ChartContainer
        config={jiraTotalsConfig}
        className="flex-1 min-h-[180px]"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={totalsData}
            margin={{ top: 16, right: 8, left: 0, bottom: 56 }}
          >
            <CartesianGrid
              horizontal
              vertical={false}              // 세로선은 숨기고
              stroke={GRID_STROKE}
              strokeDasharray="4 4"         // 가로선을 점선으로
              strokeOpacity={GRID_OPACITY}
            />
            <XAxis
              dataKey="date"
              tickFormatter={axisTickFormatter}
              tickMargin={16}
              minTickGap={12}
              angle={-45}
              textAnchor="end"
              height={56}
              tick={{ fontSize: 15 }}
            />
            <YAxis allowDecimals={false} width={64} />
            <ChartTooltip
              isAnimationActive={false}
              content={tooltipContent}
            />
            <Line
              type="monotone"
              dataKey="sendJiraCount"
              name={jiraTotalsConfig.sendJiraCount.label}
              stroke={jiraTotalsConfig.sendJiraCount.color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    )
  }

  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-hidden">
      {/* 제목 + 업데이트 시간 */}
      <div className="flex flex-col gap-1">
        <div className="flex items-baseline gap-2 text-lg font-semibold">
          <h1 className="text-lg font-semibold">
            {lineId ? `${lineId} ${LABELS.titleSuffix}` : LABELS.titleSuffix}
          </h1>
          <span
            className="text-[11px] font-normal text-muted-foreground"
            aria-live="polite"
          >
            {LABELS.updated} {lastUpdatedLabel}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          라인별 E-SOP 진행 추이를 날짜/시간 단위로 확인하고, 선택한 분류 기준에 따라
          카테고리별로 비교합니다.
        </p>
      </div>

      {/* 상단 필터 바 */}
      <div className="rounded-lg border bg-background p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {/* 날짜 범위 선택 */}
            <div className="relative">
              <Button
                ref={calendarButtonRef}
                variant="outline"
                size="sm"
                className="h-8 min-w-[220px] justify-between px-3 text-xs"
                onClick={() => setIsCalendarOpen((prev) => !prev)}
                aria-expanded={isCalendarOpen}
                aria-haspopup="dialog"
              >
                <span className="text-[11px] text-muted-foreground">
                  조회 기간
                </span>
                <span className="flex items-center gap-2">
                  <CalendarIcon className="size-4" />
                  {formatRangeLabel(dateRange)}
                </span>
              </Button>
              {isCalendarOpen && (
                <div
                  ref={calendarPopoverRef}
                  className="absolute left-0 top-full z-50 mt-2 rounded-lg border bg-popover p-3 shadow-lg"
                >
                  <DateRangeCalendar
                    selected={dateRange}
                    defaultMonth={dateRange?.from ?? today}
                    onSelect={handleDateRangeSelect}
                    disableAfter={today}
                  />
                  <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>기본값: 최근 한 달</span>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs"
                        onClick={() => handleDateRangeSelect(defaultRange)}
                      >
                        기간 초기화
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        className="h-7 px-2 text-xs"
                        onClick={() => setIsCalendarOpen(false)}
                      >
                        닫기
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* X축 집계 단위 */}
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground">
                X축 Bin
              </span>
              <div className="flex items-center gap-[2px] rounded-md border bg-muted/60 p-[2px]">
                {BIN_OPTIONS.map((option) => {
                  const isActive = binMode === option.value
                  return (
                    <Button
                      key={option.value}
                      size="sm"
                      variant={isActive ? "secondary" : "ghost"}
                      className="h-8 px-3 text-xs"
                      onClick={() => handleBinChange(option.value)}
                    >
                      {option.label}
                    </Button>
                  )
                })}
              </div>
            </div>

            {/* 분류 기준 선택 (레전드 기준) */}
            <div className="flex items-center gap-1">
              <span className="text-[11px] text-muted-foreground">
                분류 기준
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-8 px-3 text-xs"
                  >
                    <span className="font-medium">
                      {activeDimensionLabel}
                    </span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56">
                  <DropdownMenuLabel>차트 레전드 기준 선택</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {DIMENSION_OPTIONS.map((option) => {
                    const records = dimensionRecords?.[option.value]?.records
                    const hasRecords =
                      Array.isArray(records) && records.length > 0
                    return (
                      <DropdownMenuItem
                        key={option.value}
                        disabled={!hasRecords}
                        className={
                          !hasRecords ? "cursor-not-allowed opacity-60" : ""
                        }
                        onSelect={(event) => {
                          event.preventDefault()
                          if (!hasRecords) return
                          setActiveDimension(option.value)
                        }}
                      >
                        {option.label}
                        {!hasRecords && (
                          <span className="ml-1 text-[10px] text-muted-foreground">
                            (데이터 없음)
                          </span>
                        )}
                      </DropdownMenuItem>
                    )
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* 선택된 분류 기준에 대한 카테고리 필터 */}
            {activeDimension && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex items-center gap-2"
                  >
                    <FilterIcon className="size-4" />
                    <span>{activeDimensionLabel} 카테고리 필터</span>
                    {hasFilterSelection && (
                      <span className="rounded bg-muted px-1 text-[11px] text-muted-foreground">
                        {activeCategories.length}
                      </span>
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-64 max-h-80 overflow-y-auto">
                  <DropdownMenuLabel>
                    {activeDimensionLabel} 카테고리 필터
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {activeDimensionTotals.map(([category]) => (
                    <DropdownMenuCheckboxItem
                      key={category}
                      checked={activeCategories.includes(category)}
                      onSelect={(event) => event.preventDefault()}
                      onCheckedChange={(checked) =>
                        handleCategoryToggle(
                          activeDimension,
                          category,
                          checked === true,
                        )
                      }
                    >
                      {category}
                    </DropdownMenuCheckboxItem>
                  ))}
                  {hasFilterSelection && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onSelect={(event) => event.preventDefault()}
                        onClick={() =>
                          setSelectedCategoriesByDimension((prev) => ({
                            ...prev,
                            [activeDimension]: [],
                          }))
                        }
                      >
                        {activeDimensionLabel} 필터 초기화
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>

          {/* 필터 전체 초기화 + 새로고침 버튼 */}
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={handleResetAllFilters}
              disabled={!hasAnyActiveFilter || isLoading}
              className="gap-1 text-xs"
              aria-label="필터 전체 초기화"
              title="날짜 / 집계 단위 / 카테고리 / 숨김 시리즈 모두 초기화"
            >
              <FilterIcon className="size-4" />
              필터 전체 초기화
            </Button>

            <Button
              size="sm"
              variant="outline"
              onClick={handleRefresh}
              disabled={isLoading}
              className="gap-1"
              aria-label="refresh"
              title="refresh"
            >
              <IconRefresh
                className={cn("size-4", isLoading && "animate-spin")}
              />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <div className="flex items-center gap-2">
            <IconAlertCircle className="size-4" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* 메인 차트 섹션 */}
      <section className="flex flex-1 min-h-0 min-w-0 flex-col gap-6 overflow-y-auto rounded-lg border bg-background p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">E-SOP Trend</h2>
            <p className="text-xs text-muted-foreground">
              날짜/시간별 E-SOP진행 건수 Jira인폼 건수 Trend Monitoring
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2 text-[11px] text-muted-foreground">
            <span className="rounded-md bg-muted px-2 py-1">
              X축 Bin: {BIN_LABELS[binMode] ?? binMode}
            </span>
            {activeDimension && (
              <span className="rounded-md bg-muted px-2 py-1">
                분류 기준: {activeDimensionLabel}
              </span>
            )}
            {hasFilterSelection && (
              <span className="rounded-md bg-muted px-2 py-1">
                카테고리 필터 {activeCategories.length}개 적용
              </span>
            )}
          </div>
        </div>

        {combinedLegendEntries.length > 0 && (
          <div className="flex justify-end">
            <ColorLegend
              payload={combinedLegendEntries.map((entry) => ({
                dataKey: entry.key,
                value: entry.label,
                color: entry.color,
              }))}
              seriesConfig={Object.fromEntries(
                combinedLegendEntries.map((entry) => [
                  entry.key,
                  {
                    label: entry.label,
                    category: entry.category,
                    color: entry.color,
                  },
                ]),
              )}
              renderItem={(key, configEntry) => renderLegendLabel(key, configEntry)}
            />
          </div>
        )}

        <div className="grid flex-1 min-h-0 min-w-0 grid-cols-1 gap-6 lg:grid-cols-2 lg:auto-rows-fr">
          {/* 진행 건수 차트 */}
          <div className="flex h-full min-h-0 min-w-0 flex-col gap-2">
            <div className="flex items-center justify-between">
              <h3 className="text-md font-semibold uppercase tracking-wide text-muted-foreground">
                진행 건수
              </h3>
            </div>
            {renderRowChart()}
          </div>

          {/* Send Jira 차트 */}
          <div className="flex h-full min-h-0 min-w-0 flex-col gap-2">
            <div className="flex items-center justify-between">
              <h3 className="text-md font-semibold uppercase tracking-wide text-muted-foreground">
                Jira 인폼 건수
              </h3>
            </div>
            {renderJiraChart()}
          </div>
        </div>
      </section>

      {/* 로딩 인디케이터 */}
      {isLoading && (
        <div className="pointer-events-none absolute inset-x-0 top-24 flex justify-center">
          <div className="rounded-full border border-muted bg-background/90 px-3 py-1 text-xs text-muted-foreground shadow-sm">
            데이터를 불러오는 중...
          </div>
        </div>
      )}
    </div>
  )
}
