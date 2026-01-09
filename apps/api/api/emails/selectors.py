# =============================================================================
# 모듈 설명: emails 도메인의 조회 전용 ORM 쿼리를 제공합니다.
# - 주요 함수: list_mailbox_members, get_filtered_emails, resolve_email_affiliation
# - 불변 조건: 쓰기 작업 없이 조회만 수행합니다.
# =============================================================================

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence, TypedDict

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

import api.account.selectors as account_selectors
from api.account.selectors import list_distinct_user_sdwt_prod_values
from api.common.services import UNASSIGNED_USER_SDWT_PROD

from .models import Email, EmailAsset, EmailOutbox


class EmailAffiliation(TypedDict):
    """이메일 발신자 소속 판별 결과를 담는 타입입니다."""

    user_sdwt_prod: str
    classification_source: str


def _normalize_time(value: datetime | None) -> datetime:
    """datetime 값을 timezone-aware(UTC)로 정규화합니다.

    입력:
        value: datetime 또는 None.
    반환:
        timezone-aware datetime(UTC 기준).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) None 처리 및 timezone 정규화
    # -----------------------------------------------------------------------------
    if value is None:
        return timezone.now()
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.utc)
    return value


def get_accessible_user_sdwt_prods_for_user(user: Any) -> set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 값 집합을 조회합니다.

    입력:
        user: Django User 또는 유사 객체.
    반환:
        접근 가능한 user_sdwt_prod 집합.
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    return account_selectors.get_accessible_user_sdwt_prods_for_user(user)


def list_mailbox_members(*, mailbox_user_sdwt_prod: str) -> list[dict[str, object]]:
    """메일함(user_sdwt_prod)에 접근 가능한 사용자 목록을 반환합니다.

    입력:
        mailbox_user_sdwt_prod: 메일함 user_sdwt_prod 값.
    반환:
        멤버 dict 리스트(권한/발신자 카운트 포함).
    부작용:
        없음. 조회 전용.
    오류:
        mailbox_user_sdwt_prod가 비어 있으면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized = mailbox_user_sdwt_prod.strip() if isinstance(mailbox_user_sdwt_prod, str) else ""
    if not normalized:
        return []

    # -----------------------------------------------------------------------------
    # 2) 접근 권한/소속 사용자 조회
    # -----------------------------------------------------------------------------
    access_rows = list(account_selectors.list_group_members(user_sdwt_prods={normalized}))
    access_by_user_id = {row.user_id: row for row in access_rows}

    UserModel = get_user_model()
    affiliated_users = list(UserModel.objects.filter(user_sdwt_prod=normalized).order_by("id"))

    members: list[dict[str, object]] = []
    seen_user_ids: set[int] = set()
    sender_id_by_user_id: dict[int, str] = {}

    def resolve_sender_id(user: Any) -> str:
        """사용자 객체에서 sender_id(knox_id)를 추출합니다."""

        sender_id = getattr(user, "knox_id", None)
        return sender_id.strip() if isinstance(sender_id, str) and sender_id.strip() else ""

    def serialize_user(user: Any, access: Any | None) -> dict[str, object]:
        """사용자/권한 정보를 멤버 dict로 직렬화합니다."""

        sender_id_by_user_id[user.id] = resolve_sender_id(user)
        knox_id = getattr(user, "knox_id", None)
        knox_id_value = knox_id.strip() if isinstance(knox_id, str) else ""
        display_username = getattr(user, "username", None)
        display_username_value = display_username.strip() if isinstance(display_username, str) else ""
        role_value = getattr(access, "role", None) if access else "member"
        return {
            "userId": user.id,
            "username": display_username_value,
            "name": display_username_value,
            "knoxId": knox_id_value,
            "avatarid": getattr(user, "avatarid", None),
            "userSdwtProd": normalized,
            "role": role_value,
            "grantedBy": getattr(access, "granted_by_id", None) if access else None,
            "grantedAt": access.created_at.isoformat() if access else None,
            "emailCount": 0,
        }

    # -----------------------------------------------------------------------------
    # 3) 소속 사용자/권한 부여 사용자 병합
    # -----------------------------------------------------------------------------
    for user in affiliated_users:
        access = access_by_user_id.get(user.id)
        members.append(serialize_user(user, access))
        seen_user_ids.add(user.id)

    for access in access_rows:
        if access.user_id in seen_user_ids:
            continue
        members.append(serialize_user(access.user, access))
        seen_user_ids.add(access.user_id)

    # -----------------------------------------------------------------------------
    # 4) 발신자별 이메일 카운트 계산
    # -----------------------------------------------------------------------------
    sender_ids = sorted({value for value in sender_id_by_user_id.values() if value})
    if sender_ids:
        email_count_rows = (
            Email.objects.filter(user_sdwt_prod=normalized, sender_id__in=sender_ids)
            .values("sender_id")
            .annotate(email_count=Count("id"))
        )
        count_by_sender_id = {row["sender_id"]: row["email_count"] for row in email_count_rows}

        for member in members:
            user_id = member.get("userId")
            sender_id = sender_id_by_user_id.get(user_id) if isinstance(user_id, int) else ""
            member["emailCount"] = int(count_by_sender_id.get(sender_id, 0)) if sender_id else 0

    # -----------------------------------------------------------------------------
    # 5) 정렬 및 반환
    # -----------------------------------------------------------------------------
    role_order = {"manager": 0, "member": 1, "viewer": 2}
    members.sort(
        key=lambda member: (
            role_order.get(member.get("role", "viewer"), 2),
            str(member.get("username", "")),
        )
    )
    return members


