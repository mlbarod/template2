// 파일 경로: src/features/appstore/hooks/useAppstoreMutations.js
// Appstore 전용 React Query mutation 훅

import { useMutation, useQueryClient } from "@tanstack/react-query"

import {
  createApp,
  createComment,
  deleteApp,
  deleteComment,
  incrementView,
  toggleCommentLike,
  toggleLike,
  updateApp,
  updateComment,
} from "../api/appstore"
import { appstoreQueryKeys } from "../api/queryKeys"

function updateList(queryClient, updater) {
  queryClient.setQueryData(appstoreQueryKeys.apps(), (previous) => {
    if (!previous || !Array.isArray(previous.apps)) return previous
    const nextApps = updater(previous.apps)
    return {
      ...previous,
      apps: nextApps,
      total: typeof previous.total === "number" ? previous.total : nextApps.length,
    }
  })
}

function updateDetail(queryClient, appId, updater) {
  queryClient.setQueryData(appstoreQueryKeys.app(appId), (previous) => {
    if (!previous?.app) return previous
    const nextApp = updater(previous.app)
    return { app: nextApp }
  })
}

function updateCommentsQuery(queryClient, appId, updater) {
  queryClient.setQueryData(appstoreQueryKeys.comments(appId), (previous) => {
    if (!previous?.comments) return previous
    return updater(previous)
  })
}

function collectDescendantCommentIds(comments, rootId) {
  const ids = new Set([rootId])
  let changed = true
  while (changed) {
    changed = false
    comments.forEach((comment) => {
      const parentId = comment.parentCommentId
      if (parentId == null) return
      if (!ids.has(parentId)) return
      if (ids.has(comment.id)) return
      ids.add(comment.id)
      changed = true
    })
  }
  return ids
}

function replaceComment(comments, comment) {
  return comments.map((item) => (item.id === comment.id ? comment : item))
}

function applyCommentLikeResult(comments, result) {
  return comments.map((comment) =>
    comment.id === result.commentId
      ? { ...comment, liked: result.liked, likeCount: result.likeCount }
      : comment,
  )
}

