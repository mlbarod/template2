// 파일 경로: src/features/line-dashboard/components/DataTableColumnRenderers.jsx
// 컬럼별로 서로 다른 UI 표현을 담당하는 렌더러 모음입니다.
import { ExternalLink, Check, AlertTriangle } from "lucide-react"
import { toast } from "sonner"

import {
  buildJiraBrowseUrl,
  getRecordId,
  normalizeComment,
  normalizeInstantInform,
  normalizeJiraKey,
  normalizeNeedToSend,
  normalizeStatus,
  toHttpUrl,
} from "../utils/dataTableColumnNormalizers"
import {
  formatCellValue,
  normalizeStepValue,
  parseMetroSteps,
} from "../utils/dataTableFormatters"
import { STATUS_LABELS } from "../utils/statusLabels"
import { CommentCell } from "./CommentCell"
import { InstantInformCell } from "./InstantInformCell"
import { NeedToSendCell } from "./NeedToSendCell"
import { deriveFlagState } from "../utils/dataTableFlagState"
import { buildToastOptions } from "../utils/toast"

const CHANNEL_LABELS = {
  send_jira: "JIRA",
  send_messenger: "MSG",
  send_mail: "MAIL",
}

const CHANNEL_REASON_KEYS = {
  send_jira: ["jiraReason", "jira_reason"],
  send_messenger: ["messengerReason", "messenger_reason"],
  send_mail: ["mailReason", "mail_reason"],
}

function resolveChannelReason(rowOriginal, channelKey) {
  if (!rowOriginal) return null
  const keys = CHANNEL_REASON_KEYS[channelKey] ?? []
  for (const key of keys) {
    const raw = rowOriginal?.[key]
    if (typeof raw === "string" && raw.trim()) return raw.trim()
  }
  return null
}

function showRetryQueuedToast(label) {
  toast.info(`${label} 재시도 요청 완료`, {
    description: "다음 배치 실행 시 해당 채널이 재처리됩니다.",
    ...buildToastOptions({ intent: "info", duration: 2200 }),
  })
}

function showRetryAlreadyPendingToast(label) {
  toast.info(`${label} 이미 대기 상태입니다.`, {
    description: "추가 변경 없이 다음 배치에서 처리됩니다.",
    ...buildToastOptions({ intent: "info", duration: 2200 }),
  })
}

function showRetryAlreadySentToast(label) {
  toast.info(`${label} 이미 전송 완료 상태입니다.`, {
    ...buildToastOptions({ intent: "info", duration: 2200 }),
  })
}

function showRetryUnknownStatusToast(status) {
  const normalized = typeof status === "string" && status.trim() ? status.trim() : "empty"
  toast.info("채널 재시도 응답 확인 필요", {
    description: `알 수 없는 상태값(${normalized})을 받았습니다. 새로고침 후 상태를 확인해 주세요.`,
    ...buildToastOptions({ intent: "info", duration: 2600 }),
  })
}

function showRetryFailedToast(message) {
  toast.error("채널 재시도 실패", {
    description: message || "채널 재시도 처리 중 오류가 발생했습니다.",
    ...buildToastOptions({ intent: "destructive", duration: 3000 }),
  })
}

