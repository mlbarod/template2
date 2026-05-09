import * as React from "react"

export function useVocPostDetailState({
  selectedPost,
  setIsDetailOpen,
  clearSelection,
  updatePost,
  deletePost,
}) {
  const [deleteTarget, setDeleteTarget] = React.useState(null)
  const [isEditing, setIsEditing] = React.useState(false)
  const [editForm, setEditForm] = React.useState({ title: "", content: "" })

  const handleDetailOpenChange = React.useCallback(
    (open) => {
      setIsDetailOpen(open)
      if (!open) {
        clearSelection()
        setIsEditing(false)
      }
    },
    [clearSelection, setIsDetailOpen],
  )

  React.useEffect(() => {
    if (selectedPost) {
      setEditForm({
        title: selectedPost.title || "",
        content: selectedPost.content || "",
      })
      setIsEditing(false)
      return
    }

    setEditForm({ title: "", content: "" })
    setIsEditing(false)
  }, [selectedPost])

  const handleRequestDelete = React.useCallback((post) => {
    if (!post) return
    setDeleteTarget({ id: post.id, title: post.title })
  }, [])

  const handleDeleteDialogOpenChange = React.useCallback((open) => {
    if (!open) setDeleteTarget(null)
  }, [])

  const handleConfirmDelete = React.useCallback(() => {
    if (!deleteTarget?.id) return
    deletePost(deleteTarget.id)
    setDeleteTarget(null)
  }, [deletePost, deleteTarget])

  const handleSaveEdit = React.useCallback(async () => {
    if (!selectedPost) return
    const updated = await updatePost(selectedPost.id, {
      title: editForm.title,
      content: editForm.content,
    })
    if (updated) {
      setIsEditing(false)
    }
  }, [editForm.content, editForm.title, selectedPost, updatePost])

  const handleCancelEdit = React.useCallback(() => {
    if (!selectedPost) {
      setIsEditing(false)
      setEditForm({ title: "", content: "" })
      return
    }
    setEditForm({ title: selectedPost.title || "", content: selectedPost.content || "" })
    setIsEditing(false)
  }, [selectedPost])

  return {
    deleteTarget,
    setDeleteTarget,
    isEditing,
    setIsEditing,
    editForm,
    setEditForm,
    handleDetailOpenChange,
    handleRequestDelete,
    handleDeleteDialogOpenChange,
    handleConfirmDelete,
    handleSaveEdit,
    handleCancelEdit,
  }
}