export function useAppstoreMutations() {
  const queryClient = useQueryClient()

  const createAppMutation = useMutation({
    mutationFn: createApp,
    onSuccess: (app) => {
      queryClient.setQueryData(appstoreQueryKeys.apps(), (previous) => {
        const prevApps = previous?.apps ?? []
        const nextApps = [app, ...prevApps.filter((item) => item.id !== app.id)]
        const prevTotal =
          typeof previous?.total === "number" ? previous.total : prevApps.length
        return { apps: nextApps, total: prevTotal + 1 }
      })
      queryClient.setQueryData(appstoreQueryKeys.app(app.id), { app })
    },
  })

  const updateAppMutation = useMutation({
    mutationFn: ({ appId, updates }) => updateApp(appId, updates),
    onSuccess: (app) => {
      updateList(queryClient, (apps) =>
        apps.map((item) => (item.id === app.id ? { ...item, ...app } : item)),
      )
      queryClient.setQueryData(appstoreQueryKeys.app(app.id), { app })
    },
  })

  const deleteAppMutation = useMutation({
    mutationFn: (appId) => deleteApp(appId),
    onSuccess: (_result, appId) => {
      queryClient.setQueryData(appstoreQueryKeys.apps(), (previous) => {
        if (!previous?.apps) return previous
        const filtered = previous.apps.filter((item) => item.id !== appId)
        const prevTotal =
          typeof previous.total === "number" ? previous.total : previous.apps.length
        return { apps: filtered, total: Math.max(prevTotal - 1, filtered.length) }
      })
      queryClient.removeQueries({ queryKey: appstoreQueryKeys.app(appId) })
      queryClient.removeQueries({ queryKey: appstoreQueryKeys.comments(appId) })
    },
  })

  const toggleLikeMutation = useMutation({
    mutationFn: (appId) => toggleLike(appId),
    onSuccess: (result) => {
      updateList(queryClient, (apps) =>
        apps.map((item) =>
          item.id === result.appId
            ? { ...item, liked: result.liked, likeCount: result.likeCount }
            : item,
        ),
      )
      updateDetail(queryClient, result.appId, (app) => ({
        ...app,
        liked: result.liked,
        likeCount: result.likeCount,
      }))
    },
  })

  const viewMutation = useMutation({
    mutationFn: (appId) => incrementView(appId),
    onSuccess: (result) => {
      updateList(queryClient, (apps) =>
        apps.map((item) =>
          item.id === result.appId ? { ...item, viewCount: result.viewCount } : item,
        ),
      )
      updateDetail(queryClient, result.appId, (app) => ({
        ...app,
        viewCount: result.viewCount,
      }))
    },
  })

  const createCommentMutation = useMutation({
    mutationFn: ({ appId, content, parentCommentId }) => createComment(appId, content, parentCommentId),
    onSuccess: (comment, variables) => {
      updateDetail(queryClient, variables.appId, (app) => {
        const nextComments = [...(app.comments ?? []), comment]
        return { ...app, comments: nextComments, commentCount: nextComments.length }
      })
      updateList(queryClient, (apps) =>
        apps.map((item) =>
          item.id === variables.appId
            ? { ...item, commentCount: (item.commentCount ?? 0) + 1 }
            : item,
        ),
      )
      updateCommentsQuery(queryClient, variables.appId, (previous) => {
        return {
          ...previous,
          comments: [...previous.comments, comment],
          total: (previous.total ?? previous.comments.length) + 1,
        }
      })
    },
  })

  const updateCommentMutation = useMutation({
    mutationFn: ({ appId, commentId, content }) => updateComment(appId, commentId, content),
    onSuccess: (comment, variables) => {
      updateDetail(queryClient, variables.appId, (app) => {
        const nextComments = replaceComment(app.comments ?? [], comment)
        return { ...app, comments: nextComments }
      })
      updateCommentsQuery(queryClient, variables.appId, (previous) => {
        return {
          ...previous,
          comments: replaceComment(previous.comments, comment),
        }
      })
    },
  })

  const deleteCommentMutation = useMutation({
    mutationFn: ({ appId, commentId }) => deleteComment(appId, commentId),
    onSuccess: (_result, variables) => {
      let removedCount = 1
      updateDetail(queryClient, variables.appId, (app) => {
        const currentComments = app.comments ?? []
        const idsToRemove = collectDescendantCommentIds(currentComments, variables.commentId)
        removedCount = idsToRemove.size
        const nextComments = currentComments.filter((item) => !idsToRemove.has(item.id))
        return { ...app, comments: nextComments, commentCount: nextComments.length }
      })
      updateCommentsQuery(queryClient, variables.appId, (previous) => {
        const idsToRemove = collectDescendantCommentIds(previous.comments, variables.commentId)
        removedCount = Math.max(removedCount, idsToRemove.size)
        const filtered = previous.comments.filter((item) => !idsToRemove.has(item.id))
        return {
          ...previous,
          comments: filtered,
          total: Math.max((previous.total ?? filtered.length) - idsToRemove.size, filtered.length),
        }
      })
      updateList(queryClient, (apps) =>
        apps.map((item) =>
          item.id === variables.appId
            ? { ...item, commentCount: Math.max((item.commentCount ?? 0) - removedCount, 0) }
            : item,
        ),
      )
    },
  })

  const toggleCommentLikeMutation = useMutation({
    mutationFn: ({ appId, commentId }) => toggleCommentLike(appId, commentId),
    onSuccess: (result) => {
      updateDetail(queryClient, result.appId, (app) => ({
        ...app,
        comments: applyCommentLikeResult(app.comments ?? [], result),
      }))

      updateCommentsQuery(queryClient, result.appId, (previous) => {
        return {
          ...previous,
          comments: applyCommentLikeResult(previous.comments, result),
        }
      })
    },
  })

  return {
    createAppMutation,
    updateAppMutation,
    deleteAppMutation,
    toggleLikeMutation,
    viewMutation,
    createCommentMutation,
    updateCommentMutation,
    deleteCommentMutation,
    toggleCommentLikeMutation,
  }
}
