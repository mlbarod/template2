# =============================================================================
# 모듈 설명: 접근 권한(UserSdwtProdAccess) 서비스 로직을 제공합니다.
# - 주요 대상: ensure_self_access, grant_or_revoke_access, get_manageable_groups_with_members
# - 불변 조건: 권한 부여/회수는 서비스 레이어에서만 처리합니다.
# =============================================================================

"""접근 권한(UserSdwtProdAccess) 관련 서비스 모음.

- 주요 대상: 접근 권한 보장, 부여/회수, 관리 그룹 조회
- 주요 엔드포인트/클래스: ensure_self_access, grant_or_revoke_access 등
- 가정/불변 조건: 권한 부여/회수는 서비스 레이어에서만 처리됨
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..models import UserSdwtProdAccess
from .. import selectors
from .utils import _user_can_manage_user_sdwt_prod


ROLE_ORDER = {
    UserSdwtProdAccess.Roles.VIEWER: 0,
    UserSdwtProdAccess.Roles.MEMBER: 1,
    UserSdwtProdAccess.Roles.MANAGER: 2,
}


def _normalize_access_role(role: str) -> str:
    """접근 권한 역할을 정규화합니다.

    입력:
    - role: viewer/member/manager 중 하나

    반환:
    - str: 정규화된 역할

    부작용:
    - 없음

    오류:
    - 없음
    """

    normalized = (role or "").strip().lower()
    if normalized in ROLE_ORDER:
        return normalized
    return UserSdwtProdAccess.Roles.VIEWER


def _normalize_role_for_current_affiliation(
    *,
    user: Any,
    user_sdwt_prod: str,
    role: str,
) -> str:
    """현재 소속에 대한 viewer 요청을 member로 승급합니다.

    입력:
    - user: Django 사용자 객체
    - user_sdwt_prod: 대상 소속
    - role: 요청 역할(viewer/member/manager)

    반환:
    - str: 정규화된 역할

    부작용:
    - 없음

    오류:
    - 없음
    """

    normalized_role = _normalize_access_role(role)
    current_user_sdwt = (getattr(user, "user_sdwt_prod", None) or "").strip()
    target_user_sdwt = (user_sdwt_prod or "").strip()
    if current_user_sdwt and target_user_sdwt and current_user_sdwt == target_user_sdwt:
        if normalized_role == UserSdwtProdAccess.Roles.VIEWER:
            return UserSdwtProdAccess.Roles.MEMBER
    return normalized_role


def _should_upgrade_role(current_role: str, target_role: str) -> bool:
    """현재 역할에서 목표 역할로 상향이 필요한지 확인합니다."""

    current_rank = ROLE_ORDER.get(current_role, 0)
    target_rank = ROLE_ORDER.get(target_role, 0)
    return target_rank > current_rank


def ensure_self_access(user: Any, *, role: str = UserSdwtProdAccess.Roles.MEMBER) -> UserSdwtProdAccess | None:
    """사용자 본인의 user_sdwt_prod 접근 권한 행을 보장합니다.

    입력:
    - user: Django 사용자 객체
    - role: 부여할 역할(viewer/member/manager)

    반환:
    - UserSdwtProdAccess | None: 접근 권한 행 또는 None

    부작용:
    - UserSdwtProdAccess 생성/업데이트

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 현재 소속 유효성 확인
    # -----------------------------------------------------------------------------
    user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if not isinstance(user_sdwt_prod, str) or not user_sdwt_prod.strip():
        return None

    # -----------------------------------------------------------------------------
    # 2) 접근 권한 행 생성/업데이트
    # -----------------------------------------------------------------------------
    normalized_role = _normalize_role_for_current_affiliation(
        user=user,
        user_sdwt_prod=user_sdwt_prod,
        role=role,
    )

    access, created = UserSdwtProdAccess.objects.get_or_create(
        user=user,
        user_sdwt_prod=user_sdwt_prod,
        defaults={"role": normalized_role, "granted_by": None},
    )
    if not created and _should_upgrade_role(access.role, normalized_role):
        access.role = normalized_role
        access.save(update_fields=["role"])
    return access


