"""eqp_status_chg 조회 selector입니다."""

from __future__ import annotations

from datetime import datetime, time
from typing import List

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from api.data_movement.eqp_status_chg.models import EqpStatusChg


def _lookup_key(value: str) -> str:
    """조회용 정규화 키를 생성합니다."""

    return (value or "").strip().upper()


def _normalize_datetime_filter(value: object | None, *, is_end: bool = False) -> object | None:
    """문자열 시간 경계를 DateTimeField filter에 안전한 값으로 변환합니다."""

    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is None:
            parsed_date = parse_date(value)
            if parsed_date is None:
                return value
            parsed = datetime.combine(parsed_date, time.max if is_end else time.min)
    else:
        return value

    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_default_timezone())
    return parsed


def fetch_eqp_timeline_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[dict[str, object]]:
    """timeline EQP 로그 응답 형태로 상태 변경 이력을 반환합니다.

    입력:
    - eqp_id: 정규화가 끝난 EQP-CB ID
    - start_at/end_at: 조회 시간 경계
    - limit: 선택 row 제한

    반환:
    - List[dict[str, object]]: observer EQP log payload

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    normalized_start_at = _normalize_datetime_filter(start_at)
    normalized_end_at = _normalize_datetime_filter(end_at, is_end=True)

    queryset = EqpStatusChg.objects.filter(eqp_cb_lookup=_lookup_key(eqp_id)).order_by("-chg_time")
    if normalized_start_at is not None:
        queryset = queryset.filter(chg_time__gte=normalized_start_at)
    if normalized_end_at is not None:
        queryset = queryset.filter(chg_time__lte=normalized_end_at)
    if limit is not None:
        queryset = queryset[:limit]

    return [
        {
            "id": f"EQP-{row.eqp_event_key}",
            "eqpId": row.eqp_cb,
            "logType": "EQP",
            "eventType": row.eqp_status_type,
            "eventTime": row.chg_time,
            "operator": row.operator_emp_id,
            "comment": row.chg_comment,
        }
        for row in queryset
    ]


__all__ = ["fetch_eqp_timeline_logs"]
