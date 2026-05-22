# =============================================================================
# 모듈: Drone SOP 채널 수신인 서비스
# 주요 함수: replace_drone_sop_channel_recipients
# 주요 가정: 가입 사용자는 account_user FK, 미가입자는 외부 스냅샷 knox_id로 저장합니다.
# =============================================================================
"""Drone SOP 채널별 수신인 갱신 서비스 모음."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models.functions import Lower

import api.account.selectors as account_selectors

from ... import selectors
from ...models import DroneSopTargetRecipient, DroneSopTarget
from .recipient_normalization import (
    CONTACT_FIELD_BY_CHANNEL,
    normalize_external_knox_ids as _normalize_external_knox_ids,
    normalize_line_id as _normalize_line_id,
    normalize_recipient_channel,
    normalize_target_user_sdwt_prod as _normalize_target_user_sdwt_prod,
    normalize_user_ids as _normalize_user_ids,
)
from .user_sdwt_channel import (
    ensure_drone_sop_notification_target,
    get_or_create_drone_sop_target_by_name,
)


def _get_or_create_recipient_row(
    *,
    target: DroneSopTarget | None = None,
    target_user_sdwt_prod: str | None = None,
    channel: str,
    user_id: int | None = None,
    external_knox_id: str = "",
    actor: Any | None = None,
) -> DroneSopTargetRecipient:
    """동시 생성 충돌을 흡수하며 수신인 row를 조회 또는 생성합니다."""

    if target is None:
        normalized_target = _normalize_target_user_sdwt_prod(target_user_sdwt_prod)
        if not normalized_target:
            raise ValueError("targetUserSdwtProd is required")
        target = get_or_create_drone_sop_target_by_name(target_user_sdwt_prod=normalized_target)

    normalized_external_knox_id = external_knox_id.strip().lower() if external_knox_id else ""
    if user_id is None and not normalized_external_knox_id:
        raise ValueError("user_id or external_knox_id is required")
    if user_id is not None and normalized_external_knox_id:
        raise ValueError("user_id and external_knox_id cannot be used together")

    lookup = {
        "target": target,
        "channel": channel,
    }
    create_kwargs = dict(lookup)
    if user_id is not None:
        lookup["user_id"] = user_id
        create_kwargs["user_id"] = user_id
    else:
        lookup["external_knox_id"] = normalized_external_knox_id
        create_kwargs["external_knox_id"] = normalized_external_knox_id

    try:
        with transaction.atomic():
            return DroneSopTargetRecipient.objects.create(**create_kwargs)
    except IntegrityError:
        existing = (
            DroneSopTargetRecipient.objects.select_for_update()
            .filter(**lookup)
            .order_by("id")
            .first()
        )
        if existing is None:
            raise
        return existing


def _lock_recipient_target_for_replace(*, target_id: int) -> DroneSopTarget:
    """수신인 교체 작업을 target 단위로 직렬화하기 위해 target row를 잠급니다."""

    return DroneSopTarget.objects.select_for_update().get(id=target_id)


def promote_drone_sop_external_recipients_for_user(*, user: Any) -> dict[str, int]:
    """가입된 사용자 knox_id와 같은 외부 수신인 row를 user FK row로 승격합니다.

    입력:
    - user: 가입 또는 knox_id 갱신이 완료된 Django 사용자 객체

    반환:
    - dict[str, int]: promoted/deleted 카운트

    부작용:
    - DroneSopTargetRecipient의 external_knox_id row를 user FK row로 변경
    - 이미 같은 target/channel/user row가 있으면 외부 row 삭제

    오류:
    - 없음
    """

    knox_id = getattr(user, "knox_id", None)
    user_id = getattr(user, "id", None)
    is_active = bool(getattr(user, "is_active", False))
    normalized_knox_id = knox_id.strip().lower() if isinstance(knox_id, str) else ""
    if not user_id or not is_active or not normalized_knox_id:
        return {"promoted": 0, "deleted": 0}

    promoted = 0
    deleted = 0
    with transaction.atomic():
        rows = list(
            DroneSopTargetRecipient.objects.select_for_update()
            .filter(user__isnull=True)
            .exclude(external_knox_id__exact="")
            .annotate(external_knox_lookup=Lower("external_knox_id"))
            .filter(external_knox_lookup=normalized_knox_id)
            .order_by("target_id", "channel", "id")
        )
        for row in rows:
            existing = (
                DroneSopTargetRecipient.objects.select_for_update()
                .filter(
                    target_id=row.target_id,
                    channel=row.channel,
                    user_id=user_id,
                )
                .exclude(id=row.id)
                .first()
            )
            if existing is not None:
                row.delete()
                deleted += 1
                continue
            row.user_id = user_id
            row.external_knox_id = ""
            row.save(update_fields=["user", "external_knox_id", "updated_at"])
            promoted += 1
    return {"promoted": promoted, "deleted": deleted}


def replace_drone_sop_channel_recipients(
    *,
    line_id: str,
    target_user_sdwt_prod: str,
    channel: str,
    user_ids: Iterable[Any],
    external_knox_ids: Iterable[Any] | None = None,
    actor: Any | None = None,
) -> dict[str, object]:
    """Drone SOP target/channel 수신인 목록을 사용자/외부 스냅샷으로 교체합니다.

    target_user_sdwt_prod와 line_id는 Drone target 기준으로 관리하며,
    외부 소속표에 없어도 저장할 수 있습니다.

    입력:
    - line_id: target 소유 라인
    - target_user_sdwt_prod: 수신인 설정 대상 소속
    - channel: mail 또는 messenger
    - user_ids: 최종 저장할 account_user id 목록
    - external_knox_ids: 최종 저장할 외부 스냅샷 knox_id 목록
    - actor: 변경을 수행한 사용자

    반환:
    - dict[str, object]: 갱신 결과와 최신 수신인 목록

    부작용:
    - DroneSopTargetRecipient 생성/삭제

    오류:
    - ValueError: target/channel/user_ids/external_knox_ids가 유효하지 않을 때
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화 및 검증
    # -----------------------------------------------------------------------------
    normalized_line_id = _normalize_line_id(line_id)
    if not normalized_line_id:
        raise ValueError("lineId is required")
    normalized_target = _normalize_target_user_sdwt_prod(target_user_sdwt_prod)
    if not normalized_target:
        raise ValueError("targetUserSdwtProd is required")
    normalized_channel = normalize_recipient_channel(channel)
    normalized_user_ids = _normalize_user_ids(user_ids)
    normalized_external_knox_ids = _normalize_external_knox_ids(external_knox_ids)

    active_user_ids = account_selectors.list_active_user_ids_by_ids(user_ids=normalized_user_ids)
    missing_user_ids = sorted(set(normalized_user_ids) - active_user_ids)
    if missing_user_ids:
        raise ValueError("active users not found")
    contact_field = CONTACT_FIELD_BY_CHANNEL[normalized_channel]
    contact_user_ids = account_selectors.list_active_user_ids_with_contact_by_ids(
        user_ids=normalized_user_ids,
        contact_field=contact_field,
    )
    missing_contact_user_ids = sorted(active_user_ids - contact_user_ids)
    if missing_contact_user_ids:
        if normalized_channel == DroneSopTargetRecipient.Channels.MAIL:
            raise ValueError("mail recipients require email")
        raise ValueError("messenger recipients require knox_id")
    external_snapshots = account_selectors.get_external_affiliation_snapshots_by_knox_lookup_keys(
        knox_ids=normalized_external_knox_ids
    )
    missing_external_knox_ids = sorted(set(normalized_external_knox_ids) - set(external_snapshots.keys()))
    if missing_external_knox_ids:
        raise ValueError("external recipients not found")
    joined_external_knox_ids = account_selectors.list_active_user_knox_lookup_keys_by_knox_ids(
        knox_ids=normalized_external_knox_ids
    )
    if joined_external_knox_ids:
        raise ValueError("external recipients must be unregistered users")

    target, _ = ensure_drone_sop_notification_target(
        line_id=normalized_line_id,
        target_user_sdwt_prod=normalized_target,
        actor=actor,
    )

    # -----------------------------------------------------------------------------
    # 2) 기존 행 잠금 후 삭제 기반 교체 수행
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        locked_target = _lock_recipient_target_for_replace(target_id=target.id)
        existing_rows = list(
            DroneSopTargetRecipient.objects.select_for_update().filter(
                target=locked_target,
                channel=normalized_channel,
            )
        )
        target_user_id_set = set(normalized_user_ids)
        target_external_knox_id_set = set(normalized_external_knox_ids)
        delete_ids = [
            row.id
            for row in existing_rows
            if (
                (row.user_id is not None and row.user_id not in target_user_id_set)
                or (row.user_id is None and row.external_knox_id not in target_external_knox_id_set)
            )
        ]
        if delete_ids:
            DroneSopTargetRecipient.objects.filter(id__in=delete_ids).delete()

        existing_user_ids = {
            row.user_id
            for row in existing_rows
            if row.user_id is not None and row.user_id in target_user_id_set and row.id not in delete_ids
        }
        existing_external_knox_ids = {
            row.external_knox_id
            for row in existing_rows
            if row.user_id is None and row.external_knox_id in target_external_knox_id_set and row.id not in delete_ids
        }

        for user_id in normalized_user_ids:
            if user_id in existing_user_ids:
                continue
            _get_or_create_recipient_row(
                target=locked_target,
                target_user_sdwt_prod=normalized_target,
                channel=normalized_channel,
                user_id=user_id,
                actor=actor,
            )
            existing_user_ids.add(user_id)
        for external_knox_id in normalized_external_knox_ids:
            if external_knox_id in existing_external_knox_ids:
                continue
            _get_or_create_recipient_row(
                target=locked_target,
                target_user_sdwt_prod=normalized_target,
                channel=normalized_channel,
                external_knox_id=external_knox_id,
                actor=actor,
            )
            existing_external_knox_ids.add(external_knox_id)

    # -----------------------------------------------------------------------------
    # 3) 최신 조회 결과 반환
    # -----------------------------------------------------------------------------
    recipients = selectors.list_drone_sop_channel_recipients(
        line_id=normalized_line_id,
        target_user_sdwt_prod=normalized_target,
        channel=normalized_channel,
    )
    return {
        "lineId": normalized_line_id,
        "targetUserSdwtProd": normalized_target,
        "channel": normalized_channel,
        "recipients": recipients,
    }


__all__ = [
    "normalize_recipient_channel",
    "promote_drone_sop_external_recipients_for_user",
    "replace_drone_sop_channel_recipients",
]
