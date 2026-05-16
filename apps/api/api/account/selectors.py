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
from typing import Any, Iterable

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.db.models.functions import Lower
from django.utils import timezone

from api.common.services import UNKNOWN, UNCLASSIFIED_USER_SDWT_PROD

from .models import (
    Affiliation,
    ExternalAffiliationSnapshot,
    UserCurrentAffiliation,
    UserProfile,
    UserSdwtProdAccess,
    UserSdwtProdChange,
    _build_user_sdwt_display_map,
    _collapse_user_sdwt_prod_values,
    _normalize_user_sdwt_prod,
)


def _normalize_text(value: Any) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_text_list(values: Iterable[Any]) -> list[str]:
    """문자열 iterable에서 빈 값을 제거한 정규화 목록을 반환합니다."""

    normalized: list[str] = []
    for value in values:
        cleaned = _normalize_text(value)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _normalize_positive_int_set(values: Iterable[Any], *, allow_cast: bool = False) -> set[int]:
    """양의 정수 ID 집합을 중복 없이 정규화합니다."""

    normalized: set[int] = set()
    for value in values:
        if allow_cast:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
        elif isinstance(value, int):
            parsed = value
        else:
            continue
        if parsed > 0:
            normalized.add(parsed)
    return normalized


def _list_active_user_contact_values_by_user_sdwt_prod(
    *,
    user_sdwt_prod: str,
    contact_field: str,
) -> list[str]:
    """소속에 연결된 활성 사용자 연락처 값을 중복 없이 조회합니다."""

    if contact_field not in {"email", "knox_id"}:
        raise ValueError("contact_field must be email or knox_id")

    normalized_user_sdwt_prod = _normalize_text(user_sdwt_prod)
    if not normalized_user_sdwt_prod:
        return []

    User = get_user_model()
    rows = (
        User.objects.filter(
            current_affiliation__affiliation__user_sdwt_prod__iexact=normalized_user_sdwt_prod,
            is_active=True,
        )
        .exclude(**{f"{contact_field}__isnull": True})
        .exclude(**{f"{contact_field}__exact": ""})
        .values_list(contact_field, flat=True)
        .order_by(contact_field)
        .distinct()
    )

    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in rows:
        cleaned = _normalize_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized_values.append(cleaned)
    return normalized_values


def get_current_affiliation_record(*, user: Any) -> UserCurrentAffiliation | None:
    """사용자의 현재 앱 소속 행을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserCurrentAffiliation | None: 현재 소속 행 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    if not user:
        return None

    return (
        UserCurrentAffiliation.objects.filter(user=user)
        .select_related("affiliation")
        .order_by("id")
        .first()
    )


def get_current_affiliation_values(*, user: Any) -> dict[str, Any]:
    """현재 앱 소속 값을 평탄화해 반환합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - dict[str, Any]: affiliation/department/line/user_sdwt_prod/reconfirm 값

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    row = get_current_affiliation_record(user=user)
    affiliation = row.affiliation if row and row.affiliation_id else None
    return {
        "affiliation": affiliation,
        "department": affiliation.department if affiliation else None,
        "line": affiliation.line if affiliation else None,
        "user_sdwt_prod": affiliation.user_sdwt_prod if affiliation else None,
        "requires_reconfirm": bool(row.requires_reconfirm) if row else False,
        "confirmed_at": row.confirmed_at if row else None,
        "source": row.source if row else None,
    }


