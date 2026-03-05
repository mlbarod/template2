# =============================================================================
# 모듈: Drone SOP 채널 재시도 서비스
# 주요 기능: 실패(send_*=-1) 채널을 대기(0) 상태로 되돌려 다음 배치 재처리 허용
# 주요 가정: 채널 재시도는 사용자의 명시적 액션으로만 수행합니다.
# =============================================================================
"""Drone SOP 채널 재시도 서비스."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from ... import selectors

_CHANNEL_FIELD_MAP = {
    "jira": ("send_jira", "jira_reason"),
    "messenger": ("send_messenger", "messenger_reason"),
    "mail": ("send_mail", "mail_reason"),
}


@dataclass(frozen=True)
class DroneSopRetryChannelResult:
    """Drone SOP 단건 채널 재시도 요청 결과."""

    channel: str
    queued: bool = False
    already_pending: bool = False
    already_sent: bool = False
    updated_fields: dict[str, Any] = field(default_factory=dict)


def retry_drone_sop_channel(
    *,
    sop_id: int,
    channel: str,
) -> DroneSopRetryChannelResult:
    """실패 채널을 재시도 가능한 대기 상태로 되돌립니다.

    인자:
        sop_id: DroneSOP ID.
        channel: 채널 키(jira/messenger/mail).

    반환:
        DroneSopRetryChannelResult 결과 객체.

    부작용:
        - 실패 상태(send_*=-1)면 send_*=0, reason=NULL로 갱신합니다.
        - 이미 대기/완료 상태면 변경 없이 현재 상태를 반환합니다.

    오류:
        입력 검증 실패 또는 대상 미존재 시 ValueError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if sop_id <= 0:
        raise ValueError("sop_id must be a positive integer")

    normalized_channel = channel.strip().lower() if isinstance(channel, str) else ""
    channel_fields = _CHANNEL_FIELD_MAP.get(normalized_channel)
    if channel_fields is None:
        raise ValueError("channel must be one of: jira, messenger, mail")

    send_field, reason_field = channel_fields

    # -----------------------------------------------------------------------------
    # 2) 행 잠금 후 상태 전이
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        sop = selectors.get_drone_sop_for_update(sop_id=sop_id)
        if sop is None:
            raise ValueError("DroneSOP not found")

        raw_send_value = getattr(sop, send_field, 0)
        try:
            send_value = int(raw_send_value or 0)
        except (TypeError, ValueError):
            send_value = 0

        updated_fields: dict[str, Any] = {
            send_field: raw_send_value,
            reason_field: getattr(sop, reason_field, None),
        }

        if send_value < 0:
            setattr(sop, send_field, 0)
            setattr(sop, reason_field, None)
            sop.save(update_fields=[send_field, reason_field, "updated_at"])
            updated_fields[send_field] = 0
            updated_fields[reason_field] = None
            return DroneSopRetryChannelResult(
                channel=normalized_channel,
                queued=True,
                updated_fields=updated_fields,
            )

        if send_value > 0:
            return DroneSopRetryChannelResult(
                channel=normalized_channel,
                already_sent=True,
                updated_fields=updated_fields,
            )

        return DroneSopRetryChannelResult(
            channel=normalized_channel,
            already_pending=True,
            updated_fields=updated_fields,
        )


__all__ = ["DroneSopRetryChannelResult", "retry_drone_sop_channel"]
