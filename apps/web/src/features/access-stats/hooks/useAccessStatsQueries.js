import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  commitManualAppAccessStats,
  fetchAppAccessStats,
  previewManualAppAccessStats,
} from "../api/accessStatsApi"

export const accessStatsQueryKeys = {
  appAccessStats: (params) => ["access-stats", "app-access", params],
}

export function useAppAccessStatsQuery(params, options = {}) {
  return useQuery({
    queryKey: accessStatsQueryKeys.appAccessStats(params),
    queryFn: () => fetchAppAccessStats(params),
    ...options,
  })
}

export function useManualAppAccessPreviewMutation(options = {}) {
  return useMutation({
    mutationFn: previewManualAppAccessStats,
    ...options,
  })
}

export function useManualAppAccessCommitMutation(options = {}) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: commitManualAppAccessStats,
    ...options,
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["access-stats", "app-access"] })
      options.onSuccess?.(...args)
    },
  })
}
