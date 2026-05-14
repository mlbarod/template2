import { IconDeviceFloppy, IconUserPlus } from "@tabler/icons-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { getRecipientKey, getRecipientListText } from "../../utils/lineSettings"

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
  forceNewChatroom = false,
  isSavingForceNewChatroom = false,
  onForceNewChatroomChange,
  error,
}) {
  const saveDisabled = !selectedUserSdwtProd || !canManageRecipients
  const pickerDisabled = !selectedUserSdwtProd
  const isMessengerChannel = config.channel === "messenger"

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border bg-background p-4 shadow-sm">
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

      <div className="flex min-h-0 flex-1 flex-col gap-3">
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

        {isMessengerChannel ? (
          <div className="rounded-md border bg-muted/30 p-3">
            <div className="flex items-start gap-2">
              <Checkbox
                id="messenger-force-new-chatroom"
                checked={Boolean(forceNewChatroom)}
                disabled={!selectedUserSdwtProd || !canManageRecipients || isSavingForceNewChatroom}
                onCheckedChange={(checked) => onForceNewChatroomChange?.(checked === true)}
                className="mt-0.5"
              />
              <div className="min-w-0 space-y-1">
                <label
                  htmlFor="messenger-force-new-chatroom"
                  className="cursor-pointer text-xs font-medium leading-none"
                >
                  새 대화방 생성
                </label>
                <p className="text-xs text-muted-foreground">
                  체크 시 다음 메신저 발송 때 현재 저장된 수신인 기준으로 새 대화방을 생성합니다.
                  새 대화방 생성 후에는 자동으로 해제됩니다.
                </p>
              </div>
            </div>
          </div>
        ) : null}

        <div className="min-h-0 flex-1 overflow-y-auto rounded-md border">
          {isLoadingRecipients ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">{config.loadingText}</div>
          ) : recipients.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">{config.emptyText}</div>
          ) : (
            recipients.map((recipient) => (
              <div
                key={getRecipientKey(recipient)}
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
