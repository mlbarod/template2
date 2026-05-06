import { buildBackendUrl } from "@/lib/api"

import { normalizeEmailListFilters } from "../utils/filters"

const BASE_PATH = "/api/v1/emails"

async function handleJsonResponse(response) {
  let data = {}
  try {
    data = await response.json()
  } catch {
    // ignore
  }

  if (!response.ok) {
    const message =
      typeof data?.error === "string"
        ? data.error
        : `요청이 실패했습니다. (status ${response.status})`
    const error = new Error(message)
    error.status = response.status
    error.payload = data
    throw error
  }

  return data
}

export async function fetchInboxEmails(params = {}) {
  const filters = normalizeEmailListFilters(params)
  const searchParams = {}
  if (filters.page) searchParams.page = filters.page
  if (filters.pageSize) searchParams.page_size = filters.pageSize
  if (filters.userSdwtProd) searchParams.user_sdwt_prod = filters.userSdwtProd
  if (filters.q) searchParams.q = filters.q
  if (filters.sender) searchParams.sender = filters.sender
  if (filters.recipient) searchParams.recipient = filters.recipient
  if (filters.dateFrom) searchParams.date_from = filters.dateFrom
  if (filters.dateTo) searchParams.date_to = filters.dateTo

  const response = await fetch(buildBackendUrl(`${BASE_PATH}/inbox/`, searchParams), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchSentEmails(params = {}) {
  const filters = normalizeEmailListFilters(params)
  const searchParams = {}
  if (filters.page) searchParams.page = filters.page
  if (filters.pageSize) searchParams.page_size = filters.pageSize
  if (filters.q) searchParams.q = filters.q
  if (filters.sender) searchParams.sender = filters.sender
  if (filters.recipient) searchParams.recipient = filters.recipient
  if (filters.dateFrom) searchParams.date_from = filters.dateFrom
  if (filters.dateTo) searchParams.date_to = filters.dateTo

  const response = await fetch(buildBackendUrl(`${BASE_PATH}/sent/`, searchParams), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchEmails(params = {}) {
  return fetchInboxEmails(params)
}

export async function fetchEmailMailboxes() {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/mailboxes/`), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchEmailMailboxSummary() {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/mailboxes/summary/`), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchEmailMailboxMembers(userSdwtProd) {
  const trimmed = typeof userSdwtProd === "string" ? userSdwtProd.trim() : ""
  const response = await fetch(
    buildBackendUrl(`${BASE_PATH}/mailboxes/members/`, {
      user_sdwt_prod: trimmed,
    }),
    { credentials: "include" },
  )

  return handleJsonResponse(response)
}

export async function fetchEmail(emailId) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/${emailId}/`), {
    credentials: "include",
  })
  return handleJsonResponse(response)
}

export async function fetchEmailHtml(emailId) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/${emailId}/html/`), {
    credentials: "include",
  })

  if (response.status === 204) return ""
  if (!response.ok) {
    const message = `HTML 본문을 불러오지 못했습니다. (status ${response.status})`
    const error = new Error(message)
    error.status = response.status
    throw error
  }

  return response.text()
}

export async function deleteEmail(emailId) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/${emailId}/`), {
    method: "DELETE",
    credentials: "include",
  })
  return handleJsonResponse(response)
}

export async function bulkDeleteEmails(emailIds = []) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/bulk-delete/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({ email_ids: emailIds }),
  })
  return handleJsonResponse(response)
}

export async function moveEmails(emailIds = [], toUserSdwtProd = "") {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/move/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({ email_ids: emailIds, to_user_sdwt_prod: toUserSdwtProd }),
  })
  return handleJsonResponse(response)
}
