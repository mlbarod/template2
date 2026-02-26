// 파일 경로: src/features/line-dashboard/utils/dataTableFormatters.jsx
// 테이블 셀 표시/검색/스텝 렌더링에 필요한 포맷터 모음입니다.

import { useCallback, useEffect, useRef } from "react"
import { IconArrowNarrowRight } from "@tabler/icons-react"
import { cn } from "@/lib/utils"

/* ============================================
 * 공통 상수
 * ============================================ */

/** 길이가 긴 문자열을 줄여 보여줄지 결정할 기준(초과 시 작은 폰트로 표시) */
const LONG_STRING_THRESHOLD = 120

/** metro_steps 문자열을 배열로 바꿀 때 사용할 구분자들 */
const STEP_SPLIT_REGEX = />|→|,|\|/g

/** NULL/빈문자열 시 보여줄 플레이스홀더 */
const PLACEHOLDER = {
  null: <span className="text-muted-foreground">NULL</span>,
  emptyString: <span className="text-muted-foreground">{"\"\""}</span>,
  noSteps: <span className="text-muted-foreground">-</span>,
}

/* ============================================
 * 공통 유틸
 * ============================================ */

function toBooleanFlag(value) {
  if (typeof value === "boolean") return value
  if (value === null || value === undefined) return false
  if (typeof value === "number" && Number.isFinite(value)) return value > 0
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase()
    if (!normalized) return false
    if (["1", "true", "t", "y", "yes"].includes(normalized)) return true
    if (["0", "false", "f", "n", "no"].includes(normalized)) return false
    const numeric = Number(normalized)
    return Number.isFinite(numeric) ? numeric > 0 : false
  }
  if (typeof value === "bigint") return Number(value) > 0
  return false
}

/* ============================================
 * 날짜/문자 유틸
 * ============================================ */

const KST_TIME_ZONE = "Asia/Seoul"
const kstPartsFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: KST_TIME_ZONE,
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
})

function formatKstDate(value, { withSeconds = false } = {}) {
  const parsedDate = tryParseDate(value)
  if (!parsedDate) return null
  const parts = kstPartsFormatter.formatToParts(parsedDate).reduce((acc, part) => {
    if (part.type in acc) return acc
    acc[part.type] = part.value
    return acc
  }, {})

  const base = `${parts.month ?? "00"}/${parts.day ?? "00"} ${parts.hour ?? "00"}:${parts.minute ?? "00"}`
  if (withSeconds) {
    return `${base}:${parts.second ?? "00"}`
  }
  return base
}

/**
 * (표시용) 짧은 날짜 포맷: MM/DD HH:mm (KST)
 */
function formatShortDateTime(date) {
  return formatKstDate(date) ?? ""
}

export function formatTooltipValue(value) {
  const formatted = formatKstDate(value, { withSeconds: true })
  if (formatted) return formatted
  if (typeof value === "string" || typeof value === "number") {
    return String(value)
  }
  return undefined
}

/**
 * 문자열/Date 값을 Date로 파싱. 실패 시 null.
 * 허용 형식:
 *  - YYYY-MM-DD
 *  - YYYY-MM-DD HH:mm
 *  - YYYY-MM-DDTHH:mm(초/타임존 포함 가능)
 */
function tryParseDate(value) {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  if (typeof value === "string") {
    const s = value.trim()
    if (!s) return null

    // 빠른 가드: 날짜 형태가 아니면 즉시 탈출
    const looksLikeDateTime = /\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}/.test(s)
    const looksLikeDateOnly = /\d{4}-\d{2}-\d{2}$/.test(s)
    if (!looksLikeDateTime && !looksLikeDateOnly) return null

    const d = new Date(s)
    return Number.isNaN(d.getTime()) ? null : d
  }
  return null
}

/**
 * 모든 타입을 소문자 문자열로 안전 변환 (검색용)
 * @param {any} v
 * @returns {string}
 */
function toLowerSafeString(v) {
  try {
    if (v === null || v === undefined) return ""
    if (typeof v === "string") return v.toLowerCase()
    if (typeof v === "number" || typeof v === "bigint") return String(v).toLowerCase()
    if (typeof v === "boolean") return v ? "true" : "false"
    return JSON.stringify(v).toLowerCase()
  } catch {
    return String(v).toLowerCase()
  }
}

/* ============================================
 * 셀 값 포맷터 / 검색 토큰
 * ============================================ */

/**
 * 표 셀에 표시할 값 렌더링 (ReactNode 반환)
 * - null/undefined → 회색 "NULL"
 * - boolean → TRUE/FALSE
 * - number/bigint → 문자열화
 * - 날짜 문자열/객체 → MM/DD HH:mm
 * - string(빈문자) → 회색 "" 표시
 * - string(길이>LONG_STRING_THRESHOLD) → 작은 폰트로 프리랩
 * - 기타 → JSON.stringify 또는 String
 */