function renderSendChannelCell({ value, rowOriginal, channelKey, meta }) {
  const { state, numericValue, isOn, isError } = deriveFlagState(value, 0)
  const label = CHANNEL_LABELS[channelKey] ?? channelKey
  const reason = resolveChannelReason(rowOriginal, channelKey)
  const recordId = getRecordId(rowOriginal)
  const cellKey = recordId ? `${recordId}:${channelKey}` : null
  const isRetryLoading = Boolean(cellKey && meta?.updatingCells?.[cellKey])
  const canRetry =
    isError &&
    !isRetryLoading &&
    Boolean(recordId) &&
    typeof meta?.handleRetryChannel === "function"
  const title =
    state === "error"
      ? canRetry
        ? `${label} 전송 오류 상태 (값: ${numericValue}${reason ? `, 사유: ${reason}` : ""}) - 클릭해 재시도`
        : `${label} 전송 오류 상태 (값: ${numericValue}${reason ? `, 사유: ${reason}` : ""})`
      : isOn
        ? `${label} 전송 완료`
        : `${label} 미전송`

  const icon = (
    <span
      className={[
        "inline-flex h-5 w-5 items-center justify-center rounded-full border text-muted-foreground transition-colors",
        state === "error"
          ? "border-destructive/60 bg-destructive/10 text-destructive"
          : isOn
            ? "bg-primary border-primary text-primary-foreground"
            : "border-border",
      ].join(" ")}
      title={title}
      aria-label={title}
      role="img"
    >
      {state === "error" ? (
        <AlertTriangle className="h-3 w-3" strokeWidth={3} />
      ) : isOn ? (
        <Check className="h-3 w-3" strokeWidth={3} />
      ) : null}
    </span>
  )

  if (!isError || typeof meta?.handleRetryChannel !== "function" || !recordId) {
    return icon
  }

  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={isRetryLoading}
      onClick={async () => {
        if (!canRetry) return
        const result = await meta.handleRetryChannel(recordId, { channelKey })
        if (!result?.ok) {
          showRetryFailedToast(result?.message)
          return
        }

        const status = typeof result.status === "string" ? result.status : ""
        if (status === "queued") {
          showRetryQueuedToast(label)
          return
        }
        if (status === "already_pending") {
          showRetryAlreadyPendingToast(label)
          return
        }
        if (status === "already_sent") {
          showRetryAlreadySentToast(label)
          return
        }
        showRetryUnknownStatusToast(status)
      }}
      className={[
        "inline-flex rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        canRetry ? "cursor-pointer" : "cursor-not-allowed opacity-70",
      ].join(" ")}
    >
      {icon}
    </button>
  )
}

