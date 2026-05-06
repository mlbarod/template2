# =============================================================================
# 모듈: Drone SOP 채널 수신인 서비스
# 주요 함수: replace_drone_sop_channel_recipients
# 주요 가정: 수신인은 account_user FK만 허용하며 외부 주소는 저장하지 않습니다.
# =============================================================================
"""Drone SOP 채널별 수신인 갱신 서비스 모음."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

import api.account.selectors as account_selectors

from ... import selectors
from ...models import DroneSopChannelRecipient
from .user_sdwt_channel import ensure_drone_sop_notification_target


VALID_RECIPIENT_CHANNELS = {
    DroneSopChannelRecipient.Channels.MAIL,
    DroneSopChannelRecipient.Channels.MESSENGER,
}

CONTACT_FIELD_BY_CHANNEL = {
    DroneSopChannelRecipient.Channels.MAIL: "email",
    DroneSopChannelRecipient.Channels.MESSENGER: "knox_id",
}


def normalize_recipient_channel(channel: str) -> str:
    """수신인 채널 값을 mail/messenger 중 하나로 정규화합니다.

    입력:
    - channel: 원본 채널 값

    반환:
    - str: 정규화된 채널 값

    부작용:
    - 없음

    오류:
    - ValueError: 지원하지 않는 채널일 때
    """

    normalized = channel.strip().lower() if isinstance(channel, str) else ""
    if normalized not in VALID_RECIPIENT_CHANNELS:
        raise ValueError("channel must be mail or messenger")
    return normalized


def _normalize_target_user_sdwt_prod(value: Any) -> str:
    """target_user_sdwt_prod 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_line_id(value: Any) -> str:
    """line_id 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_user_ids(user_ids: Iterable[Any]) -> list[int]:
    """사용자 id 목록을 양의 정수 기준으로 중복 제거합니다."""

    if isinstance(user_ids, (str, bytes)) or isinstance(user_ids, Mapping):
        raise ValueError("user_ids must be a list")
    if not isinstance(user_ids, Iterable):
        raise ValueError("user_ids must be a list")

    normalized: list[int] = []
    seen: set[int] = set()
    for value in user_ids:
        if isinstance(value, bool):
            raise ValueError("user_ids must contain only integers")
        if isinstance(value, int):
            user_id = value
        elif isinstance(value, str):
            try:
                user_id = int(value.strip())
            except ValueError:
                raise ValueError("user_ids must contain only integers")
        else:
            raise ValueError("user_ids must contain only integers")
        if user_id <= 0:
            raise ValueError("user_ids must contain only positive integers")
        if user_id in seen:
            continue
        seen.add(user_id)
        normalized.append(user_id)
    return normalized


def _get_or_create_recipient_row(
    *,
    line_id: str | None = None,
    target_user_sdwt_prod: str,
    channel: str,
    user_id: int,
    actor: Any | None,
) -> tuple[DroneSopChannelRecipient, bool]:
    """동시 생성 충돌을 흡수하며 수신인 row를 조회 또는 생성합니다."""

    created_by = actor if getattr(actor, "is_authenticated", False) else None
    try:
        with transaction.atomic():
            return DroneSopChannelRecipient.objects.create(
                target_user_sdwt_prod=target_user_sdwt_prod,
                channel=channel,
                user_id=user_id,
                created_by=created_by,
            ), True
    except IntegrityError:
        existing = (
            DroneSopChannelRecipient.objects.select_for_update()
            .filter(
                target_user_sdwt_prod__iexact=target_user_sdwt_prod,
                channel=channel,
                user_id=user_id,
            )
            .order_by("id")
            .first()
        )
        if existing is None:
            raise
        return existing, False


def replace_drone_sop_channel_recipients(
    *,
    line_id: str,
    target_user_sdwt_prod: str,
    channel: str,
    user_ids: Iterable[Any],
    actor: Any | None = None,
) -> dict[str, object]:
    """Drone SOP target/channel 수신인 목록을 사용자 id 스냅샷으로 교체합니다.

    target_user_sdwt_prod는 account_affiliation에 없어도 되지만,
    line_id는 기존 account_affiliation 라인 안에서만 허용합니다.

    입력:
    - line_id: target 소유 라인
    - target_user_sdwt_prod: 수신인 설정 대상 소속
    - channel: mail 또는 messenger
    - user_ids: 최종 저장할 account_user id 목록
    - actor: 변경을 수행한 사용자

    반환:
    - dict[str, object]: 갱신 결과와 최신 수신인 목록

    부작용:
    - DroneSopChannelRecipient 생성/재활성화/비활성화

    오류:
    - ValueError: target/channel/user_ids가 유효하지 않을 때
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
        if normalized_channel == DroneSopChannelRecipient.Channels.MAIL:
            raise ValueError("mail recipients require email")
        raise ValueError("messenger recipients require knox_id")

    ensure_drone_sop_notification_target(
        line_id=normalized_line_id,
        target_user_sdwt_prod=normalized_target,
        actor=actor,
    )

    # -----------------------------------------------------------------------------
    # 2) 기존 행 잠금 후 soft replace 수행
    # -----------------------------------------------------------------------------
    now = timezone.now()
    with transaction.atomic():
        existing_rows = list(
            DroneSopChannelRecipient.objects.select_for_update().filter(
                target_user_sdwt_prod__iexact=normalized_target,
                channel=normalized_channel,
            )
        )
        existing_by_user_id = {row.user_id: row for row in existing_rows}

        target_user_id_set = set(normalized_user_ids)
        deactivate_ids = [
            row.id
            for row in existing_rows
            if row.user_id not in target_user_id_set and row.is_active
        ]
        if deactivate_ids:
            DroneSopChannelRecipient.objects.filter(id__in=deactivate_ids).update(
                is_active=False,
                updated_at=now,
            )

        created_count = 0
        reactivated_count = 0
        for user_id in normalized_user_ids:
            existing = existing_by_user_id.get(user_id)
            if existing is None:
                existing, created = _get_or_create_recipient_row(
                    line_id=normalized_line_id,
                    target_user_sdwt_prod=normalized_target,
                    channel=normalized_channel,
                    user_id=user_id,
                    actor=actor,
                )
                existing_by_user_id[user_id] = existing
                if created:
                    created_count += 1
                    continue
            if not existing.is_active:
                existing.is_active = True
                existing.save(update_fields=["is_active", "updated_at"])
                reactivated_count += 1

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
        "created": created_count,
        "reactivated": reactivated_count,
        "deactivated": len(deactivate_ids),
    }


__all__ = [
    "normalize_recipient_channel",
    "replace_drone_sop_channel_recipients",
]
