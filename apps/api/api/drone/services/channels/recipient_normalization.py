"""Drone SOP 채널 수신인 입력 정규화 helper."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ...models import DroneSopChannelRecipient

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


def normalize_target_user_sdwt_prod(value: Any) -> str:
    """target_user_sdwt_prod 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip()


def normalize_line_id(value: Any) -> str:
    """line_id 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip()


def normalize_user_ids(user_ids: Iterable[Any]) -> list[int]:
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


__all__ = [
    "CONTACT_FIELD_BY_CHANNEL",
    "normalize_line_id",
    "normalize_recipient_channel",
    "normalize_target_user_sdwt_prod",
    "normalize_user_ids",
]
