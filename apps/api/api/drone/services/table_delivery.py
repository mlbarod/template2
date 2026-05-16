# =============================================================================
# 모듈: Drone 테이블 delivery summary helper
# 주요 기능: line-dashboard 테이블 row에 delivery 가상 컬럼 부착
# 주요 가정: 실제 테이블 조회 SQL은 table_ops에서 수행하고 delivery 요약만 담당합니다.
# =============================================================================
"""Drone 테이블 delivery 가상 컬럼 헬퍼 모듈."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .. import selectors

_DELIVERY_VIRTUAL_COLUMNS = [
    "delivery_targets",
    "delivery_status",
]
_DELIVERY_COLUMN_BY_CHANNEL = {
    "jira": "delivery_jira",
    "messenger": "delivery_messenger",
    "mail": "delivery_mail",
}
_DELIVERY_UPDATE_FIELDS = (
    "dispatch_id",
    "deliveryRows",
    "delivery_targets",
    "delivery_status",
    "delivery_jira",
    "delivery_messenger",
    "delivery_mail",
    "informed_at",
    "jira_key",
    "inform_step",
)


def _normalize_positive_int(value: Any) -> int | None:
    """양의 정수 ID 값을 정규화합니다."""

    if isinstance(value, int) and value > 0:
        return value
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _summarize_delivery_flag(*, delivery_rows: list[dict[str, Any]], channel: str) -> int:
    """delivery row 목록을 테이블 정렬용 숫자 플래그로 요약합니다."""

    channel_rows = [row for row in delivery_rows if row.get("channel") == channel]
    if not channel_rows:
        return 0
    statuses = {str(row.get("status") or "").strip().lower() for row in channel_rows}
    if "failed" in statuses:
        return -1
    if "pending" in statuses or "unknown" in statuses:
        return 0
    if "success" in statuses:
        return 1
    return 0


def _summarize_delivery_overall_flag(*, delivery_rows: list[dict[str, Any]]) -> int:
    """전체 delivery row 목록을 테이블 정렬용 숫자 플래그로 요약합니다."""

    if not delivery_rows:
        return 0
    statuses = {str(row.get("status") or "").strip().lower() for row in delivery_rows}
    if "failed" in statuses:
        return -1
    if "pending" in statuses or "unknown" in statuses:
        return 0
    if "success" in statuses:
        return 1
    return 0


def _latest_success_sent_at(*, delivery_rows: list[dict[str, Any]]) -> datetime | None:
    """성공 delivery 중 가장 최근 발송 시각을 반환합니다."""

    latest_sent_at: datetime | None = None
    for delivery in delivery_rows:
        if delivery.get("status") != "success":
            continue
        sent_at = delivery.get("sentAt")
        if not isinstance(sent_at, datetime):
            continue
        if latest_sent_at is None or sent_at > latest_sent_at:
            latest_sent_at = sent_at
    return latest_sent_at


def _extract_row_target(row: dict[str, Any]) -> str | None:
    """테이블에 표시할 SOP row의 target 값을 반환합니다."""

    target = row.get("target_user_sdwt_prod")
    if not isinstance(target, str) or not target.strip():
        return None
    return target.strip()


def _attach_delivery_summary_columns(*, row: dict[str, Any], delivery_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """테이블 row에 delivery 가상 컬럼 값을 붙입니다."""

    dispatch_id = next(
        (
            delivery.get("dispatchId") or delivery.get("dispatch_id")
            for delivery in delivery_rows
            if delivery.get("dispatchId") or delivery.get("dispatch_id")
        ),
        None,
    )
    enriched = {
        **row,
        "dispatch_id": dispatch_id,
        "deliveryRows": delivery_rows,
        "delivery_targets": _extract_row_target(row),
        "delivery_status": _summarize_delivery_overall_flag(delivery_rows=delivery_rows),
    }
    for channel, column in _DELIVERY_COLUMN_BY_CHANNEL.items():
        enriched[column] = _summarize_delivery_flag(delivery_rows=delivery_rows, channel=channel)

    jira_success = next(
        (
            delivery
            for delivery in delivery_rows
            if delivery.get("channel") == "jira" and delivery.get("status") == "success"
        ),
        None,
    )
    if jira_success:
        enriched["jira_key"] = jira_success.get("externalKey")
        enriched["inform_step"] = jira_success.get("sentStep")
    enriched["informed_at"] = _latest_success_sent_at(delivery_rows=delivery_rows)
    return enriched


def attach_delivery_rows(*, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """테이블 row에 channel delivery 메타를 붙입니다."""

    if not rows:
        return rows

    sop_ids = [
        sop_id
        for row in rows
        if isinstance(row, dict) and (sop_id := _normalize_positive_int(row.get("id"))) is not None
    ]
    delivery_rows_by_sop_id = selectors.list_drone_sop_channel_delivery_rows_by_sop_ids(sop_ids=sop_ids)
    return [
        _attach_delivery_summary_columns(
            row=row,
            delivery_rows=delivery_rows_by_sop_id.get(
                _normalize_positive_int(row.get("id")) if isinstance(row, dict) else 0,
                [],
            ),
        )
        for row in rows
    ]


def build_delivery_update_payload(*, row: dict[str, Any]) -> dict[str, Any]:
    """단건 액션 응답에 필요한 delivery 메타만 구성합니다.

    테이블 목록 조회처럼 target별 row를 복제하지 않고, 현재 화면 row가 가진
    target_user_sdwt_prod를 보존할 수 있도록 가상 delivery 컬럼만 반환합니다.
    """

    sop_id = _normalize_positive_int(row.get("id"))
    delivery_rows = (
        selectors.list_drone_sop_channel_delivery_rows_by_sop_ids(sop_ids=[sop_id]).get(sop_id, [])
        if sop_id is not None
        else []
    )
    enriched = _attach_delivery_summary_columns(row=row, delivery_rows=delivery_rows)
    return {key: enriched.get(key) for key in _DELIVERY_UPDATE_FIELDS if key in enriched}


def append_delivery_columns(column_names: list[str]) -> list[str]:
    """DB 컬럼 목록에 delivery 가상 컬럼을 추가합니다."""

    response_columns = list(column_names)
    for summary_column in ("informed_at", "jira_key"):
        if summary_column not in response_columns:
            response_columns.append(summary_column)
    insert_index = len(response_columns)
    for anchor in ("sdwt_prod", "user_sdwt_prod", "line_id"):
        if anchor in response_columns:
            insert_index = response_columns.index(anchor) + 1
            break
    for column in reversed(_DELIVERY_VIRTUAL_COLUMNS):
        if column in response_columns:
            continue
        response_columns.insert(insert_index, column)
    return response_columns


__all__ = ["append_delivery_columns", "attach_delivery_rows", "build_delivery_update_payload"]
