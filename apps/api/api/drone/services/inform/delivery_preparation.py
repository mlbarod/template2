# =============================================================================
# 모듈: Drone SOP inform delivery 준비
# 주요 기능: 채널별 delivery 생성, target/config 검증, 전송 대기 row 구성
# 주요 가정: 실제 채널 전송은 sop_inform orchestration에서 수행합니다.
# =============================================================================
"""Drone SOP inform delivery 준비 헬퍼 모듈입니다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...models import DroneSopDelivery
from ..shared.delivery_state import (
    get_or_prepare_channel_delivery as _get_or_prepare_delivery,
    mark_channel_delivery_status as _mark_delivery_status,
    normalize_positive_ids as _normalize_positive_ids,
)
from ..shared.policy import (
    REASON_CHANNEL_CONFIG_MISSING,
    REASON_DISABLED_BY_POLICY,
)

ChannelConfig = dict[str, str | bool | int | None]


@dataclass(frozen=True)
class PendingChannelDelivery:
    """채널 전송 직전까지 해석된 SOP row와 delivery 상태를 묶습니다."""

    row: dict[str, Any]
    sop_id: int
    target_user_sdwt_prod: str
    delivery_id: int
    config: ChannelConfig

    def as_delivery_row(self) -> dict[str, Any]:
        """템플릿/발송 함수가 기대하는 target 포함 row를 반환합니다."""

        return {**self.row, "target_user_sdwt_prod": self.target_user_sdwt_prod}


def normalize_string_value(value: Any) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def normalize_target_lookup_key(value: Any) -> str | None:
    """대소문자 비구분 채널 조회용 target 키를 정규화합니다."""

    cleaned = normalize_string_value(value)
    if not cleaned:
        return None
    return cleaned.casefold()


def extract_row_id(row: dict[str, Any]) -> int | None:
    """row에서 양의 정수 id를 추출합니다."""

    row_id = row.get("id")
    if isinstance(row_id, int) and row_id > 0:
        return row_id
    return None


def _extract_row_targets(row: dict[str, Any]) -> list[str]:
    """row에서 발송 대상 target 목록을 추출합니다."""

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
        target_key = normalize_target_lookup_key(target)
        if not target or not target_key or target_key in seen:
            continue
        seen.add(target_key)
        targets.append(target)
    return targets


def collect_pending_channel_deliveries(
    *,
    rows: list[dict[str, Any]],
    channel_by_target: dict[str, ChannelConfig],
    enabled_field: str,
    channel: str,
    configured_field: str | None = None,
) -> tuple[list[PendingChannelDelivery], list[int]]:
    """채널 전송 대기 delivery를 분류합니다.

    반환:
        - ready_deliveries: (row, sop_id, target, delivery_id, config_row) 목록
        - delivery_ids: 이번 실행에서 확인한 delivery ID 목록
    """

    ready_deliveries: list[PendingChannelDelivery] = []
    delivery_ids: list[int] = []

    for row in rows:
        row_id = extract_row_id(row)
        if row_id is None:
            continue

        for target in _extract_row_targets(row):
            delivery = _get_or_prepare_delivery(
                sop_id=row_id,
                target_user_sdwt_prod=target,
                channel=channel,
            )
            delivery_ids.append(delivery.id)
            if delivery.status in {
                DroneSopDelivery.Statuses.SUCCESS,
                DroneSopDelivery.Statuses.FAILED,
                DroneSopDelivery.Statuses.DISABLED,
            }:
                continue

            config_row = channel_by_target.get(normalize_target_lookup_key(target) or "")
            if not config_row or (
                configured_field is not None
                and not bool(config_row.get(configured_field, False))
            ):
                _mark_delivery_status(
                    delivery_ids=[delivery.id],
                    status=DroneSopDelivery.Statuses.DISABLED,
                    reason=REASON_CHANNEL_CONFIG_MISSING,
                )
                continue
            if not bool(config_row.get(enabled_field, True)):
                _mark_delivery_status(
                    delivery_ids=[delivery.id],
                    status=DroneSopDelivery.Statuses.DISABLED,
                    reason=REASON_DISABLED_BY_POLICY,
                )
                continue

            ready_deliveries.append(
                PendingChannelDelivery(
                    row=row,
                    sop_id=row_id,
                    target_user_sdwt_prod=target,
                    delivery_id=delivery.id,
                    config=config_row,
                )
            )

    return ready_deliveries, _normalize_positive_ids(delivery_ids)


__all__ = [
    "ChannelConfig",
    "PendingChannelDelivery",
    "collect_pending_channel_deliveries",
    "extract_row_id",
    "normalize_string_value",
    "normalize_target_lookup_key",
]
