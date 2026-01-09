import { useQuery } from "@tanstack/react-query"

import { emailQueryKeys } from "../api/emailQueryKeys"
import { fetchEmailMailboxMembers } from "../api/emails"
import { normalizeMailbox } from "../utils/mailbox"

function normalizeText(value) {
  return typeof value === "string" ? value.trim() : ""
}

function getAvatarFallback(value) {
  const trimmed = normalizeText(value)
  if (!trimmed) return "?"

  const firstChar = Array.from(trimmed)[0] || "?"
  return /[a-z]/i.test(firstChar) ? firstChar.toUpperCase() : firstChar
}

function toSafeNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function resolveRole(member) {
  const role = normalizeText(member?.role)
  if (role === "viewer" || role === "member" || role === "manager") {
    return role
  }
  return "viewer"
}

function buildMemberRow(member) {
  const userId = member?.userId ?? member?.user_id ?? ""
  const avatarid = normalizeText(
    member?.avatarid ??
      member?.avatarId ??
      member?.avatar_id ??
      member?.userid ??
      member?.userId ??
      member?.user_id,
  )
  const name = normalizeText(member?.name)
  const username = normalizeText(member?.username)
  const knoxId = normalizeText(member?.knoxId ?? member?.knox_id)
  const userSdwtProd = normalizeText(member?.userSdwtProd ?? member?.user_sdwt_prod)

  const primary = username || name || userSdwtProd || "Unknown"
  const secondary = knoxId

  const idParts = [userId, knoxId, userSdwtProd].map((value) => String(value || "").trim()).filter(Boolean)
  const id = idParts.join("-") || primary

  return {
    id,
    userId,
    avatarid,
    userSdwtProd,
    name,
    username,
    knoxId,
    user: primary,
    secondary,
    fallback: getAvatarFallback(username || primary),
    role: resolveRole(member),
    emailCount: toSafeNumber(member?.emailCount),
  }
}

export function useEmailMailboxMembers(mailbox, options = {}) {
  const mailboxUserSdwtProd = normalizeMailbox(mailbox)
  const enabled = options.enabled ?? Boolean(mailboxUserSdwtProd)

  const query = useQuery({
    queryKey: emailQueryKeys.mailboxMembers(mailboxUserSdwtProd),
    queryFn: () => fetchEmailMailboxMembers(mailboxUserSdwtProd),
    enabled,
    staleTime: 60 * 1000,
  })

  const rawMembers = Array.isArray(query.data?.members) ? query.data.members : []
  const members = rawMembers.map(buildMemberRow)

  return {
    ...query,
    mailboxUserSdwtProd,
    members,
  }
}
