import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  CircleHelp,
  ExternalLink,
  Filter,
  ImageIcon,
  Mail,
  Radar,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

const ASSET_ROOT = "/l3-spider/l3-spider-guide-assets"

const GUIDE_META = {
  page: {
    title: "L3 Spider 페이지 설명서",
    description: "실제 화면 기준으로 Summary, Chart, 메일 설정, 제외 필터의 사용 흐름을 확인합니다.",
    icon: BookOpen,
  },
  algorithm: {
    title: "L3 Spider 알고리즘 설명서",
    description: "이상 챔버 자동 감지의 판정 흐름과 운영 기준을 확인합니다.",
    icon: CircleHelp,
  },
}

const PAGE_SECTIONS = [
  { id: "summary", label: "Summary", icon: BarChart3 },
  { id: "chart", label: "Chart", icon: Activity },
  { id: "mail-list", label: "메일 목록", icon: Mail },
  { id: "mail-form", label: "메일 Rule", icon: Bell },
  { id: "exclusion", label: "제외 필터", icon: Filter },
]

const ALGORITHM_SECTIONS = [
  { id: "intro", label: "왜 필요한가", icon: Sparkles },
  { id: "phase1", label: "1단계 스파이크", icon: Activity },
  { id: "phase2", label: "2단계 교차검증", icon: Radar },
  { id: "fadeout", label: "중복 알람 방지", icon: ShieldCheck },
  { id: "read", label: "화면 읽는 법", icon: BarChart3 },
  { id: "faq", label: "FAQ", icon: CircleHelp },
  { id: "glossary", label: "용어집", icon: BookOpen },
]

const PAGE_SCREENSHOTS = [
  {
    id: "summary",
    eyebrow: "01 Summary",
    title: "날짜 하나로 전체 이상 현황을 먼저 본다",
    image: "summary-overview.png",
    alt: "L3 Spider Summary 탭 실제 화면 캡처",
    caption: "Summary 탭 실제 캡처. 번호는 날짜, 관리 버튼, 탭, 하단 Total 지표, 라인별 집계, 라인별 세부 요약을 가리킵니다.",
    points: [
      ["Date 선택", "조회 기준 날짜입니다. 날짜를 바꾸면 Summary 집계와 Chart 선택 후보가 같은 날짜 기준으로 다시 계산됩니다."],
      ["운영 버튼", "메일 설정은 자동 알림 rule을 관리하고, 제외 필터는 노이즈 조합을 집계에서 빼며, 새로고침은 최신 메타데이터를 다시 불러옵니다."],
      ["Summary / Chart 탭", "Summary는 날짜 전체 집계, Chart는 선택 조건별 scatter trellis 분석 화면입니다."],
      ["하단 Total 지표", "분석 그룹, High Risk, Warning, 이상 건수, 이상 EQPCH 수를 한 줄로 보여줍니다."],
      ["라인별 현황", "Line별 HR/WN/합계를 비교합니다. 이상이 없는 라인도 흐리게 표시되어 전체 커버리지와 이상 집중 라인을 같이 볼 수 있습니다."],
      ["라인별 세부 요약", "Line, Process, EDS Step별 High Risk/Warning 건수를 보여줍니다. 셀을 클릭하면 같은 조건으로 Chart 탭이 열립니다."],
    ],
  },
  {
    id: "chart",
    eyebrow: "02 Chart",
    title: "Line에서 EQPCH까지 좁혀 scatter trellis로 확인한다",
    image: "chart-workflow.png",
    alt: "L3 Spider Chart 탭 실제 화면 캡처",
    caption: "Chart 탭 실제 캡처. 선택 패널과 scatter trellis, chart order, axis mode, export 도구를 함께 보여줍니다.",
    points: [
      ["Date 선택", "현재 차트가 어떤 날짜 데이터인지 고정합니다. 선택 완료 시 날짜 옆 체크 표시가 보입니다."],
      ["상위 선택축", "Line Name, Process ID, EDS Step을 고릅니다. 각 컬럼 상단 숫자는 현재 날짜에서 선택 가능한 후보 수입니다."],
      ["상세 선택축", "Step Seq, PPID, EQPCH를 순서대로 선택합니다. PPID 칼럼의 시간은 해당 조합의 마지막 TKin Time입니다."],
      ["Scatter Plot trellis", "선택된 EQPCH의 이상 Bin을 작은 차트로 나눠 보여줍니다. 빨간 점은 High Risk, 주황 점은 Warning, 회색 점은 정상 기준입니다."],
      ["Chart Order", "기본 순서 또는 High Risk가 있는 차트를 앞쪽에 배치하는 순서를 선택합니다."],
      ["X Axis", "시간 기준, 시간+Wafer 기준, EQPCH+Time 기준으로 X축을 바꿉니다."],
      ["Raw Data", "현재 선택 조건의 원천 row를 CSV로 내려받아 별도 분석이나 공유에 사용합니다."],
      ["All Charts", "현재 trellis 전체 차트를 이미지로 캡처합니다. 보고서 첨부용 전체 차트 묶음을 만들 때 사용합니다."],
    ],
  },
  {
    id: "mail-list",
    eyebrow: "03 Mail settings",
    title: "자동 알림 rule을 한 곳에서 관리한다",
    image: "mail-settings.png",
    alt: "L3 Spider 메일 설정 목록 실제 화면 캡처",
    caption: "메일 설정 목록 실제 캡처. rule 이름, 발송 조건, 수신자, 권한, 작업 버튼을 확인합니다.",
    points: [
      ["메일 발송 설정", "메일 rule을 조회, 추가, 수정, 삭제하는 시트입니다. 사용자가 등록한 rule은 지정 시각 이후 한 번 처리됩니다."],
      ["Rule 추가", "새 메일 rule 입력 창을 엽니다. 아래 Rule form 화면과 연결됩니다."],
      ["Rule / 접근", "Rule 이름과 공유 권한을 관리합니다. 접근 권한은 owner/read/write 레벨로 분리됩니다."],
      ["조건 / 주기", "High Risk만 보낼지, Warning까지 포함할지와 발송 주기를 확인합니다."],
      ["수신자 / 패턴", "수신 이메일과 Line/Process/EDS/Step/PPID/EQPCH/Bin 패턴을 요약 표시합니다."],
      ["작업", "기존 rule을 수정, 삭제, 테스트 발송하거나 권한을 조정하는 영역입니다."],
    ],
  },
  {
    id: "mail-form",
    eyebrow: "04 Mail rule form",
    title: "메일 rule은 조건과 수신자, 발송 시각으로 구성한다",
    image: "mail-rule-form.png",
    alt: "L3 Spider 메일 rule 추가 창 실제 화면 캡처",
    caption: "메일 rule 추가 모달 실제 캡처. 필수값, severity, 수신자, 패턴 필드, 활성 상태를 저장합니다.",
    points: [
      ["메일 rule 추가", "새 rule 생성 모달입니다. 수정 모드에서는 제목이 메일 rule 수정으로 바뀝니다."],
      ["Rule 이름", "목록에서 식별할 이름입니다. 예: 특정 Line의 High Risk 알림."],
      ["메일 조건", "High Risk만 또는 Warning + High Risk 중 발송 대상 severity를 고릅니다."],
      ["발송 시각", "Asia/Seoul 기준 발송 기준 시각입니다. rule 처리는 이 시각 이후의 대상 결과를 확인합니다."],
      ["수신자", "쉼표, 세미콜론, 줄바꿈으로 여러 이메일을 입력할 수 있습니다."],
      ["패턴 필드", "Line ID, Process ID, EDS Step, Step Seq, PPID, EQPCH, Bin Name, 발송 종료일을 지정합니다."],
      ["활성", "rule을 켜고 끄는 스위치입니다. 비활성 rule은 저장되어 있어도 발송 대상에서 제외됩니다."],
      ["저장", "입력한 조건을 저장합니다. 수신자 형식이나 필수값 문제가 있으면 저장 전에 오류가 표시됩니다."],
    ],
  },
  {
    id: "exclusion",
    eyebrow: "05 Exclusion filters",
    title: "노이즈 조합은 집계에서 제외해 신호를 선명하게 만든다",
    image: "exclusion-filters.png",
    alt: "L3 Spider 제외 필터 관리 실제 화면 캡처",
    caption: "제외 필터 관리 시트 실제 캡처. 기존 필터 1건이 흐리게 보이는 상태입니다.",
    points: [
      ["제외 필터 관리", "집계에서 제외할 조합을 관리하는 시트입니다. 적용된 필터는 날짜별 메타와 요약 계산에 반영됩니다."],
      ["필터 추가", "새 제외 규칙 행을 추가합니다. 추가 후 저장 아이콘으로 확정합니다."],
      ["활성", "필터를 즉시 켜거나 끕니다. 비활성 필터는 목록에는 남지만 계산에는 적용되지 않습니다."],
      ["대상 패턴", "Line ID부터 Bin Name까지 제외 조건을 적습니다. 메일 rule과 동일하게 *와 와일드카드를 사용할 수 있습니다."],
      ["날짜 시작 / 종료", "필터 적용 기간입니다. 특정 이벤트 기간만 제외하려면 시작과 종료를 함께 넣습니다."],
      ["메모", "제외 사유, 요청자, 이슈 번호 등을 남깁니다. 나중에 필터를 검토할 때 기준이 됩니다."],
      ["작업", "필터 행을 수정하거나 삭제합니다. 삭제는 적용 이력 관리 기준에 맞춰 신중하게 처리합니다."],
    ],
  },
]


