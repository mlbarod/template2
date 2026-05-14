# =============================================================================
# 모듈: Drone SOP Jira delivery 준비
# 주요 기능: target별 Jira delivery 생성, 채널 설정 검증, 전송 대상 row 구성
# 주요 가정: 실제 Jira API 호출과 성공/실패 반영은 상위 orchestration에서 수행합니다.
# =============================================================================
"""Drone SOP Jira delivery 준비 헬퍼 모듈입니다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ...models import DroneSopDelivery
from ..shared.delivery_state import (
    get_or_prepare_channel_delivery,
    mark_channel_delivery_status,
    normalize_positive_ids,
)
from ..shared.policy import (
    REASON_CHANNEL_CONFIG_INVALID,
    REASON_CHANNEL_CONFIG_MISSING,
    REASON_DISABLED_BY_POLICY,
)
from .templates.jira_template_registry import TEMPLATE_SOURCES


def _normalize_target_lookup_key(value: Any) -> str | None:
    """대소문자 비구분 채널 조회용 target 키를 정규화합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned.casefold()


def _normalize_string_value(value: Any) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _extract_row_id(row: dict[str, Any]) -> int | None:
    """row에서 양의 정수 id를 추출합니다."""

    row_id = row.get("id")
    if isinstance(row_id, int) and row_id > 0:
        return row_id
    return None


def _extract_row_targets(row: dict[str, Any]) -> list[str]:
    """row에서 target_user_sdwt_prod 목록을 추출합니다."""

    raw_targets = row.get("target_user_sdwt_prods")
    candidates: list[Any]
    if isinstance(raw_targets, list):
        candidates = raw_targets
    else:
        candidates = [row.get("target_user_sdwt_prod")]

    targets: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        target = _normalize_string_value(candidate)
        target_key = _normalize_target_lookup_key(target)
        if not target or not target_key or target_key in seen:
            continue
        seen.add(target_key)
        targets.append(target)
    return targets


@dataclass(frozen=True)
class JiraPreparedDeliveries:
    """Jira 전송용 delivery 준비 결과."""

    rows_to_send: list[dict[str, Any]]
    delivery_ids: list[int]
    project_key_by_delivery_id: dict[int, str]
    template_key_by_delivery_id: dict[int, str]
    sop_id_by_delivery_id: dict[int, int]
    step_by_delivery_id: dict[int, str]


def collect_jira_delivery_rows(
    *,
    rows: Sequence[dict[str, Any]],
    channel_by_target: dict[str, dict[str, str | bool | int | None]],
) -> JiraPreparedDeliveries:
    """target별 Jira delivery를 생성하고 전송 가능 행을 수집합니다."""

    rows_to_send: list[dict[str, Any]] = []
    delivery_ids: list[int] = []
    project_key_by_delivery_id: dict[int, str] = {}
    template_key_by_delivery_id: dict[int, str] = {}
    sop_id_by_delivery_id: dict[int, int] = {}
    step_by_delivery_id: dict[int, str] = {}

    for row in rows:
        row_id = _extract_row_id(row)
        if row_id is None:
            continue

        for target in _extract_row_targets(row):
            delivery = get_or_prepare_channel_delivery(
                sop_id=row_id,
                target_user_sdwt_prod=target,
                channel=DroneSopDelivery.Channels.JIRA,
            )
            delivery_ids.append(delivery.id)
            sop_id_by_delivery_id[delivery.id] = row_id

            step = _normalize_string_value(row.get("metro_current_step"))
            if step:
                step_by_delivery_id[delivery.id] = step

            if delivery.status in {
                DroneSopDelivery.Statuses.SUCCESS,
                DroneSopDelivery.Statuses.FAILED,
                DroneSopDelivery.Statuses.DISABLED,
            }:
                continue

            config_row = channel_by_target.get(_normalize_target_lookup_key(target) or "")
            if not config_row or not bool(config_row.get("jira_configured", False)):
                mark_channel_delivery_status(
                    delivery_ids=[delivery.id],
                    status=DroneSopDelivery.Statuses.DISABLED,
                    reason=REASON_CHANNEL_CONFIG_MISSING,
                )
                continue
            if not bool(config_row.get("jira_enabled", True)):
                mark_channel_delivery_status(
                    delivery_ids=[delivery.id],
                    status=DroneSopDelivery.Statuses.DISABLED,
                    reason=REASON_DISABLED_BY_POLICY,
                )
                continue

            jira_key = _normalize_string_value(config_row.get("jira_key"))
            template_key = _normalize_string_value(config_row.get("jira_template_key"))
            if not jira_key or not template_key or template_key not in TEMPLATE_SOURCES:
                mark_channel_delivery_status(
                    delivery_ids=[delivery.id],
                    status=DroneSopDelivery.Statuses.FAILED,
                    reason=REASON_CHANNEL_CONFIG_INVALID,
                )
                continue

            rows_to_send.append({**row, "target_user_sdwt_prod": target, "delivery_id": delivery.id})
            project_key_by_delivery_id[delivery.id] = jira_key
            template_key_by_delivery_id[delivery.id] = template_key

    return JiraPreparedDeliveries(
        rows_to_send=rows_to_send,
        delivery_ids=normalize_positive_ids(delivery_ids),
        project_key_by_delivery_id=project_key_by_delivery_id,
        template_key_by_delivery_id=template_key_by_delivery_id,
        sop_id_by_delivery_id=sop_id_by_delivery_id,
        step_by_delivery_id=step_by_delivery_id,
    )


__all__ = ["JiraPreparedDeliveries", "collect_jira_delivery_rows"]
