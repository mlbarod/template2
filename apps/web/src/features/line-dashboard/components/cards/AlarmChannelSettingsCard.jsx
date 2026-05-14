import { IconDeviceFloppy } from "@tabler/icons-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"

const ALARM_CHANNELS = [
  { key: "jira", label: "Jira", description: "Jira 이슈 생성 채널" },
  { key: "messenger", label: "Teams", description: "Teams 메신저 발송 채널" },
  { key: "mail", label: "Mail", description: "메일 발송 채널" },
]

export function AlarmChannelSettingsCard({
  selectedUserSdwtProd,
  jiraKeyDraft,
  channelEnabledDraft,
  maxJiraKeyLength,
  jiraKeyFormError,
  jiraKeyError,
  isJiraKeyLoading,
  isSavingJiraKey,
  canManage,
  onJiraKeyDraftChange,
  onChannelEnabledChange,
  onSaveJiraKey,
}) {
  const showPermissionNotice = Boolean(selectedUserSdwtProd && !canManage)

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-3 overflow-hidden rounded-lg border bg-background p-3 shadow-sm">
      <div className="shrink-0 space-y-1">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-medium">알람 채널 설정</h2>
          {showPermissionNotice ? (
            <Badge variant="secondary" className="shrink-0 text-[10px]">
              관리자 권한이 필요
            </Badge>
          ) : null}
        </div>
      </div>

      {jiraKeyFormError ? (
        <p className="shrink-0 text-xs text-destructive" role="alert">
          {jiraKeyFormError}
        </p>
      ) : jiraKeyError ? (
        <p className="shrink-0 text-xs text-destructive" role="alert">
          {jiraKeyError}
        </p>
      ) : null}

      <form className="flex min-h-0 flex-1 flex-col gap-2" onSubmit={onSaveJiraKey}>
        <div className="grid shrink-0 gap-2">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="alarm-channel-jira-key-input">
              Jira Project Key
            </label>
            <Input
              id="alarm-channel-jira-key-input"
              value={jiraKeyDraft}
              onChange={(event) => onJiraKeyDraftChange(event.target.value)}
              placeholder="ex) DRONE"
              maxLength={maxJiraKeyLength}
              disabled={!selectedUserSdwtProd || isJiraKeyLoading || isSavingJiraKey || !canManage}
            />
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto rounded-md border p-2">
          <div className="grid gap-1.5">
            {ALARM_CHANNELS.map((channel) => {
              const isEnabled = Boolean(channelEnabledDraft[channel.key])
              const checkboxId = `alarm-channel-${channel.key}-enabled`
              const statusText = channel.key === "jira" && jiraKeyDraft.trim()
                ? jiraKeyDraft.trim()
                : channel.description
              return (
                <div
                  key={channel.key}
                  className="flex items-center justify-between gap-3 rounded-md bg-muted/40 px-2 py-1.5"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <Checkbox
                      id={checkboxId}
                      checked={isEnabled}
                      disabled={!selectedUserSdwtProd || isJiraKeyLoading || isSavingJiraKey || !canManage}
                      onCheckedChange={(checked) => onChannelEnabledChange(channel.key, checked === true)}
                    />
                    <label className="min-w-0 cursor-pointer" htmlFor={checkboxId}>
                      <p className="text-xs font-medium">{channel.label}</p>
                      <p className="truncate text-[11px] text-muted-foreground">{statusText}</p>
                    </label>
                  </div>
                  <Badge variant={isEnabled ? "default" : "secondary"} className="shrink-0 text-[10px]">
                    {isEnabled ? "활성" : "비활성"}
                  </Badge>
                </div>
              )
            })}
          </div>
        </div>

        <Button
          type="submit"
          disabled={!selectedUserSdwtProd || isJiraKeyLoading || isSavingJiraKey || !canManage}
          className="shrink-0 justify-center gap-1"
        >
          <IconDeviceFloppy className="size-4" />
          저장
        </Button>
      </form>
    </div>
  )
}
