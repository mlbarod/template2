import { IconArrowRight, IconPlus } from "@tabler/icons-react"
import { AlertCircleIcon, BadgeCheckIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

function LineUserSdwtBadges({ lineId, values, selectedValue, onSelect }) {
  if (!lineId) {
    return (
      <div className="flex h-full min-h-0 items-center gap-2 rounded-md border bg-background px-2 py-2 text-sm text-muted-foreground">
        <AlertCircleIcon className="h-3 w-3" />
        라인을 선택하면 알림 Target 목록이 표시됩니다.
      </div>
    )
  }

  if (!values || values.length === 0) {
    return (
      <div className="flex h-full min-h-0 items-center gap-2 rounded-md border bg-background px-2 py-1 text-[11px] text-muted-foreground">
        <AlertCircleIcon className="h-3 w-3" />
        등록된 알림 Target이 없습니다.
      </div>
    )
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-2 content-start gap-2 overflow-y-auto rounded-md border p-2">
      {values.map((value) => (
        <button
          key={value}
          type="button"
          onClick={() => onSelect(value)}
          className="min-w-0 rounded-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          aria-pressed={selectedValue === value}
          title={`${value} 선택`}
        >
          <Badge
            variant={selectedValue === value ? "default" : "secondary"}
            className="w-full min-w-0 justify-start gap-1 text-[11px] font-mono"
          >
            <BadgeCheckIcon className="h-3 w-3" />
            <span className="truncate">{value}</span>
          </Badge>
        </button>
      ))}
    </div>
  )
}

function TargetMappingSummary({
  target,
  draft,
  userOptionValues = [],
  sdwtOptionValues = [],
  error,
  isSaving,
  canManage,
  onDraftChange,
  onSubmit,
}) {
  if (!target) {
    return (
      <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        알림 Target을 선택하면 지정 조합이 표시됩니다.
      </div>
    )
  }

  const mappings = Array.isArray(target.mappings) ? target.mappings : []
  const hasOptions = userOptionValues.length > 0 && sdwtOptionValues.length > 0
  const isSelectDisabled = !canManage || isSaving || !hasOptions

  return (
    <div className="flex flex-col rounded-md border bg-muted/30 px-3 py-2">
      <div className="flex shrink-0 items-center justify-between gap-2">
        <span className="text-xs font-medium text-foreground">지정 조합</span>
        <Badge variant={target.isConfigured ? "default" : "secondary"} className="text-[10px]">
          {target.isConfigured ? "설정됨" : "미설정"}
        </Badge>
      </div>
      <form
        className="my-2 flex min-w-0 shrink-0 items-center gap-1.5"
        onSubmit={onSubmit}
      >
        <div className="min-w-0">
          <Select
            value={draft.userSdwtProd || undefined}
            onValueChange={(value) => onDraftChange("userSdwtProd", value)}
            disabled={isSelectDisabled}
          >
            <SelectTrigger className="h-8 min-w-0 text-[11px]">
              <SelectValue placeholder="엔지니어 분임조 선택" />
            </SelectTrigger>
            <SelectContent className="max-h-64">
              {userOptionValues.map((value) => (
                <SelectItem key={`user-${value}`} value={value}>
                  {value}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <IconArrowRight className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <Select
            value={draft.sdwtProd || undefined}
            onValueChange={(value) => onDraftChange("sdwtProd", value)}
            disabled={isSelectDisabled}
          >
            <SelectTrigger className="h-8 min-w-0 text-[11px]">
              <SelectValue placeholder="설비소속 분임조 선택" />
            </SelectTrigger>
            <SelectContent className="max-h-64">
              {sdwtOptionValues.map((value) => (
                <SelectItem key={`sdwt-${value}`} value={value}>
                  {value}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          type="submit"
          size="sm"
          variant="outline"
          disabled={isSelectDisabled || !draft.userSdwtProd.trim() || !draft.sdwtProd.trim()}
          className="h-8 shrink-0"
        >
          <IconPlus className="mr-1 size-3" />
          추가
        </Button>
      </form>
      {!hasOptions ? (
        <p className="mt-1 shrink-0 text-[11px] text-muted-foreground">
          선택 가능한 drone_sop user_sdwt_prod 또는 sdwt_prod가 없습니다.
        </p>
      ) : null}
      {error ? (
        <p className="mt-1 shrink-0 text-[11px] text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap content-start gap-1.5 pr-1">
        {mappings.length > 0 ? (
          mappings.map((mapping) => {
            const sdwtProd = mapping.sdwtProd || "-"
            const userSdwtProd = mapping.userSdwtProd || "-"
            return (
              <Badge
                key={`${sdwtProd}-${userSdwtProd}`}
                variant="outline"
                className="max-w-full gap-1 font-mono text-sm"
              >
                <span className="truncate">{userSdwtProd}</span>
                <span className="text-muted-foreground">-&gt;</span>
                <span className="truncate">{sdwtProd}설비</span>
              </Badge>
            )
          })
        ) : (
          <span className="text-[11px] text-muted-foreground">설정된 조합이 없습니다.</span>
        )}
      </div>
    </div>
  )
}

export function NotificationTargetCard({
  lineId,
  newTargetDraft,
  maxTargetFieldLength,
  canCreateTarget,
  canManageMappings,
  isCreatingTarget,
  isCreatingMapping,
  targetFormError,
  mappingFormError,
  mappingDraft,
  mappingOptions = { userSdwtProds: [], sdwtProds: [] },
  userSdwtValues,
  selectedUserSdwtProd,
  selectedNotificationTarget,
  onTargetDraftChange,
  onMappingDraftChange,
  onCreateTarget,
  onCreateTargetMapping,
  onSelectTarget,
}) {
  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-2 overflow-hidden rounded-lg border bg-background p-4 shadow-sm">
      <div className="shrink-0 space-y-1">
        <h2 className="text-base font-medium">알림 Target 선택</h2>
        <p className="text-xs text-muted-foreground">
          메신저/메일 수신인을 설정할 알림 Target을 선택하세요.
        </p>
      </div>

      {targetFormError || !canCreateTarget ? (
        <div className="space-y-1">
          {targetFormError ? (
            <p className="text-xs text-destructive" role="alert">
              {targetFormError}
            </p>
          ) : null}
          {!canCreateTarget ? (
            <p className="text-[11px] text-muted-foreground">
              알림 Target 추가는 operator 권한과 선택된 line이 필요합니다.
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-hidden">
        <div className="min-h-0 flex-1">
          <LineUserSdwtBadges
            lineId={lineId}
            values={userSdwtValues}
            selectedValue={selectedUserSdwtProd}
            onSelect={onSelectTarget}
          />
        </div>

        <div className="shrink-0 rounded-md border bg-muted/30 p-2">
          <div className="flex min-w-0 gap-2">
            <Input
              id="target-create-input"
              value={newTargetDraft}
              onChange={(event) => onTargetDraftChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault()
                  void onCreateTarget()
                }
              }}
              placeholder="새 Target 추가"
              maxLength={maxTargetFieldLength}
              disabled={!lineId || !canCreateTarget || isCreatingTarget}
              className="h-8 text-xs"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onCreateTarget}
              disabled={!lineId || !canCreateTarget || isCreatingTarget || !newTargetDraft.trim()}
              className="h-8 shrink-0"
            >
              <IconPlus className="mr-1 size-3" />
              추가
            </Button>
          </div>
        </div>

        <div className="shrink-0">
          <TargetMappingSummary
            target={selectedNotificationTarget}
            draft={mappingDraft}
            userOptionValues={mappingOptions.userSdwtProds}
            sdwtOptionValues={mappingOptions.sdwtProds}
            error={mappingFormError}
            isSaving={isCreatingMapping}
            canManage={canManageMappings}
            onDraftChange={onMappingDraftChange}
            onSubmit={onCreateTargetMapping}
          />
        </div>
      </div>
    </div>
  )
}
