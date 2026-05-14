"""Drone SOP 즉시인폼 요청 서비스."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from ... import selectors
from ...models import DroneSopDelivery, DroneSopTargetDispatch
from ..mail.templates.mail_template_registry import MAIL_TEMPLATE_SOURCES
from ..messenger.templates.messenger_template_registry import EXCEL_TABLE_TEMPLATE_SENDERS
from ..shared.delivery_state import (
    ensure_channel_delivery_snapshots_for_rows,
    get_or_prepare_channel_delivery,
    mark_channel_delivery_status,
)
from ..shared.policy import (
    REASON_CHANNEL_CONFIG_INVALID,
    REASON_CHANNEL_CONFIG_MISSING,
    REASON_DISABLED_BY_POLICY,
    REASON_TEMPLATE_MISSING,
    mark_missing_target_as_failed,
)
from .templates.jira_template_registry import TEMPLATE_SOURCES

_INSTANT_INFORM_CHANNELS: tuple[str, ...] = (
    DroneSopDelivery.Channels.JIRA,
    DroneSopDelivery.Channels.MESSENGER,
    DroneSopDelivery.Channels.MAIL,
)

_CONFIGURED_FIELD_BY_CHANNEL: dict[str, str] = {
    DroneSopDelivery.Channels.JIRA: "jira_configured",
    DroneSopDelivery.Channels.MESSENGER: "messenger_configured",
    DroneSopDelivery.Channels.MAIL: "mail_configured",
}
_ENABLED_FIELD_BY_CHANNEL: dict[str, str] = {
    DroneSopDelivery.Channels.JIRA: "jira_enabled",
    DroneSopDelivery.Channels.MESSENGER: "messenger_enabled",
    DroneSopDelivery.Channels.MAIL: "mail_enabled",
}


@dataclass(frozen=True)
class DroneSopInstantInformResult:
    """Drone SOP 단건 즉시인폼 요청 결과."""

    already_informed: bool = False
    queued: bool = False
    not_queueable: bool = False
    block_reason: str | None = None
    jira_key: str | None = None
    updated_fields: dict[str, Any] = field(default_factory=dict)


def _normalize_string_value(value: Any) -> str | None:
    """문자열 설정 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _normalize_target_lookup_key(value: Any) -> str | None:
    """대소문자 비구분 target 조회 키를 정규화합니다."""

    cleaned = _normalize_string_value(value)
    return cleaned.casefold() if cleaned else None


def _resolve_instant_terminal_status(
    *,
    channel: str,
    config: dict[str, str | bool | int | None] | None,
) -> tuple[str, str | None] | None:
    """즉시인폼 재큐잉 전에 채널 설정의 최종 차단 상태를 판단합니다."""

    configured_field = _CONFIGURED_FIELD_BY_CHANNEL.get(channel)
    enabled_field = _ENABLED_FIELD_BY_CHANNEL.get(channel)
    if not config or (configured_field and not bool(config.get(configured_field, False))):
        return DroneSopDelivery.Statuses.DISABLED, REASON_CHANNEL_CONFIG_MISSING
    if enabled_field and not bool(config.get(enabled_field, True)):
        return DroneSopDelivery.Statuses.DISABLED, REASON_DISABLED_BY_POLICY

    if channel == DroneSopDelivery.Channels.JIRA:
        jira_key = _normalize_string_value(config.get("jira_key"))
        template_key = _normalize_string_value(config.get("jira_template_key"))
        if not jira_key or not template_key or template_key not in TEMPLATE_SOURCES:
            return DroneSopDelivery.Statuses.FAILED, REASON_CHANNEL_CONFIG_INVALID
        return None

    if channel == DroneSopDelivery.Channels.MESSENGER:
        template_key = _normalize_string_value(config.get("messenger_template_key"))
        if not template_key:
            return DroneSopDelivery.Statuses.FAILED, REASON_TEMPLATE_MISSING
        if template_key not in EXCEL_TABLE_TEMPLATE_SENDERS:
            return DroneSopDelivery.Statuses.FAILED, REASON_CHANNEL_CONFIG_INVALID
        return None

    if channel == DroneSopDelivery.Channels.MAIL:
        template_key = _normalize_string_value(config.get("mail_template_key"))
        if not template_key:
            return DroneSopDelivery.Statuses.FAILED, REASON_TEMPLATE_MISSING
        if template_key not in MAIL_TEMPLATE_SOURCES:
            return DroneSopDelivery.Statuses.FAILED, REASON_CHANNEL_CONFIG_INVALID
        return None

    return DroneSopDelivery.Statuses.DISABLED, REASON_CHANNEL_CONFIG_MISSING