const FAQS = [
  ["High Risk와 Warning은 무엇이 다른가요?", "High Risk는 control limit 위반과 반복성이 함께 확인된 강한 신호이고, Warning은 관찰이 필요한 초기 신호입니다."],
  ["챔버 하나만 튀면 바로 알람인가요?", "아니요. 단일 spike만으로 확정하지 않고 같은 lot/시간대의 다른 챔버와 비교해 챔버 고유 문제인지 확인합니다."],
  ["제외 필터는 언제 쓰나요?", "설비 이벤트, 계측 누락, 알려진 데이터 품질 이슈처럼 분석 대상에서 빼야 하는 조합이 있을 때 사용합니다."],
]

function GuideShell({ sections, activeSection, onSectionClick, scrollRef, children }) {
  return (
    <div className="grid h-full min-h-0 grid-rows-[auto,minmax(0,1fr)] bg-background">
      <nav className="shrink-0 border-b bg-muted/30 px-4 py-3" aria-label="가이드 섹션">
        <div className="flex flex-nowrap items-center gap-2 overflow-x-auto">
          {sections.map((section) => {
            const Icon = section.icon
            const isActive = activeSection === section.id
            return (
              <button
                key={section.id}
                type="button"
                onClick={() => onSectionClick(section.id)}
                className={cn(
                  "flex h-9 shrink-0 items-center gap-2 rounded-md px-3 text-left text-sm transition",
                  "hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isActive ? "bg-background font-semibold text-foreground shadow-sm" : "text-muted-foreground",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{section.label}</span>
              </button>
            )
          })}
        </div>
      </nav>
      <main ref={scrollRef} className="min-h-0 min-w-0 overflow-y-auto" data-guide-scroll>
        {children}
      </main>
    </div>
  )
}

function GuideHero({ eyebrow, title, description, badges, variant = "default" }) {
  return (
    <section
      className={cn(
        "border-b px-8 py-10",
        variant === "algorithm" ? "bg-primary/5" : "bg-card",
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">{eyebrow}</p>
      <h2 className="mt-3 max-w-4xl text-3xl font-semibold tracking-tight text-foreground">{title}</h2>
      <p className="mt-4 max-w-4xl text-sm leading-6 text-muted-foreground">{description}</p>
      {badges?.length ? (
        <div className="mt-5 flex flex-wrap gap-2">
          {badges.map((badge) => (
            <Badge key={badge} variant="secondary" className="rounded-md px-2.5 py-1">
              {badge}
            </Badge>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function ScreenshotFigure({ image, alt, caption }) {
  const src = `${ASSET_ROOT}/${image}`
  return (
    <figure className="overflow-hidden rounded-lg border bg-card">
      <button
        type="button"
        onClick={() => window.open(src, "_blank", "noopener,noreferrer")}
          className="group block w-full bg-muted/30 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`${alt} 원본 이미지 열기`}
      >
        <img
          src={src}
          alt={alt}
          className="block w-full max-w-full transition group-hover:opacity-95"
        />
      </button>
      <figcaption className="flex items-center gap-2 border-t px-4 py-2 text-xs text-muted-foreground">
        <ImageIcon className="size-3.5" aria-hidden="true" />
        <span className="min-w-0 flex-1">{caption}</span>
        <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
      </figcaption>
    </figure>
  )
}

function NumberedCallouts({ points }) {
  return (
    <ol className="grid gap-3 md:grid-cols-2">
      {points.map(([title, body], index) => (
        <li key={title} className="grid grid-cols-[2rem,minmax(0,1fr)] gap-3 rounded-lg border bg-card p-3">
          <span className="grid size-8 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
            {index + 1}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">{title}</p>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{body}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

function PageGuideContent() {
  return (
    <div>
      <GuideHero
        eyebrow="Actual page capture guide"
        title="L3 Spider 실제 화면 기준 사용 설명서"
        description="L3 Spider는 날짜별 이상감지 결과를 Summary에서 빠르게 훑고, Chart에서 Line/Process/EDS/Step/PPID/EQPCH 단위로 파고드는 화면입니다. 각 캡처의 번호는 실제 UI 영역을 가리키며, 아래 설명은 그 영역이 무엇을 하는지 정리합니다."
        badges={["캡처 경로 /l3_spider", "캡처 실행일 2026-07-04", "화면 데이터 날짜 2026-06-20"]}
      />
      <div className="grid gap-10 px-8 py-8">
        {PAGE_SCREENSHOTS.map((section) => (
          <section key={section.id} id={section.id} className="scroll-mt-6 space-y-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">{section.eyebrow}</p>
              <h3 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{section.title}</h3>
            </div>
            <ScreenshotFigure image={section.image} alt={section.alt} caption={section.caption} />
            <NumberedCallouts points={section.points} />
          </section>
        ))}
      </div>
    </div>
  )
}

const CHART_COLORS = {
  normal: "var(--muted-foreground)",
  limit: "var(--destructive)",
  warning: "var(--chart-1)",
  signal: "var(--chart-2)",
  accent: "var(--chart-3)",
  grid: "var(--border)",
  text: "var(--muted-foreground)",
  foreground: "var(--foreground)",
  card: "var(--card)",
  muted: "var(--muted)",
}

function createRandom(seed) {
  let state = seed
  return () => {
    state = (state * 9301 + 49297) % 233280
    return state / 233280
  }
}

function smoothPath(points) {
  if (points.length < 2) return ""
  return points.slice(1).reduce((path, point, index) => {
    const previous = points[index]
    const middleX = (previous[0] + point[0]) / 2
    return `${path} C ${middleX} ${previous[1]}, ${middleX} ${point[1]}, ${point[0]} ${point[1]}`
  }, `M ${points[0][0]} ${points[0][1]}`)
}

function quantile(sortedValues, percentage) {
  const index = (sortedValues.length - 1) * percentage
  const low = Math.floor(index)
  const high = Math.ceil(index)
  return sortedValues[low] + (sortedValues[high] - sortedValues[low]) * (index - low)
}

function ChartLegend({ items }) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
      {items.map(([label, color]) => (
        <span key={label} className="inline-flex items-center gap-1.5">
          <span className={cn("size-2.5 rounded-full", color)} />
          {label}
        </span>
      ))}
    </div>
  )
}

function AlgorithmChartCard({ title, legend, children, caption }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {legend ? <ChartLegend items={legend} /> : null}
      </div>
      <div className="mt-3 min-w-0">{children}</div>
      {caption ? <p className="mt-3 text-sm leading-6 text-muted-foreground">{caption}</p> : null}
    </div>
  )
}

function HeroTraceChart() {
  const width = 820
  const height = 220
  const padLeft = 54
  const padRight = 20
  const padTop = 24
  const padBottom = 42
  const random = createRandom(4)
  const values = Array.from({ length: 40 }, (_, index) => {
    let base = 8 + Math.sin(index * 0.4) * 1.2 + (random() - 0.5) * 1.6
    if (index >= 22 && index < 31) base += (index - 21) * 1.7 + (random() - 0.5) * 1.5
    if (index >= 31) base += 9 - (index - 31) * 0.35
    return Math.max(2, base)
  })
  const maxValue = Math.max(...values) * 1.15
  const chartHeight = height - padTop - padBottom
  const x = (index) => padLeft + (index / (values.length - 1)) * (width - padLeft - padRight)
  const y = (value) => height - padBottom - (value / maxValue) * chartHeight
  const limit = 8.6 + 6 * 1.4
  const limitY = y(limit)
  const points = values.map((value, index) => [x(index), y(value)])
  const alertX = x(27)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-64 w-full" role="img" aria-label="알람 확정까지의 bin value 추이">
      {[0, 1, 2, 3].map((gridIndex) => {
        const gridY = padTop + gridIndex * (chartHeight / 3)
        return <line key={gridY} x1={padLeft} y1={gridY} x2={width - padRight} y2={gridY} stroke={CHART_COLORS.grid} />
      })}
      <line x1={padLeft} y1={limitY} x2={width - padRight} y2={limitY} stroke={CHART_COLORS.limit} strokeDasharray="3 4" opacity="0.65" />
      <text x={width - padRight} y={limitY - 7} textAnchor="end" fill={CHART_COLORS.limit} fontSize="14" fontWeight="700">관리 상한 (USL)</text>
      <path d={smoothPath(points)} fill="none" stroke={CHART_COLORS.normal} strokeWidth="2" />
      {values.map((value, index) => {
        const warning = index >= 22 && index < 31
        const alert = index >= 27 && index < 31
        return (
          <circle
            key={`${index}-${value}`}
            cx={x(index)}
            cy={y(value)}
            r={alert ? 6 : warning ? 5 : 4.4}
            fill={alert ? CHART_COLORS.limit : warning ? CHART_COLORS.warning : CHART_COLORS.normal}
          />
        )
      })}
      <line x1={alertX} y1={padTop} x2={alertX} y2={height - padBottom} stroke={CHART_COLORS.limit} strokeDasharray="2 3" opacity="0.5" />
      <text x={alertX} y={padTop - 8} textAnchor="middle" fill={CHART_COLORS.limit} fontSize="13" fontWeight="700">ALERT 확정</text>
      <text x={(padLeft + width - padRight) / 2} y={height - 10} textAnchor="middle" fill={CHART_COLORS.text} fontSize="13">{"tkin_time ->"}</text>
      <text x="16" y={(padTop + height - padBottom) / 2} textAnchor="middle" fill={CHART_COLORS.text} fontSize="13" transform={`rotate(-90 16 ${(padTop + height - padBottom) / 2})`}>bin_value</text>
    </svg>
  )
}

function RangeFacetChart() {
  const random = createRandom(21)
  const outlierIndexes = new Set([16, 17, 46, 47, 48, 76])
  const values = Array.from({ length: 84 }, (_, index) => {
    const outlier = outlierIndexes.has(index)
    const value = outlier
      ? 2.4 + random() * 2.4
      : Math.max(0, (random() < 0.62 ? 0 : random() * 0.9) + (random() - 0.5) * 0.15)
    return { index, value, outlier }
  })
  const sorted = values.map((point) => point.value).sort((a, b) => a - b)
  const q1 = quantile(sorted, 0.25)
  const median = quantile(sorted, 0.5)
  const q3 = quantile(sorted, 0.75)
  const iqr = Math.max(q3 - q1, 0.5)
  const usl = q3 + 6 * iqr * 0.18
  const whiskerMax = Math.min(Math.max(...sorted), q3 + 1.5 * iqr)
  const maxValue = 5.4
  const padTop = 28
  const padBottom = 44
  const chartHeight = 300 - padTop - padBottom
  const y = (value) => padTop + chartHeight - (value / maxValue) * chartHeight
  const scatterWidth = 700
  const boxWidth = 200
  const scatterPadLeft = 56
  const scatterPadRight = 16
  const x = (index) => scatterPadLeft + (index / (values.length - 1)) * (scatterWidth - scatterPadLeft - scatterPadRight)
  const boxCenter = boxWidth / 2
  const boxPlotWidth = 64
  const jitter = createRandom(99)

  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_220px]">
      <svg viewBox={`0 0 ${scatterWidth} 300`} className="h-80 w-full" role="img" aria-label="시간순 bin value 산점도와 USL">
        {[0, 1, 2, 3].map((gridIndex) => {
          const gridY = padTop + gridIndex * (chartHeight / 3)
          return (
            <g key={gridY}>
              <line x1={scatterPadLeft} y1={gridY} x2={scatterWidth - scatterPadRight} y2={gridY} stroke={CHART_COLORS.grid} />
              <text x={scatterPadLeft - 10} y={gridY + 4} textAnchor="end" fill={CHART_COLORS.text} fontSize="13">
                {(maxValue * (3 - gridIndex) / 3).toFixed(1)}
              </text>
            </g>
          )
        })}
        <line x1={scatterPadLeft} y1={y(usl)} x2={scatterWidth - scatterPadRight} y2={y(usl)} stroke={CHART_COLORS.signal} strokeWidth="2.4" strokeDasharray="7 5" />
        <text x={scatterWidth - scatterPadRight} y={y(usl) - 10} textAnchor="end" fill={CHART_COLORS.signal} fontSize="13" fontWeight="700">
          {`USL ~= ${usl.toFixed(2)}`}
        </text>
        {values.map((point) => (
          <circle
            key={point.index}
            cx={x(point.index)}
            cy={y(point.value)}
            r={point.outlier ? 7.2 : 5.4}
            fill={point.outlier ? CHART_COLORS.warning : CHART_COLORS.normal}
            opacity={point.outlier ? 1 : 0.85}
          />
        ))}
        <text x={(scatterPadLeft + scatterWidth - scatterPadRight) / 2} y="290" textAnchor="middle" fill={CHART_COLORS.text} fontSize="13">{"tkin_time ->"}</text>
        <text x="14" y={padTop - 9} fill={CHART_COLORS.text} fontSize="13">bin_value</text>
      </svg>
      <svg viewBox={`0 0 ${boxWidth} 300`} className="h-80 w-full" role="img" aria-label="전체 분포 박스플롯">
        {[0, 1, 2, 3].map((gridIndex) => {
          const gridY = padTop + gridIndex * (chartHeight / 3)
          return <line key={gridY} x1="10" y1={gridY} x2={boxWidth - 10} y2={gridY} stroke={CHART_COLORS.grid} />
        })}
        <line x1="0" y1={y(usl)} x2={boxWidth} y2={y(usl)} stroke={CHART_COLORS.signal} strokeWidth="2.4" strokeDasharray="7 5" />
        <line x1={boxCenter} y1={y(q1)} x2={boxCenter} y2={y(whiskerMax)} stroke={CHART_COLORS.foreground} strokeWidth="2" />
        <line x1={boxCenter - boxPlotWidth / 4} y1={y(whiskerMax)} x2={boxCenter + boxPlotWidth / 4} y2={y(whiskerMax)} stroke={CHART_COLORS.foreground} strokeWidth="2" />
        <rect x={boxCenter - boxPlotWidth / 2} y={y(q3)} width={boxPlotWidth} height={Math.max(2, y(q1) - y(q3))} fill={CHART_COLORS.card} stroke={CHART_COLORS.foreground} strokeWidth="2" />
        <line x1={boxCenter - boxPlotWidth / 2} y1={y(median)} x2={boxCenter + boxPlotWidth / 2} y2={y(median)} stroke={CHART_COLORS.foreground} strokeWidth="2.6" />
        {values.filter((point) => point.value > whiskerMax).map((point) => (
          <circle
            key={point.index}
            cx={boxCenter + (jitter() - 0.5) * boxPlotWidth * 0.7}
            cy={y(point.value)}
            r="7.2"
            fill={CHART_COLORS.warning}
            opacity="0.9"
          />
        ))}
        <text x={boxCenter} y="290" textAnchor="middle" fill={CHART_COLORS.text} fontSize="13">전체 분포</text>
      </svg>
    </div>
  )
}

function DirectionCaseChart({ mode }) {
  const width = 460
  const height = 280
  const padLeft = 54
  const padRight = 22
  const padTop = 22
  const padBottom = 38
  const random = createRandom(mode === "low" ? 5 : 8)
  const values = Array.from({ length: 68 }, () => {
    if (mode === "low") return Math.max(0, (random() < 0.7 ? 0 : random() * 1.4) + (random() - 0.5) * 0.3)
    return 80 + (random() - 0.5) * 5
  })
  const domain = mode === "low" ? [0, 7] : [55, 95]
  const limit = mode === "low" ? 2.1 : 68
  const y = (value) => height - padBottom - ((value - domain[0]) / (domain[1] - domain[0])) * (height - padTop - padBottom)
  const x = (index) => padLeft + (index / (values.length - 1)) * (width - padLeft - padRight)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-72 w-full" role="img" aria-label={mode === "low" ? "USL 방향 판단 예시" : "LSL 방향 판단 예시"}>
      {[0, 1, 2, 3].map((gridIndex) => {
        const gridY = padTop + gridIndex * ((height - padTop - padBottom) / 3)
        const label = domain[1] - gridIndex * (domain[1] - domain[0]) / 3
        return (
          <g key={gridY}>
            <line x1={padLeft} y1={gridY} x2={width - padRight} y2={gridY} stroke={CHART_COLORS.grid} />
            <text x={padLeft - 10} y={gridY + 5} textAnchor="end" fill={CHART_COLORS.text} fontSize="14">{label.toFixed(0)}</text>
          </g>
        )
      })}
      <line x1={padLeft} y1={y(limit)} x2={width - padRight} y2={y(limit)} stroke={CHART_COLORS.limit} strokeWidth="1.8" strokeDasharray="6 4" opacity="0.75" />
      <text x={width - padRight} y={mode === "low" ? y(limit) - 10 : y(limit) + 20} textAnchor="end" fill={CHART_COLORS.limit} fontSize="15" fontWeight="700">
        {mode === "low" ? "USL" : "LSL"}
      </text>
      {values.map((value, index) => {
        const breach = mode === "low" ? value > limit : value < limit
        return (
          <circle
            key={`${index}-${value}`}
            cx={x(index)}
            cy={y(value)}
            r={breach ? 7.5 : 5}
            fill={breach ? CHART_COLORS.limit : CHART_COLORS.normal}
            opacity={breach ? 1 : 0.85}
          />
        )
      })}
      <text x={(padLeft + width - padRight) / 2} y={height - 10} textAnchor="middle" fill={CHART_COLORS.text} fontSize="13">{"tkin_time ->"}</text>
    </svg>
  )
}

function EwmaPairChart({ pattern }) {
  const width = 820
  const height = 360
  const padLeft = 50
  const padRight = 24
  const padTop = 24
  const topHeight = 150
  const bottomHeight = 100
  const middleGap = 30
  const random = createRandom(pattern === "sporadic" ? 14 : 19)
  let riskValue = 0
  const raw = []
  const risk = []

  for (let index = 0; index < 36; index += 1) {
    let value = 1 + (random() - 0.5) * (pattern === "sporadic" ? 0.6 : 0.4)
    if (pattern === "sporadic" && [8, 17, 26].includes(index)) value += 3.4 + random() * 0.8
    if (pattern === "gradual") value += Math.max(0, index - 6) * 0.17
    raw.push(value)
    riskValue = riskValue * 0.86 + (value > 3.3 ? 1 : 0) * 0.14
    risk.push(riskValue)
  }

  const x = (index) => padLeft + (index / (raw.length - 1)) * (width - padLeft - padRight)
  const yTop = (value) => padTop + topHeight - (value / 6.2) * topHeight
  const bottomTop = padTop + topHeight + middleGap
  const yBottom = (value) => bottomTop + bottomHeight - value * bottomHeight
  const rawPoints = raw.map((value, index) => [x(index), yTop(value)])
  const riskPoints = risk.map((value, index) => [x(index), yBottom(value)])
  const reachedIndex = risk.findIndex((value) => value > 0.5)
  const labelIndex = reachedIndex >= 0 ? reachedIndex : risk.indexOf(Math.max(...risk))

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-96 w-full" role="img" aria-label={pattern === "sporadic" ? "간헐적 튐 EWMA 예시" : "점진적 상승 EWMA 예시"}>
      {[0, 1, 2].map((gridIndex) => {
        const gridY = padTop + gridIndex * (topHeight / 2)
        return <line key={`top-${gridY}`} x1={padLeft} y1={gridY} x2={width - padRight} y2={gridY} stroke={CHART_COLORS.grid} />
      })}
      <line x1={padLeft} y1={yTop(3.3)} x2={width - padRight} y2={yTop(3.3)} stroke={CHART_COLORS.limit} strokeDasharray="4 4" opacity="0.6" />
      <text x={padLeft} y={yTop(3.3) - 8} fill={CHART_COLORS.limit} fontSize="14">USL/LSL</text>
      <path d={smoothPath(rawPoints)} fill="none" stroke={CHART_COLORS.normal} strokeWidth="1.8" />
      {raw.map((value, index) => (
        <circle key={`raw-${index}`} cx={x(index)} cy={yTop(value)} r={value > 3.3 ? 5.6 : 3.8} fill={value > 3.3 ? CHART_COLORS.warning : CHART_COLORS.normal} />
      ))}
      <text x={padLeft} y={padTop - 9} fill={CHART_COLORS.text} fontSize="14">bin_value</text>
      <line x1={padLeft} y1={padTop + topHeight + middleGap / 2} x2={width - padRight} y2={padTop + topHeight + middleGap / 2} stroke={CHART_COLORS.grid} />
      {[0, 1, 2].map((gridIndex) => {
        const gridY = bottomTop + gridIndex * (bottomHeight / 2)
        return <line key={`bottom-${gridY}`} x1={padLeft} y1={gridY} x2={width - padRight} y2={gridY} stroke={CHART_COLORS.grid} />
      })}
      <line x1={padLeft} y1={yBottom(0.5)} x2={width - padRight} y2={yBottom(0.5)} stroke={CHART_COLORS.signal} strokeDasharray="3 4" opacity="0.7" />
      <text x={padLeft} y={yBottom(0.5) - 7} fill={CHART_COLORS.signal} fontSize="13">임계치</text>
      <text x={padLeft} y={bottomTop - 8} fill={CHART_COLORS.text} fontSize="14">EWMA 위험도</text>
      <path d={smoothPath(riskPoints)} fill="none" stroke={CHART_COLORS.signal} strokeWidth="2.2" />
      <line x1={x(labelIndex)} y1={padTop} x2={x(labelIndex)} y2={bottomTop + bottomHeight} stroke={reachedIndex >= 0 ? CHART_COLORS.limit : CHART_COLORS.text} strokeDasharray="2 3" opacity="0.45" />
      <circle cx={x(labelIndex)} cy={yBottom(risk[labelIndex])} r="4.5" fill={reachedIndex >= 0 ? CHART_COLORS.limit : CHART_COLORS.text} />
      <text x={x(labelIndex)} y={bottomTop + bottomHeight + 20} textAnchor="middle" fill={reachedIndex >= 0 ? CHART_COLORS.limit : CHART_COLORS.text} fontSize="13" fontWeight={reachedIndex >= 0 ? "700" : "400"}>
        {reachedIndex >= 0 ? "ALERT" : "임계치 미도달"}
      </text>
      <text x={(padLeft + width - padRight) / 2} y={height - 12} textAnchor="middle" fill={CHART_COLORS.text} fontSize="13">{"tkin_time ->"}</text>
    </svg>
  )
}

function buildLotLabels(count, dateBase, subOffset = 0) {
  const prefixes = ["ABC", "DEF", "GHK", "LMN", "PQR", "STV"]
  return Array.from({ length: count }, (_, index) => {
    const prefix = prefixes[Math.floor((dateBase + index) / 7) % prefixes.length]
    const lot = `${prefix}${100 + ((dateBase + index * 3) % 900)}.${((index + subOffset) % 2) + 1}`
    return { lot }
  })
}

function buildChamberSeries(caseType, seed, targetLot) {
  const count = 24
  const random = createRandom(seed)
  const makeSeries = (peakAt, peakWidth, magnitude, gapIndexes) => Array.from({ length: count }, (_, index) => {
    if (gapIndexes?.has(index)) return null
    let value = 1 + (random() - 0.5) * 0.5
    if (peakAt != null && Math.abs(index - peakAt) <= peakWidth) {
      const distance = Math.abs(index - peakAt)
      const bell = 0.78 + 0.22 * (1 - distance / (peakWidth + 1))
      value += magnitude * bell + (random() - 0.5) * 0.4
    }
    return Math.max(0, value)
  })

  if (caseType === "all") {
    return {
      A: makeSeries(targetLot, 2, 3.6, null),
      B: makeSeries(targetLot, 2, 3.3, null),
      C: makeSeries(targetLot, 2, 3.8, null),
    }
  }
  if (caseType === "single") {
    return {
      A: makeSeries(targetLot, 2, 3.6, null),
      B: makeSeries(null, 0, 0, null),
      C: makeSeries(null, 0, 0, null),
    }
  }
  return {
    A: makeSeries(targetLot, 2, 3.6, null),
    B: makeSeries(null, 0, 0, new Set([7, 8, 9, 10, 11, 12, 13, 14, 15, 16])),
    C: makeSeries(null, 0, 0, new Set([5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18])),
  }
}

function ChamberColumnScatter({ label, values, labels, targetLot }) {
  const width = 320
  const height = 260
  const padLeft = 42
  const padRight = 14
  const padTop = 16
  const padBottom = 54
  const limit = 3.2
  const validIndexes = values.map((value, index) => (value === null ? null : index)).filter((index) => index !== null)
  const rankOf = new Map(validIndexes.map((index, rank) => [index, rank]))
  const gapBlocks = []

  values.forEach((value, index) => {
    if (value !== null) return
    let beforeRank = -1
    let afterRank = -1
    for (let prev = index - 1; prev >= 0; prev -= 1) {
      if (values[prev] !== null) {
        beforeRank = rankOf.get(prev)
        break
      }
    }
    for (let next = index + 1; next < values.length; next += 1) {
      if (values[next] !== null) {
        afterRank = rankOf.get(next)
        break
      }
    }
    if (!gapBlocks.length || gapBlocks[gapBlocks.length - 1].beforeRank !== beforeRank) {
      gapBlocks.push({ beforeRank, afterRank })
    }
  })

  const totalSlots = Math.max(1, validIndexes.length - 1 + gapBlocks.length * 1.4)
  const slotPosition = (rank) => rank + gapBlocks.reduce((offset, gap) => (gap.beforeRank < rank ? offset + 1.4 : offset), 0)
  const xByRank = (rank) => padLeft + (slotPosition(rank) / totalSlots) * (width - padLeft - padRight)
  const x = (index) => xByRank(rankOf.get(index))
  const xGapCenter = (beforeRank, afterRank) => {
    const beforeX = beforeRank >= 0 ? xByRank(beforeRank) : padLeft
    const afterX = afterRank >= 0 ? xByRank(afterRank) : width - padRight
    return (beforeX + afterX) / 2
  }
  const y = (value) => height - padBottom - (value / 6.4) * (height - padTop - padBottom)
  const highlighted = new Set(Array.from({ length: 5 }, (_, index) => targetLot - 2 + index).filter((index) => index >= 0 && index < values.length))

  return (
    <div className="rounded-lg border bg-card p-3">
      <p className="text-sm font-semibold text-foreground">{label}</p>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-2 h-72 w-full" role="img" aria-label={`${label} 챔버 산점도`}>
        {[0, 1, 2, 3].map((gridIndex) => {
          const gridY = padTop + gridIndex * ((height - padTop - padBottom) / 3)
          return <line key={gridY} x1={padLeft} y1={gridY} x2={width - padRight} y2={gridY} stroke={CHART_COLORS.grid} />
        })}
        <text x="14" y={(padTop + height - padBottom) / 2} textAnchor="middle" fill={CHART_COLORS.text} fontSize="11" transform={`rotate(-90 14 ${(padTop + height - padBottom) / 2})`}>bin_value</text>
        <line x1={padLeft} y1={y(limit)} x2={width - padRight} y2={y(limit)} stroke={CHART_COLORS.limit} strokeDasharray="4 3" opacity="0.65" />
        <text x={width - padRight} y={y(limit) - 6} textAnchor="end" fill={CHART_COLORS.limit} fontSize="10.5" fontWeight="700">USL</text>
        {gapBlocks.map((gap) => (
          <g key={`${gap.beforeRank}-${gap.afterRank}`}>
            <rect x={gap.beforeRank >= 0 ? xByRank(gap.beforeRank) : padLeft} y={padTop} width={Math.max(0, (gap.afterRank >= 0 ? xByRank(gap.afterRank) : width - padRight) - (gap.beforeRank >= 0 ? xByRank(gap.beforeRank) : padLeft))} height={height - padTop - padBottom} fill={CHART_COLORS.muted} opacity="0.65" />
            <text x={xGapCenter(gap.beforeRank, gap.afterRank)} y={(padTop + height - padBottom) / 2} textAnchor="middle" fill={CHART_COLORS.text} fontSize="10.5">미배정 구간</text>
          </g>
        ))}
        {values.map((value, index) => {
          if (value === null) return null
          const breach = value > limit
          return (
            <g key={`${label}-${index}`}>
              <circle cx={x(index)} cy={y(value)} r={breach ? 6.2 : 4.6} fill={breach ? CHART_COLORS.warning : CHART_COLORS.normal} opacity={breach ? 0.95 : 0.8} />
              {highlighted.has(index) ? <circle cx={x(index)} cy={y(value)} r={breach ? 10.2 : 8.6} fill="none" stroke={CHART_COLORS.accent} strokeWidth="1.3" opacity="0.65" /> : null}
            </g>
          )
        })}
        {values[targetLot] === null ? (
          <text x={xGapCenter(gapBlocks[0]?.beforeRank ?? -1, gapBlocks[0]?.afterRank ?? -1)} y={height - padBottom + 18} textAnchor="middle" fill={CHART_COLORS.text} fontSize="11" fontWeight="700">이 랏 미진행</text>
        ) : (
          <text x={x(targetLot)} y={height - padBottom + 18} textAnchor="middle" fill={CHART_COLORS.foreground} fontSize="12" fontWeight="700">{labels[targetLot].lot}</text>
        )}
        <text x={(padLeft + width - padRight) / 2} y={height - 8} textAnchor="middle" fill={CHART_COLORS.text} fontSize="10">{"tkin_time · lot_id · wafer_id ->"}</text>
      </svg>
    </div>
  )
}

function ChamberSplitCase({ caseType, title, caption, seed, targetLot, subOffset = 0 }) {
  const labels = buildLotLabels(24, seed * 7, subOffset)
  const seriesMap = buildChamberSeries(caseType, seed, targetLot)
  return (
    <AlgorithmChartCard
      title={title}
      legend={[["정상 범위 이탈", "bg-chart-1"], ["같은 lot 구간", "bg-chart-3"], ["정상", "bg-muted-foreground"]]}
      caption={caption}
    >
      <div className="grid gap-3 xl:grid-cols-3">
        {["A", "B", "C"].map((chamber) => (
          <ChamberColumnScatter
            key={chamber}
            label={`EXXX301-${chamber}`}
            values={seriesMap[chamber]}
            labels={labels}
            targetLot={targetLot}
          />
        ))}
      </div>
    </AlgorithmChartCard>
  )
}

function FingerprintTimeline() {
  const days = [
    { date: "06-24", fingerprint: "a3f9c12b", action: "SAVE", reason: "최초 감지", tone: "destructive" },
    { date: "06-25", fingerprint: "a3f9c12b", action: "skip", reason: "변화 없음", tone: "muted" },
    { date: "06-26", fingerprint: "a3f9c12b", action: "skip", reason: "변화 없음", tone: "muted" },
    { date: "06-27", fingerprint: "a3f9c12b", action: "skip", reason: "변화 없음", tone: "muted" },
    { date: "06-28", fingerprint: "f9a1b23c", action: "SAVE", reason: "챔버 구성 변경", tone: "chart" },
    { date: "06-29", fingerprint: "f9a1b23c", action: "skip", reason: "변화 없음", tone: "muted" },
    { date: "06-30", fingerprint: "c8e4f12a", action: "SAVE", reason: "신규 EDS 도착", tone: "primary" },
  ]
  const toneClass = {
    destructive: "border-destructive/40 bg-destructive/10 text-destructive",
    muted: "border-border bg-muted text-muted-foreground",
    chart: "border-chart-1/40 bg-chart-1/10 text-chart-1",
    primary: "border-primary/40 bg-primary/10 text-primary",
  }

  return (
    <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-7">
      {days.map((day) => (
        <div key={day.date} className={cn("rounded-lg border p-3", toneClass[day.tone])}>
          <p className="font-mono text-xs">{day.date}</p>
          <div className="mt-3 h-1.5 rounded-full bg-current opacity-50" />
          <p className="mt-3 font-mono text-xs">{day.fingerprint}</p>
          <p className="mt-1 text-sm font-semibold">{day.action}</p>
          <p className="mt-1 text-xs">{day.reason}</p>
        </div>
      ))}
    </div>
  )
}

function AlgorithmGuideContent() {
  return (
    <div>
      <GuideHero
        eyebrow="L3 Spider · Algorithm guide"
        title="챔버 하나가 흔들리면, 사람보다 먼저 잡아냅니다."
        description="매일 쏟아지는 EDS 수율 데이터 속에서 어느 챔버가, 언제부터, 얼마나 이상해졌는지 자동으로 골라내는 알고리즘의 작동 원리를 실제 데이터 예시와 시각화로 설명합니다."
        badges={["대상 EDS bin_value", "단위 챔버 × bin 항목", "주기 일 1회 batch"]}
        variant="algorithm"
      />
      <div className="grid gap-10 px-8 py-8">
        <section id="intro" className="scroll-mt-6 space-y-5">
          <h3 className="text-2xl font-semibold tracking-tight text-foreground">왜 필요한가</h3>
          <p className="max-w-4xl text-sm leading-6 text-muted-foreground">
            단일 lot 또는 단일 wafer의 튐만 보면 실제 챔버 문제와 일시적인 노이즈를 구분하기 어렵습니다. L3 Spider는 최근 기준선, 같은 시간대의 챔버 비교, 반복성 확인을 결합해 운영자가 먼저 볼 가치가 있는 신호만 끌어올립니다.
          </p>
          <AlgorithmChartCard
            title="BIN00XX · EXXX301-2"
            legend={[["정상", "bg-muted-foreground"], ["일시 spike", "bg-chart-1"], ["알람 확정", "bg-destructive"]]}
          >
            <HeroTraceChart />
          </AlgorithmChartCard>
        </section>

        <section id="phase1" className="scroll-mt-6 space-y-5">
          <h3 className="text-2xl font-semibold tracking-tight text-foreground">1단계 · 스파이크 감지</h3>
          <p className="max-w-4xl text-sm leading-6 text-muted-foreground">
            같은 챔버, 같은 bin 항목의 최근 데이터를 기준선으로 삼고, 값의 방향과 반복성을 함께 봅니다. 기준선은 고정값이 아니라 최근 분포에서 매번 다시 계산됩니다.
          </p>
          <AlgorithmChartCard
            title="기준 범위 설정 · scatter + boxplot"
            legend={[["정상 범위 내", "bg-muted-foreground"], ["범위 이탈", "bg-chart-1"], ["USL", "bg-chart-2"]]}
            caption="왼쪽은 시간순 산점도, 오른쪽은 같은 데이터를 하나의 박스플롯으로 모은 화면입니다. 박스플롯에서 계산된 USL이 산점도 기준선으로 이어집니다."
          >
            <RangeFacetChart />
          </AlgorithmChartCard>
          <div className="grid gap-4 lg:grid-cols-2">
            <AlgorithmChartCard
              title="CASE 1 · BIN00XX · USL 설정"
              legend={[["USL 위반", "bg-destructive"], ["정상", "bg-muted-foreground"]]}
              caption="값이 대부분 50 미만에 몰려 있으면 위로 튈 때 이상으로 봅니다."
            >
              <DirectionCaseChart mode="low" />
            </AlgorithmChartCard>
            <AlgorithmChartCard
              title="CASE 2 · YIELD · LSL 설정"
              legend={[["LSL 위반", "bg-destructive"], ["정상", "bg-muted-foreground"]]}
              caption="값이 대부분 50 이상에 몰려 있으면 아래로 떨어질 때 이상으로 봅니다."
            >
              <DirectionCaseChart mode="high" />
            </AlgorithmChartCard>
          </div>
          <AlgorithmChartCard
            title="CASE 1 · 간헐적 튐 · 알람 미확정"
            legend={[["bin_value", "bg-muted-foreground"], ["EWMA", "bg-chart-2"], ["범위 이탈", "bg-chart-1"]]}
            caption="단발성 spike는 위험도 점수가 금방 가라앉아 임계치에 도달하지 않습니다."
          >
            <EwmaPairChart pattern="sporadic" />
          </AlgorithmChartCard>
          <AlgorithmChartCard
            title="CASE 2 · 점진적 상승 · 알람 확정"
            legend={[["bin_value", "bg-muted-foreground"], ["EWMA", "bg-chart-2"], ["알람", "bg-destructive"]]}
            caption="작은 이탈이라도 같은 방향으로 누적되면 EWMA 위험도가 임계치를 넘어 알람으로 확정됩니다."
          >
            <EwmaPairChart pattern="gradual" />
          </AlgorithmChartCard>
        </section>

        <section id="phase2" className="scroll-mt-6 space-y-5">
          <h3 className="text-2xl font-semibold tracking-tight text-foreground">2단계 · 챔버 교차검증</h3>
          <p className="max-w-4xl text-sm leading-6 text-muted-foreground">
            같은 lot 구간에서 여러 챔버가 함께 튀면 공정/제품 요인을 의심하고, 특정 챔버만 반복적으로 튀면 챔버 고유 문제 가능성을 높게 봅니다.
          </p>
          <div className="overflow-hidden rounded-lg border bg-card">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-semibold">상황</th>
                  <th className="px-4 py-3 font-semibold">분류</th>
                  <th className="px-4 py-3 font-semibold">의미</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {[
                  ["내 챔버 불량률이 30% 이상이고 다른 챔버보다 30%p 이상 높음", "High Risk Chamber", "이 챔버를 점검해야 하는 진짜 챔버 이슈"],
                  ["같은 lot의 다른 챔버도 비슷하게 나쁨", "Warning", "앞 공정 문제 가능성"],
                  ["비교할 다른 챔버가 이 lot엔 없음", "Warning", "단일 챔버 흐름이라 비교 불가"],
                  ["알람 자체가 없음", "Normal", "정상"],
                ].map(([situation, status, meaning]) => (
                  <tr key={situation}>
                    <td className="px-4 py-3 text-muted-foreground">{situation}</td>
                    <td className="px-4 py-3">
                      <Badge variant={status === "High Risk Chamber" ? "destructive" : status === "Normal" ? "secondary" : "default"}>{status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ChamberSplitCase
            caseType="all"
            seed={31}
            targetLot={14}
            title="CASE A · 전 챔버 동반 이상 -> SKIP"
            caption="A, B, C 챔버가 같은 lot 구간에서 동시에 연속으로 튀면 챔버 개별 문제가 아니라 incoming issue로 보고 챔버 단위 알람은 건너뜁니다."
          />
          <ChamberSplitCase
            caseType="single"
            seed={37}
            targetLot={14}
            title="CASE B · 챔버 A만 단독 이상 -> High Risk Chamber"
            caption="같은 lot, 같은 타이밍인데 A만 튀고 B, C는 정상 범위에 머물면 챔버 A 단독 문제로 분류합니다."
          />
          <ChamberSplitCase
            caseType="lone"
            seed={41}
            targetLot={13}
            subOffset={1}
            title="CASE C · 단일 챔버만 진행 -> Warning"
            caption="B, C 챔버가 해당 lot 구간을 처리하지 않아 비교 대상이 없으면 챔버 탓인지 단정하지 않고 Warning으로만 표시합니다."
          />
        </section>

        <section id="fadeout" className="scroll-mt-6 space-y-5">
          <h3 className="text-2xl font-semibold tracking-tight text-foreground">중복 알람 방지</h3>
          <p className="max-w-4xl text-sm leading-6 text-muted-foreground">
            새 EDS 데이터가 없고 알람 챔버 구성도 같으면 같은 문제를 매일 새 알람처럼 저장하지 않습니다. fingerprint가 바뀌거나 신규 데이터가 들어온 경우에만 다시 저장합니다.
          </p>
          <FingerprintTimeline />
        </section>

        <section id="read" className="scroll-mt-6 space-y-5">
          <h3 className="text-2xl font-semibold tracking-tight text-foreground">화면 읽는 법</h3>
          <NumberedCallouts
            points={[
              ["빨간 점", "High Risk로 확정된 값입니다. 같은 시간대와 챔버 분포를 함께 봅니다."],
              ["주황 점", "Warning 또는 관찰 대상 신호입니다. 반복되면 rule 등록 후보입니다."],
              ["회색 점", "정상 기준 데이터입니다. 기준선의 폭과 최근 흐름을 판단하는 참고값입니다."],
              ["빈 구간", "해당 lot을 그 챔버가 처리하지 않은 구간일 수 있으므로 직접 비교 대상에서 제외합니다."],
            ]}
          />
        </section>

        <section id="faq" className="scroll-mt-6 space-y-4">
          <h3 className="text-2xl font-semibold tracking-tight text-foreground">자주 묻는 질문</h3>
          {FAQS.map(([question, answer]) => (
            <div key={question} className="rounded-lg border bg-card p-4">
              <p className="text-sm font-semibold text-foreground">{question}</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{answer}</p>
            </div>
          ))}
        </section>

        <section id="glossary" className="scroll-mt-6 space-y-4">
          <h3 className="text-2xl font-semibold tracking-tight text-foreground">용어집</h3>
          <div className="grid gap-3 md:grid-cols-2">
            {[
              ["EQPCH", "설비 챔버 단위 식별자"],
              ["PPID", "공정 recipe 또는 조건 식별자"],
              ["EDS Step", "EDS 측정 단계"],
              ["EWMA", "최근 값을 더 크게 반영하는 지수 가중 이동 평균"],
            ].map(([term, body]) => (
              <div key={term} className="rounded-lg border bg-card p-4">
                <p className="font-mono text-sm font-semibold text-foreground">{term}</p>
                <p className="mt-2 text-sm text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

export function L3SpiderGuideDialog({ guideKey, onGuideKeyChange }) {
  const scrollRef = useRef(null)
  const [activeSection, setActiveSection] = useState("")
  const activeMeta = guideKey ? GUIDE_META[guideKey] : null
  const sections = guideKey === "algorithm" ? ALGORITHM_SECTIONS : PAGE_SECTIONS
  const Icon = activeMeta?.icon ?? BookOpen

  useEffect(() => {
    setActiveSection(sections[0]?.id ?? "")
    scrollRef.current?.scrollTo({ top: 0 })
  }, [guideKey, sections])

  useEffect(() => {
    const container = scrollRef.current
    if (!container || !guideKey) return undefined

    const handleScroll = () => {
      const current = sections.reduce((selected, section) => {
        const element = container.querySelector(`#${section.id}`)
        if (!element) return selected
        const offset = element.getBoundingClientRect().top - container.getBoundingClientRect().top
        return offset <= 120 ? section.id : selected
      }, sections[0]?.id ?? "")
      setActiveSection(current)
    }

    handleScroll()
    container.addEventListener("scroll", handleScroll, { passive: true })
    return () => container.removeEventListener("scroll", handleScroll)
  }, [guideKey, sections])

  const handleOpenChange = (open) => {
    if (!open) onGuideKeyChange(null)
  }

  const scrollToSection = (sectionId) => {
    const container = scrollRef.current
    const element = container?.querySelector(`#${sectionId}`)
    if (!container || !element) return
    const top = element.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop - 16
    container.scrollTo({ top, behavior: "smooth" })
    setActiveSection(sectionId)
  }

  return (
    <Dialog open={Boolean(activeMeta)} onOpenChange={handleOpenChange}>
      <DialogContent className="grid h-[90dvh] max-h-[90dvh] w-[80vw] max-w-[80vw] grid-rows-[auto,minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:w-[80vw] sm:max-w-[80vw]">
        <DialogHeader className="shrink-0 border-b px-5 py-3 pr-14 text-left">
          <div className="flex flex-nowrap items-center justify-between gap-4">
            <div className="min-w-0 flex-1">
              <DialogTitle className="flex min-w-0 items-center gap-2">
                <Icon className="size-5 shrink-0 text-primary" aria-hidden="true" />
                <span className="truncate">{activeMeta?.title}</span>
              </DialogTitle>
              <DialogDescription className="mt-1">
                {activeMeta?.description}
              </DialogDescription>
            </div>
            <Tabs value={guideKey ?? "page"} onValueChange={onGuideKeyChange} className="shrink-0">
              <TabsList className="flex-nowrap">
                <TabsTrigger value="page" className="whitespace-nowrap">페이지 설명서</TabsTrigger>
                <TabsTrigger value="algorithm" className="whitespace-nowrap">알고리즘 설명서</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </DialogHeader>
        <div className="min-h-0 overflow-hidden">
          <GuideShell
            sections={sections}
            activeSection={activeSection}
            onSectionClick={scrollToSection}
            scrollRef={scrollRef}
          >
            {guideKey === "algorithm" ? <AlgorithmGuideContent /> : <PageGuideContent />}
          </GuideShell>
        </div>
      </DialogContent>
    </Dialog>
  )
}
