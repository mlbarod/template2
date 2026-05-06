# =============================================================================
# 모듈 설명: 이메일 이동/삭제 등 쓰기 작업을 처리합니다.
# - 주요 함수: delete_single_email, bulk_delete_emails, move_emails_for_user
# - 불변 조건: RAG 반영은 Outbox를 통해 비동기로 처리됩니다.
# =============================================================================

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Sequence

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from api.account import selectors as account_selectors
from api.common.services import UNASSIGNED_USER_SDWT_PROD
import api.account.services as account_services

from ..models import Email
from ..selectors import (
    get_accessible_user_sdwt_prods_for_user,
    get_email_for_update,
    list_email_asset_keys_by_email_ids,
    list_email_id_user_sdwt_by_ids,
    list_email_ids_by_sender_after,
    list_emails_for_update,
    list_unassigned_email_ids_for_sender_id,
    user_can_bulk_delete_emails,
)
from .rag import enqueue_rag_delete, enqueue_rag_index_for_emails
from .storage import delete_email_objects

# =============================================================================
# 상수
# =============================================================================
SENT_MAILBOX_ID = "__sent__"


def _resolve_sender_id_from_user(user: Any) -> str | None:
    """사용자에서 sender_id(knox_id)를 추출합니다.

    입력:
        user: Django User 또는 유사 객체.
    반환:
        유효한 knox_id 문자열 또는 None.
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) knox_id 추출 및 정규화
    # -----------------------------------------------------------------------------
    knox_id = getattr(user, "knox_id", None)
    if isinstance(knox_id, str) and knox_id.strip():
        return knox_id.strip()
    return None


@transaction.atomic
def delete_single_email(email_id: int) -> Email:
    """단일 메일 삭제를 수행합니다(RAG 삭제는 Outbox 처리).

    입력:
        email_id: 삭제할 Email PK.
    반환:
        삭제된 Email 인스턴스.
    부작용:
        Email 삭제 및 RAG 삭제 Outbox 적재.
    오류:
        Email이 없으면 NotFound 예외.
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 메일 조회/잠금
    # -----------------------------------------------------------------------------
    try:
        email = get_email_for_update(email_id=email_id)
    except Email.DoesNotExist:
        raise NotFound("Email not found")

    # -----------------------------------------------------------------------------
    # 2) RAG 삭제 요청 및 삭제 실행
    # -----------------------------------------------------------------------------
    asset_keys = list_email_asset_keys_by_email_ids(email_ids=[email.id])
    delete_email_objects(html_key=email.body_html_object_key, asset_keys=asset_keys)
    enqueue_rag_delete(email=email)

    email.delete()
    return email


