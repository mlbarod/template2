import { IconDeviceFloppy } from "@tabler/icons-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"

export function NeedToSendCommentRuleCard({
  selectedUserSdwtProd,
  ruleDraft,
  maxKeywordLength,
  formError,
  isLoading,
  isSaving,
  canManage,
  onDraftChange,
  onSave,
}) {
  const keyword = ruleDraft.commentKeyword || ""
  const enabledCheckboxId = "needtosend-rule-enabled"
  const ignoreSampleTypeCheckboxId = "needtosend-rule-ignore-sample-type"

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-3 overflow-hidden rounded-lg border bg-background p-4 shadow-sm">
      <div className="shrink-0 space-y-1">
        <h2 className="text-base font-medium">자동 예약 코멘트 규칙</h2>
        <p className="text-xs text-muted-foreground">
          입력한 키워드가 Comment에 포함되면 자동 예약 대상이 됩니다.
        </p>
      </div>

      {formError ? (
        <p className="text-xs text-destructive" role="alert">
          {formError}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          예: <span className="font-mono">$SETUP_EQP</span> 저장 시 해당 문구가 포함된 Comment를 예약합니다.
        </p>
      )}

      <form className="grid min-h-0 gap-3 overflow-y-auto pr-1" onSubmit={onSave}>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground" htmlFor="needtosend-comment-keyword-input">
            포함 키워드
          </label>
          <Input
            id="needtosend-comment-keyword-input"
            value={keyword}
            onChange={(event) => onDraftChange("commentKeyword", event.target.value)}
            placeholder="$SETUP_EQP"
            maxLength={maxKeywordLength}
            disabled={!selectedUserSdwtProd || isLoading || isSaving || !canManage}
          />
        </div>

        <div className="grid gap-2 rounded-md border p-3">
          <div className="flex items-center gap-2 text-xs">
            <Checkbox
              id={enabledCheckboxId}
              checked={Boolean(ruleDraft.enabled)}
              disabled={!selectedUserSdwtProd || isLoading || isSaving || !canManage}
              onCheckedChange={(checked) => onDraftChange("enabled", checked === true)}
            />
            <label htmlFor={enabledCheckboxId} className="cursor-pointer">
              자동 예약 활성화
            </label>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <Checkbox
              id={ignoreSampleTypeCheckboxId}
              checked={Boolean(ruleDraft.ignoreSampleType)}
              disabled={!selectedUserSdwtProd || isLoading || isSaving || !canManage}
              onCheckedChange={(checked) => onDraftChange("ignoreSampleType", checked === true)}
            />
            <label htmlFor={ignoreSampleTypeCheckboxId} className="cursor-pointer">
              ENGR_PRODUCTION도 예약 대상에 포함
            </label>
          </div>
        </div>

        <Button
          type="submit"
          disabled={!selectedUserSdwtProd || isLoading || isSaving || !canManage}
          className="justify-center gap-1"
        >
          <IconDeviceFloppy className="size-4" />
          저장
        </Button>
      </form>
    </div>
  )
}