export function formatCellValue(value) {
  if (value === null || value === undefined) return PLACEHOLDER.null
  if (typeof value === "boolean") return value ? "TRUE" : "FALSE"
  if (typeof value === "number" || typeof value === "bigint") return String(value)

  // 날짜 처리: 문자열/Date 모두 tryParseDate 사용
  const parsedDate = tryParseDate(value)
  if (parsedDate) return formatShortDateTime(parsedDate)

  if (typeof value === "string") {
    if (value.length === 0) return PLACEHOLDER.emptyString
    if (value.length > LONG_STRING_THRESHOLD) {
      return (
        <span className="whitespace-pre-wrap break-all text-xs leading-relaxed">
          {value}
        </span>
      )
    }
    return value
  }

  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

/**
 * 검색 인덱싱용 값 변환 (plain string)
 * - 날짜는 표시형(MM/DD HH:mm) + ISO 문자열을 함께 포함해 검색 확장
 */
export function searchableValue(value) {
  if (value === null || value === undefined) return ""
  const parsedDate = tryParseDate(value)
  if (parsedDate) {
    const human = formatShortDateTime(parsedDate)
    return `${human} ${parsedDate.toISOString()}`.toLowerCase()
  }
  return toLowerSafeString(value)
}

/* ============================================
 * 스텝 관련 유틸
 * ============================================ */

/**
 * 스텝 값 정규화: 문자열로 캐스팅 → 트림 → 빈문자면 null
 */
export function normalizeStepValue(value) {
  if (value === null || value === undefined) return null
  const normalized = String(value).trim()
  return normalized.length > 0 ? normalized : null
}

/**
 * metro_steps → 문자열/배열 모두를 "정규화된 문자열 배열"로 통일
 * - 허용 구분자: '>', '→', ',', '|'
 * - 각 원소는 normalizeStepValue 거쳐 공백 제거
 * - falsy 원소 제거
 */
export function parseMetroSteps(value) {
  if (Array.isArray(value)) {
    return value
      .map(normalizeStepValue)
      .filter(Boolean)
  }
  if (typeof value === "string") {
    return value
      .split(STEP_SPLIT_REGEX)
      .map(normalizeStepValue)
      .filter(Boolean)
  }
  const single = normalizeStepValue(value)
  return single ? [single] : []
}

/**
 * 배열의 순서를 유지한 채 중복 제거
 */
function uniquePreserveOrder(arr) {
  const seen = new Set()
  const out = []
  for (const x of arr) {
    if (!seen.has(x)) {
      seen.add(x)
      out.push(x)
    }
  }
  return out
}

/** 스텝 배지의 스타일 클래스를 결정
 * - main_step: 사각형 (rounded-none)
 * - current(현재 스텝): 연한 파란색 배경
 * - 그 외: 기본 스타일
 */
function getStepPillClasses({ isMain, isCurrent }) {
  return cn(
    "border px-2 py-0.5 text-xs font-light leading-none transition-colors",
    isMain ? "rounded-sm" : "rounded-full",
    isCurrent
      ? "bg-primary border-primary text-primary-foreground"
      : "bg-card border-border text-foreground"
  )
}

/* ============================================
 * Metro Step Flow 렌더링 컴포넌트
 * - 가로 드래그(grab)로 이동
 * - x축 스크롤바는 숨김 (scroll-x-hide 클래스 필요)
 * - 텍스트 드래그 선택 방지 (select-none)
 * - 한번 눌러서 잡으면, 영역 밖으로 나가도 window 기준으로 계속 드래그 유지
 * ============================================ */

function MetroStepFlowCell({ rowData }) {
  const containerRef = useRef(null)

  // 드래그 상태를 저장 (state 대신 ref 사용: 리렌더 유발 X)
  const dragStateRef = useRef({
    isDragging: false,
    startX: 0,
    scrollLeft: 0,
  })

  const startDrag = useCallback((event) => {
    const el = containerRef.current
    if (!el) return
    if (event.button !== 0) return
    // 서버 환경 보호 (이론상 마우스 이벤트는 브라우저에서만 발생하지만, 안전하게 한 번 더 가드)
    if (typeof window === "undefined") return

    const state = dragStateRef.current
    state.isDragging = true
    state.startX = event.clientX
    state.scrollLeft = el.scrollLeft

    // 👉 윈도우 전체에 mousemove / mouseup 리스너 등록
    const handleMouseMoveWindow = (moveEvent) => {
      const dragState = dragStateRef.current
      if (!dragState.isDragging) return

      const deltaX = moveEvent.clientX - dragState.startX
      el.scrollLeft = dragState.scrollLeft - deltaX
      moveEvent.preventDefault() // 텍스트 선택 방지
    }

    const handleMouseUpWindow = () => {
      dragStateRef.current.isDragging = false
      window.removeEventListener("mousemove", handleMouseMoveWindow)
      window.removeEventListener("mouseup", handleMouseUpWindow)
    }

    window.addEventListener("mousemove", handleMouseMoveWindow)
    window.addEventListener("mouseup", handleMouseUpWindow)
  }, [])

  const handleMouseDown = useCallback(
    (event) => {
      startDrag(event)
    },
    [startDrag]
  )

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const cell = container.closest("td")
    if (!cell) return

    const handleMouseDownOnCell = (event) => {
      const root = containerRef.current
      if (!root) return
      if (root.contains(event.target)) return
      startDrag(event)
    }

    cell.addEventListener("mousedown", handleMouseDownOnCell)
    return () => {
      cell.removeEventListener("mousedown", handleMouseDownOnCell)
    }
  }, [startDrag])

  // ─────────────────────────────────────────────
  // 아래부터는 기존 renderMetroStepFlow 로직
  // ─────────────────────────────────────────────

  const mainStep = normalizeStepValue(rowData.main_step)
  const metroSteps = parseMetroSteps(rowData.metro_steps)
  const informStep = normalizeStepValue(rowData.inform_step)           // 위치 정보로만 사용
  const currentStep = normalizeStepValue(rowData.metro_current_step)
  const customEndStep = normalizeStepValue(rowData.custom_end_step)
  const metroEndStep = normalizeStepValue(rowData.metro_end_step)
  const needToSend = toBooleanFlag(rowData.needtosend)                 // 예약(보낼 예정)
  const sendJira = toBooleanFlag(rowData.send_jira)
  const sendMessenger = toBooleanFlag(rowData.send_messenger)
  const sendMail = toBooleanFlag(rowData.send_mail)
  const isAnyInformed = sendJira || sendMessenger || sendMail          // 채널 중 하나라도 전송 완료

  // END 표시 후보: custom_end_step 우선 → metro_end_step
  const endStep = customEndStep || metroEndStep

  // 표시 순서: MAIN → METRO 배열 → INFORM(중복 제거, 순서 보존)
  const orderedSteps = uniquePreserveOrder([
    ...(mainStep ? [mainStep] : []),
    ...metroSteps,
    ...(informStep ? [informStep] : []),
  ])
  if (orderedSteps.length === 0) return PLACEHOLDER.noSteps

  const labelClasses = {
    MAIN: "text-[10px] leading-none text-muted-foreground",
    END: "text-[10px] leading-none text-muted-foreground",
    CustomEND: "text-[10px] leading-none font-semibold text-primary",
    "인폼예정": "text-[10px] leading-none text-muted-foreground",
    "Inform 완료": "text-[10px] leading-none font-semibold text-primary",
  }

  // 인폼 라벨 결정
  // - sendjira = true          → Inform 완료 (위치는 inform_step || endStep)
  // - sendjira = false, need=1 → 인폼예정   (위치는 custom_end_step || metro_end_step)
  let informLabelType = "none"  // "none" | "done" | "planned"
  let informLabelStep = null

  if (isAnyInformed) {
    informLabelType = "done"
    informLabelStep = informStep || endStep || null
  } else if (needToSend) {
    if (customEndStep) {
      informLabelType = "planned"
      informLabelStep = customEndStep
    } else if (metroEndStep) {
      informLabelType = "planned"
      informLabelStep = metroEndStep
    }
  }

  return (
    <div
      ref={containerRef}
      className="
        max-w-full
        overflow-x-auto
        overflow-y-hidden
        scroll-x-hide
        cursor-grab
        active:cursor-grabbing
        select-none
      "
      onMouseDown={handleMouseDown}
    >
      <div className="flex flex-nowrap items-start gap-1">
        {orderedSteps.map((step, index) => {
          const isMain = !!mainStep && step === mainStep
          const isCurrent = !!currentStep && step === currentStep
          const labels = new Set()

          if (isMain) labels.add("MAIN")

          // 현재 스텝에 붙일 라벨 여부
          const isEndHere = Boolean(endStep && step === endStep)
          const isInformHere = Boolean(
            informLabelType !== "none" && informLabelStep && step === informLabelStep
          )

          // END/CustomEND는 Inform 라벨이 없을 때만 표기(겹침 방지)
          if (!isInformHere && isEndHere) {
            labels.add(customEndStep ? "CustomEND" : "END")
          }

          // Inform 라벨(완료/예정)
          if (isInformHere) {
            labels.add(informLabelType === "done" ? "Inform 완료" : "인폼예정")
          }

          return (
            <div key={`${step}-${index}`} className="flex shrink-0 items-start gap-1">
              {index > 0 && (
                <IconArrowNarrowRight className="size-4 shrink-0 text-muted-foreground mt-0.5" />
              )}
              <div className="flex flex-col items-center gap-0.5">
                <span className={getStepPillClasses({ isMain, isCurrent })}>
                  {step}
                </span>
                {[...labels].map((label, i) => (
                  <span
                    key={`${step}-label-${i}`}
                    className={
                      labelClasses[label] ||
                      "text-[10px] leading-none text-muted-foreground"
                    }
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ============================================
 * 외부에서 쓰는 엔트리 포인트
 * (TanStack Table cell 등에서 사용)
 * ============================================ */

export function renderMetroStepFlow(rowData) {
  // React 컴포넌트를 반환해서, 훅(useRef)은 MetroStepFlowCell 안에서만 사용
  return <MetroStepFlowCell rowData={rowData} />
}
