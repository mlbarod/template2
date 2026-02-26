# =============================================================================
# 모듈: Drone SOP 알림 정책
# 주요 기능: 채널 전송 실패 마킹, target_user_sdwt_prod 누락 행의 실패 처리
# 주요 가정: 누락된 대상은 반복 재시도를 막기 위해 실패로 마킹합니다.
# =============================================================================
"""Drone SOP 알림 정책 유틸리티."""

from __future__ import annotations

from typing import Sequence

from django.db import transaction
from django.db.models import Q

from ...models import DroneSOP

# 허용 채널 필드(외부 입력 방어용)
_ALLOWED_CHANNEL_FIELDS = frozenset({"send_jira", "send_messenger", "send_mail"})
_REASON_FIELD_BY_CHANNEL = {
    "send_jira": "jira_reason",
    "send_messenger": "messenger_reason",
    "send_mail": "mail_reason",
}

# 채널 상태 사유 코드
REASON_DISABLED_BY_POLICY = "disabled_by_policy"
REASON_NO_VALID_TARGET = "no_valid_target"
REASON_CONFIG_MISSING = "config_missing"
REASON_CHANNEL_CONFIG_MISSING = "channel_config_missing"
REASON_CHANNEL_CONFIG_INVALID = "channel_config_invalid"
REASON_TEMPLATE_MISSING = "template_missing"
REASON_RECEIVER_NOT_FOUND = "receiver_not_found"
REASON_SEND_FAILED = "send_failed"


def _normalize_channel_fields(channel_fields: Sequence[str]) -> list[str]:
    """허용 채널 필드 목록만 정규화해서 반환합니다."""

    normalized_fields: list[str] = []
    for field in channel_fields:
        if field in _ALLOWED_CHANNEL_FIELDS and field not in normalized_fields:
            normalized_fields.append(field)
    return normalized_fields


def mark_pending_channels_as_failed(
    *,
    sop_ids: Sequence[int],
    channel_fields: Sequence[str],
    failure_reason: str | None = None,
    mark_instant_inform: bool = False,
) -> None:
    """미전송(0/NULL) 채널 상태를 실패(-1)로 갱신합니다.

    인자:
        sop_ids: DroneSOP ID 목록.
        channel_fields: 실패 처리할 채널 필드 목록(send_jira/send_messenger/send_mail).
        failure_reason: 사유 코드(옵션).
        mark_instant_inform: True면 instant_inform=1 행도 -1로 갱신.

    반환:
        없음.

    부작용:
        send_* 필드와(선택적으로) instant_inform 필드를 업데이트합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    if not sop_ids or not channel_fields:
        return

    normalized_fields = _normalize_channel_fields(channel_fields)
    if not normalized_fields:
        return

    # -----------------------------------------------------------------------------
    # 2) 채널별 실패 상태 갱신
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        for field in normalized_fields:
            pending_filter = Q(**{field: 0}) | Q(**{f"{field}__isnull": True})
            updates = {field: -1}
            reason_field = _REASON_FIELD_BY_CHANNEL.get(field)
            if reason_field and isinstance(failure_reason, str) and failure_reason:
                updates[reason_field] = failure_reason
            DroneSOP.objects.filter(id__in=sop_ids).filter(pending_filter).update(**updates)
        if mark_instant_inform:
            DroneSOP.objects.filter(id__in=sop_ids, instant_inform=1).update(instant_inform=-1)


def mark_pending_channels_as_disabled(
    *,
    sop_ids: Sequence[int],
    channel_fields: Sequence[str],
    disable_reason: str = REASON_DISABLED_BY_POLICY,
) -> None:
    """미전송(0/NULL) 채널의 비활성화 사유를 기록합니다.

    인자:
        sop_ids: DroneSOP ID 목록.
        channel_fields: 사유를 기록할 채널 필드 목록(send_jira/send_messenger/send_mail).
        disable_reason: 비활성화 사유 코드.

    반환:
        없음.

    부작용:
        채널별 reason 필드를 업데이트합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    if not sop_ids or not channel_fields:
        return

    normalized_fields = _normalize_channel_fields(channel_fields)
    if not normalized_fields:
        return

    # -----------------------------------------------------------------------------
    # 2) 채널별 비활성화 사유 기록
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        for field in normalized_fields:
            reason_field = _REASON_FIELD_BY_CHANNEL.get(field)
            if not reason_field:
                continue
            pending_filter = Q(**{field: 0}) | Q(**{f"{field}__isnull": True})
            DroneSOP.objects.filter(id__in=sop_ids).filter(pending_filter).update(**{reason_field: disable_reason})


# =============================================================================
# 누락 대상 실패 처리
# =============================================================================

def mark_missing_target_as_failed(*, sop_ids: Sequence[int]) -> None:
    """target_user_sdwt_prod 미확정 SOP를 실패 처리합니다.

    인자:
        sop_ids: DroneSOP ID 목록.

    반환:
        없음.

    부작용:
        - send_jira/send_messenger/send_mail을 실패(-1)로 갱신
        - instant_inform=1인 경우 instant_inform을 실패(-1)로 갱신
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    if not sop_ids:
        return

    # -----------------------------------------------------------------------------
    # 2) 상태 실패 처리
    # -----------------------------------------------------------------------------
    mark_pending_channels_as_failed(
        sop_ids=sop_ids,
        channel_fields=["send_jira", "send_messenger", "send_mail"],
        failure_reason=REASON_NO_VALID_TARGET,
        mark_instant_inform=True,
    )


__all__ = [
    "REASON_CHANNEL_CONFIG_INVALID",
    "REASON_CHANNEL_CONFIG_MISSING",
    "REASON_CONFIG_MISSING",
    "REASON_DISABLED_BY_POLICY",
    "REASON_NO_VALID_TARGET",
    "REASON_RECEIVER_NOT_FOUND",
    "REASON_SEND_FAILED",
    "REASON_TEMPLATE_MISSING",
    "mark_missing_target_as_failed",
    "mark_pending_channels_as_disabled",
    "mark_pending_channels_as_failed",
]