def resolve_email_affiliation(*, sender_id: str, received_at: datetime | None) -> EmailAffiliation:
    """이메일 발신자 기준으로 user_sdwt_prod 소속을 판별합니다.

    입력:
        sender_id: 발신자 식별자(로컬파트/아이디).
        received_at: 수신 시각(현재 정책에서는 사용하지 않음).
    반환:
        user_sdwt_prod 및 classification_source를 포함한 dict.
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 소속 우선 확인
    # -----------------------------------------------------------------------------
    user = account_selectors.get_user_by_knox_id(knox_id=sender_id)
    if user is not None:
        resolved = (getattr(user, "user_sdwt_prod", None) or "").strip()
        if resolved and resolved != UNASSIGNED_USER_SDWT_PROD:
            return {
                "user_sdwt_prod": resolved,
                "classification_source": Email.ClassificationSource.CONFIRMED_USER,
            }

    # -----------------------------------------------------------------------------
    # 2) 외부 예측 소속 확인
    # -----------------------------------------------------------------------------
    snapshot = account_selectors.get_external_affiliation_snapshot_by_knox_id(knox_id=sender_id)
    if snapshot is not None:
        predicted = (snapshot.predicted_user_sdwt_prod or "").strip()
        if predicted:
            return {
                "user_sdwt_prod": predicted,
                "classification_source": Email.ClassificationSource.PREDICTED_EXTERNAL,
            }

    # -----------------------------------------------------------------------------
    # 3) 기본값(UNASSIGNED) 반환
    # -----------------------------------------------------------------------------
    return {
        "user_sdwt_prod": UNASSIGNED_USER_SDWT_PROD,
        "classification_source": Email.ClassificationSource.UNASSIGNED,
    }


def _unassigned_mailbox_query() -> Q:
    """UNASSIGNED(미분류) 메일함 조건(Q)을 반환합니다.

    입력:
        없음.
    반환:
        UNASSIGNED 메일함에 해당하는 Q 객체.
    부작용:
        없음.
    오류:
        없음.
    """

    # 레거시 데이터 호환을 위해 NULL/빈값/rp-unclassified를 함께 포함합니다.
    return (
        Q(user_sdwt_prod__isnull=True)
        | Q(user_sdwt_prod__exact="")
        | Q(user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD)
        | Q(user_sdwt_prod="rp-unclassified")
    )


def count_unassigned_emails_for_sender_id(*, sender_id: str) -> int:
    """발신자(sender_id)의 UNASSIGNED 메일 개수를 반환합니다.

    입력:
        sender_id: Email.sender_id 값.
    반환:
        UNASSIGNED 메일 개수.
    부작용:
        없음. 조회 전용.
    오류:
        sender_id가 비어 있으면 0 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(sender_id, str) or not sender_id.strip():
        return 0

    # -----------------------------------------------------------------------------
    # 2) 카운트 조회
    # -----------------------------------------------------------------------------
    normalized = sender_id.strip()
    return (
        Email.objects.filter(sender_id=normalized)
        .filter(_unassigned_mailbox_query())
        .count()
    )


