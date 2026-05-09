# =============================================================================
# 모듈: Drone SOP 채널 delivery 상태 관리
# 주요 기능: target/channel별 delivery snapshot 생성과 상태 갱신
# 주요 가정: delivery row가 발송 대상과 채널 상태의 단일 기준입니다.
# =============================================================================
"""Drone SOP 채널 delivery 상태 관리 유틸리티."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from django.db import transaction
from django.utils import timezone

from ...models import DroneSopChannelDelivery, DroneSopTarget
from .delivery_snapshot import (
    DELIVERY_CHANNELS as _DELIVERY_CHANNELS,
    append_unique_target as _append_unique_target,
    extract_row_targets as _extract_row_targets,
    extract_sop_id as _extract_sop_id,
    is_sop_delivery_eligible as _is_sop_delivery_eligible,
    normalize_channels as _normalize_channels,
    normalize_lookup_key as _normalize_lookup_key,
    normalize_string_value as _normalize_string_value,
)
from .notify_resolver import UserSdwtProdMapIndex, load_user_sdwt_prod_map_index, resolve_target_user_sdwt_prods


@dataclass(frozen=True)
class DeliverySnapshotResult:
    """SOP delivery snapshot 생성 결과입니다."""

    target_user_sdwt_prods: set[str]
    missing_sop_ids: list[int]
    created_count: int = 0


def normalize_positive_ids(values: Sequence[int]) -> list[int]:
    """양의 정수 ID 목록을 중복 없이 정규화합니다."""

    normalized: list[int] = []
    seen: set[int] = set()
    for value in values:
        if not isinstance(value, int) or value <= 0:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def get_or_prepare_channel_delivery(
    *,
    sop_id: int,
    target_user_sdwt_prod: str,
    channel: str,
) -> DroneSopChannelDelivery:
    """target/channel 발송 row를 생성하거나 현재 상태로 반환합니다."""

    target = DroneSopTarget.get_or_create_by_name(target_user_sdwt_prod=target_user_sdwt_prod)
    delivery, _ = DroneSopChannelDelivery.objects.get_or_create(
        sop_id=sop_id,
        target=target,
        channel=channel,
        defaults={"status": DroneSopChannelDelivery.Statuses.PENDING},
    )
    return delivery


def ensure_channel_delivery_snapshots_for_rows(
    *,
    rows: list[dict[str, Any]],
    index: UserSdwtProdMapIndex | None = None,
    channels: Sequence[str] = _DELIVERY_CHANNELS,
) -> DeliverySnapshotResult:
    """SOP별 target/channel delivery snapshot을 생성합니다.

    이미 delivery가 있는 SOP는 기존 target snapshot을 유지합니다. delivery가 전혀 없는
    SOP만 현재 매핑을 해석해 최초 snapshot을 만듭니다.
    """

    normalized_channels = _normalize_channels(channels)
    if not rows or not normalized_channels:
        return DeliverySnapshotResult(target_user_sdwt_prods=set(), missing_sop_ids=[])

    sop_ids = [sop_id for row in rows if (sop_id := _extract_sop_id(row)) is not None]
    if not sop_ids:
        return DeliverySnapshotResult(target_user_sdwt_prods=set(), missing_sop_ids=[])

    existing_rows = DroneSopChannelDelivery.objects.filter(sop_id__in=sop_ids).values(
        "sop_id",
        "target__target_user_sdwt_prod",
        "channel",
    )
    existing_pairs_by_sop: dict[int, set[tuple[str, str]]] = {}
    existing_targets_by_sop: dict[int, list[str]] = {}
    for delivery_row in existing_rows:
        sop_id = delivery_row.get("sop_id")
        if not isinstance(sop_id, int):
            continue
        target = _normalize_string_value(delivery_row.get("target__target_user_sdwt_prod"))
        target_key = _normalize_lookup_key(target)
        channel = _normalize_string_value(delivery_row.get("channel"))
        if not target or not target_key or channel not in _DELIVERY_CHANNELS:
            continue
        existing_pairs_by_sop.setdefault(sop_id, set()).add((target_key, channel))
        _append_unique_target(target_list=existing_targets_by_sop.setdefault(sop_id, []), target=target)

    if index is None:
        index = load_user_sdwt_prod_map_index()

    target_values: set[str] = set()
    missing_ids: list[int] = []
    create_rows: list[DroneSopChannelDelivery] = []

    for row in rows:
        sop_id = _extract_sop_id(row)
        if sop_id is None:
            continue

        snapshot_targets = list(existing_targets_by_sop.get(sop_id) or [])
        if not snapshot_targets and _is_sop_delivery_eligible(row):
            snapshot_targets = _extract_row_targets(row)
            if not snapshot_targets:
                snapshot_targets = resolve_target_user_sdwt_prods(row=row, index=index)

        snapshot_targets = snapshot_targets[:1]
        row["target_user_sdwt_prods"] = snapshot_targets
        row["target_user_sdwt_prod"] = snapshot_targets[0] if snapshot_targets else None

        if not snapshot_targets:
            if _is_sop_delivery_eligible(row):
                missing_ids.append(sop_id)
            continue

        for target in snapshot_targets:
            target_key = _normalize_lookup_key(target)
            if not target_key:
                continue
            target_values.add(target)
            for channel in normalized_channels:
                pair = (target_key, channel)
                if pair in existing_pairs_by_sop.setdefault(sop_id, set()):
                    continue
                target_row = DroneSopTarget.get_or_create_by_name(target_user_sdwt_prod=target)
                create_rows.append(
                    DroneSopChannelDelivery(
                        sop_id=sop_id,
                        target=target_row,
                        channel=channel,
                        status=DroneSopChannelDelivery.Statuses.PENDING,
                    )
                )
                existing_pairs_by_sop[sop_id].add(pair)

    if create_rows:
        with transaction.atomic():
            DroneSopChannelDelivery.objects.bulk_create(create_rows, ignore_conflicts=True)

    return DeliverySnapshotResult(
        target_user_sdwt_prods=target_values,
        missing_sop_ids=normalize_positive_ids(missing_ids),
        created_count=len(create_rows),
    )


def mark_channel_delivery_status(
    *,
    delivery_ids: Sequence[int],
    status: str,
    reason: str | None = None,
    external_key_by_id: dict[int, str] | None = None,
) -> None:
    """target/channel 발송 상태를 일괄 갱신합니다."""

    normalized_ids = normalize_positive_ids(delivery_ids)
    if not normalized_ids:
        return

    now = timezone.now()
    base_updates: dict[str, Any] = {
        "status": status,
        "reason": reason,
        "sent_at": None,
        "sent_step": None,
        "external_key": None,
        "updated_at": now,
    }
    if status == DroneSopChannelDelivery.Statuses.SUCCESS:
        base_updates["reason"] = None
        base_updates["sent_at"] = now

    normalized_external_key_by_id = external_key_by_id or {}
    if not normalized_external_key_by_id:
        with transaction.atomic():
            DroneSopChannelDelivery.objects.filter(id__in=normalized_ids).update(**base_updates)
        return

    with transaction.atomic():
        for delivery_id in normalized_ids:
            updates = dict(base_updates)
            external_key = normalized_external_key_by_id.get(delivery_id)
            if isinstance(external_key, str) and external_key.strip():
                updates["external_key"] = external_key.strip()
            DroneSopChannelDelivery.objects.filter(id=delivery_id).update(**updates)


def filter_delivery_ids_for_config_failure(*, delivery_ids: Sequence[int]) -> list[int]:
    """전역 설정 누락 실패로 덮어쓸 delivery ID를 선별합니다."""

    normalized_ids = normalize_positive_ids(delivery_ids)
    if not normalized_ids:
        return []
    rows = (
        DroneSopChannelDelivery.objects.filter(id__in=normalized_ids)
        .exclude(status__in=[DroneSopChannelDelivery.Statuses.SUCCESS, DroneSopChannelDelivery.Statuses.DISABLED])
        .values_list("id", flat=True)
    )
    return normalize_positive_ids(list(rows))


__all__ = [
    "DeliverySnapshotResult",
    "ensure_channel_delivery_snapshots_for_rows",
    "filter_delivery_ids_for_config_failure",
    "get_or_prepare_channel_delivery",
    "mark_channel_delivery_status",
    "normalize_positive_ids",
]
