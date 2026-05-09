"""Drone SOP 채널 입력 정규화 helper 모음."""

from __future__ import annotations

from typing import Any

from ...models import DroneSopUserSdwtChannel

UNSET = object()
VALID_TARGET_SOURCES = {
    DroneSopUserSdwtChannel.Sources.AFFILIATION,
    DroneSopUserSdwtChannel.Sources.CUSTOM,
}


def normalize_optional_text(value: Any) -> str:
    """선택 문자열 값을 공백 제거 기준으로 정규화합니다."""

    return value.strip() if isinstance(value, str) else ""


def same_text(left: str | None, right: str | None) -> bool:
    """대소문자 차이를 무시하고 두 문자열이 같은지 확인합니다."""

    normalized_left = normalize_optional_text(left)
    normalized_right = normalize_optional_text(right)
    return normalized_left.casefold() == normalized_right.casefold()


def normalize_required_mapping_value(value: Any, field_name: str) -> str:
    """target mapping 필수 문자열 값을 검증하고 정규화합니다."""

    normalized = normalize_optional_text(value)
    if not normalized:
        raise ValueError(f"{field_name} is required")
    if len(normalized) > 64:
        raise ValueError(f"{field_name} must be 64 characters or fewer")
    return normalized


def normalize_target_source(value: str | object) -> str | object:
    """target source 값을 허용된 값으로 정규화합니다."""

    if value is UNSET:
        return value
    normalized = normalize_optional_text(value)
    if normalized not in VALID_TARGET_SOURCES:
        raise ValueError("source must be affiliation or custom")
    return normalized


def validate_optional_str(value: object, field_name: str) -> None:
    """선택 문자열 필드가 문자열 또는 None인지 검증합니다."""

    if value is UNSET:
        return
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{field_name} must be string or None")


def validate_optional_chatroom_id(value: object) -> None:
    """선택 채팅룸 ID가 양수 정수 또는 None인지 검증합니다."""

    if value is UNSET or value is None:
        return
    if not isinstance(value, int) or value <= 0:
        raise ValueError("chatroom_id must be positive int or None")


def normalize_optional_template_key(value: object) -> str | None | object:
    """선택 template key를 공백 제거 후 빈 문자열이면 None으로 정규화합니다."""

    if value is UNSET or value is None:
        return value
    assert isinstance(value, str)
    cleaned = value.strip()
    return cleaned or None


__all__ = [
    "UNSET",
    "normalize_optional_template_key",
    "normalize_optional_text",
    "normalize_required_mapping_value",
    "normalize_target_source",
    "same_text",
    "validate_optional_chatroom_id",
    "validate_optional_str",
]
