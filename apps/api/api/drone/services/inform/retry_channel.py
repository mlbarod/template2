# =============================================================================
# 모듈: Drone SOP 채널 재시도 서비스
# 주요 기능: 실패 delivery 채널을 pending 상태로 되돌려 다음 배치 재처리 허용
# 주요 가정: 채널 재시도는 사용자의 명시적 액션으로만 수행합니다.
# =============================================================================
"""Drone SOP 채널 재시도 서비스."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from ... import selectors
from ...models import DroneSOP, DroneSopDelivery
from ..shared.delivery_state import (
    ensure_channel_delivery_snapshots_for_rows,
    get_or_prepare_channel_delivery,
    mark_channel_delivery_status,
)
from ..shared.notify_resolver import load_user_sdwt_prod_map_index, resolve_target_user_sdwt_prods
from ..shared.policy import REASON_TARGET_MISSING
from .retry_results import DroneSopRetryChannelResult, build_retry_channel_result

_DELIVERY_CHANNEL_BY_CHANNEL = {
    "jira": DroneSopDelivery.Channels.JIRA,
    "messenger": DroneSopDelivery.Channels.MESSENGER,
    "mail": DroneSopDelivery.Channels.MAIL,
}
_CHANNEL_KEYS_TEXT = ", ".join(_DELIVERY_CHANNEL_BY_CHANNEL.keys())


def _build_resolution_row(*, sop: DroneSOP) -> dict[str, Any]:
    """현재 SOP 값으로 target 재해석용 row를 구성합니다."""

    return {
        "id": int(sop.id),
        "sdwt_prod": sop.sdwt_prod,
        "user_sdwt_prod": sop.user_sdwt_prod,
        "target_user_sdwt_prod": sop.target_user_sdwt_prod,
        "status": sop.status,
        "needtosend": sop.needtosend,
        "instant_inform": sop.instant_inform,
    }


def _is_target_missing_delivery(delivery: DroneSopDelivery) -> bool:
    """target 미확정 실패 delivery인지 확인합니다."""

    return delivery.reason == REASON_TARGET_MISSING


def _resolve_current_target_for_sop(*, sop: DroneSOP) -> str | None:
    """수동 재시도 시점의 mapping 기준으로 target을 다시 계산합니다."""

    targets = resolve_target_user_sdwt_prods(
        row=_build_resolution_row(sop=sop),
        index=load_user_sdwt_prod_map_index(),
    )
    for target in targets:
        cleaned = target.strip() if isinstance(target, str) else ""
        if cleaned and not cleaned.startswith("__"):
            return cleaned
    return None


def _requeue_target_missing_delivery(
    *,
    sop: DroneSOP,
    channel: str,
    failed_deliveries: list[DroneSopDelivery],
) -> str | None:
    """target 미확정 실패 row를 현재 mapping target의 pending row로 전환합니다."""

    target_missing_deliveries = [delivery for delivery in failed_deliveries if _is_target_missing_delivery(delivery)]
    if not target_missing_deliveries:
        return None

    resolved_target = _resolve_current_target_for_sop(sop=sop)
    if not resolved_target:
        raise ValueError("target mapping is still missing")

    if sop.target_user_sdwt_prod != resolved_target:
        sop.target_user_sdwt_prod = resolved_target
        sop.save(update_fields=["target_user_sdwt_prod", "updated_at"])
    resolved_delivery = get_or_prepare_channel_delivery(
        sop_id=int(sop.id),
        target_user_sdwt_prod=resolved_target,
        channel=channel,
    )
    mark_channel_delivery_status(
        delivery_ids=[int(resolved_delivery.id)],
        status=DroneSopDelivery.Statuses.PENDING,
    )
    DroneSopDelivery.objects.filter(
        id__in=[int(delivery.id) for delivery in target_missing_deliveries if delivery.id],
    ).delete()
    return "queued"


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
        - 실패 delivery row가 있으면 pending으로 갱신합니다.
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
    delivery_channel = _DELIVERY_CHANNEL_BY_CHANNEL.get(normalized_channel)
    if delivery_channel is None:
        raise ValueError(f"channel must be one of: {_CHANNEL_KEYS_TEXT}")

    # -----------------------------------------------------------------------------
    # 2) 행 잠금 후 delivery snapshot 보장
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        sop = selectors.get_drone_sop_for_update(sop_id=sop_id)
        if sop is None:
            raise ValueError("DroneSOP not found")

        ensure_channel_delivery_snapshots_for_rows(rows=[_build_resolution_row(sop=sop)])

        failed_deliveries = list(
            DroneSopDelivery.objects.filter(
                sop_id=sop_id,
                channel=delivery_channel,
                status=DroneSopDelivery.Statuses.FAILED,
            )
            .order_by("id")
        )
        target_missing_result = _requeue_target_missing_delivery(
            sop=sop,
            channel=delivery_channel,
            failed_deliveries=failed_deliveries,
        )
        if target_missing_result is not None:
            return build_retry_channel_result(channel=normalized_channel, state=target_missing_result)

        failed_delivery_ids = [int(delivery.id) for delivery in failed_deliveries if delivery.id]
        pending_exists = DroneSopDelivery.objects.filter(
            sop_id=sop_id,
            channel=delivery_channel,
            status=DroneSopDelivery.Statuses.PENDING,
        ).exists()
        success_exists = DroneSopDelivery.objects.filter(
            sop_id=sop_id,
            channel=delivery_channel,
            status=DroneSopDelivery.Statuses.SUCCESS,
        ).exists()
        disabled_exists = DroneSopDelivery.objects.filter(
            sop_id=sop_id,
            channel=delivery_channel,
            status=DroneSopDelivery.Statuses.DISABLED,
        ).exists()

        if failed_delivery_ids:
            mark_channel_delivery_status(
                delivery_ids=[int(delivery_id) for delivery_id in failed_delivery_ids],
                status=DroneSopDelivery.Statuses.PENDING,
            )
            return build_retry_channel_result(channel=normalized_channel, state="queued")

        if pending_exists:
            return build_retry_channel_result(channel=normalized_channel, state="pending")

        if success_exists:
            return build_retry_channel_result(channel=normalized_channel, state="success")

        if disabled_exists:
            return build_retry_channel_result(channel=normalized_channel, state="disabled")

        return build_retry_channel_result(channel=normalized_channel, state="pending")


__all__ = ["DroneSopRetryChannelResult", "retry_drone_sop_channel"]