def get_current_affiliation_values_by_user_ids(*, user_ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    """사용자 id별 현재 앱 소속 값을 평탄화해 반환합니다.

    입력:
    - user_ids: 사용자 id iterable

    반환:
    - dict[int, dict[str, Any]]: user_id → 소속 값 매핑

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_ids = _normalize_positive_int_set(user_ids, allow_cast=True)
    if not normalized_ids:
        return {}

    rows = (
        UserCurrentAffiliation.objects.filter(user_id__in=normalized_ids)
        .select_related("affiliation")
        .order_by("user_id")
    )
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        affiliation = row.affiliation if row.affiliation_id else None
        result[row.user_id] = {
            "department": affiliation.department if affiliation else None,
            "line": affiliation.line if affiliation else None,
            "user_sdwt_prod": affiliation.user_sdwt_prod if affiliation else None,
            "source": row.source,
        }
    return result


def get_current_user_sdwt_prod(*, user: Any) -> str | None:
    """현재 앱 소속의 user_sdwt_prod 값을 반환합니다."""

    values = get_current_affiliation_values(user=user)
    current = values.get("user_sdwt_prod")
    return current if isinstance(current, str) and current.strip() else None


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
        values = set(list_distinct_user_sdwt_prod_values())
        values.update(
            UserCurrentAffiliation.objects.select_related("affiliation")
            .exclude(affiliation__user_sdwt_prod__isnull=True)
            .exclude(affiliation__user_sdwt_prod="")
            .values_list("affiliation__user_sdwt_prod", flat=True)
            .distinct()
        )
        return _collapse_user_sdwt_prod_values(values)

    # -----------------------------------------------------------------------------
    # 3) 접근 권한 및 본인 소속 포함
    # -----------------------------------------------------------------------------
    values = set(
        UserSdwtProdAccess.objects.filter(user=user).values_list(
            "affiliation__user_sdwt_prod",
            flat=True,
        )
    )

    user_sdwt_prod = get_current_user_sdwt_prod(user=user)
    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        values.add(user_sdwt_prod)
    # -----------------------------------------------------------------------------
    # 4) 최종 정제 및 반환
    # -----------------------------------------------------------------------------
    return _collapse_user_sdwt_prod_values(values)


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
        UserSdwtProdAccess.objects.exclude(affiliation__user_sdwt_prod="")
        .values_list("affiliation__user_sdwt_prod", flat=True)
        .distinct()
    )

    combined = affiliation_values | access_values
    return _collapse_user_sdwt_prod_values(combined)


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

    normalized = _normalize_text(user_sdwt_prod)
    if not normalized:
        return False

    return Affiliation.objects.filter(user_sdwt_prod__iexact=normalized).exists()


def list_active_user_emails_by_user_sdwt_prod(*, user_sdwt_prod: str) -> list[str]:
    """user_sdwt_prod에 대응하는 활성 사용자 이메일 목록을 조회합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - list[str]: 이메일 주소 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return _list_active_user_contact_values_by_user_sdwt_prod(
        user_sdwt_prod=user_sdwt_prod,
        contact_field="email",
    )


def list_active_user_knox_ids_by_user_sdwt_prod(*, user_sdwt_prod: str) -> list[str]:
    """user_sdwt_prod에 대응하는 활성 사용자 knox_id 목록을 조회합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - list[str]: knox_id 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return _list_active_user_contact_values_by_user_sdwt_prod(
        user_sdwt_prod=user_sdwt_prod,
        contact_field="knox_id",
    )


def list_active_user_ids_by_ids(*, user_ids: Iterable[int]) -> set[int]:
    """활성 사용자 id 집합을 조회합니다.

    입력:
    - user_ids: 검증할 사용자 id 목록

    반환:
    - set[int]: 실제 존재하는 활성 사용자 id 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_ids = _normalize_positive_int_set(user_ids)
    if not normalized_ids:
        return set()

    User = get_user_model()
    return set(
        User.objects.filter(id__in=normalized_ids, is_active=True).values_list("id", flat=True)
    )


def list_active_user_ids_with_contact_by_ids(*, user_ids: Iterable[int], contact_field: str) -> set[int]:
    """활성 사용자 중 지정 연락처 값이 있는 사용자 id 집합을 조회합니다.

    입력:
    - user_ids: 검증할 사용자 id 목록
    - contact_field: email 또는 knox_id

    반환:
    - set[int]: 연락처 값이 있는 활성 사용자 id 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - ValueError: 지원하지 않는 연락처 필드일 때
    """

    if contact_field not in {"email", "knox_id"}:
        raise ValueError("contact_field must be email or knox_id")
    normalized_ids = _normalize_positive_int_set(user_ids)
    if not normalized_ids:
        return set()

    User = get_user_model()
    rows = (
        User.objects.filter(id__in=normalized_ids, is_active=True)
        .exclude(**{f"{contact_field}__isnull": True})
        .values("id", contact_field)
    )
    valid_ids: set[int] = set()
    for row in rows:
        value = row.get(contact_field)
        if isinstance(value, str) and value.strip():
            valid_ids.add(int(row["id"]))
    return valid_ids


def list_distinct_active_user_sdwt_prod_values(*, include_external_snapshots: bool = False) -> list[str]:
    """활성 사용자 pool에 존재하는 user_sdwt_prod 목록을 반환합니다.

    입력:
    - include_external_snapshots: 외부 소속 스냅샷의 예측 소속 포함 여부

    반환:
    - list[str]: 정렬된 user_sdwt_prod 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 활성 사용자에서 소속 값 수집
    # -----------------------------------------------------------------------------
    User = get_user_model()
    values = (
        User.objects.filter(is_active=True)
        .exclude(current_affiliation__affiliation__user_sdwt_prod__isnull=True)
        .exclude(current_affiliation__affiliation__user_sdwt_prod__exact="")
        .values_list("current_affiliation__affiliation__user_sdwt_prod", flat=True)
        .order_by("current_affiliation__affiliation__user_sdwt_prod")
        .distinct()
    )

    # -----------------------------------------------------------------------------
    # 2) 공백 제거 및 대소문자 비구분 중복 제거
    # -----------------------------------------------------------------------------
    collapsed_values = set(_collapse_user_sdwt_prod_values(values))
    if include_external_snapshots:
        external_values = ExternalAffiliationSnapshot.objects.exclude(
            predicted_user_sdwt_prod__exact=""
        ).values_list("predicted_user_sdwt_prod", flat=True)
        collapsed_values.update(_collapse_user_sdwt_prod_values(external_values))
    return sorted(collapsed_values)


def _build_external_snapshot_email(*, knox_id: str) -> str:
    """외부 스냅샷 사용자의 표준 Samsung 메일 주소를 생성합니다."""

    return f"{knox_id}@samsung.com"


def _list_active_user_knox_lookup_keys() -> set[str]:
    """활성 account_user의 knox_id lookup key 집합을 반환합니다."""

    User = get_user_model()
    return {
        str(value or "").strip().lower()
        for value in (
            User.objects.filter(is_active=True)
            .exclude(knox_id__isnull=True)
            .exclude(knox_id__exact="")
            .annotate(knox_lookup=Lower("knox_id"))
            .values_list("knox_lookup", flat=True)
        )
        if str(value or "").strip()
    }


def list_active_user_knox_lookup_keys_by_knox_ids(*, knox_ids: list[str]) -> set[str]:
    """입력 knox_id 중 활성 account_user에 존재하는 lookup key 집합을 반환합니다."""

    lookup_keys = sorted({value.lower() for value in _normalize_text_list(knox_ids)})
    if not lookup_keys:
        return set()

    User = get_user_model()
    return {
        str(value or "").strip().lower()
        for value in (
            User.objects.filter(is_active=True)
            .exclude(knox_id__isnull=True)
            .exclude(knox_id__exact="")
            .annotate(knox_lookup=Lower("knox_id"))
            .filter(knox_lookup__in=lookup_keys)
            .values_list("knox_lookup", flat=True)
        )
        if str(value or "").strip()
    }


def _list_external_affiliation_pool(
    *,
    search: str = "",
    user_sdwt_prod: str = "",
    limit: int | None = 50,
) -> list[dict[str, object]]:
    """수신인 선택 UI에 표시할 미가입 외부 스냅샷 사용자 목록을 조회합니다."""

    safe_limit = None if limit is None else max(1, min(int(limit or 50), 500))
    normalized_search = _normalize_text(search) or ""
    normalized_user_sdwt = _normalize_text(user_sdwt_prod) or ""
    active_knox_lookup_keys = _list_active_user_knox_lookup_keys()

    queryset = ExternalAffiliationSnapshot.objects.all()
    if normalized_user_sdwt:
        queryset = queryset.filter(predicted_user_sdwt_prod__iexact=normalized_user_sdwt)
    if normalized_search:
        queryset = queryset.filter(
            Q(knox_id__icontains=normalized_search)
            | Q(username__icontains=normalized_search)
            | Q(department__icontains=normalized_search)
            | Q(predicted_user_sdwt_prod__icontains=normalized_search)
        )

    rows = queryset.order_by("predicted_user_sdwt_prod", "username", "knox_id")
    if safe_limit is not None:
        rows = rows[:safe_limit]

    results: list[dict[str, object]] = []
    for snapshot in rows:
        knox_id = _normalize_text(snapshot.knox_id) or ""
        knox_lookup_key = knox_id.lower()
        if not knox_id or knox_lookup_key in active_knox_lookup_keys:
            continue
        recipient_key = f"external:{knox_lookup_key}"
        results.append(
            {
                "id": recipient_key,
                "userId": None,
                "recipientType": "external",
                "recipientKey": recipient_key,
                "externalKnoxId": knox_id,
                "username": snapshot.username or "",
                "displayName": snapshot.username or knox_id,
                "sabun": "",
                "knoxId": knox_id,
                "email": _build_external_snapshot_email(knox_id=knox_id),
                "department": snapshot.department or "",
                "line": "",
                "userSdwtProd": snapshot.predicted_user_sdwt_prod or "",
            }
        )
    return results


def list_active_user_pool(
    *,
    search: str = "",
    user_sdwt_prod: str = "",
    contact_field: str = "",
    limit: int | None = 50,
    include_external_snapshots: bool = False,
) -> list[dict[str, object]]:
    """수신인 선택 UI에서 사용할 활성 사용자 pool을 조회합니다.

    입력:
    - search: 이름/사번/knox_id/email 검색어
    - user_sdwt_prod: 특정 소속 필터
    - contact_field: email 또는 knox_id 보유 사용자 필터
    - limit: 최대 반환 개수(None이면 제한 없음)
    - include_external_snapshots: 미가입 외부 스냅샷 사용자 포함 여부

    반환:
    - list[dict[str, object]]: 사용자 선택 옵션 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 사용자 queryset 구성
    # -----------------------------------------------------------------------------
    safe_limit = None if limit is None else max(1, min(int(limit or 50), 500))
    normalized_search = _normalize_text(search) or ""
    normalized_user_sdwt = _normalize_text(user_sdwt_prod) or ""
    normalized_contact_field = _normalize_text(contact_field) or ""

    User = get_user_model()
    queryset = User.objects.filter(is_active=True).select_related(
        "current_affiliation__affiliation"
    )
    if normalized_user_sdwt:
        queryset = queryset.filter(
            current_affiliation__affiliation__user_sdwt_prod__iexact=normalized_user_sdwt
        )
    if normalized_contact_field in {"email", "knox_id"}:
        queryset = queryset.exclude(**{f"{normalized_contact_field}__isnull": True}).exclude(
            **{f"{normalized_contact_field}__exact": ""}
        )

    # -----------------------------------------------------------------------------
    # 2) 검색어 필터 적용
    # -----------------------------------------------------------------------------
    if normalized_search:
        queryset = queryset.filter(
            Q(username__icontains=normalized_search)
            | Q(username_en__icontains=normalized_search)
            | Q(givenname__icontains=normalized_search)
            | Q(surname__icontains=normalized_search)
            | Q(sabun__icontains=normalized_search)
            | Q(knox_id__icontains=normalized_search)
            | Q(email__icontains=normalized_search)
            | Q(current_affiliation__affiliation__user_sdwt_prod__icontains=normalized_search)
        )

    rows = queryset.order_by(
        "current_affiliation__affiliation__user_sdwt_prod",
        "username",
        "id",
    )
    if safe_limit is not None:
        rows = rows[:safe_limit]

    # -----------------------------------------------------------------------------
    # 3) 프론트엔드 선택 옵션 형태로 직렬화
    # -----------------------------------------------------------------------------
    results: list[dict[str, object]] = []
    for user in rows:
        affiliation = getattr(
            getattr(user, "current_affiliation", None),
            "affiliation",
            None,
        )
        display_name = (
            getattr(user, "username", None)
            or getattr(user, "username_en", None)
            or getattr(user, "givenname", None)
            or getattr(user, "knox_id", None)
            or getattr(user, "sabun", None)
            or ""
        )
        results.append(
            {
                "id": user.id,
                "userId": user.id,
                "recipientType": "user",
                "recipientKey": f"user:{user.id}",
                "username": getattr(user, "username", None) or "",
                "displayName": display_name,
                "sabun": getattr(user, "sabun", None) or "",
                "knoxId": getattr(user, "knox_id", None) or "",
                "email": getattr(user, "email", None) or "",
                "department": getattr(affiliation, "department", "") or "",
                "line": getattr(affiliation, "line", "") or "",
                "userSdwtProd": getattr(affiliation, "user_sdwt_prod", "") or "",
            }
        )
    if include_external_snapshots:
        results.extend(
            _list_external_affiliation_pool(
                search=normalized_search,
                user_sdwt_prod=normalized_user_sdwt,
                limit=limit,
            )
        )
        results = sorted(
            results,
            key=lambda item: (
                str(item.get("userSdwtProd") or "").casefold(),
                str(item.get("displayName") or item.get("knoxId") or "").casefold(),
                str(item.get("recipientKey") or "").casefold(),
            ),
        )
        if safe_limit is not None:
            results = results[:safe_limit]
    return results


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
        UserSdwtProdAccess.objects.filter(user=user)
        .select_related("affiliation", "user", "granted_by")
        .order_by("affiliation__user_sdwt_prod", "id")
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


def is_operator_user(*, user: Any) -> bool:
    """전역 운영자 권한 여부를 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - bool: 운영자이면 True

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 인증 및 Django 특권 플래그 확인
    # -----------------------------------------------------------------------------
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True

    # -----------------------------------------------------------------------------
    # 2) account profile의 admin 역할을 운영자로 해석
    # -----------------------------------------------------------------------------
    return get_user_profile_role(user=user) == UserProfile.Roles.ADMIN


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

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return False

    return UserSdwtProdAccess.objects.filter(
        user=user,
        affiliation__user_sdwt_prod__iexact=normalized,
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

    normalized_knox_id = _normalize_text(knox_id)
    if not normalized_knox_id:
        return None

    UserModel = get_user_model()
    if not hasattr(UserModel, "knox_id"):
        return None

    return UserModel.objects.filter(knox_id=normalized_knox_id).first()


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

    normalized_ids = _normalize_text_list(knox_ids)
    if not normalized_ids:
        return {}

    UserModel = get_user_model()
    if not hasattr(UserModel, "knox_id"):
        return {}

    users = UserModel.objects.filter(knox_id__in=normalized_ids)
    mapped: dict[str, Any] = {}
    for user in users:
        knox_id = getattr(user, "knox_id", None)
        normalized_knox_id = _normalize_text(knox_id)
        if normalized_knox_id:
            mapped[normalized_knox_id] = user
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

    normalized_knox_id = _normalize_text(knox_id)
    if not normalized_knox_id:
        return None

    return ExternalAffiliationSnapshot.objects.filter(knox_id=normalized_knox_id).first()


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

    normalized_ids = _normalize_text_list(knox_ids)
    if not normalized_ids:
        return {}

    return ExternalAffiliationSnapshot.objects.in_bulk(normalized_ids, field_name="knox_id")


def get_external_affiliation_snapshots_by_knox_lookup_keys(
    *,
    knox_ids: list[str],
) -> dict[str, ExternalAffiliationSnapshot]:
    """knox_id 목록을 대소문자 비구분 lookup key 기준으로 조회합니다.

    입력:
    - knox_ids: knox_id 목록

    반환:
    - dict[str, ExternalAffiliationSnapshot]: 소문자 knox_id → 스냅샷 매핑

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    lookup_keys = sorted({value.lower() for value in _normalize_text_list(knox_ids)})
    if not lookup_keys:
        return {}

    snapshots = (
        ExternalAffiliationSnapshot.objects.annotate(knox_lookup=Lower("knox_id"))
        .filter(knox_lookup__in=lookup_keys)
        .order_by("knox_lookup", "id")
    )
    result: dict[str, ExternalAffiliationSnapshot] = {}
    for snapshot in snapshots:
        lookup_key = (snapshot.knox_id or "").strip().lower()
        if lookup_key and lookup_key not in result:
            result[lookup_key] = snapshot
    return result


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

    if not user:
        return None

    current_user_sdwt_prod = get_current_user_sdwt_prod(user=user)
    normalized = _normalize_text(current_user_sdwt_prod)
    if not normalized:
        return None

    return (
        UserSdwtProdChange.objects.filter(user=user, to_user_sdwt_prod__iexact=normalized)
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

    normalized = _normalize_positive_int_set(user_ids)
    if not normalized:
        return set()

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

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return None

    return (
        UserSdwtProdAccess.objects.filter(
            user=user,
            affiliation__user_sdwt_prod__iexact=normalized,
        )
        .select_related("user", "affiliation")
        .order_by("id")
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

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return False

    return (
        UserSdwtProdAccess.objects.filter(
            affiliation__user_sdwt_prod__iexact=normalized,
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
            "affiliation__user_sdwt_prod",
            flat=True,
        )
    )
    return _collapse_user_sdwt_prod_values(values)


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
            "affiliation__user_sdwt_prod",
            flat=True,
        )
    )
    return _collapse_user_sdwt_prod_values(values)


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
        allowed_lookup_keys = list(_build_user_sdwt_display_map(allowed_user_sdwt_prods).keys())
        if not allowed_lookup_keys:
            return UserSdwtProdChange.objects.none()
        qs = qs.annotate(to_user_sdwt_prod_lookup=Lower("to_user_sdwt_prod")).filter(
            to_user_sdwt_prod_lookup__in=allowed_lookup_keys
        )

    normalized_status_input = _normalize_text(status)
    if normalized_status_input:
        normalized_status = normalized_status_input.upper()
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

    normalized_user_sdwt_prod = _normalize_text(user_sdwt_prod)
    if normalized_user_sdwt_prod:
        qs = qs.filter(to_user_sdwt_prod__iexact=normalized_user_sdwt_prod)

    keyword = _normalize_text(search)
    if keyword:
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

    lookup_keys = list(_build_user_sdwt_display_map(user_sdwt_prods).keys())
    if not lookup_keys:
        return UserSdwtProdAccess.objects.none()

    return (
        UserSdwtProdAccess.objects.annotate(
            user_sdwt_prod_lookup=Lower("affiliation__user_sdwt_prod")
        )
        .filter(user_sdwt_prod_lookup__in=lookup_keys)
        .select_related("user", "affiliation")
        .order_by("affiliation__user_sdwt_prod", "user_id")
    )


def list_current_affiliation_users_by_user_sdwt_prod(*, user_sdwt_prod: str) -> list[Any]:
    """현재 앱 소속이 지정 user_sdwt_prod인 사용자를 조회합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - list[Any]: 사용자 객체 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return []

    UserModel = get_user_model()
    return list(
        UserModel.objects.filter(
            current_affiliation__affiliation__user_sdwt_prod__iexact=normalized
        )
        .select_related("current_affiliation__affiliation")
        .order_by("id")
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


def list_user_sdwt_prod_values_for_line(*, line_id: str) -> list[str]:
    """라인 ID에 매핑되는 account_affiliation user_sdwt_prod 목록을 조회합니다.

    입력:
    - line_id: 라인 ID

    반환:
    - list[str]: user_sdwt_prod 문자열 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_line_id = _normalize_text(line_id)
    if not normalized_line_id:
        return []

    values = (
        Affiliation.objects.filter(line__iexact=normalized_line_id)
        .exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .values_list("user_sdwt_prod", flat=True)
        .order_by("user_sdwt_prod")
    )
    return sorted(_collapse_user_sdwt_prod_values(values))


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

    current_values = get_current_affiliation_values(user=user)
    current_department = current_values.get("department")
    current_line = current_values.get("line")
    current_user_sdwt_prod = current_values.get("user_sdwt_prod")

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
            "department": change.department or current_department or UNKNOWN,
            "line": change.line or current_line or "",
            "user_sdwt_prod": change.to_user_sdwt_prod
            or current_user_sdwt_prod
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
        "department": current_department or UNKNOWN,
        "line": current_line or "",
        "user_sdwt_prod": before_user_sdwt_prod
        or current_user_sdwt_prod
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

    normalized_department = _normalize_text(department)
    normalized_line = _normalize_text(line)
    normalized_user_sdwt_prod = _normalize_text(user_sdwt_prod)
    if not normalized_department or not normalized_line or not normalized_user_sdwt_prod:
        return None

    return (
        Affiliation.objects.filter(
            department=normalized_department,
            line=normalized_line,
            user_sdwt_prod__iexact=normalized_user_sdwt_prod,
        )
        .order_by("id")
        .first()
    )


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

    normalized = _normalize_text(user_sdwt_prod)
    if not normalized:
        return None

    rows = list(Affiliation.objects.filter(user_sdwt_prod__iexact=normalized).order_by("id")[:2])
    if len(rows) != 1:
        return None
    return rows[0]
