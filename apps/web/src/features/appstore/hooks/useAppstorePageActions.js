import { toast } from "sonner"

export function useAppstorePageActions({
  apps,
  editingApp,
  mutations,
  setDeletingCommentId,
  setEditingApp,
  setIsDetailOpen,
  setIsFormOpen,
  setSelectedAppId,
  setTogglingCommentLikeId,
  setUpdatingCommentId,
}) {
  const handleToggleLike = async (app) => {
    try {
      await mutations.toggleLikeMutation.mutateAsync(app.id)
    } catch (error) {
      toast.error(error?.message || "좋아요 토글에 실패했습니다.")
    }
  }

  const handleOpenLink = async (app) => {
    if (!app?.url) return
    try {
      await mutations.viewMutation.mutateAsync(app.id)
    } catch {
      // 조회수 증가는 실패해도 링크 열기는 유지합니다.
    } finally {
      if (typeof window !== "undefined") {
        window.open(app.url, "_blank", "noopener,noreferrer")
      }
    }
  }

  const handleOpenManual = (app) => {
    const manualUrl = typeof app?.manualUrl === "string" ? app.manualUrl.trim() : ""
    if (!manualUrl) return
    if (typeof window !== "undefined") {
      window.open(manualUrl, "_blank", "noopener,noreferrer")
    }
  }

  const handleSubmitApp = async (payload) => {
    try {
      if (editingApp) {
        const updated = await mutations.updateAppMutation.mutateAsync({
          appId: editingApp.id,
          updates: payload,
        })
        toast.success("앱 정보를 수정했어요.")
        setSelectedAppId(updated.id)
      } else {
        const created = await mutations.createAppMutation.mutateAsync(payload)
        toast.success("앱을 등록했어요.")
        setSelectedAppId(created.id)
      }
      setIsFormOpen(false)
      setEditingApp(null)
    } catch (error) {
      toast.error(error?.message || "앱 정보를 저장하지 못했습니다.")
    }
  }

  const handleEditApp = (app) => {
    setEditingApp(app)
    setIsFormOpen(true)
  }

  const handleDeleteApp = async (app) => {
    const confirmed = typeof window === "undefined" ? true : window.confirm("이 앱을 삭제할까요?")
    if (!confirmed) return
    try {
      await mutations.deleteAppMutation.mutateAsync(app.id)
      toast.success("앱을 삭제했어요.")
      const nextId = apps.find((item) => item.id !== app.id)?.id ?? null
      setSelectedAppId(nextId)
      setIsDetailOpen(false)
    } catch (error) {
      toast.error(error?.message || "앱을 삭제하지 못했습니다.")
    }
  }

  const handleAddComment = async (appId, content, parentCommentId) => {
    try {
      const result = await mutations.createCommentMutation.mutateAsync({
        appId,
        content,
        parentCommentId,
      })
      toast.success("댓글을 추가했어요.")
      return result
    } catch (error) {
      toast.error(error?.message || "댓글을 추가하지 못했습니다.")
      throw error
    }
  }

  const handleToggleCommentLike = async (appId, commentId) => {
    setTogglingCommentLikeId(commentId)
    try {
      await mutations.toggleCommentLikeMutation.mutateAsync({ appId, commentId })
    } catch (error) {
      toast.error(error?.message || "댓글 좋아요 토글에 실패했습니다.")
    } finally {
      setTogglingCommentLikeId(null)
    }
  }

  const handleUpdateComment = async (appId, commentId, content) => {
    setUpdatingCommentId(commentId)
    try {
      const result = await mutations.updateCommentMutation.mutateAsync({ appId, commentId, content })
      toast.success("댓글을 수정했어요.")
      return result
    } catch (error) {
      toast.error(error?.message || "댓글을 수정하지 못했습니다.")
      throw error
    } finally {
      setUpdatingCommentId(null)
    }
  }

  const handleDeleteComment = async (appId, commentId) => {
    setDeletingCommentId(commentId)
    try {
      await mutations.deleteCommentMutation.mutateAsync({ appId, commentId })
      toast.success("댓글을 삭제했어요.")
    } catch (error) {
      toast.error(error?.message || "댓글을 삭제하지 못했습니다.")
    } finally {
      setDeletingCommentId(null)
    }
  }

  return {
    handleAddComment,
    handleDeleteApp,
    handleDeleteComment,
    handleEditApp,
    handleOpenLink,
    handleOpenManual,
    handleSubmitApp,
    handleToggleCommentLike,
    handleToggleLike,
    handleUpdateComment,
  }
}
