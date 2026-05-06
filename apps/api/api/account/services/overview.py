# =============================================================================
# 모듈 설명: 계정 화면 개요 데이터를 구성하는 서비스를 제공합니다.
# - 주요 대상: get_account_overview
# - 불변 조건: account 도메인의 사용자/소속/권한 정보만 구성합니다.
# =============================================================================

"""계정 화면 개요 데이터를 구성하는 서비스 모음.

- 주요 대상: 사용자 프로필, 소속 요약, 소속 변경 이력, 관리 그룹
- 주요 엔드포인트/클래스: 없음(서비스 함수 제공)
- 가정/불변 조건: 메일함/이메일 정보는 emails 도메인에서 제공합니다.
"""
from __future__ import annotations

from typing import Any

from .. import selectors
from .access import _current_access_list, get_manageable_groups_with_members
from .affiliation_requests import _serialize_affiliation_change
from .affiliations import get_affiliation_reconfirm_status


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
    current_values = selectors.get_current_affiliation_values(user=user)
    profile = {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "knoxId": getattr(user, "knox_id", None),
        "userSdwtProd": current_values.get("user_sdwt_prod"),
        "role": selectors.get_user_profile_role(user=user),
        "isSuperuser": bool(getattr(user, "is_superuser", False)),
        "isStaff": bool(getattr(user, "is_staff", False)),
    }

    # -----------------------------------------------------------------------------
    # 3) 소속 요약 정보 구성
    # -----------------------------------------------------------------------------
    current_department = current_values.get("department") or getattr(user, "department", None)
    affiliation_payload = {
        "currentUserSdwtProd": current_values.get("user_sdwt_prod"),
        "currentDepartment": current_department,
        "currentLine": current_values.get("line"),
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
    # 6) 최종 응답 반환
    # -----------------------------------------------------------------------------
    return {
        "user": profile,
        "affiliation": affiliation_payload,
        "affiliationReconfirm": get_affiliation_reconfirm_status(user=user),
        "affiliationHistory": history_payload,
        "manageableGroups": manageable_groups,
    }