const CellRenderers = {
  defect_url: ({ value }) => {
    const href = toHttpUrl(value)
    if (!href) return null
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center justify-center text-primary transition-colors hover:text-primary/80"
        aria-label="Open defect URL in a new tab"
        title="Open defect"
      >
        <ExternalLink className="h-4 w-4" />
      </a>
    )
  },

  jira_key: ({ value }) => {
    const key = normalizeJiraKey(value)
    const href = buildJiraBrowseUrl(key)
    if (!href || !key) return null
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-primary transition-colors hover:text-primary/80"
        aria-label={`Open JIRA issue ${key} in a new tab`}
        title={key}
      >
        <ExternalLink className="h-4 w-4" />
      </a>
    )
  },

  comment: ({ value, rowOriginal, meta }) => {
    const recordId = getRecordId(rowOriginal)
    if (!meta || !recordId) return formatCellValue(value)
    return (
      <CommentCell
        meta={meta}
        recordId={recordId}
        baseValue={normalizeComment(rowOriginal?.comment)}
      />
    )
  },

  instant_inform: ({ value, rowOriginal, meta }) => {
    const recordId = getRecordId(rowOriginal)
    if (!meta || !recordId) return formatCellValue(value)
    const baseState = deriveFlagState(normalizeInstantInform(rowOriginal?.instant_inform), 0)
    const isLocked = deriveFlagState(rowOriginal?.send_jira, 0).isOn
    return (
      <InstantInformCell
        meta={meta}
        recordId={recordId}
        baseValue={baseState.numericValue}
        rowOriginal={rowOriginal}
        disabled={isLocked}
        disabledReason="이미 JIRA 전송됨 (즉시인폼 불가)"
      />
    )
  },

  needtosend: ({ value, rowOriginal, meta }) => {
    const recordId = getRecordId(rowOriginal)
    if (!meta || !recordId) return formatCellValue(value)
    const baseState = deriveFlagState(normalizeNeedToSend(rowOriginal?.needtosend), 0)
    const sendJiraState = deriveFlagState(rowOriginal?.send_jira, 0)
    const instantInformState = deriveFlagState(normalizeInstantInform(rowOriginal?.instant_inform), 0)
    const isSendJiraComplete = sendJiraState.numericValue === 1
    const isInstantInformComplete = instantInformState.numericValue === 1
    const disabledReason = isSendJiraComplete
      ? "이미 JIRA 전송됨 (needtosend 수정 불가)"
      : isInstantInformComplete
        ? "이미 즉시 인폼됨 (needtosend 수정 불가)"
        : "needtosend 수정 불가"
    return (
      <NeedToSendCell
        meta={meta}
        recordId={recordId}
        baseValue={baseState.numericValue}
        state={baseState}
        sendJiraValue={sendJiraState.numericValue}
        instantInformValue={instantInformState.numericValue}
        disabled={isSendJiraComplete || isInstantInformComplete}
        disabledReason={disabledReason}
      />
    )
  },

  send_jira: ({ value, rowOriginal, meta }) =>
    renderSendChannelCell({ value, rowOriginal, meta, channelKey: "send_jira" }),
  send_messenger: ({ value, rowOriginal, meta }) =>
    renderSendChannelCell({ value, rowOriginal, meta, channelKey: "send_messenger" }),
  send_mail: ({ value, rowOriginal, meta }) =>
    renderSendChannelCell({ value, rowOriginal, meta, channelKey: "send_mail" }),

  status: ({ value, rowOriginal }) => {
    const status = normalizeStatus(value)
    const label = STATUS_LABELS[status] ?? status ?? "Unknown"
    const { completed, total } = computeMetroProgress(rowOriginal, status)
    const percent = total > 0 ? Math.min(100, Math.max(0, (completed / total) * 100)) : 0

    return (
      <div className="flex w-full flex-col gap-1">
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={Number.isFinite(percent) ? Math.round(percent) : 0}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuetext={`${completed} of ${total} steps`}
        >
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${percent}%` }}
            role="presentation"
          />
        </div>
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span className="truncate" title={label}>
            {label}
          </span>
          <span>
            {completed}
            <span aria-hidden="true">/</span>
            {total}
          </span>
        </div>
      </div>
    )
  },
}

function computeMetroProgress(rowOriginal, normalizedStatus) {
  const mainStep = normalizeStepValue(rowOriginal?.main_step)
  const metroSteps = parseMetroSteps(rowOriginal?.metro_steps)
  const customEndStep = normalizeStepValue(rowOriginal?.custom_end_step)
  const currentStep = normalizeStepValue(rowOriginal?.metro_current_step)

  const effectiveMetroSteps = (() => {
    if (!metroSteps.length) return []
    if (!customEndStep) return metroSteps
    const endIndex = metroSteps.findIndex((step) => step === customEndStep)
    return endIndex >= 0 ? metroSteps.slice(0, endIndex + 1) : metroSteps
  })()

  const orderedSteps = []
  if (mainStep && !metroSteps.includes(mainStep)) orderedSteps.push(mainStep)
  orderedSteps.push(...effectiveMetroSteps)

  const total = orderedSteps.length
  if (total === 0) return { completed: 0, total: 0 }

  let completed = 0
  if (!currentStep) {
    completed = 0
  } else {
    const currentIndex = orderedSteps.findIndex((step) => step === currentStep)

    if (customEndStep) {
      const currentIndexInFull = metroSteps.findIndex((step) => step === currentStep)
      const endIndexInFull = metroSteps.findIndex((step) => step === customEndStep)

      if (currentIndexInFull >= 0 && endIndexInFull >= 0 && currentIndexInFull > endIndexInFull) {
        completed = total
      } else if (currentIndex >= 0) {
        completed = currentIndex + 1
      }
    } else if (currentIndex >= 0) {
      completed = currentIndex + 1
    }
  }

  if (normalizedStatus === "COMPLETE") completed = total
  return { completed: Math.max(0, Math.min(completed, total)), total }
}

// 컬럼 키에 맞는 렌더러를 찾아 실행하고, 없으면 기본 포맷터를 사용합니다.
export function renderCellByKey(colKey, info) {
  const meta = info.table?.options?.meta
  const value = info.getValue()
  const rowOriginal = info.row?.original
  const renderer = CellRenderers[colKey]
  if (renderer) return renderer({ value, rowOriginal, meta })
  return formatCellValue(value)
}
