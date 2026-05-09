import * as React from "react"

import { DEFAULT_APP_CATEGORY } from "../utils/constants"
import { hasMeaningfulContent, sanitizeContentHtml } from "../utils"

export function useVocCreateDialogState({
  appFilter,
  form,
  updateForm,
  setIsCreateOpen,
  createPost,
  isSubmitting,
}) {
  const handleCreateOpenChange = React.useCallback(
    (open) => {
      setIsCreateOpen(open)
      if (open) {
        updateForm("app", appFilter || form.app || DEFAULT_APP_CATEGORY)
      }
    },
    [appFilter, form.app, setIsCreateOpen, updateForm],
  )

  const handleCreatePost = React.useCallback(
    async (event) => {
      event.preventDefault()
      await createPost()
    },
    [createPost],
  )

  const sanitizedDraft = React.useMemo(
    () => sanitizeContentHtml(form.content),
    [form.content],
  )

  const hasDraftContent = React.useMemo(
    () => hasMeaningfulContent(sanitizedDraft, { skipSanitize: true }),
    [sanitizedDraft],
  )

  const isSubmitDisabled =
    isSubmitting || !form.title.trim() || !form.app?.trim() || !hasDraftContent

  return {
    handleCreateOpenChange,
    handleCreatePost,
    isSubmitDisabled,
  }
}
