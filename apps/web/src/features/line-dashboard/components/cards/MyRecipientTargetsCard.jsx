import { IconInbox, IconMail, IconMessageCircle } from "@tabler/icons-react"

import { Badge } from "@/components/ui/badge"

const CHANNEL_LABELS = {
  mail: "메일",
  messenger: "메신저",
}

const CHANNEL_ICONS = {
  mail: IconMail,
  messenger: IconMessageCircle,
}

function ChannelBadge({ channel }) {
  const Icon = CHANNEL_ICONS[channel] || IconInbox

  return (
    <Badge variant="secondary" className="gap-1 text-[10px]">
      <Icon className="size-3" />
      {CHANNEL_LABELS[channel] || channel}
    </Badge>
  )
}

export function MyRecipientTargetsCard({
  lineId,
  targets,
  selectedUserSdwtProd,
  isLoading,
  error,
  onSelectTarget,
}) {
  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col rounded-lg border bg-background p-4 shadow-sm">
      <div className="shrink-0 space-y-1 pb-3">
        <h2 className="flex items-center gap-1.5 text-base font-medium">
          <IconInbox className="size-4" />
          내 수신 Target
        </h2>
        {error ? (
          <p className="text-xs text-destructive" role="alert">
            {error}
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            {lineId ? "현재 Line에서 본인이 수신인인 Target입니다." : "라인을 선택하세요."}
          </p>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-md border">
        {isLoading ? (
          <div className="px-3 py-6 text-center text-xs text-muted-foreground">내 수신 Target을 불러오는 중입니다.</div>
        ) : targets.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-muted-foreground">
            {lineId ? "본인이 수신인인 Target이 없습니다." : "라인을 선택하면 목록이 표시됩니다."}
          </div>
        ) : (
          targets.map((target) => {
            const isSelected = selectedUserSdwtProd === target.targetUserSdwtProd
            return (
              <button
                key={`${target.lineId}-${target.targetUserSdwtProd}`}
                type="button"
                onClick={() => onSelectTarget(target.targetUserSdwtProd)}
                className={`flex w-full min-w-0 flex-col gap-2 border-b px-3 py-2 text-left last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 ${
                  isSelected ? "bg-muted" : ""
                }`}
                aria-pressed={isSelected}
                title={`${target.targetUserSdwtProd} 선택`}
              >
                <span className="truncate font-mono text-xs font-medium">{target.targetUserSdwtProd}</span>
                <span className="flex flex-wrap gap-1">
                  {(target.channels || []).map((channel) => (
                    <ChannelBadge key={channel} channel={channel} />
                  ))}
                </span>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}
