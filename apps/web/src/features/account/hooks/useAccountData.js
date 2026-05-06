import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { accountApi } from "../api/accountApi"

export const AFFILIATION_QUERY_KEY = ["account", "affiliation"]
export const AFFILIATION_REQUESTS_QUERY_KEY = ["account", "affiliationRequests"]
export const AFFILIATION_MEMBERS_QUERY_KEY = ["account", "affiliationMembers"]
export const MANAGEABLE_QUERY_KEY = ["account", "manageable"]
export const OVERVIEW_QUERY_KEY = ["account", "overview"]

export function useAffiliation() {
  return useQuery({
    queryKey: AFFILIATION_QUERY_KEY,
    queryFn: accountApi.fetchAffiliation,
  })
}

export function useUpdateAffiliation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.updateAffiliation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AFFILIATION_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: OVERVIEW_QUERY_KEY })
    },
  })
}

export function useAccountOverview() {
  return useQuery({
    queryKey: OVERVIEW_QUERY_KEY,
    queryFn: accountApi.fetchOverview,
  })
}

export function useManageableGroups() {
  return useQuery({
    queryKey: MANAGEABLE_QUERY_KEY,
    queryFn: accountApi.fetchManageableGroups,
  })
}

export function useAffiliationRequests({
  page = 1,
  pageSize = 20,
  status = "pending",
  search = "",
  userSdwtProd = "",
} = {}) {
  return useQuery({
    queryKey: [
      ...AFFILIATION_REQUESTS_QUERY_KEY,
      page,
      pageSize,
      status,
      search,
      userSdwtProd,
    ],
    queryFn: () =>
      accountApi.fetchAffiliationRequests({
        page,
        pageSize,
        status,
        search,
        userSdwtProd,
      }),
  })
}

export function useAffiliationMembers({ userSdwtProd } = {}) {
  return useQuery({
    queryKey: [...AFFILIATION_MEMBERS_QUERY_KEY, userSdwtProd],
    queryFn: () => accountApi.fetchAffiliationMembers({ userSdwtProd }),
    enabled: Boolean(userSdwtProd),
  })
}

export function useAffiliationDecision() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.decideAffiliationRequest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AFFILIATION_REQUESTS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: AFFILIATION_MEMBERS_QUERY_KEY })
    },
  })
}

export function useUpdateGrant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.updateGrant,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MANAGEABLE_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: AFFILIATION_QUERY_KEY })
    },
  })
}
