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
from django.db.models import Q
from django.utils import timezone

from ...models import DroneSOP, DroneSopDelivery, DroneSopTarget, DroneSopTargetDispatch
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


def normalize_sent_comment(value: Any) -> str | None:
    """발송 시점에 실제 템플릿에 사용되는 comment 스냅샷을 정규화합니다."""

    if value is None:
        return None
    comment = str(value).split("$@$", 1)[0].strip()
    return comment or None


def _get_target_by_code(*, target_code: str) -> DroneSopTarget | None:
    """target code와 일치하는 설정 target을 조회합니다."""

    return DroneSopTarget.objects.filter(target_user_sdwt_prod__iexact=target_code).order_by("id").first()


def _get_or_create_target_dispatch(
    *,
    sop_id: int,
    target_user_sdwt_prod: str,
    dispatch_type: str = DroneSopTargetDispatch.DispatchTypes.AUTO,
) -> DroneSopTargetDispatch:
    """SOP + target 단위 dispatch row를 생성하거나 반환합니다."""

    cleaned_target = _normalize_string_value(target_user_sdwt_prod) or "__TARGET_MISSING__"
    target = None if cleaned_target.startswith("__") else _get_target_by_code(target_code=cleaned_target)
    dispatch, _ = DroneSopTargetDispatch.objects.get_or_create(
        sop_id=sop_id,
        target_code_snapshot=cleaned_target,
        defaults={
            "target": target,
            "target_display_snapshot": cleaned_target,
            "resolution_status": "target_missing" if cleaned_target.startswith("__") else "resolved",
            "dispatch_type": dispatch_type,
            "status": DroneSopTargetDispatch.Statuses.PENDING,
        },
    )
    if target is not None and dispatch.target_id is None:
        dispatch.target = target
        dispatch.save(update_fields=["target", "updated_at"])
    return dispatch


def _summarize_dispatch_status(statuses: set[str]) -> str:
    """채널 delivery 상태 집합을 dispatch 상태로 요약합니다."""

    if not statuses:
        return DroneSopTargetDispatch.Statuses.PENDING
    if statuses <= {DroneSopDelivery.Statuses.DISABLED}:
        return DroneSopTargetDispatch.Statuses.DISABLED
    if DroneSopDelivery.Statuses.PENDING in statuses or DroneSopDelivery.Statuses.SENDING in statuses:
        return DroneSopTargetDispatch.Statuses.DISPATCHING
    if DroneSopDelivery.Statuses.FAILED in statuses and DroneSopDelivery.Statuses.SUCCESS in statuses:
        return DroneSopTargetDispatch.Statuses.PARTIAL_FAILED
    if DroneSopDelivery.Statuses.FAILED in statuses:
        return DroneSopTargetDispatch.Statuses.FAILED
    if DroneSopDelivery.Statuses.CANCELLED in statuses:
        return DroneSopTargetDispatch.Statuses.CANCELLED
    if DroneSopDelivery.Statuses.SUCCESS in statuses:
        return DroneSopTargetDispatch.Statuses.SUCCESS
    return DroneSopTargetDispatch.Statuses.PENDING


def _refresh_dispatch_statuses_for_delivery_ids(*, delivery_ids: Sequence[int]) -> None:
    """변경된 delivery가 속한 dispatch의 요약 상태를 갱신합니다."""

    normalized_ids = normalize_positive_ids(delivery_ids)
    if not normalized_ids:
        return
    dispatch_ids = normalize_positive_ids(
        list(
            DroneSopDelivery.objects.filter(id__in=normalized_ids).values_list(
                "dispatch_id",
                flat=True,
            )
        )
    )
    if not dispatch_ids:
        return
    now = timezone.now()
    for dispatch_id in dispatch_ids:
        statuses = set(
            DroneSopDelivery.objects.filter(dispatch_id=dispatch_id).values_list(
                "status",
                flat=True,
            )
        )
        DroneSopTargetDispatch.objects.filter(id=dispatch_id).update(
            status=_summarize_dispatch_status(statuses),
            updated_at=now,
        )


def get_or_prepare_channel_delivery(
    *,
    sop_id: int,
    target_user_sdwt_prod: str,
    channel: str,
) -> DroneSopDelivery:
    """target/channel 발송 row를 생성하거나 현재 상태로 반환합니다."""

    cleaned_target = _normalize_string_value(target_user_sdwt_prod)
    if cleaned_target and not cleaned_target.startswith("__"):
        DroneSOP.objects.filter(id=sop_id).filter(
            Q(target_user_sdwt_prod__isnull=True) | Q(target_user_sdwt_prod="")
        ).update(target_user_sdwt_prod=cleaned_target)
    dispatch = _get_or_create_target_dispatch(
        sop_id=sop_id,
        target_user_sdwt_prod=cleaned_target or "__TARGET_MISSING__",
    )
    delivery, _ = DroneSopDelivery.objects.get_or_create(
        dispatch=dispatch,
        channel=channel,
        defaults={
            "sop_id": sop_id,
            "status": DroneSopDelivery.Statuses.PENDING,
        },
    )
    if delivery.sop_id != sop_id:
        delivery.sop_id = sop_id
        delivery.save(update_fields=["sop", "updated_at"])
    return delivery


