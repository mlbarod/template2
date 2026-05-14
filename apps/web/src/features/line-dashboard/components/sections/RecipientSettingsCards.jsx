import * as React from "react"

import { RecipientChannelCard } from "../cards/RecipientChannelCard"
import { RecipientPickerDialog } from "../dialog/RecipientPickerDialog"

export function RecipientSettingsCards({
  recipientChannels,
  selectedUserSdwtProd,
  canManageRecipients,
  currentRecipientDrafts,
  isMessengerRecipientsLoading,
  isMailRecipientsLoading,
  onRemoveUser,
  onSave,
  onOpenPicker,
  isRecipientDraftCurrent,
  isSavingRecipients,
  messengerForceNewChatroom,
  isSavingMessengerForceNewChatroom,
  onMessengerForceNewChatroomChange,
  recipientActionErrors,
  messengerRecipientsError,
  mailRecipientsError,
  recipientPickerOpen,
  recipientPickerTabs,
  accountUserSdwtValues,
  recipientSourceSdwt,
  onPickerOpenChange,
  onPickerTabChange,
  onSourceSdwtChange,
  isLoadingSourceUsers,
  onLoadSourceRecipients,
  recipientSearches,
  onRecipientSearchChange,
  isSearchingRecipients,
  onRecipientSearch,
  recipientPickerResults,
  recipientPickerSelectedIds,
  onRecipientPickerUserToggle,
  onRecipientPickerAllToggle,
  onApplyRecipientPicker,
}) {
  return recipientChannels.map((config) => {
    const isMessenger = config.channel === "messenger"
    const channelError =
      recipientActionErrors[config.channel] ||
      (isMessenger ? messengerRecipientsError : mailRecipientsError)

    return (
      <React.Fragment key={config.channel}>
        <div className="min-h-0 min-w-0">
          <RecipientChannelCard
            config={config}
            selectedUserSdwtProd={selectedUserSdwtProd}
            canManageRecipients={canManageRecipients}
            recipients={currentRecipientDrafts[config.channel] || []}
            isLoadingRecipients={isMessenger ? isMessengerRecipientsLoading : isMailRecipientsLoading}
            onRemoveUser={onRemoveUser}
            onSave={onSave}
            onOpenPicker={onOpenPicker}
            isDraftCurrent={Boolean(isRecipientDraftCurrent[config.channel])}
            isSavingRecipients={Boolean(isSavingRecipients[config.channel])}
            forceNewChatroom={isMessenger ? messengerForceNewChatroom : false}
            isSavingForceNewChatroom={isMessenger ? isSavingMessengerForceNewChatroom : false}
            onForceNewChatroomChange={isMessenger ? onMessengerForceNewChatroomChange : undefined}
            error={channelError}
          />
        </div>
        <RecipientPickerDialog
          open={Boolean(recipientPickerOpen[config.channel])}
          activeTab={recipientPickerTabs[config.channel] || "group"}
          config={config}
          selectedUserSdwtProd={selectedUserSdwtProd}
          canManageRecipients={canManageRecipients}
          accountUserSdwtValues={accountUserSdwtValues}
          sourceSdwt={recipientSourceSdwt[config.channel] || ""}
          onOpenChange={(open) => onPickerOpenChange(config.channel, open)}
          onTabChange={(value) => onPickerTabChange(config.channel, value)}
          onSourceSdwtChange={(value) => onSourceSdwtChange(config.channel, value)}
          isLoadingSourceUsers={Boolean(isLoadingSourceUsers[config.channel])}
          onLoadSourceRecipients={(sourceSdwt) => onLoadSourceRecipients(config.channel, sourceSdwt)}
          searchValue={recipientSearches[config.channel] || ""}
          onSearchChange={(value) => onRecipientSearchChange(config.channel, value)}
          isSearchingRecipients={Boolean(isSearchingRecipients[config.channel])}
          onSearch={(event) => onRecipientSearch(config.channel, event)}
          results={recipientPickerResults[config.channel] || { group: [], search: [] }}
          selectedIds={recipientPickerSelectedIds[config.channel] || []}
          onToggleUser={(userId, checked) => onRecipientPickerUserToggle(config.channel, userId, checked)}
          onToggleAll={(users, checked) => onRecipientPickerAllToggle(config.channel, users, checked)}
          onApply={() => onApplyRecipientPicker(config.channel)}
          error={recipientActionErrors[config.channel]}
        />
      </React.Fragment>
    )
  })
}