def downgrade_member_access(*, user: Any, user_sdwt_prod: str) -> None:
    """특정 소속의 member 역할을 viewer로 강등합니다.

    입력:
    - user: Django 사용자 객체
    - user_sdwt_prod: 대상 소속

    반환:
    - 없음

    부작용:
    - UserSdwtProdAccess role 업데이트

    오류:
    - 없음
    """

    access = selectors.get_access_row_for_user_and_prod(user=user, user_sdwt_prod=user_sdwt_prod)
    if access and access.role == UserSdwtProdAccess.Roles.MEMBER:
        access.role = UserSdwtProdAccess.Roles.VIEWER
        access.save(update_fields=["role"])


def grant_or_revoke_access(
    *,
    grantor: Any,
    target_group: str,
    target_user: Any,
    action: str,
    role: str | None,
) -> tuple[dict[str, object], int]:
    """사용자의 user_sdwt_prod 그룹 접근 권한을 부여/회수합니다.

    입력:
    - grantor: 권한을 부여/회수하는 사용자
    - target_group: 대상 그룹
    - target_user: 대상 사용자
    - action: grant/revoke (부여/회수)
    - role: 부여할 역할(viewer/member/manager)

    반환:
    - tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - UserSdwtProdAccess 생성/업데이트/삭제

    오류:
    - 403: 권한 없음
    - 400: 마지막 관리자 제거 시도
    """

    # -----------------------------------------------------------------------------
    # 1) 부여자 기본 접근 권한 보장
    # -----------------------------------------------------------------------------
    ensure_self_access(grantor, role=UserSdwtProdAccess.Roles.MEMBER)

    # -----------------------------------------------------------------------------
    # 2) 권한 검증
    # -----------------------------------------------------------------------------
    if not _user_can_manage_user_sdwt_prod(user=grantor, user_sdwt_prod=target_group):
        return {"error": "forbidden"}, 403

    # -----------------------------------------------------------------------------
    # 3) 액션 분기 처리
    # -----------------------------------------------------------------------------
    normalized_action = (action or "grant").lower()
    if normalized_action == "revoke":
        current_target_sdwt = (getattr(target_user, "user_sdwt_prod", None) or "").strip()
        if current_target_sdwt and current_target_sdwt == target_group:
            return {"error": "Cannot revoke access for the user's current affiliation"}, 400
        access = selectors.get_access_row_for_user_and_prod(
            user=target_user,
            user_sdwt_prod=target_group,
        )
        if not access:
            return {"status": "ok", "deleted": 0}, 200

        if access.role == UserSdwtProdAccess.Roles.MANAGER:
            if not selectors.other_manager_exists(
                user_sdwt_prod=target_group,
                exclude_user=target_user,
            ):
                return {"error": "Cannot remove the last manager for this group"}, 400

        access.delete()
        return {"status": "ok", "deleted": 1}, 200

    # -----------------------------------------------------------------------------
    # 4) 부여 처리
    # -----------------------------------------------------------------------------
    normalized_role = _normalize_role_for_current_affiliation(
        user=target_user,
        user_sdwt_prod=target_group,
        role=role or UserSdwtProdAccess.Roles.VIEWER,
    )
    access, created = UserSdwtProdAccess.objects.get_or_create(
        user=target_user,
        user_sdwt_prod=target_group,
        defaults={"role": normalized_role, "granted_by": grantor},
    )
    if not created and (access.role != normalized_role or access.granted_by_id != grantor.id):
        access.role = normalized_role
        access.granted_by = grantor
        access.save(update_fields=["role", "granted_by"])

    # -----------------------------------------------------------------------------
    # 5) 결과 반환
    # -----------------------------------------------------------------------------
    return _serialize_member(access), 200


