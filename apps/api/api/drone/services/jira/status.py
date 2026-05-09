# =============================================================================
# 모듈: Drone SOP Jira 상태 반영
# 주요 기능: Jira 성공 delivery metadata와 legacy status update 호환 처리
# 주요 가정: Jira API 호출 결과는 delivery id/key 매핑으로 전달됩니다.
# =============================================================================
"""Drone SOP Jira 상태 반영 헬퍼 모듈입니다."""

from __future__ import annotations

from typing import Any, Sequence

from django.db import transaction
from django.utils import timezone

from ...models import DroneSopChannelDelivery, DroneSopTarget
from ..shared.delivery_state import (
    ensure_channel_delivery_snapshots_for_rows,
    mark_channel_delivery_status,
    normalize_positive_ids,
)


def _normalize_string_value(value: Any) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def update_drone_sop_jira_summary(
    *,
    delivery_ids: Sequence[int],
    key_by_delivery_id: dict[int, str] | None = None,
    step_by_delivery_id: dict[int, str] | None = None,
) -> int:
    """Jira delivery 성공 메타데이터를 delivery row에 반영합니다."""

    # -------------------------------------------------------------------------
    # 1) delivery → SOP 매핑 확인
    # -------------------------------------------------------------------------
    normalized_delivery_ids = normalize_positive_ids(delivery_ids)
    if not normalized_delivery_ids:
        return 0

    delivery_rows = list(
        DroneSopChannelDelivery.objects.filter(id__in=normalized_delivery_ids).values("id", "sop_id")
    )
    if not delivery_rows:
        return 0

    # -------------------------------------------------------------------------
    # 2) 단계/키 매핑 구성
    # -------------------------------------------------------------------------
    step_source = step_by_delivery_id or {}
    sop_ids: list[int] = []
    step_by_id: dict[int, str] = {}
    for row in delivery_rows:
        delivery_id = row.get("id")
        sop_id = row.get("sop_id")
        if not isinstance(delivery_id, int) or not isinstance(sop_id, int):
            continue
        if sop_id not in sop_ids:
            sop_ids.append(sop_id)
        step = step_source.get(delivery_id)
        if isinstance(step, str) and step.strip():
            step_by_id[delivery_id] = step.strip()
    if not sop_ids:
        return 0

    # -------------------------------------------------------------------------
    # 3) delivery별 step snapshot 보정
    # -------------------------------------------------------------------------
    with transaction.atomic():
        for delivery_id, sent_step in step_by_id.items():
            DroneSopChannelDelivery.objects.filter(id=delivery_id).update(
                sent_step=sent_step,
                updated_at=timezone.now(),
            )
    return len(sop_ids)


def update_drone_sop_jira_status(
    *,
    done_ids: Sequence[int],
    rows: Sequence[dict[str, Any]],
    key_by_id: dict[int, str],
) -> int:
    """Jira 생성 완료된 SOP의 Jira delivery를 성공으로 표시합니다."""

    normalized_done_ids = normalize_positive_ids(list(done_ids))
    if not normalized_done_ids:
        return 0

    candidate_rows = [row for row in rows if isinstance(row.get("id"), int) and int(row["id"]) in normalized_done_ids]
    if not candidate_rows:
        return 0

    ensure_channel_delivery_snapshots_for_rows(
        rows=list(candidate_rows),
        channels=[DroneSopChannelDelivery.Channels.JIRA],
    )
    pending_delivery_rows = list(
        DroneSopChannelDelivery.objects.filter(
            sop_id__in=normalized_done_ids,
            channel=DroneSopChannelDelivery.Channels.JIRA,
        )
        .exclude(status=DroneSopChannelDelivery.Statuses.SUCCESS)
        .order_by("sop_id", "id")
        .values("id", "sop_id")
    )
    if not pending_delivery_rows:
        legacy_target = DroneSopTarget.get_or_create_by_name(target_user_sdwt_prod="__legacy_target__")
        DroneSopChannelDelivery.objects.bulk_create(
            [
                DroneSopChannelDelivery(
                    sop_id=sop_id,
                    target=legacy_target,
                    channel=DroneSopChannelDelivery.Channels.JIRA,
                    status=DroneSopChannelDelivery.Statuses.PENDING,
                )
                for sop_id in normalized_done_ids
            ],
            ignore_conflicts=True,
        )
        pending_delivery_rows = list(
            DroneSopChannelDelivery.objects.filter(
                sop_id__in=normalized_done_ids,
                channel=DroneSopChannelDelivery.Channels.JIRA,
            )
            .exclude(status=DroneSopChannelDelivery.Statuses.SUCCESS)
            .order_by("sop_id", "id")
            .values("id", "sop_id")
        )
    if not pending_delivery_rows:
        return 0

    delivery_ids = [int(row["id"]) for row in pending_delivery_rows if isinstance(row.get("id"), int)]
    key_by_delivery_id = {
        int(row["id"]): key_by_id[int(row["sop_id"])]
        for row in pending_delivery_rows
        if isinstance(row.get("id"), int)
        and isinstance(row.get("sop_id"), int)
        and isinstance(key_by_id.get(int(row["sop_id"])), str)
    }
    step_by_sop_id: dict[int, str] = {}
    for row in candidate_rows:
        sop_id = int(row["id"])
        step = _normalize_string_value(row.get("metro_current_step"))
        if step:
            step_by_sop_id[sop_id] = step
    step_by_delivery_id = {
        int(row["id"]): step_by_sop_id[int(row["sop_id"])]
        for row in pending_delivery_rows
        if isinstance(row.get("id"), int)
        and isinstance(row.get("sop_id"), int)
        and int(row["sop_id"]) in step_by_sop_id
    }

    mark_channel_delivery_status(
        delivery_ids=delivery_ids,
        status=DroneSopChannelDelivery.Statuses.SUCCESS,
        external_key_by_id=key_by_delivery_id,
    )
    return update_drone_sop_jira_summary(
        delivery_ids=delivery_ids,
        key_by_delivery_id=key_by_delivery_id,
        step_by_delivery_id=step_by_delivery_id,
    )


__all__ = ["update_drone_sop_jira_status", "update_drone_sop_jira_summary"]
