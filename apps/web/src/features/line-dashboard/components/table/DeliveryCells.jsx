import { AlertTriangle, Ban, Check, Clock3, RotateCcw } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { getRecordId } from "../../utils/dataTableColumnNormalizers"
import { formatCellValue, formatTooltipValue } from "../../utils/dataTableFormatters"
import { deriveFlagState } from "../../utils/dataTableFlagState"
import {
  DELIVERY_CHANNELS,
  getDeliveryStatusLabel,
  normalizeDeliveryRows,
  normalizeTextValue,
  resolveChannelReason,
  summarizeRowDeliveryOverall,
  summarizeRowDeliveryChannel,
  uniqueDeliveryTargets,
} from "../../utils/dataTableDelivery"
import { buildToastOptions } from "../../utils/toast"

const CHANNEL_LABELS = {
  delivery_jira: "JIRA",
  delivery_messenger: "MSG",
  delivery_mail: "MAIL",
  send_jira: "JIRA",
  send_messenger: "MSG",
  send_mail: "MAIL",
}

const DELIVERY_STATUS_CLASSES = {
  success: "border-primary/20 bg-primary/10 text-primary",
  failed: "border-destructive/30 bg-destructive/10 text-destructive",
  pending: "border-border bg-muted text-muted-foreground",
  disabled: "border-border bg-muted/60 text-muted-foreground",
  cancelled: "border-border bg-muted/60 text-muted-foreground",
  partial_failed: "border-destructive/30 bg-destructive/10 text-destructive",
  partial_success: "border-primary/20 bg-primary/10 text-primary",
  unknown: "border-border bg-background text-muted-foreground",
}

const DELIVERY_STATUS_ICONS = {
  success: Check,
  failed: AlertTriangle,
  partial_failed: AlertTriangle,
  pending: Clock3,
  disabled: Ban,
  cancelled: Ban,
  partial_success: Check,
  unknown: Clock3,
}

