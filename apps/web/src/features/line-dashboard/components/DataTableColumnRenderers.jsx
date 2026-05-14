// 파일 경로: src/features/line-dashboard/components/DataTableColumnRenderers.jsx
// 컬럼별로 서로 다른 UI 표현을 담당하는 렌더러 모음입니다.
import * as React from "react"
import { ExternalLink } from "lucide-react"
import { toast } from "sonner"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  buildJiraBrowseUrl,
  getRecordId,
  normalizeComment,
  normalizeInstantInform,
  normalizeJiraKey,
  normalizeNeedToSend,
  normalizeStatus,
  parseDefectUrls,
} from "../utils/dataTableColumnNormalizers"
import {
  formatCellValue,
  normalizeStepValue,
  parseMetroSteps,
} from "../utils/dataTableFormatters"
import { isDeliveryChannelSuccessful } from "../utils/dataTableDelivery"
import { STATUS_LABELS } from "../utils/statusLabels"
import { CommentCell } from "./CommentCell"
import { InstantInformCell } from "./InstantInformCell"
import { NeedToSendCell } from "./NeedToSendCell"
import {
  DeliveryChannelSummaryCell,
  DeliverySummaryCell,
  TargetSummaryCell,
} from "./table/DeliveryCells"
import { deriveFlagState } from "../utils/dataTableFlagState"
import { buildToastOptions } from "../utils/toast"

async function copyTextToClipboard(text) {
  if (!text || !navigator?.clipboard?.writeText) {
    throw new Error("clipboard_unavailable")
  }
  await navigator.clipboard.writeText(text)
}

function showLotIdCopiedToast(lotId) {
  toast.success("LOT ID 복사 완료", {
    description: lotId,
    ...buildToastOptions({ intent: "success", duration: 1800 }),
  })
}

function showLotIdCopyFailedToast() {
  toast.error("LOT ID 복사 실패", {
    description: "클립보드에 값을 복사하지 못했습니다.",
    ...buildToastOptions({ intent: "destructive", duration: 2600 }),
  })
}

function DefectUrlHoverList({ links }) {
  const [open, setOpen] = React.useState(false)
  const closeTimerRef = React.useRef(null)

  const clearCloseTimer = React.useCallback(() => {
    if (!closeTimerRef.current) return
    window.clearTimeout(closeTimerRef.current)
    closeTimerRef.current = null
  }, [])

  const openList = React.useCallback(() => {
    clearCloseTimer()
    setOpen(true)
  }, [clearCloseTimer])

  const scheduleClose = React.useCallback(() => {
    clearCloseTimer()
    closeTimerRef.current = window.setTimeout(() => {
      setOpen(false)
      closeTimerRef.current = null
    }, 120)
  }, [clearCloseTimer])

  React.useEffect(() => () => clearCloseTimer(), [clearCloseTimer])

  return (
    <DropdownMenu modal={false} open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-border px-1.5 text-xs font-medium text-primary transition-colors hover:border-primary/40 hover:bg-primary/5 hover:text-primary/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label={`${links.length} defect URLs`}
          title={`${links.length} defect URLs`}
          onMouseEnter={openList}
          onMouseLeave={scheduleClose}
          onFocus={openList}
          onBlur={scheduleClose}
          onPointerDown={(event) => event.preventDefault()}
        >
          {links.length}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="center"
        className="w-52 p-1"
        onMouseEnter={openList}
        onMouseLeave={scheduleClose}
        onCloseAutoFocus={(event) => event.preventDefault()}
      >
        {links.map((link, index) => (
          <DropdownMenuItem key={`${link.href}:${index}`} asChild>
            <a
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex cursor-pointer items-center justify-between gap-2"
              title={link.href}
              aria-label={`Open defect URL ${link.label || index + 1} in a new tab`}
            >
              <span className="min-w-0 truncate">{link.label || index + 1}</span>
              <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            </a>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function DefectUrlCell({ value }) {
  const links = parseDefectUrls(value)
  if (!links.length) return null

  if (links.length === 1) {
    const [link] = links
    return (
      <a
        href={link.href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-primary transition-colors hover:text-primary/80"
        aria-label="Open defect URL in a new tab"
        title={`${link.label}: ${link.href}`}
      >
        <ExternalLink className="h-4 w-4" />
      </a>
    )
  }

  return <DefectUrlHoverList links={links} />
}

const CellRenderers = {
  defect_url: ({ value }) => <DefectUrlCell value={value} />,

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

  lot_id: ({ value }) => {
    const lotId = typeof value === "string" ? value.trim() : value == null ? "" : String(value).trim()
    if (!lotId) return formatCellValue(value)

    return (
      <button
        type="button"
        onClick={async () => {
          try {
            await copyTextToClipboard(lotId)
            showLotIdCopiedToast(lotId)
          } catch {
            showLotIdCopyFailedToast()
          }
        }}
        className="inline-flex max-w-full cursor-copy items-center justify-center truncate rounded-sm text-inherit transition-colors hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        title={`${lotId} 복사`}
        aria-label={`Copy lot id ${lotId}`}
      >
        <span className="truncate">{lotId}</span>
      </button>
    )
  },

  delivery_targets: ({ value, rowOriginal }) => (
    <TargetSummaryCell value={value} rowOriginal={rowOriginal} />
  ),
  delivery_status: ({ rowOriginal, meta }) => (
    <DeliverySummaryCell rowOriginal={rowOriginal} meta={meta} />
  ),
  target_user_sdwt_prod: ({ value, rowOriginal }) => (
    <TargetSummaryCell value={value} rowOriginal={rowOriginal} />
  ),

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
    const isLocked = isDeliveryChannelSuccessful(rowOriginal, "jira")
    return (
      <InstantInformCell
        meta={meta}
        recordId={recordId}
        baseValue={baseState.numericValue}
        rowOriginal={rowOriginal}
        disabled={isLocked}
        disabledReason="이미 JIRA 전송됨 (즉시 발송 불가)"
      />
    )
  },

  needtosend: ({ value, rowOriginal, meta }) => {
    const recordId = getRecordId(rowOriginal)
    if (!meta || !recordId) return formatCellValue(value)
    const baseState = deriveFlagState(normalizeNeedToSend(rowOriginal?.needtosend), 0)
    const sendJiraState = deriveFlagState(rowOriginal?.delivery_jira ?? rowOriginal?.send_jira, 0)
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

  delivery_jira: ({ value, rowOriginal, meta }) =>
    <DeliveryChannelSummaryCell value={value} rowOriginal={rowOriginal} meta={meta} channelKey="delivery_jira" />,
  delivery_messenger: ({ value, rowOriginal, meta }) =>
    <DeliveryChannelSummaryCell value={value} rowOriginal={rowOriginal} meta={meta} channelKey="delivery_messenger" />,
  delivery_mail: ({ value, rowOriginal, meta }) =>
    <DeliveryChannelSummaryCell value={value} rowOriginal={rowOriginal} meta={meta} channelKey="delivery_mail" />,
  send_jira: ({ value, rowOriginal, meta }) =>
    <DeliveryChannelSummaryCell value={value} rowOriginal={rowOriginal} meta={meta} channelKey="send_jira" />,
  send_messenger: ({ value, rowOriginal, meta }) =>
    <DeliveryChannelSummaryCell value={value} rowOriginal={rowOriginal} meta={meta} channelKey="send_messenger" />,
  send_mail: ({ value, rowOriginal, meta }) =>
    <DeliveryChannelSummaryCell value={value} rowOriginal={rowOriginal} meta={meta} channelKey="send_mail" />,

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
