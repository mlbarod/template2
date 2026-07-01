import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createMailRule,
  deleteMailRule,
  fetchMailRules,
  l3SpiderQueryKeys,
  updateMailRule,
  updateMailRulePermissions,
} from "../api"

export function useMailRules() {
  return useQuery({
    queryKey: l3SpiderQueryKeys.mailRules(),
    queryFn: fetchMailRules,
  })
}

function useInvalidateMailRules() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: l3SpiderQueryKeys.mailRules() })
  }
}

export function useCreateMailRule() {
  const invalidate = useInvalidateMailRules()
  return useMutation({
    mutationFn: createMailRule,
    onSuccess: invalidate,
  })
}

export function useUpdateMailRule() {
  const invalidate = useInvalidateMailRules()
  return useMutation({
    mutationFn: ({ id, ...data }) => updateMailRule(id, data),
    onSuccess: invalidate,
  })
}

export function useDeleteMailRule() {
  const invalidate = useInvalidateMailRules()
  return useMutation({
    mutationFn: deleteMailRule,
    onSuccess: invalidate,
  })
}

export function useUpdateMailRulePermissions() {
  const invalidate = useInvalidateMailRules()
  return useMutation({
    mutationFn: ({ id, permissions }) => updateMailRulePermissions(id, permissions),
    onSuccess: invalidate,
  })
}