def create_channel_delivery_with_dispatch(
    *,
    sop: DroneSOP,
    channel: str,
    status: str = DroneSopDelivery.Statuses.PENDING,
    reason: str | None = None,
    target_user_sdwt_prod: str | None = None,
) -> DroneSopDelivery:
    """명시적인 service 경로로 dispatch가 연결된 delivery row를 생성합니다."""

    target_code = _normalize_string_value(target_user_sdwt_prod) or _normalize_string_value(sop.target_user_sdwt_prod)
    delivery = get_or_prepare_channel_delivery(
        sop_id=int(sop.id),
        target_user_sdwt_prod=target_code or "__TARGET_MISSING__",
        channel=channel,
    )
    delivery.status = status
    delivery.reason = reason
    delivery.save(update_fields=["status", "reason", "updated_at"])
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

    if index is None:
        index = load_user_sdwt_prod_map_index()

    target_values: set[str] = set()
    missing_ids: list[int] = []
    created_count = 0

    for row in rows:
        sop_id = _extract_sop_id(row)
        if sop_id is None:
            continue

        snapshot_targets = _extract_row_targets(row)
        if not snapshot_targets and _is_sop_delivery_eligible(row):
            snapshot_targets = resolve_target_user_sdwt_prods(row=row, index=index)

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
            if not _normalize_string_value(row.get("target_user_sdwt_prod")) and not target.startswith("__"):
                row["target_user_sdwt_prod"] = target
                DroneSOP.objects.filter(id=sop_id).filter(
                    Q(target_user_sdwt_prod__isnull=True) | Q(target_user_sdwt_prod="")
                ).update(target_user_sdwt_prod=target)
            for channel in normalized_channels:
                before_id = get_or_prepare_channel_delivery(
                    sop_id=sop_id,
                    target_user_sdwt_prod=target,
                    channel=channel,
                ).id
                if before_id:
                    created_count += 1

    return DeliverySnapshotResult(
        target_user_sdwt_prods=target_values,
        missing_sop_ids=normalize_positive_ids(missing_ids),
        created_count=created_count,
    )


def mark_channel_delivery_status(
    *,
    delivery_ids: Sequence[int],
    status: str,
    reason: str | None = None,
    external_key_by_id: dict[int, str] | None = None,
    sent_comment_by_id: dict[int, Any] | None = None,
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
        "sent_comment": None,
        "updated_at": now,
    }
    if status == DroneSopDelivery.Statuses.SUCCESS:
        base_updates["reason"] = None
        base_updates["sent_at"] = now

    normalized_external_key_by_id = external_key_by_id or {}
    normalized_sent_comment_by_id = sent_comment_by_id or {}
    if not normalized_external_key_by_id and not normalized_sent_comment_by_id:
        with transaction.atomic():
            DroneSopDelivery.objects.filter(id__in=normalized_ids).update(**base_updates)
            _refresh_dispatch_statuses_for_delivery_ids(delivery_ids=normalized_ids)
        return

    with transaction.atomic():
        for delivery_id in normalized_ids:
            updates = dict(base_updates)
            external_key = normalized_external_key_by_id.get(delivery_id)
            if isinstance(external_key, str) and external_key.strip():
                updates["external_key"] = external_key.strip()
            if delivery_id in normalized_sent_comment_by_id:
                updates["sent_comment"] = normalize_sent_comment(
                    normalized_sent_comment_by_id.get(delivery_id)
                )
            DroneSopDelivery.objects.filter(id=delivery_id).update(**updates)
        _refresh_dispatch_statuses_for_delivery_ids(delivery_ids=normalized_ids)


def filter_delivery_ids_for_config_failure(*, delivery_ids: Sequence[int]) -> list[int]:
    """전역 설정 누락 실패로 덮어쓸 delivery ID를 선별합니다."""

    normalized_ids = normalize_positive_ids(delivery_ids)
    if not normalized_ids:
        return []
    rows = (
        DroneSopDelivery.objects.filter(id__in=normalized_ids)
        .exclude(status__in=[DroneSopDelivery.Statuses.SUCCESS, DroneSopDelivery.Statuses.DISABLED])
        .values_list("id", flat=True)
    )
    return normalize_positive_ids(list(rows))


__all__ = [
    "DeliverySnapshotResult",
    "create_channel_delivery_with_dispatch",
    "ensure_channel_delivery_snapshots_for_rows",
    "filter_delivery_ids_for_config_failure",
    "get_or_prepare_channel_delivery",
    "mark_channel_delivery_status",
    "normalize_sent_comment",
    "normalize_positive_ids",
]