def get_manageable_groups_with_members(*, user: Any) -> dict[str, object]:
    """사용자가 관리 가능한 그룹과 멤버 목록을 반환합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - dict[str, object]: 그룹/멤버 목록

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 관리 가능한 그룹 집합 계산
    # -----------------------------------------------------------------------------
    manageable_set = selectors.list_manageable_user_sdwt_prod_values(user=user)

    groups: List[Dict[str, object]] = []
    if not manageable_set:
        return {"groups": groups}

    # -----------------------------------------------------------------------------
    # 2) 멤버 목록 구성
    # -----------------------------------------------------------------------------
    members_by_group: Dict[str, List[Dict[str, object]]] = {prod: [] for prod in manageable_set}
    for access in selectors.list_group_members(user_sdwt_prods=manageable_set):
        members_by_group.setdefault(access.user_sdwt_prod, []).append(_serialize_member(access))

    # -----------------------------------------------------------------------------
    # 3) 응답 정렬 및 반환
    # -----------------------------------------------------------------------------
    for prod in sorted(manageable_set):
        groups.append({"userSdwtProd": prod, "members": members_by_group.get(prod, [])})

    return {"groups": groups}


def _serialize_access(access: UserSdwtProdAccess, source: str) -> Dict[str, object]:
    """UserSdwtProdAccess 행을 API 응답용 dict로 직렬화합니다.

    입력:
    - access: 접근 권한 행
    - source: 권한 출처 문자열

    반환:
    - Dict[str, object]: 직렬화 결과

    부작용:
    - 없음

    오류:
    - 없음
    """

    return {
        "userSdwtProd": access.user_sdwt_prod,
        "role": access.role,
        "source": source,
        "grantedBy": access.granted_by_id,
        "grantedAt": access.created_at.isoformat(),
    }


def _serialize_access_fallback(
    *,
    user_sdwt_prod: str,
    source: str,
    role: str,
) -> Dict[str, object]:
    """DB row가 없는 경우를 위한 접근 권한 기본값을 생성합니다.

    입력:
    - user_sdwt_prod: 소속 식별자
    - source: 권한 출처 문자열

    반환:
    - Dict[str, object]: 기본값 응답

    부작용:
    - 없음

    오류:
    - 없음
    """

    return {
        "userSdwtProd": user_sdwt_prod,
        "role": role,
        "source": source,
        "grantedBy": None,
        "grantedAt": None,
    }


def _serialize_member(access: UserSdwtProdAccess) -> Dict[str, object]:
    """그룹 멤버(access + user)를 API 응답용 dict로 직렬화합니다.

    입력:
    - access: 접근 권한 행

    반환:
    - Dict[str, object]: 멤버 응답

    부작용:
    - 없음

    오류:
    - 없음
    """

    user = access.user
    return {
        "userId": user.id,
        "username": user.username,
        "name": (user.first_name or "") + (user.last_name or ""),
        "knoxId": getattr(user, "knox_id", None),
        "userSdwtProd": access.user_sdwt_prod,
        "role": access.role,
        "grantedBy": access.granted_by_id,
        "grantedAt": access.created_at.isoformat(),
    }


def _current_access_list(user: Any) -> List[Dict[str, object]]:
    """현재 사용자 기준 접근 가능한 그룹 목록을 구성합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - List[Dict[str, object]]: 접근 가능한 그룹 목록

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 접근 권한 행 조회
    # -----------------------------------------------------------------------------
    rows = selectors.list_user_sdwt_prod_access_rows(user=user)
    access_map = {row.user_sdwt_prod: row for row in rows}

    # -----------------------------------------------------------------------------
    # 2) 현재 소속 포함
    # -----------------------------------------------------------------------------
    current_user_sdwt = getattr(user, "user_sdwt_prod", None)
    if isinstance(current_user_sdwt, str) and current_user_sdwt.strip():
        access_map.setdefault(current_user_sdwt, None)

    # -----------------------------------------------------------------------------
    # 3) 응답 목록 구성
    # -----------------------------------------------------------------------------
    result: List[Dict[str, object]] = []
    for prod, entry in sorted(access_map.items()):
        source = "self" if prod == current_user_sdwt else "grant"
        if entry is None:
            fallback_role = (
                UserSdwtProdAccess.Roles.MEMBER
                if prod == current_user_sdwt
                else UserSdwtProdAccess.Roles.VIEWER
            )
            result.append(
                _serialize_access_fallback(
                    user_sdwt_prod=prod,
                    source=source,
                    role=fallback_role,
                )
            )
        else:
            result.append(_serialize_access(entry, source))
    return result
