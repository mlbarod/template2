"""Drone SOP Jira 즉시인폼 요청 서비스."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from ... import selectors
from ...models import DroneSopChannelDelivery
from ..shared.delivery_state import ensure_channel_delivery_snapshots_for_rows


@dataclass(frozen=True)
class DroneSopInstantInformResult:
    """Drone SOP 단건 즉시인폼 요청 결과."""

    already_informed: bool = False
    queued: bool = False
    jira_key: str | None = None
    updated_fields: dict[str, Any] = field(default_factory=dict)


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

        success_delivery = sop.channel_deliveries.filter(
            channel=DroneSopChannelDelivery.Channels.JIRA,
            status=DroneSopChannelDelivery.Statuses.SUCCESS,
        ).order_by("id").first()
        if success_delivery is not None:
            if sop.instant_inform is None or int(sop.instant_inform) != 1:
                sop.instant_inform = 1
                updated_fields["instant_inform"] = 1
                update_fields.append("instant_inform")
            else:
                updated_fields["instant_inform"] = sop.instant_inform

            if update_fields:
                sop.save(update_fields=[*update_fields, "updated_at"])
            jira_key = success_delivery.external_key
            updated_fields["jira_key"] = jira_key
            updated_fields["inform_step"] = success_delivery.sent_step
            informed_at = success_delivery.sent_at
            updated_fields["informed_at"] = informed_at.isoformat() if informed_at else None
            return DroneSopInstantInformResult(
                already_informed=True,
                jira_key=jira_key,
                updated_fields=updated_fields,
            )

        if sop.instant_inform is None or int(sop.instant_inform) != 1:
            sop.instant_inform = 1
            updated_fields["instant_inform"] = 1
            update_fields.append("instant_inform")

        if update_fields:
            sop.save(update_fields=[*update_fields, "updated_at"])

        ensure_channel_delivery_snapshots_for_rows(
            rows=[
                {
                    "id": int(sop.id),
                    "sdwt_prod": sop.sdwt_prod,
                    "user_sdwt_prod": sop.user_sdwt_prod,
                    "status": sop.status,
                    "needtosend": sop.needtosend,
                    "instant_inform": sop.instant_inform,
                }
            ]
        )

    return DroneSopInstantInformResult(
        queued=True,
        updated_fields=updated_fields,
    )


__all__ = [
    "DroneSopInstantInformResult",
    "enqueue_drone_sop_jira_instant_inform",
]