def enqueue_drone_sop_jira_instant_inform(
    *,
    sop_id: int,
    comment: str | None = None,
) -> DroneSopInstantInformResult:
    """Drone SOP 단건 즉시인폼 체크를 요청합니다.

    인자:
        sop_id: DroneSOP ID(드론 SOP ID).
        comment: 덮어쓸 코멘트(옵션).

    반환:
        DroneSopInstantInformResult 결과 객체(queued/already_informed/updated_fields 포함).

    부작용:
        - comment/instant_inform 상태 업데이트(필요 시)
        - 성공 delivery는 유지하고, 현재 설정상 유효한 미성공 delivery만 대기 상태로 준비

    오류:
        입력 검증 실패 시 ValueError를 발생시킵니다.
    """

    # -------------------------------------------------------------------------
    # 1) 입력 검증
    # -------------------------------------------------------------------------
    if sop_id <= 0:
        raise ValueError("sop_id must be a positive integer")

    updated_fields: dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # 2) 상태 업데이트(체크 + 코멘트)
    # -------------------------------------------------------------------------
    with transaction.atomic():
        sop = selectors.get_drone_sop_for_update(sop_id=sop_id)
        if sop is None:
            raise ValueError("DroneSOP not found")

        update_fields: list[str] = []

        if comment is not None:
            sop.comment = comment
            updated_fields["comment"] = sop.comment
            update_fields.append("comment")

        success_jira_delivery = sop.channel_deliveries.filter(
            channel=DroneSopDelivery.Channels.JIRA,
            status=DroneSopDelivery.Statuses.SUCCESS,
        ).order_by("id").first()

        if update_fields:
            sop.save(update_fields=[*update_fields, "updated_at"])

        snapshot = ensure_channel_delivery_snapshots_for_rows(
            rows=[
                {
                    "id": int(sop.id),
                    "sdwt_prod": sop.sdwt_prod,
                    "user_sdwt_prod": sop.user_sdwt_prod,
                    "target_user_sdwt_prod": sop.target_user_sdwt_prod,
                    "status": sop.status,
                    "needtosend": sop.needtosend,
                    "instant_inform": 1,
                }
            ]
        )
        if snapshot.missing_sop_ids:
            mark_missing_target_as_failed(
                sop_ids=snapshot.missing_sop_ids,
                channels=_INSTANT_INFORM_CHANNELS,
            )

        channel_by_target = selectors.list_drone_sop_user_sdwt_channels_by_targets(
            target_user_sdwt_prod_values=snapshot.target_user_sdwt_prods,
        )
        DroneSopTargetDispatch.objects.filter(sop=sop).update(
            dispatch_type=DroneSopTargetDispatch.DispatchTypes.INSTANT,
        )

        queue_delivery_ids: list[int] = []
        for target in snapshot.target_user_sdwt_prods:
            target_key = _normalize_target_lookup_key(target)
            config = channel_by_target.get(target_key or "")
            for channel in _INSTANT_INFORM_CHANNELS:
                delivery = get_or_prepare_channel_delivery(
                    sop_id=int(sop.id),
                    target_user_sdwt_prod=target,
                    channel=channel,
                )
                if delivery.status == DroneSopDelivery.Statuses.SUCCESS:
                    continue
                terminal_status = _resolve_instant_terminal_status(
                    channel=channel,
                    config=config,
                )
                if terminal_status is None:
                    queue_delivery_ids.append(int(delivery.id))
                    continue
                status, reason = terminal_status
                mark_channel_delivery_status(
                    delivery_ids=[int(delivery.id)],
                    status=status,
                    reason=reason,
                )

        if queue_delivery_ids:
            if sop.instant_inform is None or int(sop.instant_inform) != 1:
                sop.instant_inform = 1
                sop.save(update_fields=["instant_inform", "updated_at"])
                updated_fields["instant_inform"] = 1
            mark_channel_delivery_status(
                delivery_ids=queue_delivery_ids,
                status=DroneSopDelivery.Statuses.PENDING,
            )
            if success_jira_delivery is not None:
                updated_fields["jira_key"] = success_jira_delivery.external_key
            return DroneSopInstantInformResult(
                queued=True,
                jira_key=success_jira_delivery.external_key if success_jira_delivery else None,
                updated_fields=updated_fields,
            )

        success_jira_delivery = sop.channel_deliveries.filter(
            channel=DroneSopDelivery.Channels.JIRA,
            status=DroneSopDelivery.Statuses.SUCCESS,
        ).order_by("id").first()
        if success_jira_delivery is not None:
            jira_key = success_jira_delivery.external_key
            updated_fields["jira_key"] = jira_key
            updated_fields["inform_step"] = success_jira_delivery.sent_step
            informed_at = success_jira_delivery.sent_at
            updated_fields["informed_at"] = informed_at.isoformat() if informed_at else None
            return DroneSopInstantInformResult(
                already_informed=True,
                jira_key=jira_key,
                updated_fields=updated_fields,
            )

    return DroneSopInstantInformResult(
        not_queueable=True,
        block_reason="no_queueable_channel",
        updated_fields=updated_fields,
    )


__all__ = [
    "DroneSopInstantInformResult",
    "enqueue_drone_sop_jira_instant_inform",
]
