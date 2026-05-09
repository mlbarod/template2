// 앱스토어 메인 페이지
import { useEffect, useMemo, useState } from "react"

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { useAuth } from "@/features/auth"
import { useAppstorePageActions } from "../hooks/useAppstorePageActions"
import { useAppstoreMutations } from "../hooks/useAppstoreMutations"
import { useAppDetailQuery, useAppsQuery } from "../hooks/useAppstoreQueries"
import { AppDetail } from "../components/AppDetail"
import { AppFilters } from "../components/AppFilters"
import { AppFormDialog } from "../components/AppFormDialog"
import { AppList } from "../components/AppList"
import {
  buildAppCategories,
  buildCategoryCounts,
  buildFormCategoryOptions,
  filterApps,
} from "../utils/appFilters"

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

  const mutations = useAppstoreMutations()
  const {
    createAppMutation,
    updateAppMutation,
    toggleLikeMutation,
    toggleCommentLikeMutation,
    createCommentMutation,
  } = mutations

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
    return buildAppCategories(apps)
  }, [apps])

  const formCategoryOptions = useMemo(() => {
    return buildFormCategoryOptions(apps)
  }, [apps])

  const categoryCounts = useMemo(() => {
    return buildCategoryCounts(apps)
  }, [apps])

  const filteredApps = useMemo(() => {
    return filterApps(apps, { category, query })
  }, [apps, category, query])

  const detailApp = appDetailQuery.data?.app ?? null

  const handleSelect = (appId) => {
    setSelectedAppId(appId)
    setIsDetailOpen(true)
  }

  const {
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
  } = useAppstorePageActions({
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
  })

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
          <DialogTitle className="sr-only">앱 상세</DialogTitle>
          <DialogDescription className="sr-only">선택한 앱의 상세 정보와 댓글을 확인합니다.</DialogDescription>
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
                  onOpenManual={handleOpenManual}
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
        categoryOptions={formCategoryOptions}
        defaultContactName={defaultContactName}
        defaultContactKnoxid={defaultContactKnoxid}
        isSubmitting={createAppMutation.isPending || updateAppMutation.isPending}
      />
    </div>
  )
}
