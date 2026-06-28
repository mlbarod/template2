import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createExclusionFilter,
  deleteExclusionFilter,
  fetchExclusionFilters,
  l3SpiderQueryKeys,
  updateExclusionFilter,
} from "../api"

export function useExclusionFilters() {
  return useQuery({
    queryKey: l3SpiderQueryKeys.exclusionFilters(),
    queryFn: fetchExclusionFilters,
  })
}

function useInvalidateAfterMutation() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: l3SpiderQueryKeys.exclusionFilters() })
    // 필터 변경 시 meta·structure·stats·data 전체 무효화
    queryClient.invalidateQueries({ queryKey: l3SpiderQueryKeys.meta() })
    queryClient.invalidateQueries({ queryKey: ["l3-spider", "structure"] })
    queryClient.invalidateQueries({ queryKey: ["l3-spider", "stats"] })
    queryClient.invalidateQueries({ queryKey: ["l3-spider", "filter-candidates"] })
    queryClient.invalidateQueries({ queryKey: ["l3-spider", "data"] })
  }
}

export function useCreateExclusionFilter() {
  const invalidate = useInvalidateAfterMutation()
  return useMutation({
    mutationFn: createExclusionFilter,
    onSuccess: invalidate,
  })
}

export function useUpdateExclusionFilter() {
  const invalidate = useInvalidateAfterMutation()
  return useMutation({
    mutationFn: ({ id, ...data }) => updateExclusionFilter(id, data),
    onSuccess: invalidate,
  })
}

export function useDeleteExclusionFilter() {
  const invalidate = useInvalidateAfterMutation()
  return useMutation({
    mutationFn: deleteExclusionFilter,
    onSuccess: invalidate,
  })
}
