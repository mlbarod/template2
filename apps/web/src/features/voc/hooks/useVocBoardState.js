// 파일 경로: src/features/voc/hooks/useVocBoardState.js
// VOC 게시판 상태/동작을 캡슐화한 훅 (React Query 기반 데이터 소스)
import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { DEFAULT_APP_CATEGORY, DEFAULT_STATUS } from "../utils/constants"
import { vocQueryKeys } from "../api/queryKeys"
import {
  createVocPost,
  createVocReply,
  deleteVocPost,
  fetchVocPosts,
  updateVocPost,
} from "../api/voc"
import { hasMeaningfulContent, sanitizeContentHtml } from "../utils"
import {
  EMPTY_POSTS,
  buildVocStatusCounts,
  getVocPostAuthorKey,
  normalizeVocPosts,
  sanitizeVocPost,
} from "../utils/postTransforms"

export function useVocBoardState({ currentUser, isAdmin }) {
  const queryClient = useQueryClient()

  const [statusFilter, setStatusFilter] = React.useState(null)
  const [appFilter, setAppFilter] = React.useState(null)
  const [isMyPostsOnly, setIsMyPostsOnly] = React.useState(false)
  const [form, setForm] = React.useState({
    title: "",
    content: "",
    app: DEFAULT_APP_CATEGORY,
  })
  const [replyDrafts, setReplyDrafts] = React.useState({})
  const [selectedPostId, setSelectedPostId] = React.useState(null)
  const [isCreateOpen, setIsCreateOpen] = React.useState(false)
  const [pagination, setPagination] = React.useState({ pageIndex: 0, pageSize: 8 })
  const [isDetailOpen, setIsDetailOpen] = React.useState(false)
  const [error, setError] = React.useState(null)

  // 서버에서 VOC 글 목록과 상태 집계를 받아 클라이언트에서 정규화
  const postsQuery = useQuery({
    queryKey: vocQueryKeys.posts(),
    queryFn: fetchVocPosts,
    select: (payload) => {
      const posts = normalizeVocPosts(payload?.posts)
      return {
        posts,
        statusCounts: buildVocStatusCounts(posts, payload?.statusCounts),
      }
    },
  })

  React.useEffect(() => {
    if (postsQuery.error) {
      setError(postsQuery.error?.message || "VOC 데이터를 불러오지 못했습니다.")
    }
  }, [postsQuery.error])

  React.useEffect(() => {
    if (postsQuery.isSuccess) {
      setError(null)
    }
  }, [postsQuery.isSuccess])

  const posts = postsQuery.data?.posts ?? EMPTY_POSTS
  const currentUserId = currentUser?.id
  const basePosts = isMyPostsOnly
    ? posts.filter((post) => {
        const authorKey = getVocPostAuthorKey(post)
        return Boolean(authorKey && currentUserId && authorKey === currentUserId)
      })
    : posts

  const appScopedPosts = appFilter
    ? basePosts.filter((post) => post.app === appFilter)
    : basePosts
  const statusCounts = buildVocStatusCounts(appScopedPosts)

  const filteredPosts = statusFilter
    ? appScopedPosts.filter((post) => post.status === statusFilter)
    : appScopedPosts
  const start = pagination.pageIndex * pagination.pageSize
  const end = start + pagination.pageSize
  const visiblePosts = filteredPosts.slice(start, end)

  const pageCount = Math.max(Math.ceil(Math.max(filteredPosts.length, 1) / pagination.pageSize), 1)
  const currentPage = pagination.pageIndex + 1
  const totalPages = pageCount

  const selectedPost = basePosts.find((post) => post.id === selectedPostId) || null
  const isRefreshing = postsQuery.isFetching && !postsQuery.isPending

  React.useEffect(() => {
    if (!selectedPostId) return
    const exists = basePosts.some((post) => post.id === selectedPostId)
    if (!exists) {
      setSelectedPostId(null)
      setIsDetailOpen(false)
    }
  }, [basePosts, selectedPostId])

  React.useEffect(() => {
    const lastPageIndex = Math.max(
      Math.ceil(Math.max(filteredPosts.length, 1) / pagination.pageSize) - 1,
      0,
    )
    if (pagination.pageIndex > lastPageIndex) {
      setPagination((prev) => ({ ...prev, pageIndex: lastPageIndex }))
    }
  }, [filteredPosts.length, pagination.pageIndex, pagination.pageSize])

  const updateForm = (key, valueOrUpdater) => {
    setForm((prev) => {
      const nextValue =
        typeof valueOrUpdater === "function" ? valueOrUpdater(prev[key]) : valueOrUpdater
      return { ...prev, [key]: nextValue }
    })
  }

  const resetForm = () => {
    setForm({ title: "", content: "", app: DEFAULT_APP_CATEGORY })
  }

  const clearSelection = () => {
    setSelectedPostId(null)
    setIsDetailOpen(false)
  }

  const canDeletePost = (post) => {
    if (isAdmin) return true
    const authorKey = getVocPostAuthorKey(post)
    return Boolean(authorKey && currentUserId && authorKey === currentUserId)
  }

  const toggleStatusFilter = (status) => {
    setStatusFilter((prev) => (prev === status ? null : status))
    setPagination((prev) => ({ ...prev, pageIndex: 0 }))
  }

  const selectAppFilter = (app) => {
    setAppFilter(app)
    setPagination((prev) => ({ ...prev, pageIndex: 0 }))
  }

  const toggleMyPostsOnly = () => {
    setIsMyPostsOnly((prev) => !prev)
    setPagination((prev) => ({ ...prev, pageIndex: 0 }))
  }

  // React Query 캐시를 한 지점에서만 갱신해 리스트/집계의 일관성을 보장
  const updatePostsCache = (updater, nextStatusCounts) => {
    queryClient.setQueryData(vocQueryKeys.posts(), (previous) => {
      const base = previous?.posts ?? posts
      const updated = normalizeVocPosts(updater(base))
      const countsSource =
        nextStatusCounts && typeof nextStatusCounts === "object" ? nextStatusCounts : undefined
      return {
        posts: updated,
        statusCounts: buildVocStatusCounts(updated, countsSource),
      }
    })
  }

  const createPostMutation = useMutation({
    mutationFn: ({ title, content, status, app }) =>
      createVocPost({ title, content, status, app }),
    onMutate: () => {
      setError(null)
    },
    onError: (err) => {
      setError(err?.message || "글 등록에 실패했습니다.")
    },
    onSuccess: (result) => {
      if (!result?.post) return
      const safePost = sanitizeVocPost(result.post)
      if (!safePost) return

      updatePostsCache((prev) => [safePost, ...(prev ?? [])], result.statusCounts)
      setSelectedPostId(safePost.id)
      setPagination((prev) => ({ ...prev, pageIndex: 0 }))
      resetForm()
      setIsCreateOpen(false)
    },
  })

  const deletePostMutation = useMutation({
    mutationFn: (postId) => deleteVocPost(postId),
    onMutate: () => setError(null),
    onError: (err) => {
      setError(err?.message || "게시글을 삭제하지 못했습니다.")
    },
    onSuccess: (result, postId) => {
      updatePostsCache(
        (prev) => (prev ?? []).filter((post) => post.id !== postId),
        result?.statusCounts,
      )
      if (selectedPostId === postId) {
        clearSelection()
      }
    },
  })

  const updatePostMutation = useMutation({
    mutationFn: ({ postId, updates }) => updateVocPost(postId, updates),
    onMutate: () => setError(null),
    onError: (err) => {
      setError(err?.message || "게시글을 수정하지 못했습니다.")
    },
    onSuccess: (result) => {
      if (!result?.post) return
      const safePost = sanitizeVocPost(result.post)
      if (!safePost) return

      updatePostsCache(
        (prev) => (prev ?? []).map((post) => (post.id === safePost.id ? safePost : post)),
        result.statusCounts,
      )
    },
  })

  const replyMutation = useMutation({
    mutationFn: ({ postId, content }) => createVocReply({ postId, content }),
    onMutate: () => setError(null),
    onError: (err) => {
      setError(err?.message || "답변을 등록하지 못했습니다.")
    },
    onSuccess: (result, variables) => {
      const reply = result?.reply
      const safePost = sanitizeVocPost(result?.post)
      if (!reply && !safePost) return
      const targetId = variables.postId

      updatePostsCache((prev) =>
        (prev ?? []).map((post) => {
          if (post.id !== targetId) return post
          if (safePost) return safePost
          return { ...post, replies: [...post.replies, reply].filter(Boolean) }
        }),
      )
      setReplyDrafts((prev) => ({ ...prev, [targetId]: "" }))
    },
  })

  const createPost = async () => {
    const title = form.title.trim()
    const content = sanitizeContentHtml(form.content)
    const status = DEFAULT_STATUS
    const app = typeof form.app === "string" ? form.app.trim() : ""

    if (!title || !hasMeaningfulContent(content, { skipSanitize: true }) || !status) return null
    if (!app) return null
    try {
      const result = await createPostMutation.mutateAsync({ title, content, status, app })
      return result?.post ? sanitizeVocPost(result.post) : null
    } catch {
      return null
    }
  }

  const deletePost = async (postId) => {
    const target = posts.find((post) => post.id === postId)
    if (target && !canDeletePost(target)) {
      setError("작성자 또는 관리자만 삭제할 수 있습니다.")
      return
    }
    try {
      await deletePostMutation.mutateAsync(postId)
    } catch {
      // mutateAsync에서 에러 메시지를 이미 설정합니다.
    }
  }

  const addReply = async (postId) => {
    const replyText = (replyDrafts[postId] || "").trim()
    if (!replyText) return null
    try {
      await replyMutation.mutateAsync({ postId, content: replyText })
    } catch {
      return null
    }
    return null
  }

  const updateStatus = async (postId, status) => {
    if (!status) return
    try {
      await updatePostMutation.mutateAsync({ postId, updates: { status } })
    } catch {
      // mutation onError에서 처리합니다.
    }
  }

  const updatePost = async (postId, updates = {}) => {
    const target = posts.find((post) => post.id === postId)
    if (target && !canDeletePost(target)) {
      setError("작성자 또는 관리자만 수정할 수 있습니다.")
      return null
    }

    const title = typeof updates.title === "string" ? updates.title.trim() : ""
    const content = sanitizeContentHtml(updates.content)
    if (!title || !hasMeaningfulContent(content, { skipSanitize: true })) {
      setError("제목과 내용을 입력해주세요.")
      return null
    }

    try {
      const result = await updatePostMutation.mutateAsync({
        postId,
        updates: { title, content },
      })
      return result?.post ? sanitizeVocPost(result.post) : null
    } catch {
      return null
    }
  }

  const selectPost = (postId) => {
    setSelectedPostId(postId)
    setIsDetailOpen(true)
  }

  const updateReplyDraft = (postId, value) => {
    setReplyDrafts((prev) => ({ ...prev, [postId]: value }))
  }

  const changePageSize = (nextSize) => {
    setPagination({ pageIndex: 0, pageSize: nextSize })
  }

  const goToPage = (pageIndex) => {
    setPagination((prev) => {
      const clamped = Math.min(
        Math.max(pageIndex, 0),
        Math.max(Math.ceil(Math.max(filteredPosts.length, 1) / prev.pageSize) - 1, 0),
      )
      return { ...prev, pageIndex: clamped }
    })
  }

  const nextPage = () => {
    goToPage(pagination.pageIndex + 1)
  }

  const prevPage = () => {
    goToPage(pagination.pageIndex - 1)
  }

  const firstPage = () => {
    goToPage(0)
  }

  const lastPage = () => {
    goToPage(pageCount - 1)
  }

  return {
    statusCounts,
    statusFilter,
    appFilter,
    isMyPostsOnly,
    filteredPosts,
    visiblePosts,
    pagination: {
      ...pagination,
      pageCount,
      currentPage,
      totalPages,
      totalRows: filteredPosts.length,
    },
    selectedPost,
    selectedPostId,
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
    updatePost,
    selectPost,
    toggleStatusFilter,
    selectAppFilter,
    toggleMyPostsOnly,
    changePageSize,
    nextPage,
    prevPage,
    firstPage,
    lastPage,
    canDeletePost,
    isLoading: postsQuery.isPending,
    isRefreshing,
    error,
    reload: postsQuery.refetch,
    isSubmitting: createPostMutation.isPending,
    isUpdating: updatePostMutation.isPending,
    isReplying: replyMutation.isPending,
  }
}