def list_unassigned_email_ids_for_sender_id(*, sender_id: str) -> list[int]:
    """발신자(sender_id)의 UNASSIGNED 메일 id 목록을 반환합니다.

    입력:
        sender_id: Email.sender_id 값.
    반환:
        UNASSIGNED 메일 id 리스트.
    부작용:
        없음. 조회 전용.
    오류:
        sender_id가 비어 있으면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(sender_id, str) or not sender_id.strip():
        return []

    # -----------------------------------------------------------------------------
    # 2) id 목록 조회
    # -----------------------------------------------------------------------------
    normalized = sender_id.strip()
    return list(
        Email.objects.filter(sender_id=normalized)
        .filter(_unassigned_mailbox_query())
        .order_by("id")
        .values_list("id", flat=True)
    )


def list_pending_rag_emails(*, limit: int) -> list[Email]:
    """rag_doc_id가 없는 이메일 목록을 limit 만큼 반환합니다.

    입력:
        limit: 조회할 최대 건수.
    반환:
        Email 리스트.
    부작용:
        없음. 조회 전용.
    오류:
        limit <= 0이면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if limit <= 0:
        return []

    # -----------------------------------------------------------------------------
    # 2) 조회 실행
    # -----------------------------------------------------------------------------
    queryset = (
        Email.objects.filter(
            Q(rag_doc_id__isnull=True) | Q(rag_doc_id=""),
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
        )
        .order_by("id")[:limit]
    )
    return list(queryset)


def list_pending_email_outbox(
    *,
    limit: int,
    ready_before: datetime | None = None,
    for_update: bool = False,
    skip_locked: bool = True,
) -> list[EmailOutbox]:
    """처리 대기 중인 EmailOutbox 항목을 반환합니다.

    입력:
        limit: 조회할 최대 건수.
        ready_before: 처리 가능 시각 상한.
        for_update: select_for_update 적용 여부.
        skip_locked: 잠긴 행 건너뛰기 여부.
    반환:
        EmailOutbox 리스트.
    부작용:
        없음. 조회 전용.
    오류:
        limit <= 0이면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if limit <= 0:
        return []

    # -----------------------------------------------------------------------------
    # 2) 조회 쿼리 구성
    # -----------------------------------------------------------------------------
    when = _normalize_time(ready_before)
    queryset = EmailOutbox.objects.filter(
        status=EmailOutbox.Status.PENDING,
        available_at__lte=when,
    ).order_by("id")
    if for_update:
        queryset = queryset.select_for_update(skip_locked=skip_locked)
    queryset = queryset[:limit]
    return list(queryset)


def list_email_id_user_sdwt_by_ids(*, email_ids: list[int]) -> dict[int, str | None]:
    """Email id 목록으로 (id -> user_sdwt_prod) 매핑을 반환합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        {id: user_sdwt_prod} 매핑.
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 빈 dict 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return {}

    # -----------------------------------------------------------------------------
    # 2) 매핑 조회
    # -----------------------------------------------------------------------------
    rows = Email.objects.filter(id__in=email_ids).values("id", "user_sdwt_prod")
    return {row["id"]: row["user_sdwt_prod"] for row in rows}


