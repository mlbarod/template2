// 파일 경로: src/features/voc/pages/VocBoardPage.jsx
// VOC 게시판: 새 글 작성, 답변, 상태 관리, 권한 기반 삭제를 제공하는 클라이언트 사이드 UI
import * as React from "react"
import { useOutletContext } from "react-router-dom"
import { Loader2, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card"
import { VocCreateDialog } from "../components/VocCreateDialog"
import { VocDeleteDialog } from "../components/VocDeleteDialog"
import { VocPagination } from "../components/VocPagination"
import { VocPostDetailDialog } from "../components/VocPostDetailDialog"
import { VocPostTable } from "../components/VocPostTable"
import { VocStatusSummary } from "../components/VocStatusSummary"
import { useVocCreateDialogState } from "../hooks/useVocCreateDialogState"
import { useVocPostDetailState } from "../hooks/useVocPostDetailState"
import "../utils/quill.css"
import "quill/dist/quill.snow.css"

export function VocBoardPage() {
  const {
    statusCounts,
    statusFilter,
    appFilter,
    isMyPostsOnly,
    filteredPosts,
    visiblePosts,
    pagination,
    selectedPost,
    clearSelection,
    isCreateOpen,
    setIsCreateOpen,
    isDetailOpen,
    setIsDetailOpen,
    replyDrafts,
    updateReplyDraft,
    form,
    updateForm,
    resetForm,
    createPost,
    deletePost,
    addReply,
    updateStatus,
    selectPost,
    toggleStatusFilter,
    toggleMyPostsOnly,
    changePageSize,
    nextPage,
    prevPage,
    firstPage,
    lastPage,
    canDeletePost,
    updatePost,
    isLoading,
    error,
    reload,
    isSubmitting,
    isUpdating,
    isRefreshing,
    isReplying,
  } = useOutletContext()

  const totalPosts = Object.values(statusCounts || {}).reduce(
    (sum, count) => sum + (Number.isFinite(count) ? count : 0),
    0,
  )
  const appFilterLabel = appFilter || "전체"

  const clearStatusFilter = React.useCallback(() => {
    if (statusFilter) {
      toggleStatusFilter(statusFilter)
    }
  }, [statusFilter, toggleStatusFilter])

  const {
    handleCreateOpenChange,
    handleCreatePost,
    isSubmitDisabled,
  } = useVocCreateDialogState({
    appFilter,
    form,
    updateForm,
    setIsCreateOpen,
    createPost,
    isSubmitting,
  })

  const {
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
  } = useVocPostDetailState({
    selectedPost,
    setIsDetailOpen,
    clearSelection,
    updatePost,
    deletePost,
  })

  const canEditSelected = selectedPost ? canDeletePost(selectedPost) : false
  const replyDraftValue = selectedPost ? replyDrafts[selectedPost.id] || "" : ""
  const isReplyDisabled = !replyDraftValue.trim() || isReplying

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      <Card className="flex-shrink-0">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-3">
              <CardDescription className="text-sm text-muted-foreground">
                VOC를 남겨 주시면 빠르게 답변드리겠습니다.
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="rounded-full bg-muted px-2 py-1 text-foreground shadow-xs">
                총 {totalPosts}건의 문의
              </span>
              <span className="rounded-full bg-muted px-2 py-1 text-foreground shadow-xs">
                앱 {appFilterLabel}
              </span>
              {isRefreshing ? (
                <span className="inline-flex items-center gap-1 text-primary">
                  <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                  최신 상태로 동기화 중
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 self-start sm:ml-auto">
            <Button
              variant="outline"
              size="icon"
              onClick={() => reload()}
              disabled={isLoading || isRefreshing}
              aria-label="VOC 게시판 새로고침"
              title="새로고침"
            >
              {isRefreshing ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="size-4" aria-hidden="true" />
              )}
            </Button>
            <VocCreateDialog
              open={isCreateOpen}
              onOpenChange={handleCreateOpenChange}
              form={form}
              updateForm={updateForm}
              resetForm={resetForm}
              onSubmit={handleCreatePost}
              isSubmitting={isSubmitting}
              isSubmitDisabled={isSubmitDisabled}
            />
          </div>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="mb-3 flex flex-wrap items-start justify-between gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <span>{error}</span>
              <Button size="sm" variant="outline" onClick={reload}>
                다시 시도
              </Button>
            </div>
          ) : null}
          <VocStatusSummary
            totalPosts={totalPosts}
            statusCounts={statusCounts}
            statusFilter={statusFilter}
            isMyPostsOnly={isMyPostsOnly}
            onClearStatusFilter={clearStatusFilter}
            onToggleStatusFilter={toggleStatusFilter}
            onToggleMyPostsOnly={toggleMyPostsOnly}
          />
        </CardContent>
      </Card>

      <section className="grid flex-1 min-h-0 grid-rows-[1fr_auto] gap-3">
        <VocPostTable
          isLoading={isLoading}
          isRefreshing={isRefreshing}
          filteredPosts={filteredPosts}
          visiblePosts={visiblePosts}
          statusFilter={statusFilter}
          selectedPost={selectedPost}
          pagination={pagination}
          onSelectPost={selectPost}
        />
        <VocPagination
          isLoading={isLoading}
          isRefreshing={isRefreshing}
          filteredCount={filteredPosts.length}
          visibleCount={visiblePosts.length}
          statusFilter={statusFilter}
          pagination={pagination}
          onFirstPage={firstPage}
          onPrevPage={prevPage}
          onNextPage={nextPage}
          onLastPage={lastPage}
          onChangePageSize={changePageSize}
        />
      </section>

      <VocPostDetailDialog
        open={isDetailOpen}
        selectedPost={selectedPost}
        onOpenChange={handleDetailOpenChange}
        updateStatus={updateStatus}
        canDeletePost={canDeletePost}
        canEditSelected={canEditSelected}
        isEditing={isEditing}
        setIsEditing={setIsEditing}
        editForm={editForm}
        setEditForm={setEditForm}
        handleSaveEdit={handleSaveEdit}
        handleCancelEdit={handleCancelEdit}
        handleRequestDelete={handleRequestDelete}
        replyDraftValue={replyDraftValue}
        updateReplyDraft={updateReplyDraft}
        addReply={addReply}
        isReplyDisabled={isReplyDisabled}
        isUpdating={isUpdating}
        isReplying={isReplying}
      />

      <VocDeleteDialog
        deleteTarget={deleteTarget}
        onOpenChange={handleDeleteDialogOpenChange}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
      />
    </div>
  )
}
