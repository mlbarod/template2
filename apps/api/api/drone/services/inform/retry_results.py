"""Drone SOP 채널 재시도 결과 helper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DroneSopRetryChannelResult:
    """Drone SOP 단건 채널 재시도 요청 결과."""

    channel: str
    queued: bool = False
    already_pending: bool = False
    already_sent: bool = False
    already_disabled: bool = False
    updated_fields: dict[str, Any] = field(default_factory=dict)


def build_retry_channel_result(*, channel: str, state: str) -> DroneSopRetryChannelResult:
    """재시도 상태 문자열을 API 응답 결과 객체로 변환합니다."""

    if state == "queued":
        return DroneSopRetryChannelResult(
            channel=channel,
            queued=True,
            updated_fields={},
        )
    if state == "pending":
        return DroneSopRetryChannelResult(
            channel=channel,
            already_pending=True,
            updated_fields={},
        )
    if state == "success":
        return DroneSopRetryChannelResult(
            channel=channel,
            already_sent=True,
            updated_fields={},
        )
    if state == "disabled":
        return DroneSopRetryChannelResult(
            channel=channel,
            already_disabled=True,
            updated_fields={},
        )
    raise ValueError("unknown retry channel state")


__all__ = ["DroneSopRetryChannelResult", "build_retry_channel_result"]
