import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import { useAuth } from "@/lib/auth"

import { accountApi } from "./accountApi"
import { normalizeAccountOverview } from "./accountOverview"
import {
  withDevAccessAuditFixtures,
  withDevManageableGroupFixtures,
  withDevPendingAccessUserFixtures,
} from "./devFixtures"

export const AFFILIATION_QUERY_KEY = ["account", "affiliation"]
export const AFFILIATION_REQUESTS_QUERY_KEY = ["account", "affiliationRequests"]
export const AFFILIATION_MEMBERS_QUERY_KEY = ["account", "affiliationMembers"]
export const MANAGEABLE_QUERY_KEY = ["account", "manageable"]
export const OVERVIEW_QUERY_KEY = ["account", "overview"]
export const ACCESS_USERS_QUERY_KEY = ["account", "accessUsers"]
export const ACCESS_MATRIX_QUERY_KEY = ["account", "accessMatrix"]
export const ACCESS_POLICY_RULES_QUERY_KEY = ["account", "accessPolicyRules"]
export const ACCESS_AUDIT_LOGS_QUERY_KEY = ["account", "accessAuditLogs"]

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

export function useAccountOverview({ enabled = true } = {}) {
  return useQuery({
    queryKey: OVERVIEW_QUERY_KEY,
    queryFn: accountApi.fetchOverview,
    select: normalizeAccountOverview,
    enabled,
  })
}

export function useManageableGroups() {
  return useQuery({
    queryKey: MANAGEABLE_QUERY_KEY,
    queryFn: accountApi.fetchManageableGroups,
    select: withDevManageableGroupFixtures,
  })
}

export function useAffiliationRequests({
  page = 1,
  pageSize = 20,
  status = "pending",
  search = "",
  userSdwtProd = "",
  enabled = true,
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
    enabled,
  })
}

export function useInfiniteAffiliationRequests({
  pageSize = 20,
  status = "pending",
  search = "",
  userSdwtProd = "",
} = {}) {
  return useInfiniteQuery({
    queryKey: [
      ...AFFILIATION_REQUESTS_QUERY_KEY,
      "infinite",
      pageSize,
      status,
      search,
      userSdwtProd,
    ],
    queryFn: ({ pageParam = 1 }) =>
      accountApi.fetchAffiliationRequests({
        page: pageParam,
        pageSize,
        status,
        search,
        userSdwtProd,
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const currentPage = Number(lastPage?.page) || 1
      const totalPages = Number(lastPage?.totalPages) || 1
      return currentPage < totalPages ? currentPage + 1 : undefined
    },
    enabled: Boolean(userSdwtProd),
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

export function useAccessUsers({
  page = 1,
  pageSize = 20,
  status = "",
  source = "",
  search = "",
  department = "",
  scope = "portal",
  enabled = true,
} = {}) {
  return useQuery({
    queryKey: [
      ...ACCESS_USERS_QUERY_KEY,
      page,
      pageSize,
      status,
      source,
      search,
      department,
      scope,
    ],
    queryFn: () =>
      accountApi.fetchAccessUsers({
        page,
        pageSize,
        status,
        source,
        search,
        department,
        scope,
      }),
    select: (data) => withDevPendingAccessUserFixtures(data, { page, pageSize, status }),
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function useAccessMatrix({
  page = 1,
  pageSize = 20,
  search = "",
  department = "",
  enabled = true,
} = {}) {
  return useQuery({
    queryKey: [...ACCESS_MATRIX_QUERY_KEY, page, pageSize, search, department],
    queryFn: () => accountApi.fetchAccessMatrix({ page, pageSize, search, department }),
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function useAccessUserDecision() {
  const queryClient = useQueryClient()
  const { refresh: refreshAuth } = useAuth()
  return useMutation({
    mutationFn: accountApi.decideAccessUser,
    onSuccess: async () => {
      await Promise.all([
        refreshAuth(),
        queryClient.invalidateQueries({ queryKey: ACCESS_MATRIX_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: OVERVIEW_QUERY_KEY }),
      ])
    },
  })
}

export function useAccessPolicyRules({ scope = "portal", enabled = true } = {}) {
  return useQuery({
    queryKey: [...ACCESS_POLICY_RULES_QUERY_KEY, scope],
    queryFn: () => accountApi.fetchAccessPolicyRules({ scope }),
    enabled,
  })
}

export function useCreateAccessPolicyRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.createAccessPolicyRule,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ACCESS_POLICY_RULES_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
      ])
    },
  })
}

export function useUpdateAccessPolicyRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.updateAccessPolicyRule,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ACCESS_POLICY_RULES_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
      ])
    },
  })
}

export function useDeleteAccessPolicyRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.deleteAccessPolicyRule,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ACCESS_POLICY_RULES_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
      ])
    },
  })
}

export function useAccessAuditLogs({
  page = 1,
  pageSize = 20,
  scope = "",
  userId = "",
  action = "",
  enabled = true,
} = {}) {
  return useQuery({
    queryKey: [...ACCESS_AUDIT_LOGS_QUERY_KEY, page, pageSize, scope, userId, action],
    queryFn: () =>
      accountApi.fetchAccessAuditLogs({
        page,
        pageSize,
        scope,
        userId,
        action,
      }),
    select: (data) => withDevAccessAuditFixtures(data, { page, pageSize }),
    placeholderData: keepPreviousData,
    enabled,
  })
}
