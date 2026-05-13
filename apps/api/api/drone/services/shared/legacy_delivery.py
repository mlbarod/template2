"""Drone SOP legacy delivery 입력을 명시적으로 delivery row로 변환하는 서비스."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, Mapping

from django.db import transaction
from django.db.models import Q

from ...models import DroneSOP, DroneSopDelivery, DroneSopTargetMapping
from .delivery_state import get_or_prepare_channel_delivery

LEGACY_DELIVERY_SEED_KEYS = {
    "send_jira",
    "send_messenger",
    "send_mail",
    "jira_reason",
    "messenger_reason",
    "mail_reason",
    "inform_step",
    "jira_key",
    "informed_at",
}


def pop_legacy_delivery_seed(values: MutableMapping[str, Any]) -> dict[str, Any]:
    """legacy delivery 필드를 payload에서 분리해 반환합니다."""

    return {
        key: values.pop(key)
        for key in list(values.keys())
        if key in LEGACY_DELIVERY_SEED_KEYS
    }


def _normalize_seed_text(value: object) -> str | None:
    """legacy seed 문자열을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _resolve_legacy_delivery_seed_targets(*, sop: DroneSOP) -> list[str]:
    """legacy target seed 또는 현재 매핑으로 delivery target을 해석합니다."""

    explicit_target = _normalize_seed_text(sop.target_user_sdwt_prod)
    if explicit_target:
        return [explicit_target]

    sdwt_prod = _normalize_seed_text(sop.sdwt_prod)
    user_sdwt_prod = _normalize_seed_text(sop.user_sdwt_prod)
    if sdwt_prod and user_sdwt_prod:
        pair_targets = list(
            DroneSopTargetMapping.objects.filter(sdwt_prod__iexact=sdwt_prod, user_sdwt_prod__iexact=user_sdwt_prod)
            .select_related("target")
            .exclude(target__target_user_sdwt_prod="")
            .values_list("target__target_user_sdwt_prod", flat=True)
            .order_by("id")
        )
        if pair_targets:
            return [target for target in pair_targets if isinstance(target, str) and target.strip()][:1]
    if sdwt_prod:
        sdwt_targets = list(
            DroneSopTargetMapping.objects.filter(sdwt_prod__iexact=sdwt_prod)
            .filter(Q(user_sdwt_prod__isnull=True) | Q(user_sdwt_prod=""))
            .select_related("target")
            .exclude(target__target_user_sdwt_prod="")
            .values_list("target__target_user_sdwt_prod", flat=True)
            .order_by("id")
        )
        if sdwt_targets:
            return [target for target in sdwt_targets if isinstance(target, str) and target.strip()][:1]
    if user_sdwt_prod:
        user_targets = list(
            DroneSopTargetMapping.objects.filter(user_sdwt_prod__iexact=user_sdwt_prod)
            .filter(Q(sdwt_prod__isnull=True) | Q(sdwt_prod=""))
            .select_related("target")
            .exclude(target__target_user_sdwt_prod="")
            .values_list("target__target_user_sdwt_prod", flat=True)
            .order_by("id")
        )
        if user_targets:
            return [target for target in user_targets if isinstance(target, str) and target.strip()][:1]
    fallback = user_sdwt_prod or sdwt_prod
    return [fallback] if fallback else []


def _normalize_legacy_status(value: Any) -> int:
    """legacy 발송 상태값을 정수로 정규화합니다."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def seed_legacy_delivery_rows(*, sop: DroneSOP, seed: Mapping[str, Any]) -> None:
    """분리된 legacy delivery seed를 명시적으로 delivery row에 반영합니다."""

    if not seed or not sop.pk:
        return

    targets = _resolve_legacy_delivery_seed_targets(sop=sop)
    if not targets:
        return

    target_code = targets[0]
    channel_specs = (
        (DroneSopDelivery.Channels.JIRA, "send_jira", "jira_reason"),
        (DroneSopDelivery.Channels.MESSENGER, "send_messenger", "messenger_reason"),
        (DroneSopDelivery.Channels.MAIL, "send_mail", "mail_reason"),
    )
    with transaction.atomic():
        for channel, send_key, reason_key in channel_specs:
            numeric_status = _normalize_legacy_status(seed.get(send_key, 0))
            status = DroneSopDelivery.Statuses.PENDING
            reason = None
            external_key = None
            sent_at = None
            if numeric_status > 0:
                status = DroneSopDelivery.Statuses.SUCCESS
                sent_at = seed.get("informed_at")
                if channel == DroneSopDelivery.Channels.JIRA:
                    external_key = seed.get("jira_key")
            elif numeric_status < 0:
                status = DroneSopDelivery.Statuses.FAILED
                reason = seed.get(reason_key) or "send_failed"

            delivery = get_or_prepare_channel_delivery(
                sop_id=int(sop.pk),
                target_user_sdwt_prod=target_code,
                channel=channel,
            )
            delivery.status = status
            delivery.reason = reason
            delivery.external_key = external_key
            delivery.sent_at = sent_at
            delivery.sent_step = seed.get("inform_step")
            delivery.save(
                update_fields=[
                    "status",
                    "reason",
                    "external_key",
                    "sent_at",
                    "sent_step",
                    "updated_at",
                ]
            )


__all__ = [
    "LEGACY_DELIVERY_SEED_KEYS",
    "pop_legacy_delivery_seed",
    "seed_legacy_delivery_rows",
]