@transaction.atomic
def bulk_delete_emails(email_ids: List[int]) -> int:
    """여러 메일을 한 번에 삭제합니다(RAG 삭제는 Outbox 처리).

    입력:
        email_ids: 삭제할 Email PK 목록.
    반환:
        삭제된 메일 개수.
    부작용:
        Email 삭제 및 RAG 삭제 Outbox 적재.
    오류:
        대상이 없으면 NotFound 예외.
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 메일 조회/잠금
    # -----------------------------------------------------------------------------
    emails = list_emails_for_update(email_ids=email_ids)
    if not emails:
        raise NotFound("No emails found to delete")

    # -----------------------------------------------------------------------------
    # 2) RAG 삭제 요청
    # -----------------------------------------------------------------------------
    for email in emails:
        enqueue_rag_delete(email=email)

    # -----------------------------------------------------------------------------
    # 3) MinIO 오브젝트 삭제
    # -----------------------------------------------------------------------------
    target_ids = [email.id for email in emails]
    asset_keys = list_email_asset_keys_by_email_ids(email_ids=target_ids)
    for email in emails:
        delete_email_objects(html_key=email.body_html_object_key, asset_keys=[])
    delete_email_objects(html_key=None, asset_keys=asset_keys)

    # -----------------------------------------------------------------------------
    # 4) 일괄 삭제 수행
    # -----------------------------------------------------------------------------
    Email.objects.filter(id__in=target_ids).delete()

    return len(emails)


def claim_unassigned_emails_for_user(*, user: Any) -> Dict[str, int]:
    """사용자의 UNASSIGNED 메일을 현재 user_sdwt_prod로 귀속(옮김)합니다.

    입력:
        user: Django User 또는 유사 객체.
    반환:
        moved/ragRegistered/ragFailed/ragMissing 카운트 dict.
    부작용:
        - Email.user_sdwt_prod 업데이트.
        - RAG 인덱싱 Outbox 적재.
    오류:
        - knox_id 미설정 시 PermissionError
        - user_sdwt_prod 미설정/UNASSIGNED 지정 시 ValueError
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자/메일함 유효성 확인
    # -----------------------------------------------------------------------------
    sender_id = _resolve_sender_id_from_user(user)
    if not sender_id:
        raise PermissionError("knox_id is required to claim unassigned emails")

    target_user_sdwt_prod = account_selectors.get_current_user_sdwt_prod(user=user)
    if not isinstance(target_user_sdwt_prod, str) or not target_user_sdwt_prod.strip():
        raise ValueError("user_sdwt_prod must be set to claim unassigned emails")

    target_user_sdwt_prod = target_user_sdwt_prod.strip()
    if target_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD:
        raise ValueError("Cannot claim emails into the UNASSIGNED mailbox")

    # -----------------------------------------------------------------------------
    # 2) 대상 메일 식별 및 업데이트
    # -----------------------------------------------------------------------------
    email_ids = list_unassigned_email_ids_for_sender_id(sender_id=sender_id)
    if not email_ids:
        return {"moved": 0, "ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    with transaction.atomic():
        Email.objects.filter(id__in=email_ids).update(
            user_sdwt_prod=target_user_sdwt_prod,
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
        )

    # -----------------------------------------------------------------------------
    # 3) RAG 인덱싱 큐 적재
    # -----------------------------------------------------------------------------
    rag_result = enqueue_rag_index_for_emails(
        email_ids=email_ids,
        target_user_sdwt_prod=target_user_sdwt_prod,
        previous_user_sdwt_prod_by_email_id=None,
    )

    return {"moved": len(email_ids), **rag_result}


def move_emails_to_user_sdwt_prod(*, email_ids: Sequence[int], to_user_sdwt_prod: str) -> Dict[str, int]:
    """지정한 Email id들을 다른 user_sdwt_prod 메일함으로 이동합니다.

    입력:
        email_ids: 이동할 Email id 목록.
        to_user_sdwt_prod: 대상 메일함(user_sdwt_prod).
    반환:
        moved/ragRegistered/ragFailed/ragMissing 카운트 dict.
    부작용:
        - Email.user_sdwt_prod 업데이트.
        - RAG 인덱싱 Outbox 적재.
    오류:
        - 대상 메일함 미입력/금지된 값이면 ValueError
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 메일함/ID 정규화
    # -----------------------------------------------------------------------------
    target_user_sdwt_prod = (to_user_sdwt_prod or "").strip()
    if not target_user_sdwt_prod:
        raise ValueError("to_user_sdwt_prod is required")
    if target_user_sdwt_prod in {UNASSIGNED_USER_SDWT_PROD, SENT_MAILBOX_ID}:
        raise ValueError("Cannot move emails into the target mailbox")

    ids = [int(value) for value in email_ids if isinstance(value, int) or str(value).isdigit()]
    if not ids:
        return {"moved": 0, "ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    # -----------------------------------------------------------------------------
    # 2) 기존 메일함 매핑 조회 및 이동 개수 계산
    # -----------------------------------------------------------------------------
    previous_user_sdwt = list_email_id_user_sdwt_by_ids(email_ids=ids)
    resolved_ids = list(previous_user_sdwt.keys())
    if not resolved_ids:
        return {"moved": 0, "ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    moved_count = 0
    for previous in previous_user_sdwt.values():
        if (previous or "").strip() != target_user_sdwt_prod:
            moved_count += 1

    # -----------------------------------------------------------------------------
    # 3) 메일함 업데이트
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        Email.objects.filter(id__in=resolved_ids).update(
            user_sdwt_prod=target_user_sdwt_prod,
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
        )

    # -----------------------------------------------------------------------------
    # 4) RAG 인덱싱 큐 적재
    # -----------------------------------------------------------------------------
    rag_result = enqueue_rag_index_for_emails(
        email_ids=ids,
        target_user_sdwt_prod=target_user_sdwt_prod,
        previous_user_sdwt_prod_by_email_id=previous_user_sdwt,
    )

    return {"moved": moved_count, **rag_result}


def move_emails_for_user(
    *,
    user: Any,
    email_ids: Sequence[int],
    to_user_sdwt_prod: str,
) -> Dict[str, int]:
    """현재 사용자 권한을 확인한 뒤 메일을 다른 메일함으로 이동합니다.

    입력:
        user: Django User 또는 유사 객체.
        email_ids: 이동할 Email id 목록.
        to_user_sdwt_prod: 대상 메일함(user_sdwt_prod).
    반환:
        moved/ragRegistered/ragFailed/ragMissing 카운트 dict.
    부작용:
        Email.user_sdwt_prod 업데이트 및 RAG 큐 적재.
    오류:
        - 인증/권한 부족 시 PermissionError
        - 잘못된 입력 시 ValueError
    """

    # -----------------------------------------------------------------------------
    # 1) 인증/권한 기본 검증
    # -----------------------------------------------------------------------------
    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionError("unauthorized")

    sender_id = _resolve_sender_id_from_user(user)
    if not sender_id:
        raise PermissionError("forbidden")

    # -----------------------------------------------------------------------------
    # 2) 입력값 정규화 및 대상 메일함 검증
    # -----------------------------------------------------------------------------
    target_user_sdwt_prod = (to_user_sdwt_prod or "").strip()
    if not target_user_sdwt_prod:
        raise ValueError("to_user_sdwt_prod is required")
    if target_user_sdwt_prod in {UNASSIGNED_USER_SDWT_PROD, SENT_MAILBOX_ID}:
        raise ValueError("Cannot move emails into the target mailbox")

    normalized_ids = [int(value) for value in email_ids if isinstance(value, int) or str(value).isdigit()]
    if not normalized_ids:
        return {"moved": 0, "ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    # -----------------------------------------------------------------------------
    # 3) 접근 권한 검증
    # -----------------------------------------------------------------------------
    is_privileged = bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))
    accessible = get_accessible_user_sdwt_prods_for_user(user) if not is_privileged else set()
    if not is_privileged and target_user_sdwt_prod not in accessible:
        raise PermissionError("forbidden")

    if not is_privileged:
        if not user_can_bulk_delete_emails(
            email_ids=normalized_ids,
            accessible_user_sdwt_prods=accessible,
            sender_id=sender_id,
        ):
            raise PermissionError("forbidden")

    # -----------------------------------------------------------------------------
    # 4) 실제 이동 처리
    # -----------------------------------------------------------------------------
    return move_emails_to_user_sdwt_prod(email_ids=normalized_ids, to_user_sdwt_prod=target_user_sdwt_prod)


def move_sender_emails_after(
    *,
    sender_id: str,
    received_at_gte: datetime,
    to_user_sdwt_prod: str,
) -> Dict[str, int]:
    """발신자(sender_id)의 특정 시각 이후 메일을 다른 메일함으로 이동합니다.

    입력:
        sender_id: Email.sender_id (KNOX ID, 발신자 식별자).
        received_at_gte: 기준 시각(이 시각 이상 수신된 메일만).
        to_user_sdwt_prod: 대상 메일함(user_sdwt_prod).
    반환:
        moved/ragRegistered/ragFailed/ragMissing 카운트 dict.
    부작용:
        Email.user_sdwt_prod 업데이트 및 RAG 큐 적재.
    오류:
        sender_id 미입력 시 ValueError.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증 및 시각 정규화
    # -----------------------------------------------------------------------------
    normalized_sender_id = (sender_id or "").strip()
    if not normalized_sender_id:
        raise ValueError("sender_id is required")

    when = received_at_gte
    if timezone.is_naive(when):
        when = timezone.make_aware(when, timezone.get_current_timezone())

    # -----------------------------------------------------------------------------
    # 2) 대상 메일 조회 및 이동 처리
    # -----------------------------------------------------------------------------
    email_ids = list_email_ids_by_sender_after(sender_id=normalized_sender_id, received_at_gte=when)

    return move_emails_to_user_sdwt_prod(email_ids=email_ids, to_user_sdwt_prod=to_user_sdwt_prod)


def move_emails_after_sender_affiliation_change(
    *,
    sender_ids: Sequence[str],
) -> Dict[str, object]:
    """발신자 소속 변경 이후 메일을 현재 소속 메일함으로 이동합니다.

    입력:
        sender_ids: Email.sender_id 목록.
    반환:
        moved/ragRegistered/ragFailed/ragMissing/failures 집계 dict.
    부작용:
        Email.user_sdwt_prod 업데이트 및 RAG 인덱싱 Outbox 적재.
    오류:
        - 없음(개별 발신자 실패는 failures에 기록).
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized_sender_ids = sorted(
        {sender_id.strip() for sender_id in sender_ids if isinstance(sender_id, str) and sender_id.strip()}
    )
    if not normalized_sender_ids:
        return {
            "moved": 0,
            "ragRegistered": 0,
            "ragFailed": 0,
            "ragMissing": 0,
            "failures": [],
        }

    # -----------------------------------------------------------------------------
    # 2) 결과 집계 준비
    # -----------------------------------------------------------------------------
    total_moved = 0
    total_rag_registered = 0
    total_rag_failed = 0
    total_rag_missing = 0
    failures: list[str] = []

    # -----------------------------------------------------------------------------
    # 3) 발신자별 이동 처리
    # -----------------------------------------------------------------------------
    for sender_id in normalized_sender_ids:
        user = account_services.get_user_by_knox_id(knox_id=sender_id)
        if user is None:
            failures.append(f"{sender_id}: 사용자 없음")
            continue

        target_user_sdwt_prod = (account_selectors.get_current_user_sdwt_prod(user=user) or "").strip()
        if not target_user_sdwt_prod or target_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD:
            failures.append(f"{sender_id}: user_sdwt_prod 없음/UNASSIGNED")
            continue

        change = account_services.get_current_user_sdwt_prod_change(user=user)
        if change is None:
            failures.append(f"{sender_id}: 소속 변경 이력(UserSdwtProdChange) 없음")
            continue

        try:
            result = move_sender_emails_after(
                sender_id=sender_id,
                received_at_gte=change.effective_from,
                to_user_sdwt_prod=target_user_sdwt_prod,
            )
        except Exception as exc:
            failures.append(f"{sender_id}: {exc}")
            continue

        total_moved += result.get("moved", 0)
        total_rag_registered += result.get("ragRegistered", 0)
        total_rag_failed += result.get("ragFailed", 0)
        total_rag_missing += result.get("ragMissing", 0)

    # -----------------------------------------------------------------------------
    # 4) 결과 반환
    # -----------------------------------------------------------------------------
    return {
        "moved": total_moved,
        "ragRegistered": total_rag_registered,
        "ragFailed": total_rag_failed,
        "ragMissing": total_rag_missing,
        "failures": failures,
    }
