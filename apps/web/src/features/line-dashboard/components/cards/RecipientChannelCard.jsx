import { IconDeviceFloppy, IconUserPlus } from "@tabler/icons-react"

import { Button } from "@/components/ui/button"
import { getRecipientListText } from "../../utils/lineSettings"

export function RecipientChannelCard({
  config,
  selectedUserSdwtProd,
  canManageRecipients,
  recipients,
  isLoadingRecipients,
  onRemoveUser,
  onSave,
  onOpenPicker,
  isDraftCurrent,
  isSavingRecipients,
  error,
}) {
  const saveDisabled = !selectedUserSdwtProd || !canManageRecipients
  const pickerDisabled = !selectedUserSdwtProd

  return (
    <div className="flex min-w-0 flex-col rounded-lg border bg-background p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3 pb-3">
        <div className="min-w-0 space-y-1">
          <h2 className="text-base font-medium">{config.title}</h2>
          {error ? (
            <p className="text-xs text-destructive" role="alert">
              {error}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              {selectedUserSdwtProd
                ? `${selectedUserSdwtProd} ${recipients.length}명`
                : "알림 Target을 선택하세요."}
              {selectedUserSdwtProd && !canManageRecipients ? " · 변경 권한 없음" : ""}
            </p>
          )}
        </div>
        <Button
          type="button"
          size="sm"
          onClick={() => onSave(config.channel)}
          disabled={saveDisabled || !isDraftCurrent || isSavingRecipients || isLoadingRecipients}
          className="shrink-0 gap-1"
        >
          <IconDeviceFloppy className="size-4" />
          수신인 저장
        </Button>
      </div>

      <div className="flex flex-col gap-3">
        <Button
          type="button"
          variant="outline"
          onClick={() => onOpenPicker(config.channel)}
          disabled={pickerDisabled}
          className="justify-start gap-1"
        >
          <IconUserPlus className="size-4" />
          수신인 검색/추가
        </Button>

        <div className="max-h-80 min-h-64 overflow-y-auto rounded-md border">
          {isLoadingRecipients ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">{config.loadingText}</div>
          ) : recipients.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">{config.emptyText}</div>
          ) : (
            recipients.map((recipient) => (
              <div
                key={recipient.userId}
                className="flex min-w-0 items-center justify-between gap-2 border-b px-3 py-2 last:border-b-0"
              >
                <div className="min-w-0">
                  <div className="truncate text-xs font-medium">{getRecipientListText(recipient)}</div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => onRemoveUser(config.channel, recipient)}
                  disabled={!canManageRecipients}
                  className="h-7 shrink-0 text-destructive"
                >
                  제거
                </Button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