const DETAIL_GRID_COLUMNS_BY_COUNT = {
  1: "grid-cols-[180px_minmax(150px,1fr)]",
  2: "grid-cols-[180px_repeat(2,minmax(150px,1fr))]",
  3: "grid-cols-[180px_repeat(3,minmax(150px,1fr))]",
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

function showRetryDisabledToast(label) {
  toast.info(`${label} 비활성 상태입니다.`, {
    description: "비활성 delivery는 자동 재전송되지 않습니다. 설정을 켠 뒤 신규 예약으로 처리해 주세요.",
    ...buildToastOptions({ intent: "info", duration: 3600 }),
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

function showRetryResultToast(label, result) {
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
  if (status === "disabled") {
    showRetryDisabledToast(label)
    return
  }
  showRetryUnknownStatusToast(status)
}

function DeliveryStatusBadge({ summary, compact = false }) {
  const Icon = DELIVERY_STATUS_ICONS[summary.status] ?? Clock3
  return (
    <span
      className={[
        "inline-flex min-w-0 items-center justify-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium",
        DELIVERY_STATUS_CLASSES[summary.status] ?? DELIVERY_STATUS_CLASSES.unknown,
        compact ? "max-w-full" : "",
      ].join(" ")}
    >
      <Icon className="h-3 w-3 shrink-0" />
      <span className="truncate whitespace-nowrap">{getDeliveryStatusLabel(summary)}</span>
    </span>
  )
}

function DeliveryChannelPill({ channel, summary }) {
  const Icon = DELIVERY_STATUS_ICONS[summary.status] ?? Clock3
  return (
    <span
      className={[
        "inline-flex min-w-0 items-center justify-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium",
        DELIVERY_STATUS_CLASSES[summary.status] ?? DELIVERY_STATUS_CLASSES.unknown,
      ].join(" ")}
    >
      <Icon className="h-3 w-3 shrink-0" />
      <span className="shrink-0">{channel.shortLabel}</span>
      <span className="truncate whitespace-nowrap">{getDeliveryStatusLabel(summary)}</span>
    </span>
  )
}

function groupDeliveryRowsByChannel(deliveryRows) {
  const grouped = new Map()
  for (const row of deliveryRows) {
    grouped.set(row.channel, row)
  }
  return grouped
}

function buildVisibleChannelSummaries(rowOriginal, channels = DELIVERY_CHANNELS) {
  return channels
    .map((channel) => ({
      channel,
      summary: summarizeRowDeliveryChannel(rowOriginal, channel.channel),
    }))
    .filter(({ summary }) => summary && summary.status !== "disabled")
}

function buildSingleDeliverySummary(delivery) {
  const status = delivery?.status ?? "unknown"
  const summary = {
    status,
    total: 1,
    success: 0,
    failed: 0,
    pending: 0,
    disabled: 0,
    cancelled: 0,
    unknown: 0,
  }
  if (status in summary) {
    summary[status] = 1
  } else {
    summary.unknown = 1
  }
  return summary
}

function DeliveryCellDetail({ delivery, summaryFallback }) {
  const summary = delivery ? buildSingleDeliverySummary(delivery) : summaryFallback
  if (!summary || summary.status === "disabled") {
    return <span className="text-xs text-muted-foreground">-</span>
  }

  const timestamp = delivery?.sentAt || delivery?.updatedAt
  return (
    <div className="flex min-w-0 flex-col items-center gap-1 text-center">
      <div className="flex max-w-full items-center justify-center gap-1">
        <DeliveryStatusBadge summary={summary} compact />
        {timestamp && (
          <span className="shrink-0 whitespace-nowrap text-[10px] text-muted-foreground" title={formatTooltipValue(timestamp)}>
            {formatTooltipValue(timestamp)}
          </span>
        )}
      </div>
      {delivery?.reason && (
        <span className="max-w-full truncate text-[10px] text-destructive" title={delivery.reason}>
          {delivery.reason}
        </span>
      )}
      {delivery?.externalKey && (
        <span className="max-w-full truncate text-[10px] text-muted-foreground" title={delivery.externalKey}>
          {delivery.externalKey}
        </span>
      )}
    </div>
  )
}

function getFlagLabel(value, labels) {
  const { state } = deriveFlagState(value, 0)
  return labels[state] ?? labels.off
}

function DeliveryOverallFallbackDialog({ rowOriginal, summary, trigger }) {
  const primaryTarget = normalizeTextValue(rowOriginal?.delivery_targets ?? rowOriginal?.target_user_sdwt_prod)
  const sopStatus = normalizeTextValue(rowOriginal?.status) ?? "-"
  const needToSendLabel = getFlagLabel(rowOriginal?.needtosend, {
    on: "예약됨",
    off: "예약 안됨",
    error: "예약 오류",
  })
  const instantInformLabel = getFlagLabel(rowOriginal?.instant_inform, {
    on: "요청됨",
    off: "요청 안됨",
    error: "요청 오류",
  })

  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Delivery 상세</DialogTitle>
          <DialogDescription>
            아직 표시 가능한 채널별 delivery 정보가 없어 SOP 기준 상태만 표시합니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 rounded-md border p-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">전송 상태</span>
            <DeliveryStatusBadge summary={summary} compact />
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">Target</span>
            <span className="min-w-0 truncate font-mono">{primaryTarget ?? "-"}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">SOP 상태</span>
            <span className="min-w-0 truncate">{sopStatus}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">예약</span>
            <span>{needToSendLabel}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">즉시인폼</span>
            <span>{instantInformLabel}</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function DeliverySummaryCell({ rowOriginal, meta }) {
  const visibleSummaries = buildVisibleChannelSummaries(rowOriginal)
  if (visibleSummaries.length === 0) {
    const overallSummary = summarizeRowDeliveryOverall(rowOriginal)
    if (!overallSummary) return null
    const trigger = (
      <button
        type="button"
        className="inline-flex max-w-full rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        title={`전송 상태: ${getDeliveryStatusLabel(overallSummary)}`}
      >
        <DeliveryStatusBadge summary={overallSummary} compact />
      </button>
    )
    return (
      <DeliveryOverallFallbackDialog
        rowOriginal={rowOriginal}
        summary={overallSummary}
        trigger={trigger}
      />
    )
  }

  const title = visibleSummaries
    .map(({ channel, summary }) => `${channel.label}: ${getDeliveryStatusLabel(summary)}`)
    .join(" · ")

  const trigger = (
    <button
      type="button"
      className="inline-flex max-w-full flex-wrap items-center justify-center gap-1 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      title={title}
    >
      {visibleSummaries.map(({ channel, summary }) => (
        <DeliveryChannelPill key={channel.channel} channel={channel} summary={summary} />
      ))}
    </button>
  )

  return <DeliveryDetailsDialog rowOriginal={rowOriginal} trigger={trigger} meta={meta} />
}

function DeliveryDetailsDialog({ rowOriginal, trigger, initialChannel = null, meta }) {
  const deliveryRows = normalizeDeliveryRows(rowOriginal)
  const primaryTarget = normalizeTextValue(rowOriginal?.delivery_targets ?? rowOriginal?.target_user_sdwt_prod)
  const targetValues = primaryTarget ? [primaryTarget] : uniqueDeliveryTargets(deliveryRows, null)
  const recordId = getRecordId(rowOriginal)

  const orderedChannels = initialChannel
    ? [
        ...DELIVERY_CHANNELS.filter((item) => item.channel === initialChannel),
        ...DELIVERY_CHANNELS.filter((item) => item.channel !== initialChannel),
      ]
    : DELIVERY_CHANNELS
  const visibleChannelSummaries = buildVisibleChannelSummaries(rowOriginal, orderedChannels)
  if (visibleChannelSummaries.length === 0) return trigger

  const visibleChannelSet = new Set(visibleChannelSummaries.map(({ channel }) => channel.channel))
  const visibleDeliveryRows = deliveryRows.filter((row) => visibleChannelSet.has(row.channel))
  const deliveryByChannel = groupDeliveryRowsByChannel(visibleDeliveryRows)
  const detailGridClass =
    DETAIL_GRID_COLUMNS_BY_COUNT[Math.min(3, Math.max(1, visibleChannelSummaries.length))]

  const retryChannels = visibleChannelSummaries.map(({ channel }) => channel).filter((channel) =>
    visibleDeliveryRows.some((row) => row.channel === channel.channel && row.status === "failed"),
  )

  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="grid max-h-[85vh] w-[min(1280px,calc(100%-2rem))] min-w-[min(1280px,calc(100%-2rem))] max-w-[min(1280px,calc(100%-2rem))] grid-rows-[auto,1fr,auto] overflow-hidden sm:max-w-[min(1280px,calc(100%-2rem))]">
        <DialogHeader>
          <DialogTitle>Delivery 상세</DialogTitle>
          <DialogDescription>
            알림 Target의 Jira, Teams, Mail 발송 상태입니다.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 overflow-auto rounded-md border">
          <div className={`grid min-w-[680px] ${detailGridClass} border-b bg-muted/60 text-xs font-medium`}>
            <div className="px-3 py-2">Target</div>
            {visibleChannelSummaries.map(({ channel }) => (
              <div key={channel.channel} className="px-3 py-2 text-center">
                {channel.label}
              </div>
            ))}
          </div>

          {targetValues.length > 0 ? (
            targetValues.map((target) => {
              return (
                <div
                  key={target}
                  className={`grid min-w-[680px] ${detailGridClass} border-b last:border-b-0`}
                >
                  <div className="min-w-0 px-3 py-3">
                    <Badge variant="secondary" className="max-w-full justify-start font-mono">
                      <span className="truncate">{target}</span>
                    </Badge>
                  </div>
                  {visibleChannelSummaries.map(({ channel, summary }) => (
                    <div key={`${target}:${channel.channel}`} className="min-w-0 px-3 py-3">
                      <DeliveryCellDetail
                        delivery={deliveryByChannel.get(channel.channel)}
                        summaryFallback={summary}
                      />
                    </div>
                  ))}
                </div>
              )
            })
          ) : (
            <div className="px-3 py-10 text-center text-sm text-muted-foreground">
              Delivery 정보가 없습니다.
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            목록의 채널 상태는 delivery row를 요약한 값입니다. 비활성 delivery는 채널 설정을 다시 켜도 자동 재전송되지 않습니다.
          </span>
          <div className="flex flex-wrap justify-end gap-2">
            {retryChannels.map((channel) => {
              const cellKey = recordId ? `${recordId}:${channel.field}` : null
              const isRetryLoading = Boolean(cellKey && meta?.updatingCells?.[cellKey])
              return (
                <Button
                  key={channel.channel}
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!recordId || isRetryLoading || typeof meta?.handleRetryChannel !== "function"}
                  onClick={async () => {
                    if (!recordId || typeof meta?.handleRetryChannel !== "function") return
                    const result = await meta.handleRetryChannel(recordId, { channelKey: channel.field })
                    showRetryResultToast(channel.label, result)
                  }}
                  className="gap-1"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  {channel.label} 재시도
                </Button>
              )
            })}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function TargetSummaryCell({ value, rowOriginal }) {
  const deliveryRows = normalizeDeliveryRows(rowOriginal)
  const primaryTarget =
    normalizeTextValue(value ?? rowOriginal?.target_user_sdwt_prod) ??
    uniqueDeliveryTargets(deliveryRows, null)[0]
  if (!primaryTarget) return formatCellValue(value)

  const trigger = (
    <button
      type="button"
      className="inline-flex max-w-full items-center justify-center gap-1 rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      title={primaryTarget}
    >
      <Badge variant="secondary" className="max-w-[118px] justify-start font-mono">
        <span className="truncate">{primaryTarget}</span>
      </Badge>
    </button>
  )

  if (!deliveryRows.length) return trigger
  return <DeliveryDetailsDialog rowOriginal={rowOriginal} trigger={trigger} />
}

export function DeliveryChannelSummaryCell({ value, rowOriginal, channelKey, meta }) {
  const channel = DELIVERY_CHANNELS.find((item) => item.field === channelKey || item.fallbackField === channelKey)
  const deliveryRows = normalizeDeliveryRows(rowOriginal)
  if (!channel) {
    return renderSendChannelCell({ value, rowOriginal, channelKey, meta })
  }

  if (channelKey === channel.field && (value === null || value === undefined)) {
    return null
  }

  if (!deliveryRows.length) {
    return renderSendChannelCell({ value, rowOriginal, channelKey, meta })
  }

  const summary = summarizeRowDeliveryChannel(rowOriginal, channel.channel)
  if (!summary || summary.status === "disabled") return null

  const trigger = (
    <button
      type="button"
      className="inline-flex max-w-full rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      title={`${channel.label}: ${getDeliveryStatusLabel(summary)}`}
    >
      <DeliveryStatusBadge summary={summary} compact />
    </button>
  )

  return (
    <DeliveryDetailsDialog
      rowOriginal={rowOriginal}
      trigger={trigger}
      initialChannel={channel.channel}
      meta={meta}
    />
  )
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
        showRetryResultToast(label, result)
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