def list_email_ids_by_sender_after(
    *,
    sender_id: str,
    received_at_gte: datetime,
) -> list[int]:
    """sender_id의 특정 시각 이후 이메일 id 목록을 반환합니다.

    입력:
        sender_id: Email.sender_id 값.
        received_at_gte: 기준 시각(이 시각 이상 수신).
    반환:
        Email id 리스트.
    부작용:
        없음. 조회 전용.
    오류:
        sender_id가 비어 있으면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(sender_id, str) or not sender_id.strip():
        return []

    # -----------------------------------------------------------------------------
    # 2) id 목록 조회
    # -----------------------------------------------------------------------------
    normalized = sender_id.strip()
    return list(
        Email.objects.filter(sender_id=normalized, received_at__gte=received_at_gte)
        .values_list("id", flat=True)
        .order_by("id")
    )


def contains_unassigned_emails(*, email_ids: list[int]) -> bool:
    """email_ids 중 UNASSIGNED(미분류) 메일이 포함되는지 확인합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        UNASSIGNED 포함 여부.
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 False 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return False

    # -----------------------------------------------------------------------------
    # 2) 포함 여부 조회
    # -----------------------------------------------------------------------------
    return Email.objects.filter(id__in=email_ids).filter(_unassigned_mailbox_query()).exists()


def list_emails_by_ids(*, email_ids: list[int]) -> QuerySet[Email]:
    """Email id 목록으로 Email QuerySet을 조회합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        Email QuerySet(조회 결과).
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return Email.objects.none()
    return Email.objects.filter(id__in=email_ids).order_by("id")


def get_filtered_emails(
    *,
    accessible_user_sdwt_prods: set[str],
    is_privileged: bool,
    can_view_unassigned: bool,
    mailbox_user_sdwt_prod: str,
    search: str,
    sender: str,
    recipient: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> QuerySet[Email]:
    """검색/기간/발신자/수신자 조건으로 Email QuerySet을 필터링해 반환합니다.

    입력:
        accessible_user_sdwt_prods: 접근 가능한 user_sdwt_prod 집합.
        is_privileged: 특권 사용자 여부(메일함 필터 생략).
        can_view_unassigned: UNASSIGNED 조회 가능 여부.
        mailbox_user_sdwt_prod: 특정 메일함 필터 값.
        search: 자유 검색(제목/본문/발신자/참여자).
        sender: 발신자 문자열 필터.
        recipient: 수신자 문자열 필터(To/Cc).
        date_from: 시작 시각(포함).
        date_to: 종료 시각(포함).
    반환:
        최신순으로 정렬된 Email QuerySet.
    부작용:
        없음. 조회 전용.
    오류:
        접근 범위가 비어 있고 특권이 아니면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 접근 범위 검증
    # -----------------------------------------------------------------------------
    if not is_privileged and not accessible_user_sdwt_prods:
        return Email.objects.none()

    # -----------------------------------------------------------------------------
    # 2) 기본 쿼리 구성 및 권한 필터
    # -----------------------------------------------------------------------------
    queryset = Email.objects.order_by("-received_at", "-id")
    if not is_privileged:
        queryset = queryset.filter(user_sdwt_prod__in=accessible_user_sdwt_prods)

    if not can_view_unassigned:
        queryset = queryset.exclude(_unassigned_mailbox_query())

    # -----------------------------------------------------------------------------
    # 3) 검색/기간 필터 적용
    # -----------------------------------------------------------------------------
    if mailbox_user_sdwt_prod:
        queryset = queryset.filter(user_sdwt_prod=mailbox_user_sdwt_prod)

    if search:
        normalized_participant_search = search.lower()
        queryset = queryset.filter(
            Q(subject__icontains=search)
            | Q(body_text__icontains=search)
            | Q(sender__icontains=search)
            | Q(participants_search__contains=normalized_participant_search)
        )
    if sender:
        queryset = queryset.filter(sender__icontains=sender)
    if recipient:
        queryset = queryset.filter(participants_search__contains=recipient.lower())
    if date_from:
        queryset = queryset.filter(received_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(received_at__lte=date_to)

    return queryset


def get_sent_emails(
    *,
    sender_id: str,
    search: str,
    sender: str,
    recipient: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> QuerySet[Email]:
    """발신자(sender_id) 기준으로 보낸 메일 QuerySet을 반환합니다.

    입력:
        sender_id: Email.sender_id (KNOX ID, 발신자 식별자).
        search: 자유 검색(제목/본문/발신자/참여자).
        sender: 발신자 문자열 필터.
        recipient: 수신자 문자열 필터(To/Cc).
        date_from: 시작 시각(포함).
        date_to: 종료 시각(포함).
    반환:
        최신순으로 정렬된 Email QuerySet.
    부작용:
        없음. 조회 전용.
    오류:
        sender_id가 비어 있으면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증 및 기본 쿼리 구성
    # -----------------------------------------------------------------------------
    if not isinstance(sender_id, str) or not sender_id.strip():
        return Email.objects.none()

    queryset = Email.objects.filter(sender_id=sender_id.strip()).order_by("-received_at", "-id")

    # -----------------------------------------------------------------------------
    # 2) 검색/기간 필터 적용
    # -----------------------------------------------------------------------------
    if search:
        normalized_participant_search = search.lower()
        queryset = queryset.filter(
            Q(subject__icontains=search)
            | Q(body_text__icontains=search)
            | Q(sender__icontains=search)
            | Q(participants_search__contains=normalized_participant_search)
        )
    if sender:
        queryset = queryset.filter(sender__icontains=sender)
    if recipient:
        queryset = queryset.filter(participants_search__contains=recipient.lower())
    if date_from:
        queryset = queryset.filter(received_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(received_at__lte=date_to)

    return queryset


def list_distinct_email_mailboxes() -> list[str]:
    """Email 테이블에서 중복 제거된 user_sdwt_prod 목록을 반환합니다.

    입력:
        없음.
    반환:
        중복 제거된 user_sdwt_prod 문자열 리스트(정렬됨).
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) distinct 쿼리 수행
    # -----------------------------------------------------------------------------
    queryset = (
        Email.objects.exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
        .order_by("user_sdwt_prod")
    )
    return list(queryset)


def list_privileged_email_mailboxes() -> list[str]:
    """특권 사용자(staff/superuser)가 볼 메일함(user_sdwt_prod) 목록을 반환합니다.

    입력:
        없음.
    반환:
        특권 사용자에게 노출할 user_sdwt_prod 목록(정렬됨).
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 계정/메일 기준 목록 병합
    # -----------------------------------------------------------------------------
    known = set(list_distinct_user_sdwt_prod_values())
    known.update(list_distinct_email_mailboxes())
    known.add(UNASSIGNED_USER_SDWT_PROD)
    return sorted({val for val in known if isinstance(val, str) and val.strip()})


def get_email_by_id(*, email_id: int) -> Email | None:
    """email_id로 Email을 조회하고 없으면 None을 반환합니다.

    입력:
        email_id: Email PK(이메일 ID).
    반환:
        Email 인스턴스 또는 None.
    부작용:
        없음. 조회 전용.
    오류:
        없으면 None 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) PK 조회
    # -----------------------------------------------------------------------------
    try:
        return Email.objects.get(id=email_id)
    except Email.DoesNotExist:
        return None


