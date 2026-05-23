import * as React from "react"
import { IconArrowRight, IconCheck, IconChevronDown, IconPlus, IconTrash } from "@tabler/icons-react"
import { AlertCircleIcon, BadgeCheckIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"

function resolveSelectedOptionValue(values, selectedValue) {
  const normalizedSelectedValue = String(selectedValue || "").trim()
  if (!normalizedSelectedValue) return ""
  return values.includes(normalizedSelectedValue) ? normalizedSelectedValue : ""
}

function getMappingValueLineLabel(labels, value) {
  const key = String(value || "").trim().toLowerCase()
  return key ? labels?.[key] || "" : ""
}

function formatMappingLineLabel(optionLineId) {
  return optionLineId
}

function findLineOption(lineOptions, lineId) {
  const normalizedLineId = String(lineId || "").trim().toLowerCase()
  return (Array.isArray(lineOptions) ? lineOptions : []).find((option) => (
    String(option?.lineId || "").trim().toLowerCase() === normalizedLineId
  )) || null
}

function normalizeSelectedValues(values, fallbackValue = "") {
  const sourceValues = Array.isArray(values) && values.length > 0 ? values : [fallbackValue]
  const seenValues = new Set()
  return sourceValues
    .map((value) => String(value || "").trim())
    .filter((value) => {
      const key = value.toLowerCase()
      if (!value || seenValues.has(key)) return false
      seenValues.add(key)
      return true
    })
}

function orderMappingLineOptions(lineOptions, pinSystemLineToTop) {
  const options = Array.isArray(lineOptions) ? lineOptions : []
  if (!pinSystemLineToTop) return options

  return [...options].sort((left, right) => {
    const leftIsSystem = String(left?.lineId || "").trim().toLowerCase() === "system"
    const rightIsSystem = String(right?.lineId || "").trim().toLowerCase() === "system"
    if (leftIsSystem === rightIsSystem) return 0
    return leftIsSystem ? -1 : 1
  })
}

function MappingAffiliationDropdown({
  label,
  placeholder,
  currentLineId,
  selectedLineId,
  selectedValue,
  selectedValues = [],
  lineOptions = [],
  multiSelect = false,
  pinSystemLineToTop = false,
  disabled,
  onSelect,
  onMultiSelect,
}) {
  const [open, setOpen] = React.useState(false)
  const [activeLineId, setActiveLineId] = React.useState(selectedLineId || currentLineId || "")
  const visibleLineOptions = React.useMemo(
    () => orderMappingLineOptions(lineOptions, pinSystemLineToTop),
    [lineOptions, pinSystemLineToTop],
  )

  React.useEffect(() => {
    if (!open) {
      setActiveLineId(selectedLineId || currentLineId || "")
    }
  }, [currentLineId, open, selectedLineId])

  React.useEffect(() => {
    if (!activeLineId && visibleLineOptions.length > 0) {
      setActiveLineId(visibleLineOptions[0].lineId)
    }
  }, [activeLineId, visibleLineOptions])

  const selectedLineLabel = selectedLineId ? formatMappingLineLabel(selectedLineId) : ""
  const normalizedSelectedValues = normalizeSelectedValues(selectedValues, selectedValue)
  const displaySelectedValue = multiSelect && normalizedSelectedValues.length > 1
    ? `${normalizedSelectedValues[0]} 외 ${normalizedSelectedValues.length - 1}개`
    : selectedValue
  const displayValue = displaySelectedValue
    ? `${selectedLineLabel ? `${selectedLineLabel} · ` : ""}${displaySelectedValue}`
    : placeholder
  const activeLineOption = findLineOption(lineOptions, activeLineId)
  const activeValues = Array.isArray(activeLineOption?.values) ? activeLineOption.values : []
  const activeSelectedValues = activeLineId === selectedLineId ? normalizedSelectedValues : []
  const selectedValueSet = new Set(activeSelectedValues.map((value) => value.toLowerCase()))

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            "flex h-8 w-46 min-w-0 items-center justify-between rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
            selectedValue && "border-primary bg-primary/10 text-primary",
          )}
          aria-label={`${label} 선택`}
          title={displayValue}
        >
          <span className={cn("truncate", !selectedValue && "text-muted-foreground")}>
            {displayValue}
          </span>
          <IconChevronDown className="size-4 shrink-0" aria-hidden />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="w-96 p-2">
        <div className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] gap-2">
          <div className="rounded-md border p-1">
            <div className="px-1 pb-1 text-[10px] font-semibold text-muted-foreground">
              Line 선택
            </div>
            <div className="flex max-h-52 flex-col gap-1 overflow-y-auto pr-1">
              {visibleLineOptions.length > 0 ? (
                visibleLineOptions.map((option) => {
                  const isActive = option.lineId === activeLineId
                  const isSelectedLine = option.lineId === selectedLineId
                  return (
                    <button
                      key={option.lineId}
                      type="button"
                      onClick={(event) => {
                        event.preventDefault()
                        setActiveLineId(option.lineId)
                      }}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-md border border-transparent px-2 py-1 text-left text-xs transition-colors",
                        isActive ? "bg-primary/10 text-primary" : "hover:bg-muted",
                      )}
                    >
                      <span className="flex h-4 w-4 items-center justify-center">
                        {isSelectedLine ? <IconCheck className="size-4 text-primary" aria-hidden /> : null}
                      </span>
                      <span className="truncate">{formatMappingLineLabel(option.lineId)}</span>
                    </button>
                  )
                })
              ) : (
                <div className="px-2 py-1 text-[11px] text-muted-foreground">
                  선택 가능한 Line이 없습니다.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-md border p-1">
            <div className="flex items-center justify-between gap-2 px-1 pb-1 text-[10px] font-semibold text-muted-foreground">
              <span>{label} 선택</span>
              <span
                className={cn(
                  "min-w-0 truncate rounded px-1 py-[2px] text-[10px] font-medium",
                  activeLineId ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
                )}
                title={activeLineId || "Line 미선택"}
              >
                {activeLineId ? formatMappingLineLabel(activeLineId) : "Line 미선택"}
              </span>
            </div>
            {activeLineId ? (
              <div className="flex max-h-52 flex-col gap-1 overflow-y-auto pr-1">
                {activeValues.length > 0 ? (
                  activeValues.map((value) => {
                    const valueKey = String(value || "").trim().toLowerCase()
                    const isSelected = activeLineId === selectedLineId && (
                      multiSelect ? selectedValueSet.has(valueKey) : value === selectedValue
                    )
                    if (multiSelect) {
                      return (
                        <DropdownMenuCheckboxItem
                          key={`${activeLineId}-${value}`}
                          checked={isSelected}
                          onSelect={(event) => {
                            event.preventDefault()
                          }}
                          onCheckedChange={() => {
                            const nextValues = selectedValueSet.has(valueKey)
                              ? activeSelectedValues.filter((selected) => (
                                  selected.toLowerCase() !== valueKey
                                ))
                              : [...activeSelectedValues, value]
                            onMultiSelect?.({ lineId: activeLineId, values: nextValues })
                          }}
                          className="rounded-md py-1 pr-2 text-xs"
                        >
                          <span className="truncate">{value}</span>
                        </DropdownMenuCheckboxItem>
                      )
                    }
                    return (
                      <button
                        key={`${activeLineId}-${value}`}
                        type="button"
                        onClick={(event) => {
                          event.preventDefault()
                          onSelect?.({ lineId: activeLineId, value })
                          setOpen(false)
                        }}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-md border border-transparent px-2 py-1 text-left text-xs transition-colors",
                          isSelected ? "bg-primary/10 text-primary" : "hover:bg-muted",
                        )}
                      >
                        <span className="flex h-4 w-4 items-center justify-center">
                          {isSelected ? <IconCheck className="size-4 text-primary" aria-hidden /> : null}
                        </span>
                        <span className="truncate">{value}</span>
                      </button>
                    )
                  })
                ) : (
                  <div className="px-2 py-1 text-[11px] text-muted-foreground">
                    선택 가능한 소속이 없습니다.
                  </div>
                )}
              </div>
            ) : (
              <div className="px-2 py-1 text-[11px] text-muted-foreground">
                Line을 먼저 선택하세요.
              </div>
            )}
          </div>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

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
  lineId,
  target,
  draft,
  userOptionValues = [],
  sdwtOptionValues = [],
  mappingUserLineId,
  mappingSdwtLineId,
  mappingUserLineOptions = [],
  mappingSdwtLineOptions = [],
  mappingOptionLinesError,
  mappingValueLineLabels = {},
  isMappingOptionLinesLoading,
  error,
  isSaving,
  deletingMappingKey,
  canManage,
  onDraftChange,
  onMappingUserLineChange,
  onMappingSdwtLineChange,
  onSubmit,
  onDeleteMapping,
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
  const hasLineOptions = mappingUserLineOptions.length > 0 && mappingSdwtLineOptions.length > 0
  const isControlDisabled = !canManage || isSaving
  const isSelectDisabled = isControlDisabled || !hasOptions
  const selectedUserSdwtProd = resolveSelectedOptionValue(userOptionValues, draft.userSdwtProd)
  const selectedSdwtProd = resolveSelectedOptionValue(sdwtOptionValues, draft.sdwtProd)
  const selectedUserSdwtProds = normalizeSelectedValues(draft.userSdwtProds, selectedUserSdwtProd)
    .filter((value) => userOptionValues.includes(value))
  const canSubmitMapping = Boolean(selectedUserSdwtProds.length > 0 && selectedSdwtProd)

  return (
    <div className="flex h-full min-h-0 flex-col rounded-md border bg-muted/30 px-3 py-2">
      <div className="flex shrink-0 items-center justify-between gap-2">
        <span className="text-xs font-medium text-foreground">Engr분임조 - 설비분임조 조합</span>
        <Badge variant={target.isConfigured ? "default" : "secondary"} className="text-[10px]">
          {target.isConfigured ? "설정됨" : "미설정"}
        </Badge>
      </div>
      {mappingOptionLinesError ? (
        <p className="mt-1 shrink-0 text-[11px] text-destructive" role="alert">
          Line 옵션을 불러오지 못했습니다. {mappingOptionLinesError}
        </p>
      ) : null}
      {isMappingOptionLinesLoading ? (
        <p className="mt-1 shrink-0 text-[11px] text-muted-foreground">
          Line 옵션을 불러오는 중입니다.
        </p>
      ) : null}
      <form
        className="my-2 flex min-w-0 shrink-0 items-end gap-1.5"
        onSubmit={(event) => {
          if (!canSubmitMapping) {
            event.preventDefault()
            return
          }
          onSubmit(event)
        }}
      >
        <div className="min-w-0 space-y-1">
          <span className="block truncate text-[10px] font-medium text-muted-foreground">
            Engr 분임조
          </span>
          <MappingAffiliationDropdown
            label="Engr"
            placeholder="Engr 선택"
            currentLineId={lineId}
            selectedLineId={mappingUserLineId}
            selectedValue={selectedUserSdwtProd}
            selectedValues={selectedUserSdwtProds}
            lineOptions={mappingUserLineOptions}
            multiSelect
            pinSystemLineToTop
            disabled={isControlDisabled || !hasLineOptions}
            onSelect={({ lineId: nextLineId, value }) => {
              onMappingUserLineChange(nextLineId)
              onDraftChange("userSdwtProds", [value])
              onDraftChange("userSdwtProd", value)
            }}
            onMultiSelect={({ lineId: nextLineId, values }) => {
              onMappingUserLineChange(nextLineId)
              onDraftChange("userSdwtProds", values)
              onDraftChange("userSdwtProd", values[0] || "")
            }}
          />
        </div>
        <span className="flex h-8 shrink-0 items-center">
          <IconArrowRight className="size-4 text-muted-foreground" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <span className="block truncate text-[10px] font-medium text-muted-foreground">
            설비 분임조
          </span>
          <MappingAffiliationDropdown
            label="설비"
            placeholder="설비 선택"
            currentLineId={lineId}
            selectedLineId={mappingSdwtLineId}
            selectedValue={selectedSdwtProd}
            lineOptions={mappingSdwtLineOptions}
            disabled={isControlDisabled || !hasLineOptions}
            onSelect={({ lineId: nextLineId, value }) => {
              onMappingSdwtLineChange(nextLineId)
              onDraftChange("sdwtProd", value)
            }}
          />
        </div>
        <Button
          type="submit"
          size="sm"
          variant="outline"
          disabled={isSelectDisabled || !canSubmitMapping}
          className="h-8 shrink-0"
        >
          <IconPlus className="mr-1 size-3" />
          {selectedUserSdwtProds.length > 1 ? `${selectedUserSdwtProds.length}개 추가` : "추가"}
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
      <div className="mt-2 flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto pr-1">
        {mappings.length > 0 ? (
          mappings.map((mapping) => {
            const sdwtProd = mapping.sdwtProd || "-"
            const userSdwtProd = mapping.userSdwtProd || "-"
            const sdwtProdLineLabel = getMappingValueLineLabel(mappingValueLineLabels, sdwtProd)
            const userSdwtProdLineLabel = getMappingValueLineLabel(mappingValueLineLabels, userSdwtProd)
            const sdwtProdLabel = sdwtProdLineLabel ? `${sdwtProdLineLabel} · ${sdwtProd}` : sdwtProd
            const userSdwtProdLabel = userSdwtProdLineLabel
              ? `${userSdwtProdLineLabel} · ${userSdwtProd}`
              : userSdwtProd
            const mappingKey = `${userSdwtProd.trim().toLowerCase()}::${sdwtProd.trim().toLowerCase()}`
            const isDeleting = deletingMappingKey === mappingKey
            const isDeleteDisabled = !canManage || isSaving || isDeleting
            return (
              <Badge
                key={`${sdwtProd}-${userSdwtProd}`}
                variant="outline"
                className="group grid max-w-full grid-cols-[minmax(5.5rem,9rem)_4.5rem_auto_minmax(5.5rem,9rem)_auto_auto] items-center gap-2 rounded-lg bg-background px-2.5 py-1.5 text-[11px] shadow-sm transition-colors hover:bg-accent/50"
              >
                <span className="min-w-0 truncate text-center font-mono font-semibold text-foreground" title={userSdwtProdLabel}>
                  {userSdwtProdLabel}
                </span>
                <span className="shrink-0 text-muted-foreground">분임조원이</span>
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <IconArrowRight className="size-3.5" aria-hidden="true" />
                </span>
                <span className="min-w-0 truncate text-center font-mono font-semibold" title={sdwtProdLabel}>
                  {sdwtProdLabel}
                </span>
                <span className="shrink-0 text-muted-foreground">설비로 보낸 E-SOP</span>
                <button
                  type="button"
                  disabled={isDeleteDisabled}
                  onClick={() => onDeleteMapping(mapping)}
                  className="flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                  aria-label={`${userSdwtProd} - ${sdwtProd} 지정 조합 삭제`}
                  title="지정 조합 삭제"
                >
                  <IconTrash className="size-3.5" aria-hidden="true" />
                </button>
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
  isCreateTargetPermissionLoading = false,
  canManageMappings,
  isCreatingTarget,
  isCreatingMapping,
  deletingMappingKey,
  targetFormError,
  mappingFormError,
  mappingDraft,
  mappingOptions = { userSdwtProds: [], sdwtProds: [] },
  mappingUserLineId = "",
  mappingSdwtLineId = "",
  mappingUserLineOptions = [],
  mappingSdwtLineOptions = [],
  mappingOptionLinesError,
  mappingValueLineLabels = {},
  isMappingOptionLinesLoading = false,
  userSdwtValues,
  selectedUserSdwtProd,
  selectedNotificationTarget,
  onTargetDraftChange,
  onMappingDraftChange,
  onMappingUserLineChange,
  onMappingSdwtLineChange,
  onCreateTarget,
  onCreateTargetMapping,
  onDeleteTargetMapping,
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

      {targetFormError || (!canCreateTarget && !isCreateTargetPermissionLoading) ? (
        <div className="space-y-1">
          {targetFormError ? (
            <p className="text-xs text-destructive" role="alert">
              {targetFormError}
            </p>
          ) : null}
          {!canCreateTarget && !isCreateTargetPermissionLoading ? (
            <p className="text-[11px] text-muted-foreground">
              알림 Target 추가는 operator 권한과 선택된 line이 필요합니다.
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-hidden">
        <div className="min-h-0 flex-[0.75_1_0]">
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

        <div className="min-h-0 flex-[2_1_0]">
          <TargetMappingSummary
            lineId={lineId}
            target={selectedNotificationTarget}
            draft={mappingDraft}
            userOptionValues={mappingOptions.userSdwtProds}
            sdwtOptionValues={mappingOptions.sdwtProds}
            mappingUserLineId={mappingUserLineId}
            mappingSdwtLineId={mappingSdwtLineId}
            mappingUserLineOptions={mappingUserLineOptions}
            mappingSdwtLineOptions={mappingSdwtLineOptions}
            mappingOptionLinesError={mappingOptionLinesError}
            mappingValueLineLabels={mappingValueLineLabels}
            isMappingOptionLinesLoading={isMappingOptionLinesLoading}
            error={mappingFormError}
            isSaving={isCreatingMapping}
            deletingMappingKey={deletingMappingKey}
            canManage={canManageMappings}
            onDraftChange={onMappingDraftChange}
            onMappingUserLineChange={onMappingUserLineChange}
            onMappingSdwtLineChange={onMappingSdwtLineChange}
            onSubmit={onCreateTargetMapping}
            onDeleteMapping={onDeleteTargetMapping}
          />
        </div>
      </div>
    </div>
  )
}
