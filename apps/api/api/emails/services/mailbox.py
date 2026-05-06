# =============================================================================
# 모듈 설명: 메일함 접근 요약 정보를 제공합니다.
# - 주요 함수: get_mailbox_access_summary_for_user
# - 불변 조건: UNASSIGNED 메일함은 권한에 따라 제외될 수 있습니다.
# =============================================================================

from __future__ import annotations

from typing import Any

import api.account.selectors as account_selectors
from api.common.services import UNASSIGNED_USER_SDWT_PROD

from ..selectors import (
    get_accessible_user_sdwt_prods_for_user,
    list_mailbox_members,
    list_privileged_email_mailboxes,
)
from ..permissions import user_can_view_unassigned


def get_mailbox_access_summary_for_user(*, user: Any) -> list[dict[str, object]]:
    """현재 사용자 기준 메일함 접근 요약을 반환합니다.

    입력:
        user: Django User 또는 유사 객체.
    반환:
        메일함별 멤버/권한 요약 리스트.
    부작용:
        없음. 조회 전용.
    오류:
        비인증 사용자는 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 인증 여부 및 권한 구분
    # -----------------------------------------------------------------------------
    if not user or not getattr(user, "is_authenticated", False):
        return []

    is_privileged = bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))

    # -----------------------------------------------------------------------------
    # 2) 접근 가능한 메일함 목록 구성
    # -----------------------------------------------------------------------------
    if is_privileged:
        mailboxes = list_privileged_email_mailboxes()
        if not user_can_view_unassigned(user):
            mailboxes = [
                mailbox
                for mailbox in mailboxes
                if mailbox not in {UNASSIGNED_USER_SDWT_PROD, "rp-unclassified"}
            ]
    else:
        mailboxes = sorted(get_accessible_user_sdwt_prods_for_user(user))

    # -----------------------------------------------------------------------------
    # 3) 메일함별 멤버 요약 구성
    # -----------------------------------------------------------------------------
    summaries: list[dict[str, object]] = []
    user_id = getattr(user, "id", None)
    current_user_sdwt = (account_selectors.get_current_user_sdwt_prod(user=user) or "").strip()
    current_lookup = current_user_sdwt.casefold()

    for mailbox in mailboxes:
        members = list_mailbox_members(mailbox_user_sdwt_prod=mailbox)
        member_count = len(members)
        current_member = None
        if isinstance(user_id, int):
            for member in members:
                if member.get("userId") == user_id:
                    current_member = member
                    break
        mailbox_lookup = mailbox.casefold() if isinstance(mailbox, str) else ""
        if is_privileged:
            access_source = "privileged"
        elif current_lookup and mailbox_lookup == current_lookup:
            access_source = "self"
        elif current_member is not None:
            access_source = "grant"
        else:
            access_source = "unknown"

        summaries.append(
            {
                "userSdwtProd": mailbox,
                "accessSource": access_source,
                "memberCount": member_count,
                "myEmailCount": int(current_member.get("emailCount", 0)) if current_member else 0,
                "role": current_member.get("role") if current_member else "viewer",
                "myGrantedAt": current_member.get("grantedAt") if current_member else None,
                "myGrantedBy": current_member.get("grantedBy") if current_member else None,
            }
        )

    return summaries
