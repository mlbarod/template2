import { IconSearch, IconUserPlus } from "@tabler/icons-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  getRecipientListText,
  getRecipientKey,
  getRecipientPickerUsers,
  getRecipientSecondaryText,
} from "../../utils/lineSettings"

const RECIPIENT_PICKER_LIST_HEIGHT_CLASS = "h-[420px]"

function RecipientPickerUserList({
  users,
  selectedIds,
  isLoading,
  loadingText,
  emptyText,
  onToggleUser,
  onToggleAll,
}) {
  const visibleRecipientKeys = users.map(getRecipientKey).filter(Boolean)
  const selectedVisibleCount = visibleRecipientKeys.filter((recipientKey) =>
    selectedIds.includes(recipientKey),
  ).length
  const allChecked = visibleRecipientKeys.length > 0 && selectedVisibleCount === visibleRecipientKeys.length
  const checked = allChecked ? true : selectedVisibleCount > 0 ? "indeterminate" : false

  if (isLoading) {
    return (
      <div className={`flex ${RECIPIENT_PICKER_LIST_HEIGHT_CLASS} min-h-0 min-w-0 items-center justify-center rounded-md border px-3 py-8 text-center text-xs text-muted-foreground`}>
        {loadingText}
      </div>
    )
  }

  if (users.length === 0) {
    return (
      <div className={`flex ${RECIPIENT_PICKER_LIST_HEIGHT_CLASS} min-h-0 min-w-0 items-center justify-center rounded-md border px-3 py-8 text-center text-xs text-muted-foreground`}>
        {emptyText}
      </div>
    )
  }

  return (
    <div className={`grid ${RECIPIENT_PICKER_LIST_HEIGHT_CLASS} min-h-0 grid-rows-[auto,minmax(0,1fr)] overflow-hidden rounded-md border`}>
      <label className="flex h-8 items-center gap-2 border-b px-3 text-xs font-medium">
        <Checkbox
          checked={checked}
          onCheckedChange={(nextChecked) => onToggleAll(nextChecked === true)}
        />
        현재 결과 전체 선택
      </label>
      <div className="min-h-0 overflow-y-auto">
        <div className="flex flex-col">
          {users.map((user) => {
            const recipientKey = getRecipientKey(user)
            if (!recipientKey) return null
            return (
              <label
                key={recipientKey}
                className="flex h-[44px] max-h-[44px] min-h-[44px] flex-none min-w-0 cursor-pointer items-center gap-3 border-b px-3"
              >
                <Checkbox
                  checked={selectedIds.includes(recipientKey)}
                  onCheckedChange={(nextChecked) => onToggleUser(recipientKey, nextChecked === true)}
                />
                <div className="min-w-0">
                  <div className="truncate text-xs font-medium leading-tight">{getRecipientListText(user)}</div>
                  <div className="truncate text-[11px] leading-tight text-muted-foreground">
                    {getRecipientSecondaryText(user)}
                  </div>
                </div>
              </label>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export function RecipientPickerDialog({
  open,
  activeTab,
  config,
  selectedUserSdwtProd,
  canManageRecipients,
  accountUserSdwtValues,
  sourceSdwt,
  onOpenChange,
  onTabChange,
  onSourceSdwtChange,
  isLoadingSourceUsers,
  onLoadSourceRecipients,
  searchValue,
  onSearchChange,
  isSearchingRecipients,
  onSearch,
  results,
  selectedIds,
  onToggleUser,
  onToggleAll,
  onApply,
  error,
}) {
  const groupUsers = results?.group || []
  const searchUsers = results?.search || []
  const selectableUsers = getRecipientPickerUsers(results)
  const selectedCount = selectableUsers.filter((user) => {
    const recipientKey = getRecipientKey(user)
    return recipientKey && selectedIds.includes(recipientKey)
  }).length
  const handleSourceSdwtChange = (value) => {
    onSourceSdwtChange(value)
    onLoadSourceRecipients(value)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid h-[min(85dvh,720px)] w-[min(760px,calc(100%-2rem))] max-w-[min(760px,calc(100%-2rem))] grid-rows-[auto,minmax(0,1fr),auto] overflow-hidden">
        <DialogHeader>
          <DialogTitle>{config.title} 선택</DialogTitle>
          <DialogDescription>
            {selectedUserSdwtProd || "알림 Target"}에 추가할 수신인을 선택한 뒤 적용합니다.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={onTabChange} className="h-full min-h-0 overflow-hidden">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="group">소속에서 불러오기</TabsTrigger>
            <TabsTrigger value="search">이름 · KnoxID 검색</TabsTrigger>
          </TabsList>

          <TabsContent
            value="group"
            className="h-full min-h-0 grid-rows-[auto,minmax(0,1fr)] gap-3 overflow-hidden data-[state=active]:grid data-[state=inactive]:hidden"
          >
            <div className="grid grid-cols-1 gap-2">
              <Select
                value={sourceSdwt || undefined}
                onValueChange={handleSourceSdwtChange}
                disabled={!canManageRecipients || accountUserSdwtValues.length === 0}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="소속 선택" />
                </SelectTrigger>
                <SelectContent>
                  {accountUserSdwtValues.map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <RecipientPickerUserList
              users={groupUsers}
              selectedIds={selectedIds}
              isLoading={isLoadingSourceUsers}
              loadingText="소속 사용자를 불러오는 중입니다."
              emptyText="소속을 선택하면 사용자를 불러옵니다."
              onToggleUser={onToggleUser}
              onToggleAll={(checked) => onToggleAll(groupUsers, checked)}
            />
          </TabsContent>

          <TabsContent
            value="search"
            className="h-full min-h-0 grid-rows-[auto,minmax(0,1fr)] gap-3 overflow-hidden data-[state=active]:grid data-[state=inactive]:hidden"
          >
            <form className="grid grid-cols-[minmax(0,1fr)_auto] gap-2" onSubmit={onSearch}>
              <Input
                value={searchValue}
                onChange={(event) => onSearchChange(event.target.value)}
                placeholder="이름/사번/Knox/email 검색"
                disabled={!canManageRecipients || isSearchingRecipients}
              />
              <Button
                type="submit"
                variant="outline"
                disabled={!canManageRecipients || isSearchingRecipients}
                className="gap-1"
              >
                <IconSearch className="size-4" />
                검색
              </Button>
            </form>

            <RecipientPickerUserList
              users={searchUsers}
              selectedIds={selectedIds}
              isLoading={isSearchingRecipients}
              loadingText="사용자를 검색하는 중입니다."
              emptyText="검색어를 입력하고 검색을 누르세요."
              onToggleUser={onToggleUser}
              onToggleAll={(checked) => onToggleAll(searchUsers, checked)}
            />
          </TabsContent>
        </Tabs>

        <DialogFooter className="items-center gap-2 sm:justify-between">
          <div className="min-w-0 text-xs text-muted-foreground">
            {error ? <span className="text-destructive">{error}</span> : `${selectedCount}명 선택됨`}
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              취소
            </Button>
            <Button type="button" onClick={onApply} disabled={!canManageRecipients || selectedCount === 0}>
              <IconUserPlus className="mr-1 size-4" />
              선택 인원 적용
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
