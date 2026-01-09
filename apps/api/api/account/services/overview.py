# =============================================================================
# 모듈 설명: 계정 화면 개요 데이터를 구성하는 서비스를 제공합니다.
# - 주요 대상: get_account_overview
# - 불변 조건: 메일함 요약은 emails 서비스에 위임합니다.
# =============================================================================

"""계정 화면 개요 데이터를 구성하는 서비스 모음.

- 주요 대상: get_account_overview
- 주요 엔드포인트/클래스: 없음(서비스 함수 제공)
- 가정/불변 조건: 메일함 요약은 emails 서비스에 위임됨
"""
from __future__ import annotations

from typing import Any

import api.emails.services as email_services

from .. import selectors
from .access import _current_access_list, get_manageable_groups_with_members
from .affiliation_requests import _serialize_affiliation_change
from .affiliations import get_affiliation_reconfirm_status
from .utils import _is_privileged_user


def get_account_overview(*, user: Any, timezone_name: str) -> dict[str, object]:
    """계정 화면에서 필요한 전체 정보를 한번에 구성합니다.

    입력:
    - user: Django 사용자 객체
    - timezone_name: 시간대 이름

    반환:
    - dict[str, object]: 계정 개요 payload

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 접근 가능 그룹 및 관리 가능 그룹 계산
    # -----------------------------------------------------------------------------
    access_list = _current_access_list(user)
    manageable = [entry["userSdwtProd"] for entry in access_list if entry["role"] == "manager"]

    # -----------------------------------------------------------------------------
    # 2) 프로필/소속 기본 정보 구성
    # -----------------------------------------------------------------------------
    profile = {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "knoxId": getattr(user, "knox_id", None),
        "userSdwtProd": getattr(user, "user_sdwt_prod", None),
        "role": selectors.get_user_profile_role(user=user),
        "isSuperuser": bool(getattr(user, "is_superuser", False)),
        "isStaff": bool(getattr(user, "is_staff", False)),
    }

    # -----------------------------------------------------------------------------
    # 3) 소속 요약 정보 구성
    # -----------------------------------------------------------------------------
    affiliation_payload = {
        "currentUserSdwtProd": getattr(user, "user_sdwt_prod", None),
        "currentDepartment": getattr(user, "department", None),
        "currentLine": getattr(user, "line", None),
        "timezone": timezone_name,
        "accessibleUserSdwtProds": access_list,
        "manageableUserSdwtProds": manageable,
    }

    # -----------------------------------------------------------------------------
    # 4) 소속 변경 이력 구성
    # -----------------------------------------------------------------------------
    history_rows = selectors.list_user_sdwt_prod_changes(user=user)
    history_payload = [_serialize_affiliation_change(change) for change in history_rows]

    # -----------------------------------------------------------------------------
    # 5) 관리 가능한 그룹 구성
    # -----------------------------------------------------------------------------
    manageable_groups = get_manageable_groups_with_members(user=user)

    # -----------------------------------------------------------------------------
    # 6) 메일함 접근 요약 구성
    # -----------------------------------------------------------------------------
    mailbox_rows = email_services.get_mailbox_access_summary_for_user(user=user)
    access_map = {entry["userSdwtProd"]: entry for entry in access_list}
    is_privileged = _is_privileged_user(user)

    mailbox_payload: list[dict[str, object]] = []
    for mailbox in mailbox_rows:
        user_sdwt_prod = mailbox.get("userSdwtProd")
        access = access_map.get(user_sdwt_prod)
        if access is None and is_privileged:
            access_source = "privileged"
            role = "manager"
            granted_by = None
            granted_at = None
        else:
            access_source = access.get("source") if access else "unknown"
            role = access.get("role") if access else mailbox.get("role") or "viewer"
            granted_by = access.get("grantedBy") if access else None
            granted_at = access.get("grantedAt") if access else None

        mailbox_payload.append(
            {
                **mailbox,
                "accessSource": access_source,
                "role": role,
                "grantedBy": granted_by,
                "grantedAt": granted_at,
            }
        )

    # -----------------------------------------------------------------------------
    # 7) 최종 응답 반환
    # -----------------------------------------------------------------------------
    return {
        "user": profile,
        "affiliation": affiliation_payload,
        "affiliationReconfirm": get_affiliation_reconfirm_status(user=user),
        "affiliationHistory": history_payload,
        "manageableGroups": manageable_groups,
        "mailboxAccess": mailbox_payload,
    }