def get_email_for_update(*, email_id: int) -> Email:
    """Email을 행 잠금(select_for_update)으로 조회합니다.

    입력:
        email_id: Email PK(이메일 ID).
    반환:
        Email 인스턴스.
    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.
    오류:
        Email.DoesNotExist 예외가 발생할 수 있습니다.
    """

    return Email.objects.select_for_update().get(id=email_id)


def list_emails_for_update(*, email_ids: Sequence[int]) -> list[Email]:
    """Email 목록을 행 잠금(select_for_update)으로 조회합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        Email 인스턴스 리스트(없으면 빈 리스트).
    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return []
    normalized = [int(value) for value in email_ids if isinstance(value, int) or str(value).isdigit()]
    if not normalized:
        return []

    # -----------------------------------------------------------------------------
    # 2) 행 잠금 조회
    # -----------------------------------------------------------------------------
    return list(Email.objects.select_for_update().filter(id__in=normalized))


def get_email_asset_by_id(*, asset_id: int) -> EmailAsset | None:
    """asset_id로 EmailAsset을 조회하고 없으면 None을 반환합니다.

    입력:
        asset_id: EmailAsset 기본 키.
    반환:
        EmailAsset 인스턴스 또는 None.
    부작용:
        없음. 조회 전용.
    오류:
        없으면 None 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    if not isinstance(asset_id, int):
        return None

    # -----------------------------------------------------------------------------
    # 2) 조회 수행
    # -----------------------------------------------------------------------------
    try:
        return EmailAsset.objects.get(id=asset_id)
    except EmailAsset.DoesNotExist:
        return None


