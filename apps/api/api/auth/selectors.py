# =============================================================================
# 모듈 설명: auth 도메인 읽기 전용 셀렉터를 제공합니다.
# - 주요 대상: 사용자 조회, 현재 사용자 응답 payload 조립
# - 불변 조건: 모든 조회는 부작용 없이 수행합니다.
# =============================================================================

"""auth 도메인 읽기 전용 셀렉터 모음.

- 주요 대상: 사용자 조회, 현재 사용자 응답 payload 조립
- 주요 엔드포인트/클래스: 없음(셀렉터 함수만 제공)
- 가정/불변 조건: 읽기 전용 ORM 접근만 수행함
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser

import api.account.selectors as account_selectors
import api.account.services as account_services


# =============================================================================
# 사용자 조회
# =============================================================================


def get_user_by_sabun(*, sabun: str) -> Optional[AbstractBaseUser]:
    """사번으로 사용자 정보를 조회합니다.

    입력:
    - sabun: 사번 문자열

    반환:
    - Optional[AbstractBaseUser]: 사용자 객체 또는 None

    부작용:
    - 없음

    오류:
    - 없음
    """
    # -----------------------------------------------------------------------------
    # 1) 사용자 모델 준비
    # -----------------------------------------------------------------------------
    UserModel = get_user_model()
    # -----------------------------------------------------------------------------
    # 2) 사번으로 단건 조회
    # -----------------------------------------------------------------------------
    return UserModel.objects.filter(sabun=sabun).first()


def get_current_user_payload(*, user: Any) -> Dict[str, Any]:
    """현재 로그인한 사용자 응답 payload를 읽기 전용으로 구성합니다.

    입력:
    - user: 인증된 Django 사용자 객체

    반환:
    - Dict[str, Any]: 기존 `/api/v1/auth/me` 응답 shape

    부작용:
    - 없음

    오류:
    - 없음
    """
    username = user.username if isinstance(getattr(user, "username", None), str) else ""
    pending_change = account_selectors.get_pending_user_sdwt_prod_change(user=user)
    pending_user_sdwt_prod = pending_change.to_user_sdwt_prod if pending_change else None
    has_pending_affiliation = pending_change is not None
    current_values = account_selectors.get_current_affiliation_values(user=user)
    raw_department = getattr(user, "department", None)
    department = raw_department.strip() if isinstance(raw_department, str) else raw_department
    if not department:
        department = current_values.get("department")

    portal_access = account_services.get_portal_access_payload(user=user)
    return {
        "id": user.pk,
        "usr_id": getattr(user, "knox_id", None),
        "avatarid": getattr(user, "avatarid", None),
        "username": username,
        "email": user.email,
        "is_superuser": bool(getattr(user, "is_superuser", False)),
        "is_staff": bool(getattr(user, "is_staff", False)),
        "roles": [],
        "department": department,
        "line": current_values.get("line"),
        "user_sdwt_prod": current_values.get("user_sdwt_prod"),
        "pending_user_sdwt_prod": pending_user_sdwt_prod,
        "has_pending_affiliation": has_pending_affiliation,
        "portal_access": portal_access,
        "app_access": account_services.get_app_access_payloads(
            user=user,
            portal_access=portal_access,
        ),
    }
