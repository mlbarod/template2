# =============================================================================
# 모듈 설명: account 도메인의 읽기 전용 셀렉터를 제공합니다.
# - 주요 대상: 소속/권한/변경 요청 조회 함수
# - 불변 조건: 모든 조회는 부작용 없는 ORM 읽기만 수행합니다.
# =============================================================================

"""계정 도메인의 읽기 전용 셀렉터 모음.

- 주요 대상: 소속/권한/변경 요청 조회 함수
- 주요 엔드포인트/클래스: 없음(셀렉터 함수 제공)
- 가정/불변 조건: 모든 조회는 부작용 없는 ORM 읽기만 수행함
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from api.common.services import UNKNOWN, UNCLASSIFIED_USER_SDWT_PROD

from .models import (
    Affiliation,
    ExternalAffiliationSnapshot,
    UserProfile,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)


def get_accessible_user_sdwt_prods_for_user(user: Any) -> set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 값 집합을 조회합니다.

    입력:
    - user: Django 사용자 객체(비인증 가능)

    반환:
    - set[str]: 접근 가능한 user_sdwt_prod 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 인증 여부 확인
    # -----------------------------------------------------------------------------
    if not user or not getattr(user, "is_authenticated", False):
        return set()

    # -----------------------------------------------------------------------------
    # 2) 슈퍼유저는 전체 집합 반환
    # -----------------------------------------------------------------------------
    if getattr(user, "is_superuser", False):
        UserModel = get_user_model()
        values = set(list_distinct_user_sdwt_prod_values())
        values.update(
            UserModel.objects.exclude(user_sdwt_prod__isnull=True)
            .exclude(user_sdwt_prod="")
            .values_list("user_sdwt_prod", flat=True)
            .distinct()
        )
        return {val.strip() for val in values if isinstance(val, str) and val.strip()}

    # -----------------------------------------------------------------------------
    # 3) 접근 권한 및 본인 소속 포함
    # -----------------------------------------------------------------------------
    values = set(
        UserSdwtProdAccess.objects.filter(user=user).values_list("user_sdwt_prod", flat=True)
    )

    user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        values.add(user_sdwt_prod)
    else:
        # -----------------------------------------------------------------------------
        # 4) 초기 소속이 없으면 대기 변경 대상 포함
        # -----------------------------------------------------------------------------
        pending_change = get_pending_user_sdwt_prod_change(user=user)
        pending_user_sdwt_prod = getattr(pending_change, "to_user_sdwt_prod", None)
        if isinstance(pending_user_sdwt_prod, str) and pending_user_sdwt_prod.strip():
            values.add(pending_user_sdwt_prod.strip())

    # -----------------------------------------------------------------------------
    # 5) 최종 정제 및 반환
    # -----------------------------------------------------------------------------
    return {val for val in values if isinstance(val, str) and val.strip()}


def list_distinct_user_sdwt_prod_values() -> set[str]:
    """시스템에 등록된 user_sdwt_prod 값 집합을 조회합니다.

    입력:
    - 없음

    반환:
    - set[str]: 중복 제거된 user_sdwt_prod 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    affiliation_values = set(
        Affiliation.objects.exclude(user_sdwt_prod="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
    )
    access_values = set(
        UserSdwtProdAccess.objects.exclude(user_sdwt_prod="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
    )

    combined = affiliation_values | access_values
    return {val.strip() for val in combined if isinstance(val, str) and val.strip()}


def list_affiliation_options() -> list[dict[str, str]]:
    """소속 선택 옵션(부서/라인/user_sdwt_prod) 전체를 조회합니다.

    입력:
    - 없음

    반환:
    - list[dict[str, str]]: 소속 옵션 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return list(
        Affiliation.objects.all()
        .order_by("department", "line", "user_sdwt_prod")
        .values("department", "line", "user_sdwt_prod")
    )


def get_existing_affiliation_user_sdwt_prods(*, user_sdwt_prods: list[str]) -> set[str]:
    """user_sdwt_prod 목록 중 기존 소속에 존재하는 값을 세트로 반환합니다.

    입력:
    - user_sdwt_prods: 소속 식별자 목록

    반환:
    - set[str]: 존재하는 user_sdwt_prod 값 세트

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized = [value.strip() for value in user_sdwt_prods if isinstance(value, str) and value.strip()]
    if not normalized:
        return set()

    # -----------------------------------------------------------------------------
    # 2) 기존 소속 조회
    # -----------------------------------------------------------------------------
    rows = Affiliation.objects.filter(user_sdwt_prod__in=normalized).values_list("user_sdwt_prod", flat=True)
    return {value for value in rows if isinstance(value, str) and value.strip()}


def affiliation_exists_for_user_sdwt_prod(*, user_sdwt_prod: str) -> bool:
    """user_sdwt_prod에 대응하는 Affiliation 존재 여부를 확인합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - bool: 존재 여부

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    if not isinstance(user_sdwt_prod, str) or not user_sdwt_prod.strip():
        return False
    # -----------------------------------------------------------------------------
    # 2) 존재 여부 조회
    # -----------------------------------------------------------------------------
    return Affiliation.objects.filter(user_sdwt_prod=user_sdwt_prod.strip()).exists()


def list_user_sdwt_prod_access_rows(*, user: Any) -> list[UserSdwtProdAccess]:
    """사용자의 접근 권한(UserSdwtProdAccess) 행 목록을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - list[UserSdwtProdAccess]: 접근 권한 행 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return list(
        UserSdwtProdAccess.objects.filter(user=user).order_by("user_sdwt_prod", "id")
    )


def get_user_profile_role(*, user: Any) -> str:
    """사용자 프로필(role) 값을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - str: 역할 문자열(없으면 viewer)

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 유효성 확인
    # -----------------------------------------------------------------------------
    if not user:
        return UserProfile.Roles.VIEWER

    # -----------------------------------------------------------------------------
    # 2) 프로필 조회
    # -----------------------------------------------------------------------------
    profile = UserProfile.objects.filter(user=user).only("role").first()
    if profile is None:
        return UserProfile.Roles.VIEWER
    return profile.role or UserProfile.Roles.VIEWER


def get_user_profile_by_user(*, user: Any) -> UserProfile | None:
    """사용자 프로필(UserProfile) 행을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserProfile | None: 프로필 행 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 유효성 확인
    # -----------------------------------------------------------------------------
    if not user:
        return None

    # -----------------------------------------------------------------------------
    # 2) 프로필 조회
    # -----------------------------------------------------------------------------
    return UserProfile.objects.filter(user=user).first()


def list_user_sdwt_prod_changes(
    *, user: Any, limit: int = 50
) -> list[UserSdwtProdChange]:
    """사용자의 user_sdwt_prod 변경 히스토리를 최신순으로 반환합니다.

    입력:
    - user: Django 사용자 객체
    - limit: 최대 반환 개수

    반환:
    - list[UserSdwtProdChange]: 변경 이력 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 유효성 확인
    # -----------------------------------------------------------------------------
    if not user:
        return []

    # -----------------------------------------------------------------------------
    # 2) 조회 개수 보정 및 조회
    # -----------------------------------------------------------------------------
    normalized_limit = max(1, int(limit or 50))
    return list(
        UserSdwtProdChange.objects.filter(user=user)
        .select_related("approved_by", "created_by")
        .order_by("-effective_from", "-id")[:normalized_limit]
    )


def user_has_manage_permission(*, user: Any, user_sdwt_prod: str) -> bool:
    """사용자가 특정 user_sdwt_prod 그룹을 관리할 권한이 있는지 확인합니다.

    입력:
    - user: Django 사용자 객체
    - user_sdwt_prod: 소속 식별자

    반환:
    - bool: 관리 권한 여부

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return UserSdwtProdAccess.objects.filter(
        user=user,
        user_sdwt_prod=user_sdwt_prod,
        role=UserSdwtProdAccess.Roles.MANAGER,
    ).exists()


def get_user_by_id(*, user_id: int) -> Any | None:
    """id로 사용자를 조회하고 없으면 None을 반환합니다.

    입력:
    - user_id: 사용자 id

    반환:
    - Any | None: 사용자 객체 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 조회 시도
    # -----------------------------------------------------------------------------
    UserModel = get_user_model()
    try:
        return UserModel.objects.get(id=user_id)
    except UserModel.DoesNotExist:
        # -----------------------------------------------------------------------------
        # 2) 미존재 처리
        # -----------------------------------------------------------------------------
        return None


def get_user_by_knox_id(*, knox_id: str) -> Any | None:
    """knox_id로 사용자를 조회하고 없으면 None을 반환합니다.

    입력:
    - knox_id: 사용자 knox_id

    반환:
    - Any | None: 사용자 객체 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    if not isinstance(knox_id, str) or not knox_id.strip():
        return None

    UserModel = get_user_model()
    if not hasattr(UserModel, "knox_id"):
        return None

    # -----------------------------------------------------------------------------
    # 2) 사용자 조회
    # -----------------------------------------------------------------------------
    return UserModel.objects.filter(knox_id=knox_id.strip()).first()


def get_users_by_knox_ids(*, knox_ids: list[str]) -> dict[str, Any]:
    """knox_id 목록으로 사용자 매핑을 조회합니다.

    입력:
    - knox_ids: knox_id 목록

    반환:
    - dict[str, Any]: knox_id → 사용자 객체 매핑

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized_ids = [value.strip() for value in knox_ids if isinstance(value, str) and value.strip()]
    if not normalized_ids:
        return {}

    UserModel = get_user_model()
    if not hasattr(UserModel, "knox_id"):
        return {}

    # -----------------------------------------------------------------------------
    # 2) 사용자 조회 및 매핑
    # -----------------------------------------------------------------------------
    users = UserModel.objects.filter(knox_id__in=normalized_ids)
    mapped: dict[str, Any] = {}
    for user in users:
        knox_id = getattr(user, "knox_id", None)
        if isinstance(knox_id, str) and knox_id.strip():
            mapped[knox_id.strip()] = user
    return mapped


def get_user_sdwt_prod_change_by_id(*, change_id: int) -> UserSdwtProdChange | None:
    """id로 UserSdwtProdChange를 조회하고 없으면 None을 반환합니다.

    입력:
    - change_id: 변경 요청 id

    반환:
    - UserSdwtProdChange | None: 변경 요청 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 변경 요청 조회 시도
    # -----------------------------------------------------------------------------
    try:
        return UserSdwtProdChange.objects.select_related("user").get(id=change_id)
    except UserSdwtProdChange.DoesNotExist:
        # -----------------------------------------------------------------------------
        # 2) 미존재 처리
        # -----------------------------------------------------------------------------
        return None


def get_external_affiliation_snapshot_by_knox_id(
    *,
    knox_id: str,
) -> ExternalAffiliationSnapshot | None:
    """knox_id로 외부 예측 소속 스냅샷을 조회합니다.

    입력:
    - knox_id: 사용자 knox_id

    반환:
    - ExternalAffiliationSnapshot | None: 스냅샷 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    if not isinstance(knox_id, str) or not knox_id.strip():
        return None

    # -----------------------------------------------------------------------------
    # 2) 스냅샷 조회
    # -----------------------------------------------------------------------------
    return ExternalAffiliationSnapshot.objects.filter(knox_id=knox_id.strip()).first()


def get_external_affiliation_snapshots_by_knox_ids(
    *,
    knox_ids: list[str],
) -> dict[str, ExternalAffiliationSnapshot]:
    """knox_id 목록으로 외부 예측 소속 스냅샷을 조회해 dict로 반환합니다.

    입력:
    - knox_ids: knox_id 목록

    반환:
    - dict[str, ExternalAffiliationSnapshot]: knox_id → 스냅샷 매핑

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized_ids = [value.strip() for value in knox_ids if isinstance(value, str) and value.strip()]
    if not normalized_ids:
        return {}

    # -----------------------------------------------------------------------------
    # 2) 스냅샷 조회 및 매핑
    # -----------------------------------------------------------------------------
    return ExternalAffiliationSnapshot.objects.in_bulk(normalized_ids, field_name="knox_id")


def get_current_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """현재 user_sdwt_prod에 해당하는 승인 변경 이력을 반환합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserSdwtProdChange | None: 승인된 변경 이력 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 및 현재 소속 확인
    # -----------------------------------------------------------------------------
    if not user:
        return None

    current_user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if not isinstance(current_user_sdwt_prod, str) or not current_user_sdwt_prod.strip():
        return None

    # -----------------------------------------------------------------------------
    # 2) 승인된 변경 이력 조회
    # -----------------------------------------------------------------------------
    normalized = current_user_sdwt_prod.strip()
    return (
        UserSdwtProdChange.objects.filter(user=user, to_user_sdwt_prod=normalized)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("-effective_from", "-id")
        .first()
    )


def get_pending_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """현재 사용자의 PENDING 상태 변경 요청을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserSdwtProdChange | None: 대기 변경 요청 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 유효성 확인
    # -----------------------------------------------------------------------------
    if not user:
        return None

    # -----------------------------------------------------------------------------
    # 2) 대기 상태 조회
    # -----------------------------------------------------------------------------
    return (
        UserSdwtProdChange.objects.filter(user=user)
        .filter(
            Q(status=UserSdwtProdChange.Status.PENDING)
            | Q(status__isnull=True, approved=False, applied=False)
        )
        .order_by("-created_at", "-id")
        .first()
    )


def get_pending_user_sdwt_prod_changes_by_user_ids(*, user_ids: list[int]) -> set[int]:
    """사용자 id 목록에 대한 PENDING 변경 요청 존재 여부를 조회합니다.

    입력:
    - user_ids: 사용자 id 목록

    반환:
    - set[int]: 대기 변경 요청이 존재하는 사용자 id 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized = [value for value in user_ids if isinstance(value, int)]
    if not normalized:
        return set()

    # -----------------------------------------------------------------------------
    # 2) 대기 요청 사용자 id 조회
    # -----------------------------------------------------------------------------
    rows = (
        UserSdwtProdChange.objects.filter(user_id__in=normalized)
        .filter(
            Q(status=UserSdwtProdChange.Status.PENDING)
            | Q(status__isnull=True, approved=False, applied=False)
        )
        .values_list("user_id", flat=True)
    )
    return {value for value in rows if isinstance(value, int)}


def get_access_row_for_user_and_prod(
    *,
    user: Any,
    user_sdwt_prod: str,
) -> UserSdwtProdAccess | None:
    """(user, user_sdwt_prod)에 대한 접근 권한 행을 조회합니다.

    입력:
    - user: Django 사용자 객체
    - user_sdwt_prod: 소속 식별자

    반환:
    - UserSdwtProdAccess | None: 접근 권한 행 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return (
        UserSdwtProdAccess.objects.filter(user=user, user_sdwt_prod=user_sdwt_prod)
        .select_related("user")
        .first()
    )


def other_manager_exists(
    *,
    user_sdwt_prod: str,
    exclude_user: Any,
) -> bool:
    """그룹에 현재 사용자 외 다른 관리자(role=manager)가 존재하는지 확인합니다.

    입력:
    - user_sdwt_prod: 소속 식별자
    - exclude_user: 제외할 사용자

    반환:
    - bool: 다른 관리자 존재 여부

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return (
        UserSdwtProdAccess.objects.filter(
            user_sdwt_prod=user_sdwt_prod,
            role=UserSdwtProdAccess.Roles.MANAGER,
        )
        .exclude(user=exclude_user)
        .exists()
    )


def list_manageable_user_sdwt_prod_values(*, user: Any) -> set[str]:
    """사용자가 관리(role=manager)할 수 있는 user_sdwt_prod 값 집합을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - set[str]: 관리 가능한 user_sdwt_prod 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    values = set(
        UserSdwtProdAccess.objects.filter(
            user=user,
            role=UserSdwtProdAccess.Roles.MANAGER,
        ).values_list(
            "user_sdwt_prod",
            flat=True,
        )
    )
    return {val for val in values if isinstance(val, str) and val.strip()}


def list_approvable_user_sdwt_prod_values(*, user: Any) -> set[str]:
    """사용자가 승인(role=member/manager)할 수 있는 user_sdwt_prod 값 집합을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - set[str]: 승인 가능한 user_sdwt_prod 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    values = set(
        UserSdwtProdAccess.objects.filter(
            user=user,
            role__in=[UserSdwtProdAccess.Roles.MEMBER, UserSdwtProdAccess.Roles.MANAGER],
        ).values_list(
            "user_sdwt_prod",
            flat=True,
        )
    )
    return {val for val in values if isinstance(val, str) and val.strip()}


def has_approver_for_user_sdwt_prod(*, user_sdwt_prod: str) -> bool:
    """특정 소속에 승인(role=member/manager) 가능한 사용자가 존재하는지 확인합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - bool: 승인 가능 사용자 존재 여부

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized = (user_sdwt_prod or "").strip()
    if not normalized:
        return False

    return UserSdwtProdAccess.objects.filter(
        user_sdwt_prod=normalized,
        role__in=[UserSdwtProdAccess.Roles.MEMBER, UserSdwtProdAccess.Roles.MANAGER],
    ).exists()


def list_affiliation_change_requests(
    *,
    allowed_user_sdwt_prods: set[str] | None,
    status: str | None,
    search: str | None,
    user_sdwt_prod: str | None,
) -> QuerySet[UserSdwtProdChange]:
    """승인 대상 소속 변경 요청 목록을 필터링하여 조회합니다.

    입력:
    - allowed_user_sdwt_prods: 조회 가능한 user_sdwt_prod 집합(None이면 전체)
    - status: 상태 필터(PENDING/APPROVED/REJECTED/SUPERSEDED)
    - search: 사용자 정보 검색어
    - user_sdwt_prod: to_user_sdwt_prod 필터

    반환:
    - QuerySet[UserSdwtProdChange]: 필터링된 변경 요청 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 쿼리셋(QuerySet) 준비
    # -----------------------------------------------------------------------------
    qs = UserSdwtProdChange.objects.select_related("user", "created_by", "approved_by")

    # -----------------------------------------------------------------------------
    # 2) 조회 가능 범위 필터
    # -----------------------------------------------------------------------------
    if allowed_user_sdwt_prods is not None:
        if not allowed_user_sdwt_prods:
            return UserSdwtProdChange.objects.none()
        qs = qs.filter(to_user_sdwt_prod__in=allowed_user_sdwt_prods)

    # -----------------------------------------------------------------------------
    # 3) 상태 필터
    # -----------------------------------------------------------------------------
    if isinstance(status, str) and status.strip():
        normalized_status = status.strip().upper()
        if normalized_status == UserSdwtProdChange.Status.PENDING:
            qs = qs.filter(
                Q(status=UserSdwtProdChange.Status.PENDING)
                | Q(status__isnull=True, approved=False, applied=False)
            )
        elif normalized_status == UserSdwtProdChange.Status.APPROVED:
            qs = qs.filter(
                Q(status=UserSdwtProdChange.Status.APPROVED)
                | Q(approved=True)
                | Q(applied=True)
            )
        elif normalized_status == UserSdwtProdChange.Status.REJECTED:
            qs = qs.filter(
                status__in=[
                    UserSdwtProdChange.Status.REJECTED,
                    UserSdwtProdChange.Status.SUPERSEDED,
                ]
            )
        elif normalized_status == UserSdwtProdChange.Status.SUPERSEDED:
            qs = qs.filter(status=UserSdwtProdChange.Status.SUPERSEDED)

    # -----------------------------------------------------------------------------
    # 4) 소속 필터
    # -----------------------------------------------------------------------------
    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        qs = qs.filter(to_user_sdwt_prod=user_sdwt_prod.strip())

    # -----------------------------------------------------------------------------
    # 5) 검색어 필터
    # -----------------------------------------------------------------------------
    if isinstance(search, str) and search.strip():
        keyword = search.strip()
        qs = qs.filter(
            Q(user__username__icontains=keyword)
            | Q(user__email__icontains=keyword)
            | Q(user__sabun__icontains=keyword)
            | Q(user__knox_id__icontains=keyword)
            | Q(user__givenname__icontains=keyword)
            | Q(user__surname__icontains=keyword)
        )

    # -----------------------------------------------------------------------------
    # 6) 정렬 및 반환
    # -----------------------------------------------------------------------------
    return qs.order_by("-created_at", "-id")


def list_group_members(*, user_sdwt_prods: set[str]) -> QuerySet[UserSdwtProdAccess]:
    """지정한 user_sdwt_prods 그룹에 속한 멤버 접근 권한 행을 조회합니다.

    입력:
    - user_sdwt_prods: 소속 식별자 집합

    반환:
    - QuerySet[UserSdwtProdAccess]: 멤버 접근 권한 행 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return (
        UserSdwtProdAccess.objects.filter(user_sdwt_prod__in=user_sdwt_prods)
        .select_related("user")
        .order_by("user_sdwt_prod", "user_id")
    )


def list_line_sdwt_pairs() -> list[dict[str, str]]:
    """선택 가능한 (line_id, user_sdwt_prod) 쌍 목록을 조회합니다.

    입력:
    - 없음

    반환:
    - list[dict[str, str]]: line_id/user_sdwt_prod 쌍 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 라인/소속 값 조회 및 정제
    # -----------------------------------------------------------------------------
    pairs = (
        Affiliation.objects.filter(line__isnull=False)
        .exclude(line__exact="")
        .exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .values("line", "user_sdwt_prod")
        .distinct()
        .order_by("line", "user_sdwt_prod")
    )
    # -----------------------------------------------------------------------------
    # 2) 응답 형식 변환
    # -----------------------------------------------------------------------------
    return [{"line_id": row["line"], "user_sdwt_prod": row["user_sdwt_prod"]} for row in pairs]


def get_next_user_sdwt_prod_change(
    *,
    user: Any,
    effective_from: datetime,
) -> UserSdwtProdChange | None:
    """effective_from 이후 예정된 다음 소속 변경을 조회합니다.

    입력:
    - user: Django 사용자 객체
    - effective_from: 기준 시각

    반환:
    - UserSdwtProdChange | None: 다음 변경 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기준 시각 보정
    # -----------------------------------------------------------------------------
    if effective_from is None:
        effective_from = timezone.now()
    if timezone.is_naive(effective_from):
        effective_from = timezone.make_aware(effective_from, timezone.utc)

    # -----------------------------------------------------------------------------
    # 2) 다음 승인 변경 조회
    # -----------------------------------------------------------------------------
    return (
        UserSdwtProdChange.objects.filter(user=user, effective_from__gt=effective_from)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("effective_from", "id")
        .first()
    )


def resolve_user_affiliation(user: Any, at_time: datetime | None) -> dict[str, str]:
    """지정 시점의 사용자 소속 스냅샷을 계산합니다.

    입력:
    - user: Django 사용자 객체
    - at_time: 기준 시각(없으면 현재 시각)

    반환:
    - dict[str, str]: 부서/라인/user_sdwt_prod 스냅샷

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기준 시각 보정
    # -----------------------------------------------------------------------------
    if at_time is None:
        at_time = timezone.now()
    if timezone.is_naive(at_time):
        at_time = timezone.make_aware(at_time, timezone.utc)

    # -----------------------------------------------------------------------------
    # 2) 기준 시각까지 승인된 변경 조회
    # -----------------------------------------------------------------------------
    change = (
        UserSdwtProdChange.objects.filter(user=user, effective_from__lte=at_time)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("-effective_from", "-id")
        .first()
    )

    # -----------------------------------------------------------------------------
    # 3) 변경 이력이 있으면 해당 스냅샷 반환
    # -----------------------------------------------------------------------------
    if change:
        return {
            "department": change.department or getattr(user, "department", None) or UNKNOWN,
            "line": change.line or getattr(user, "line", None) or "",
            "user_sdwt_prod": change.to_user_sdwt_prod
            or getattr(user, "user_sdwt_prod", None)
            or UNCLASSIFIED_USER_SDWT_PROD,
        }

    # -----------------------------------------------------------------------------
    # 4) 다음 변경이 있는 경우 이전 소속 추정
    # -----------------------------------------------------------------------------
    next_change = (
        UserSdwtProdChange.objects.filter(user=user, effective_from__gt=at_time)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("effective_from", "id")
        .first()
    )

    before_user_sdwt_prod = None
    if next_change:
        before_user_sdwt_prod = next_change.from_user_sdwt_prod

    # -----------------------------------------------------------------------------
    # 5) 기본 스냅샷 반환
    # -----------------------------------------------------------------------------
    return {
        "department": getattr(user, "department", None) or UNKNOWN,
        "line": getattr(user, "line", None) or "",
        "user_sdwt_prod": before_user_sdwt_prod
        or getattr(user, "user_sdwt_prod", None)
        or UNCLASSIFIED_USER_SDWT_PROD,
    }


def get_affiliation_option(
    department: str,
    line: str,
    user_sdwt_prod: str,
) -> Affiliation | None:
    """부서/라인/user_sdwt_prod 조합에 해당하는 소속 옵션 행을 조회합니다.

    입력:
    - department: 부서명
    - line: 라인 식별자
    - user_sdwt_prod: 소속 식별자

    반환:
    - Affiliation | None: 소속 옵션 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    if not department or not line or not user_sdwt_prod:
        return None

    # -----------------------------------------------------------------------------
    # 2) 단일 행 조회
    # -----------------------------------------------------------------------------
    try:
        return Affiliation.objects.get(
            department=department.strip(),
            line=line.strip(),
            user_sdwt_prod=user_sdwt_prod.strip(),
        )
    except Affiliation.DoesNotExist:
        return None


def get_affiliation_option_by_user_sdwt_prod(*, user_sdwt_prod: str) -> Affiliation | None:
    """user_sdwt_prod로 단일 Affiliation 옵션을 조회합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - Affiliation | None: 단일 옵션 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    if not isinstance(user_sdwt_prod, str) or not user_sdwt_prod.strip():
        return None

    # -----------------------------------------------------------------------------
    # 2) 단일 행 여부 확인
    # -----------------------------------------------------------------------------
    normalized = user_sdwt_prod.strip()
    rows = list(Affiliation.objects.filter(user_sdwt_prod=normalized).order_by("id")[:2])
    if len(rows) != 1:
        return None
    return rows[0]