def get_email_asset_by_email_and_sequence(*, email_id: int, sequence: int) -> EmailAsset | None:
    """email_id/sequence로 EmailAsset을 조회하고 없으면 None을 반환합니다.

    입력:
        email_id: Email 기본 키.
        sequence: 이미지 순번.
    반환:
        EmailAsset 인스턴스 또는 None.
    부작용:
        없음. 조회 전용.
    오류:
        없으면 None 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    if not isinstance(email_id, int) or not isinstance(sequence, int):
        return None

    # -----------------------------------------------------------------------------
    # 2) 조회 수행
    # -----------------------------------------------------------------------------
    try:
        return EmailAsset.objects.get(email_id=email_id, sequence=sequence)
    except EmailAsset.DoesNotExist:
        return None


def list_email_assets_by_email_ids(*, email_ids: Sequence[int]) -> QuerySet[EmailAsset]:
    """Email id 목록에 해당하는 EmailAsset QuerySet을 반환합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        EmailAsset QuerySet(조회 결과).
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return EmailAsset.objects.none()
    normalized = [int(value) for value in email_ids if isinstance(value, int) or str(value).isdigit()]
    if not normalized:
        return EmailAsset.objects.none()

    # -----------------------------------------------------------------------------
    # 2) QuerySet 반환
    # -----------------------------------------------------------------------------
    return EmailAsset.objects.filter(email_id__in=normalized).order_by("email_id", "sequence")


def list_claimable_email_assets(
    *,
    now: datetime,
    max_attempts: int,
) -> QuerySet[EmailAsset]:
    """OCR 처리 대상 EmailAsset QuerySet을 반환합니다.

    입력:
        now: 기준 시각(락 만료 판단용).
        max_attempts: 최대 시도 횟수.
    반환:
        OCR 처리 대상 EmailAsset QuerySet.
    부작용:
        없음. 조회 전용.
    오류:
        입력이 잘못되면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(now, datetime):
        return EmailAsset.objects.none()
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        return EmailAsset.objects.none()

    # -----------------------------------------------------------------------------
    # 2) OCR 처리 대상 필터 구성
    # -----------------------------------------------------------------------------
    return (
        EmailAsset.objects.filter(
            Q(ocr_status=EmailAsset.OcrStatus.PENDING)
            | Q(ocr_status=EmailAsset.OcrStatus.FAILED, ocr_attempt_count__lt=max_attempts)
            | Q(ocr_status=EmailAsset.OcrStatus.FAILED, ocr_attempt_count__isnull=True)
            | Q(ocr_status=EmailAsset.OcrStatus.PROCESSING, ocr_lock_expires_at__lte=now)
            | Q(ocr_status=EmailAsset.OcrStatus.PROCESSING, ocr_lock_expires_at__isnull=True)
        )
        .order_by("id")
    )


def list_claimable_email_assets_for_update(
    *,
    now: datetime,
    max_attempts: int,
    limit: int,
) -> list[EmailAsset]:
    """OCR 처리 대상 EmailAsset을 행 잠금으로 조회해 반환합니다.

    입력:
        now: 기준 시각(락 만료 판단용).
        max_attempts: 최대 시도 횟수.
        limit: 최대 조회 개수.
    반환:
        EmailAsset 인스턴스 리스트.
    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) limit 검증
    # -----------------------------------------------------------------------------
    if not isinstance(limit, int) or limit <= 0:
        return []

    # -----------------------------------------------------------------------------
    # 2) 행 잠금 조회
    # -----------------------------------------------------------------------------
    queryset = list_claimable_email_assets(now=now, max_attempts=max_attempts)
    return list(queryset.select_for_update(skip_locked=True)[:limit])


