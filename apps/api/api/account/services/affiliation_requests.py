# =============================================================================
# 모듈 설명: 소속 변경 요청/승인/거절 서비스 로직을 제공합니다.
# - 주요 대상: request_affiliation_change, approve_affiliation_change, reject_affiliation_change
# - 불변 조건: 승인/거절은 권한 검증 후 처리합니다.
# =============================================================================

"""소속 변경 요청/승인/거절 서비스 모음.

- 주요 대상: 변경 요청 조회/생성/승인/거절
- 주요 엔드포인트/클래스: request_affiliation_change 등
- 가정/불변 조건: 승인/거절은 권한 검증 후 처리됨
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Tuple

from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.utils import timezone

from ..models import UserCurrentAffiliation, UserSdwtProdChange
from .. import selectors
from .access import downgrade_member_access, ensure_self_access
from .utils import (
    _build_user_sdwt_display_map,
    _is_privileged_user,
    _normalize_user_sdwt_lookup_key,
    _same_user_sdwt_prod,
    _user_can_approve_affiliation_change,
)


def _serialize_actor(user: Any) -> dict[str, object] | None:
    """승인/요청 사용자 정보를 직렬화합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - dict[str, object] | None: 직렬화 결과 또는 None

    부작용:
    - 없음

    오류:
    - 없음
    """

    if not user:
        return None
    username = getattr(user, "username", "") or ""
    return {"id": user.id, "username": username}


def _serialize_affiliation_change(change: UserSdwtProdChange) -> dict[str, object]:
    """UserSdwtProdChange를 응답용 dict로 직렬화합니다.

    입력:
    - change: UserSdwtProdChange 객체

    반환:
    - dict[str, object]: 직렬화 결과

    부작용:
    - 없음

    오류:
    - 없음
    """

    return {
        "id": change.id,
        "status": change.status,
        "department": change.department,
        "line": change.line,
        "fromUserSdwtProd": change.from_user_sdwt_prod,
        "toUserSdwtProd": change.to_user_sdwt_prod,
        "effectiveFrom": change.effective_from.isoformat(),
        "approvedAt": change.approved_at.isoformat() if change.approved_at else None,
        "requestedAt": change.created_at.isoformat(),
        "approvedBy": _serialize_actor(change.approved_by),
        "requestedBy": _serialize_actor(change.created_by),
        "rejectionReason": change.rejection_reason,
    }


def _serialize_affiliation_change_request(
    change: UserSdwtProdChange,
    *,
    role: str,
) -> dict[str, object]:
    """승인 요청용 UserSdwtProdChange 응답 payload를 구성합니다.

    입력:
    - change: UserSdwtProdChange 객체
    - role: 사용자 역할(viewer/member/manager)

    반환:
    - dict[str, object]: 승인 요청용 payload

    부작용:
    - 없음

    오류:
    - 없음
    """

    user = change.user
    current_values = selectors.get_current_affiliation_values(user=user)
    user_payload = {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
        "sabun": getattr(user, "sabun", None),
        "knoxId": getattr(user, "knox_id", None),
        "department": current_values.get("department"),
        "line": current_values.get("line"),
        "userSdwtProd": current_values.get("user_sdwt_prod"),
    }

    return {
        **_serialize_affiliation_change(change),
        "role": role,
        "user": user_payload,
    }


def _resolve_affiliation_change_role(*, user: Any, change: UserSdwtProdChange) -> str:
    """소속 변경 요청 항목의 역할을 계산합니다.

    입력:
    - user: Django 사용자 객체
    - change: UserSdwtProdChange 객체

    반환:
    - str: viewer/member/manager

    부작용:
    - 없음

    오류:
    - 없음
    """

    if _is_privileged_user(user):
        return "manager"

    access = selectors.get_access_row_for_user_and_prod(
        user=user,
        user_sdwt_prod=change.to_user_sdwt_prod,
    )
    if access and access.role in {"viewer", "member", "manager"}:
        return access.role

    return "viewer"


def get_pending_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """대기 중인 user_sdwt_prod 변경 요청을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserSdwtProdChange | None: 대기 중인 변경 요청 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return selectors.get_pending_user_sdwt_prod_change(user=user)


