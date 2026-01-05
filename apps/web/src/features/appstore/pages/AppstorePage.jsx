// 앱스토어 메인 페이지
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { Dialog, DialogContent } from "@/components/ui/dialog"
import { useAuth } from "@/features/auth"
import { useAppstoreMutations } from "../hooks/useAppstoreMutations"
import { useAppDetailQuery, useAppsQuery } from "../hooks/useAppstoreQueries"
import { AppDetail } from "../components/AppDetail"
import { AppFilters } from "../components/AppFilters"
import { AppFormDialog } from "../components/AppFormDialog"
import { AppList } from "../components/AppList"

const EMPTY_APPS = []

export function AppstorePage() {
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [selectedAppId, setSelectedAppId] = useState(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [isDetailOpen, setIsDetailOpen] = useState(false)
  const [editingApp, setEditingApp] = useState(null)
  const [updatingCommentId, setUpdatingCommentId] = useState(null)
  const [deletingCommentId, setDeletingCommentId] = useState(null)
  const [togglingCommentLikeId, setTogglingCommentLikeId] = useState(null)

  const appsQuery = useAppsQuery()
  const apps = appsQuery.data?.apps ?? EMPTY_APPS
  const { user } = useAuth()

  const {
    createAppMutation,
    updateAppMutation,
    deleteAppMutation,
    toggleLikeMutation,
    toggleCommentLikeMutation,
    viewMutation,
    createCommentMutation,
    updateCommentMutation,
    deleteCommentMutation,
  } = useAppstoreMutations()

  useEffect(() => {
    if (selectedAppId && !apps.some((app) => app.id === selectedAppId)) {
      setSelectedAppId(null)
      setIsDetailOpen(false)
    }
  }, [apps, selectedAppId])

  const appDetailQuery = useAppDetailQuery(selectedAppId, {
    staleTime: 30_000,
  })

  const defaultContactName = useMemo(() => {
    return user?.username || user?.knox_id || ""
  }, [user])

  const defaultContactKnoxid = useMemo(() => {
    return user?.usr_id || ""
  }, [user])

  const categories = useMemo(() => {
    const unique = new Set(["all"])
    apps.forEach((app) => {
      const value = app.category || "기타"
      unique.add(value)
    })
    return Array.from(unique)
  }, [apps])

  const categoryCounts = useMemo(() => {
    return apps.reduce((acc, app) => {
      const key = app.category || "기타"
      acc[key] = (acc[key] ?? 0) + 1
      return acc
    }, {})
  }, [apps])

  const normalizedQuery = query.trim().toLowerCase()
  const filteredApps = useMemo(() => {
    return apps.filter((app) => {
      const categoryValueRaw = app.category || "기타"
      const matchesCategory = category === "all" || categoryValueRaw === category
      const name = (app.name || "").toLowerCase()
      const description = (app.description || "").toLowerCase()
      const categoryValue = categoryValueRaw.toLowerCase()
      const matchesQuery =
        !normalizedQuery ||
        name.includes(normalizedQuery) ||
        description.includes(normalizedQuery) ||
        categoryValue.includes(normalizedQuery)
      return matchesCategory && matchesQuery
    })
  }, [apps, category, normalizedQuery])

  const detailApp = appDetailQuery.data?.app ?? null

  const handleSelect = (appId) => {
    setSelectedAppId(appId)
    setIsDetailOpen(true)
  }

  const handleToggleLike = async (app) => {
    try {
      await toggleLikeMutation.mutateAsync(app.id)
    } catch (error) {
      toast.error(error?.message || "좋아요 토글에 실패했습니다.")
    }
  }

  const handleOpenLink = async (app) => {
    if (!app?.url) return
    try {
      await viewMutation.mutateAsync(app.id)
    } catch {
      // 조회수 증가는 실패해도 링크는 열어줍니다.
    } finally {
      if (typeof window !== "undefined") {
        window.open(app.url, "_blank", "noopener,noreferrer")
      }
    }
  }

  const handleSubmitApp = async (payload) => {
    try {
      if (editingApp) {
        const updated = await updateAppMutation.mutateAsync({ appId: editingApp.id, updates: payload })
        toast.success("앱 정보를 수정했어요.")
        setSelectedAppId(updated.id)
      } else {
        const created = await createAppMutation.mutateAsync(payload)
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
      await deleteAppMutation.mutateAsync(app.id)
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
      const result = await createCommentMutation.mutateAsync({ appId, content, parentCommentId })
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
      await toggleCommentLikeMutation.mutateAsync({ appId, commentId })
    } catch (error) {
      toast.error(error?.message || "댓글 좋아요 토글에 실패했습니다.")
    } finally {
      setTogglingCommentLikeId(null)
    }
  }

  const handleUpdateComment = async (appId, commentId, content) => {
    setUpdatingCommentId(commentId)
    try {
      const result = await updateCommentMutation.mutateAsync({ appId, commentId, content })
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
      await deleteCommentMutation.mutateAsync({ appId, commentId })
      toast.success("댓글을 삭제했어요.")
    } catch (error) {
      toast.error(error?.message || "댓글을 삭제하지 못했습니다.")
    } finally {
      setDeletingCommentId(null)
    }
  }

  const resetFilters = () => {
    setQuery("")
    setCategory("all")
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="grid flex-1 min-h-0 gap-4 lg:grid-cols-[280px_1fr]">
        <div className="h-full min-h-0">
          <AppFilters
            totalApps={apps.length}
            query={query}
            onQueryChange={setQuery}
            category={category}
            categories={categories}
            categoryCounts={categoryCounts}
            onCategoryChange={setCategory}
            onReset={resetFilters}
            onCreate={() => {
              setEditingApp(null)
              setIsFormOpen(true)
            }}
            isCreating={createAppMutation.isPending}
          />
        </div>

        <div className="min-h-0 overflow-y-auto pt-0.5">
          <AppList
            apps={filteredApps}
            selectedAppId={selectedAppId}
            onSelect={handleSelect}
            onOpenLink={handleOpenLink}
            onToggleLike={handleToggleLike}
            onEdit={handleEditApp}
            onDelete={handleDeleteApp}
            isLoading={appsQuery.isLoading || appsQuery.isFetching}
          />
        </div>
      </div>

      <Dialog
        open={isDetailOpen}
        onOpenChange={(open) => {
          setIsDetailOpen(open)
          if (!open) {
            setSelectedAppId(null)
          }
        }}
      >
        <DialogContent className="sm:max-w-4xl overflow-hidden p-0">
          <div className="grid max-h-[80vh] min-h-[60vh] grid-rows-[auto,1fr]">
            <div className="border-b px-6 py-4">
              <div className="text-sm font-semibold">앱 상세</div>
              <p className="text-xs text-muted-foreground">
                카드 선택 시 상세 정보와 댓글을 모달에서 확인할 수 있습니다.
              </p>
            </div>
            <div className="min-h-0 overflow-y-auto px-1 py-4">
              <div className="px-4">
                <AppDetail
                  app={detailApp}
                  isLoading={appDetailQuery.isFetching && !detailApp}
                  onOpenLink={handleOpenLink}
                  onToggleLike={handleToggleLike}
                  onEdit={handleEditApp}
                  onDelete={handleDeleteApp}
                  onAddComment={handleAddComment}
                  onUpdateComment={handleUpdateComment}
                  onDeleteComment={handleDeleteComment}
                  onToggleCommentLike={handleToggleCommentLike}
                  isLiking={toggleLikeMutation.isPending}
                  isAddingComment={createCommentMutation.isPending}
                  updatingCommentId={updatingCommentId}
                  deletingCommentId={deletingCommentId}
                  togglingCommentLikeId={togglingCommentLikeId}
                  isTogglingCommentLike={toggleCommentLikeMutation.isPending}
                />
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AppFormDialog
        open={isFormOpen}
        onOpenChange={(open) => {
          setIsFormOpen(open)
          if (!open) {
            setEditingApp(null)
          }
        }}
        onSubmit={handleSubmitApp}
        initialData={editingApp}
        defaultContactName={defaultContactName}
        defaultContactKnoxid={defaultContactKnoxid}
        isSubmitting={createAppMutation.isPending || updateAppMutation.isPending}
      />
    </div>
  )
}