def list_email_asset_keys_by_email_ids(*, email_ids: Sequence[int]) -> list[str]:
    """Email id 목록에 연결된 EmailAsset object_key 목록을 반환합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        object_key 문자열 리스트(빈 값 제외).
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) QuerySet 조회
    # -----------------------------------------------------------------------------
    assets = list_email_assets_by_email_ids(email_ids=email_ids)

    # -----------------------------------------------------------------------------
    # 2) 키 목록 구성
    # -----------------------------------------------------------------------------
    keys = [row.object_key for row in assets if isinstance(row.object_key, str) and row.object_key.strip()]
    return keys


def build_email_ocr_text(*, email_id: int) -> str:
    """이메일에 연결된 OCR 텍스트를 sequence 순서로 합쳐 반환합니다.

    입력:
        email_id: Email 기본 키.
    반환:
        결합된 OCR 텍스트(없으면 빈 문자열).
    부작용:
        없음. 조회 전용.
    오류:
        email_id가 유효하지 않으면 빈 문자열 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(email_id, int):
        return ""

    # -----------------------------------------------------------------------------
    # 2) OCR 텍스트 조회
    # -----------------------------------------------------------------------------
    rows = (
        EmailAsset.objects.filter(email_id=email_id, ocr_status=EmailAsset.OcrStatus.DONE)
        .exclude(ocr_text="")
        .order_by("sequence")
        .values_list("ocr_text", flat=True)
    )

    # -----------------------------------------------------------------------------
    # 3) 결합 결과 반환
    # -----------------------------------------------------------------------------
    return "\n".join([text for text in rows if text])


def has_unprocessed_email_assets(*, email_id: int, max_attempts: int) -> bool:
    """해당 Email에 OCR 미처리 자산이 존재하는지 확인합니다.

    입력:
        email_id: Email 기본 키.
        max_attempts: 최대 시도 횟수.
    반환:
        미처리 자산이 있으면 True.
    부작용:
        없음. 조회 전용.
    오류:
        입력이 유효하지 않으면 False 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(email_id, int):
        return False
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        return False

    # -----------------------------------------------------------------------------
    # 2) 처리 완료 조건 구성
    # -----------------------------------------------------------------------------
    done_or_exhausted = Q(ocr_status=EmailAsset.OcrStatus.DONE) | Q(
        ocr_status=EmailAsset.OcrStatus.FAILED, ocr_attempt_count__gte=max_attempts
    )

    # -----------------------------------------------------------------------------
    # 3) 미처리 자산 존재 여부 확인
    # -----------------------------------------------------------------------------
    return EmailAsset.objects.filter(email_id=email_id).exclude(done_or_exhausted).exists()


def user_can_bulk_delete_emails(
    *,
    email_ids: list[int],
    accessible_user_sdwt_prods: set[str],
    sender_id: str | None = None,
) -> bool:
    """요청한 email_ids가 모두 접근 가능한 user_sdwt_prod 범위인지 검사합니다.

    입력:
        email_ids: 삭제 요청 Email id 목록.
        accessible_user_sdwt_prods: 접근 가능한 user_sdwt_prod 집합.
        sender_id: 본인 발신자 ID(옵션).
    반환:
        모든 id가 접근 가능 범위면 True.
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 False 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return False

    # -----------------------------------------------------------------------------
    # 2) 접근 범위 필터 구성
    # -----------------------------------------------------------------------------
    mailbox_filter = Q(user_sdwt_prod__in=accessible_user_sdwt_prods)
    normalized_sender_id = sender_id.strip() if isinstance(sender_id, str) else ""
    if normalized_sender_id:
        mailbox_filter |= Q(sender_id=normalized_sender_id)

    # -----------------------------------------------------------------------------
    # 3) 접근 가능한 메일 개수 비교
    # -----------------------------------------------------------------------------
    owned_count = Email.objects.filter(id__in=email_ids).filter(mailbox_filter).count()
    return owned_count == len(email_ids)