def get_current_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """현재 적용 중인 user_sdwt_prod 변경 이력을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserSdwtProdChange | None: 가장 최근 변경 이력 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return selectors.get_current_user_sdwt_prod_change(user=user)


def get_affiliation_change_requests(
    *,
    user: Any,
    status: str | None,
    search: str | None,
    user_sdwt_prod: str | None,
    page: int,
    page_size: int,
) -> Tuple[dict[str, object], int]:
    """조회 가능한 소속 변경 요청 목록을 페이지 단위로 조회합니다.

    입력:
    - user: Django 사용자 객체
    - status/search/user_sdwt_prod: 필터 조건
    - page/page_size: 페이지네이션 값

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - 없음(읽기 전용)

    오류:
    - 403: 조회 권한 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 승인 가능 범위 산정
    # -----------------------------------------------------------------------------
    is_privileged = _is_privileged_user(user)
    approvable_user_sdwt_prods = None
    allowed_user_sdwt_prods: set[str] | None = None
    if not is_privileged:
        approvable_user_sdwt_prods = selectors.list_approvable_user_sdwt_prod_values(user=user)
        allowed_user_sdwt_prods = set(approvable_user_sdwt_prods)
        current_user_sdwt = selectors.get_current_user_sdwt_prod(user=user)
        if isinstance(current_user_sdwt, str) and current_user_sdwt.strip():
            allowed_user_sdwt_prods.add(current_user_sdwt.strip())
        if not allowed_user_sdwt_prods:
            return {"error": "forbidden"}, 403
        allowed_lookup_keys = set(_build_user_sdwt_display_map(allowed_user_sdwt_prods).keys())
        requested_lookup_key = _normalize_user_sdwt_lookup_key(user_sdwt_prod)
        if requested_lookup_key and requested_lookup_key not in allowed_lookup_keys:
            return {"error": "forbidden"}, 403
        approvable_user_sdwt_prods = allowed_user_sdwt_prods

    # -----------------------------------------------------------------------------
    # 2) 변경 요청 목록 조회
    # -----------------------------------------------------------------------------
    qs = selectors.list_affiliation_change_requests(
        allowed_user_sdwt_prods=approvable_user_sdwt_prods,
        status=status,
        search=search,
        user_sdwt_prod=user_sdwt_prod,
    )

    # -----------------------------------------------------------------------------
    # 3) 페이지네이션 처리
    # -----------------------------------------------------------------------------
    paginator = Paginator(qs, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    # -----------------------------------------------------------------------------
    # 4) 응답 구성 및 반환
    # -----------------------------------------------------------------------------
    results = [
        _serialize_affiliation_change_request(
            change,
            role=_resolve_affiliation_change_role(user=user, change=change),
        )
        for change in page_obj.object_list
    ]

    return (
        {
            "results": results,
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        },
        200,
    )


def _apply_affiliation_change(*, change: UserSdwtProdChange, approver: Any | None) -> dict[str, object]:
    """소속 변경을 즉시 승인/적용합니다.

    입력:
    - change: UserSdwtProdChange 객체
    - approver: 승인자 사용자(없으면 None)

    반환:
    - dict[str, object]: 승인/적용 결과 payload

    부작용:
    - 사용자 소속 필드 업데이트
    - UserSdwtProdChange 상태 업데이트
    - 접근 권한 행 보장

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 현재 앱 소속 업데이트
    # -----------------------------------------------------------------------------
    target_user = change.user
    previous_user_sdwt = (getattr(change, "from_user_sdwt_prod", None) or "").strip()
    now = timezone.now()
    option = selectors.get_affiliation_option_by_user_sdwt_prod(
        user_sdwt_prod=change.to_user_sdwt_prod
    )
    if option is None:
        raise ValueError("Invalid user_sdwt_prod")

    source = (
        UserCurrentAffiliation.Sources.ADMIN_ASSIGNED
        if approver is not None and getattr(approver, "id", None) != target_user.id
        else UserCurrentAffiliation.Sources.USER_SELECTED
    )
    UserCurrentAffiliation.objects.update_or_create(
        user=target_user,
        defaults={
            "affiliation": option,
            "source": source,
            "confirmed_at": now,
            "requires_reconfirm": False,
        },
    )

    # -----------------------------------------------------------------------------
    # 2) 변경 요청 승인/적용 상태 반영
    # -----------------------------------------------------------------------------
    change.approved = True
    change.approved_by = approver
    change.approved_at = now
    change.applied = True
    change.status = UserSdwtProdChange.Status.APPROVED
    change.rejection_reason = None
    change.save(
        update_fields=[
            "approved",
            "approved_by",
            "approved_at",
            "applied",
            "status",
            "rejection_reason",
        ]
    )

    ensure_self_access(target_user, role="member")
    if previous_user_sdwt and not _same_user_sdwt_prod(previous_user_sdwt, change.to_user_sdwt_prod):
        downgrade_member_access(user=target_user, user_sdwt_prod=previous_user_sdwt)

    return {
        "status": "applied",
        "changeId": change.id,
        "userId": target_user.id,
        "userSdwtProd": option.user_sdwt_prod,
        "effectiveFrom": change.effective_from.isoformat(),
    }


def request_affiliation_change(
    *,
    user: Any,
    option: Any,
    to_user_sdwt_prod: str,
    effective_from: datetime,
    timezone_name: str,
    force_pending: bool = False,
) -> Tuple[dict[str, object], int]:
    """user_sdwt_prod 소속 변경을 요청합니다.

    입력:
    - user: Django 사용자 객체
    - option: 소속 옵션 객체
    - to_user_sdwt_prod: 대상 소속
    - effective_from: 효력 시작 시각
    - timezone_name: 시간대 이름
    - force_pending: 자동 승인 차단 여부

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - UserSdwtProdChange 생성
    - 자동 적용 조건 충족 시 즉시 승인/반영

    오류:
    - 400: 동일 소속 요청
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 소속 정규화 및 동일 소속 요청 차단
    # -----------------------------------------------------------------------------
    normalized_target = (to_user_sdwt_prod or "").strip()
    current_user_sdwt = (selectors.get_current_user_sdwt_prod(user=user) or "").strip()
    if _same_user_sdwt_prod(current_user_sdwt, normalized_target):
        return {"error": "already current affiliation"}, 400

    # -----------------------------------------------------------------------------
    # 2) 자기 접근 권한 보장
    # -----------------------------------------------------------------------------
    ensure_self_access(user, role="member")

    # -----------------------------------------------------------------------------
    # 3) 기존 대기 요청 확인 및 대체 여부 판단
    # -----------------------------------------------------------------------------
    existing_pending = selectors.get_pending_user_sdwt_prod_change(user=user)
    has_existing_pending = existing_pending is not None

    # -----------------------------------------------------------------------------
    # 4) 예측 소속 일치 여부 확인 및 자동 적용 판단
    # -----------------------------------------------------------------------------
    knox_id = (getattr(user, "knox_id", None) or "").strip()
    predicted_user_sdwt = ""
    if knox_id:
        snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(knox_id=knox_id)
        predicted_user_sdwt = (snapshot.predicted_user_sdwt_prod or "").strip() if snapshot else ""

    predicted_match = _same_user_sdwt_prod(predicted_user_sdwt, normalized_target)
    should_auto_apply = predicted_match
    if force_pending:
        should_auto_apply = False
    if has_existing_pending:
        should_auto_apply = False

    # -----------------------------------------------------------------------------
    # 5) effective_from 보정
    # -----------------------------------------------------------------------------
    if should_auto_apply:
        effective_from = timezone.now()
    else:
        if effective_from is None:
            effective_from = timezone.now()
        elif timezone.is_naive(effective_from):
            effective_from = timezone.make_aware(effective_from, timezone.utc)
    # -----------------------------------------------------------------------------
    # 6) 변경 요청 생성 및 자동 적용 분기
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        if existing_pending is not None:
            existing_pending.status = UserSdwtProdChange.Status.SUPERSEDED
            existing_pending.approved = False
            existing_pending.approved_by = None
            existing_pending.approved_at = None
            existing_pending.applied = False
            existing_pending.rejection_reason = "취소(대체됨)"
            existing_pending.save(
                update_fields=[
                    "status",
                    "approved",
                    "approved_by",
                    "approved_at",
                    "applied",
                    "rejection_reason",
                ]
            )

        change = UserSdwtProdChange.objects.create(
            user=user,
            department=getattr(option, "department", None),
            line=getattr(option, "line", None),
            from_user_sdwt_prod=selectors.get_current_user_sdwt_prod(user=user),
            to_user_sdwt_prod=normalized_target,
            effective_from=effective_from,
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        if should_auto_apply:
            return _apply_affiliation_change(change=change, approver=user), 200

        current_affiliation = selectors.get_current_affiliation_record(user=user)
        if current_affiliation is not None and current_affiliation.requires_reconfirm:
            current_affiliation.requires_reconfirm = False
            current_affiliation.save(update_fields=["requires_reconfirm"])

    # -----------------------------------------------------------------------------
    # 7) 승인 대기 응답 반환
    # -----------------------------------------------------------------------------
    return (
        {
            "status": "pending",
            "changeId": change.id,
            "userSdwtProd": normalized_target,
            "effectiveFrom": change.effective_from.isoformat(),
        },
        202,
    )


def approve_affiliation_change(
    *,
    approver: Any,
    change_id: int,
) -> Tuple[dict[str, object], int]:
    """대기 중인 UserSdwtProdChange를 승인하고 사용자 정보에 반영합니다.

    입력:
    - approver: 승인자 사용자
    - change_id: 변경 요청 id

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - 사용자 소속 필드 업데이트
    - UserSdwtProdChange 상태 업데이트
    - 접근 권한 행 보장

    오류:
    - 403: 권한 없음
    - 404: 변경 요청 없음
    - 400: 이미 처리됨
    """

    # -----------------------------------------------------------------------------
    # 1) 변경 요청 조회
    # -----------------------------------------------------------------------------
    change = selectors.get_user_sdwt_prod_change_by_id(change_id=change_id)
    if change is None:
        return {"error": "Change not found"}, 404

    # -----------------------------------------------------------------------------
    # 2) 권한 검증
    # -----------------------------------------------------------------------------
    if not _user_can_approve_affiliation_change(
        user=approver,
        target_user_sdwt_prod=change.to_user_sdwt_prod,
    ):
        return {"error": "forbidden"}, 403

    # -----------------------------------------------------------------------------
    # 3) 상태 검증
    # -----------------------------------------------------------------------------
    if change.status == UserSdwtProdChange.Status.APPROVED or change.approved or change.applied:
        return {"error": "already applied"}, 400
    if change.status in {
        UserSdwtProdChange.Status.REJECTED,
        UserSdwtProdChange.Status.SUPERSEDED,
    }:
        return {"error": "already rejected"}, 400

    # -----------------------------------------------------------------------------
    # 4) 트랜잭션 내 승인/적용 처리
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        payload = _apply_affiliation_change(change=change, approver=approver)
        payload["status"] = "approved"

    # -----------------------------------------------------------------------------
    # 5) 응답 반환
    # -----------------------------------------------------------------------------
    return payload, 200


def reject_affiliation_change(
    *,
    approver: Any,
    change_id: int,
    rejection_reason: str | None,
) -> Tuple[dict[str, object], int]:
    """대기 중인 UserSdwtProdChange를 거절 처리합니다.

    입력:
    - approver: 승인자 사용자
    - change_id: 변경 요청 id
    - rejection_reason: 거절 사유(없으면 None)

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - UserSdwtProdChange 상태를 REJECTED로 업데이트
    - 거절 사유 저장

    오류:
    - 403: 권한 없음
    - 404: 변경 요청 없음
    - 400: 이미 처리됨
    """

    # -----------------------------------------------------------------------------
    # 1) 변경 요청 조회
    # -----------------------------------------------------------------------------
    change = selectors.get_user_sdwt_prod_change_by_id(change_id=change_id)
    if change is None:
        return {"error": "Change not found"}, 404

    # -----------------------------------------------------------------------------
    # 2) 권한 검증
    # -----------------------------------------------------------------------------
    if not _user_can_approve_affiliation_change(
        user=approver,
        target_user_sdwt_prod=change.to_user_sdwt_prod,
    ):
        return {"error": "forbidden"}, 403

    # -----------------------------------------------------------------------------
    # 3) 상태 검증
    # -----------------------------------------------------------------------------
    if change.status in {
        UserSdwtProdChange.Status.REJECTED,
        UserSdwtProdChange.Status.SUPERSEDED,
    }:
        return {"error": "already rejected"}, 400
    if change.status == UserSdwtProdChange.Status.APPROVED or change.approved or change.applied:
        return {"error": "already applied"}, 400

    # -----------------------------------------------------------------------------
    # 4) 거절 처리 및 저장
    # -----------------------------------------------------------------------------
    normalized_reason = rejection_reason.strip() if isinstance(rejection_reason, str) else ""
    rejection_reason_value = normalized_reason or None
    change.status = UserSdwtProdChange.Status.REJECTED
    change.approved = False
    change.approved_by = approver
    change.approved_at = timezone.now()
    change.applied = False
    change.rejection_reason = rejection_reason_value
    change.save(
        update_fields=[
            "status",
            "approved",
            "approved_by",
            "approved_at",
            "applied",
            "rejection_reason",
        ]
    )

    return {"status": "rejected", "changeId": change.id}, 200
