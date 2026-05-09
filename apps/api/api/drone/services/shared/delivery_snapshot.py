"""Drone SOP delivery snapshot 정규화 helper."""

from __future__ import annotations

from typing import Any, Sequence

from ...models import DroneSopChannelDelivery

DELIVERY_CHANNELS: tuple[str, ...] = (
    DroneSopChannelDelivery.Channels.JIRA,
    DroneSopChannelDelivery.Channels.MESSENGER,
    DroneSopChannelDelivery.Channels.MAIL,
)


def normalize_string_value(value: Any) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def normalize_lookup_key(value: Any) -> str | None:
    """대소문자 비구분 비교용 문자열 키를 생성합니다."""

    cleaned = normalize_string_value(value)
    if not cleaned:
        return None
    return cleaned.casefold()


def normalize_int_flag(value: Any) -> int:
    """숫자 플래그 값을 정수 상태로 정규화합니다."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def is_sop_delivery_eligible(row: dict[str, Any]) -> bool:
    """SOP가 delivery snapshot 생성 대상인지 확인합니다."""

    if normalize_int_flag(row.get("instant_inform")) == 1:
        return True
    return normalize_int_flag(row.get("needtosend")) == 1 and str(row.get("status") or "").strip() == "COMPLETE"


def extract_sop_id(row: dict[str, Any]) -> int | None:
    """row에서 양의 정수 SOP ID를 추출합니다."""

    raw_id = row.get("id")
    if isinstance(raw_id, int) and raw_id > 0:
        return raw_id
    return None


def extract_row_targets(row: dict[str, Any]) -> list[str]:
    """row에 포함된 target snapshot 값을 단일 target 목록으로 정규화합니다."""

    raw_targets = row.get("target_user_sdwt_prods")
    candidates: list[Any]
    if isinstance(raw_targets, list):
        candidates = raw_targets
    else:
        candidates = [row.get("target_user_sdwt_prod")]

    targets: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        target = normalize_string_value(candidate)
        target_key = normalize_lookup_key(target)
        if not target or not target_key or target_key in seen:
            continue
        seen.add(target_key)
        targets.append(target)
        break
    return targets


def append_unique_target(*, target_list: list[str], target: str) -> None:
    """target 목록에 대소문자 비구분 중복 없이 추가합니다."""

    target_key = normalize_lookup_key(target)
    if not target_key:
        return
    if any(normalize_lookup_key(existing) == target_key for existing in target_list):
        return
    target_list.append(target)


def normalize_channels(channels: Sequence[str]) -> list[str]:
    """허용 delivery 채널만 중복 없이 정규화합니다."""

    normalized: list[str] = []
    for channel in channels:
        if channel in DELIVERY_CHANNELS and channel not in normalized:
            normalized.append(channel)
    return normalized


__all__ = [
    "DELIVERY_CHANNELS",
    "append_unique_target",
    "extract_row_targets",
    "extract_sop_id",
    "is_sop_delivery_eligible",
    "normalize_channels",
    "normalize_lookup_key",
    "normalize_string_value",
]
