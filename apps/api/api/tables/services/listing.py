# =============================================================================
# 모듈 설명: tables 조회 payload 구성 로직을 제공합니다.
# - 주요 함수: get_table_list_payload
# - 불변 조건: recentHours 규칙과 날짜 범위를 준수합니다.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

from api.common.services import DEFAULT_TABLE
from api.common.services import (
    build_date_range_filters,
    build_line_filters,
    ensure_date_bounds,
    normalize_date_only,
    normalize_line_id,
)

from .. import selectors
from .utils import _raise_if_table_missing

# =============================================================================
# 상수: Drone SOP reason camelCase alias
# =============================================================================
_DRONE_SOP_REASON_ALIASES = (
    ("jira_reason", "jiraReason"),
    ("messenger_reason", "messengerReason"),
    ("mail_reason", "mailReason"),
)


def _append_drone_sop_reason_aliases(
    *,
    table_name: str,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    """drone_sop 조회 응답에 reason camelCase 별칭 필드를 추가합니다.

    입력:
    - table_name: 조회 대상 테이블명
    - columns: 원본 컬럼 목록
    - rows: 원본 행 목록

    반환:
    - tuple[list[str], list[dict[str, Any]]]: (보강된 컬럼 목록, 보강된 행 목록)

    부작용:
    - 없음(입력 리스트를 직접 수정하지 않고 복사본을 생성합니다)
    """

    # -----------------------------------------------------------------------------
    # 1) drone_sop 테이블이 아니면 원본 그대로 반환
    # -----------------------------------------------------------------------------
    if table_name != "drone_sop":
        return columns, rows

    # -----------------------------------------------------------------------------
    # 2) 행 복사본 생성
    # -----------------------------------------------------------------------------
    next_columns = list(columns)
    next_rows = [dict(row) for row in rows]

    # -----------------------------------------------------------------------------
    # 3) reason snake_case -> camelCase 별칭 추가
    # -----------------------------------------------------------------------------
    for snake_key, camel_key in _DRONE_SOP_REASON_ALIASES:
        has_source = snake_key in next_columns or any(snake_key in row for row in next_rows)
        if not has_source:
            continue
        for row in next_rows:
            row[camel_key] = row.get(snake_key)

    return next_columns, next_rows


# =============================================================================
# 상수: recentHours 기본/범위 설정
# =============================================================================
RECENT_HOURS_MIN = 0
RECENT_HOURS_DAY_STEP = 24
RECENT_HOURS_DAY_MODE_MIN_DAYS = 2
RECENT_HOURS_DAY_MODE_MAX_DAYS = 7
RECENT_HOURS_DAY_MODE_THRESHOLD = 24
RECENT_HOURS_MAX = RECENT_HOURS_DAY_MODE_MAX_DAYS * RECENT_HOURS_DAY_STEP
RECENT_HOURS_DEFAULT_START = 8
RECENT_HOURS_DEFAULT_END = 0
RECENT_FUTURE_TOLERANCE_MINUTES = 5


def _snap_recent_hours(value: int) -> int:
    """recentHours 값을 허용 범위/단위(일 단위)로 스냅(보정)합니다.

    입력:
    - value: recentHours 입력 값

    반환:
    - int: 보정된 recentHours 값

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 범위 클램프
    # -----------------------------------------------------------------------------
    clamped = max(RECENT_HOURS_MIN, min(value, RECENT_HOURS_MAX))
    if clamped <= RECENT_HOURS_DAY_MODE_THRESHOLD:
        return clamped

    # -----------------------------------------------------------------------------
    # 2) 일 단위 스냅 및 상한/하한 보정
    # -----------------------------------------------------------------------------
    days = (clamped + RECENT_HOURS_DAY_STEP - 1) // RECENT_HOURS_DAY_STEP
    bounded_days = max(
        RECENT_HOURS_DAY_MODE_MIN_DAYS,
        min(days, RECENT_HOURS_DAY_MODE_MAX_DAYS),
    )
    return bounded_days * RECENT_HOURS_DAY_STEP


def _clamp_recent_hours(value: Any, fallback: int) -> int:
    """입력값을 정수로 파싱해 recentHours 규칙에 맞게 보정합니다.

    입력:
    - value: recentHours 후보 값
    - fallback: 파싱 실패 시 기본값

    반환:
    - int: 보정된 recentHours 값

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 정수 파싱 시도
    # -----------------------------------------------------------------------------
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = fallback
    # -----------------------------------------------------------------------------
    # 2) 스냅 규칙 적용
    # -----------------------------------------------------------------------------
    return _snap_recent_hours(numeric)


def _resolve_recent_hours_range(params: Mapping[str, Any]) -> tuple[int, int]:
    """쿼리 파라미터에서 recentHoursStart/End 범위를 계산합니다.

    입력:
    - params: 요청 파라미터 맵

    반환:
    - tuple[int, int]: (recentHoursStart, recentHoursEnd) (조회 범위)

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) start/end 파싱
    # -----------------------------------------------------------------------------
    start = _clamp_recent_hours(params.get("recentHoursStart"), RECENT_HOURS_DEFAULT_START)
    end = _clamp_recent_hours(params.get("recentHoursEnd"), RECENT_HOURS_DEFAULT_END)
    # -----------------------------------------------------------------------------
    # 2) 역전 보정
    # -----------------------------------------------------------------------------
    if start < end:
        start = end
    return start, end


def get_table_list_payload(*, params: Mapping[str, Any]) -> dict[str, Any]:
    """테이블 조회 결과를 응답 payload로 구성합니다.

    입력:
    - params: request.GET 기반 파라미터 맵

    반환:
    - dict[str, Any]: 테이블 조회 응답 payload

    부작용:
    - 없음(읽기 전용)

    오류:
    - TableNotFoundError: 테이블이 없을 때
    - LookupError/ValueError: 컬럼/입력 오류
    """

    # -----------------------------------------------------------------------------
    # 1) 날짜/라인/최근 범위 파라미터 정규화
    # -----------------------------------------------------------------------------
    from_param = normalize_date_only(params.get("from"))
    to_param = normalize_date_only(params.get("to"))
    normalized_line_id = normalize_line_id(params.get("lineId"))
    recent_hours_start, recent_hours_end = _resolve_recent_hours_range(params)

    # -----------------------------------------------------------------------------
    # 2) 날짜 범위 역전 보정
    # -----------------------------------------------------------------------------
    if from_param and to_param:
        from_param, to_param = ensure_date_bounds(from_param, to_param)

    # -----------------------------------------------------------------------------
    # 3) 테이블 스키마/컬럼 정보 조회
    # -----------------------------------------------------------------------------
    from api.tables import services as table_services

    schema = table_services.resolve_table_schema(
        params.get("table"),
        default_table=DEFAULT_TABLE,
        require_timestamp=True,
    )
    table_name = schema.name
    column_names = schema.columns
    base_ts_col = schema.timestamp_column

    # -----------------------------------------------------------------------------
    # 4) 필터/파라미터 구성
    # -----------------------------------------------------------------------------
    line_filter_result = build_line_filters(column_names, normalized_line_id)
    where_parts = list(line_filter_result["filters"])
    query_params = list(line_filter_result["params"])

    now_utc = datetime.utcnow()
    recent_start_dt = now_utc - timedelta(hours=recent_hours_start)
    recent_end_dt = now_utc - timedelta(hours=recent_hours_end)
    recent_end_dt += timedelta(minutes=RECENT_FUTURE_TOLERANCE_MINUTES)

    where_parts.append(f"{base_ts_col} BETWEEN %s AND %s")
    query_params.append(recent_start_dt.strftime("%Y-%m-%d %H:%M:%S"))
    query_params.append(recent_end_dt.strftime("%Y-%m-%d %H:%M:%S"))

    date_conditions, date_params = build_date_range_filters(base_ts_col, from_param, to_param)
    where_parts.extend(date_conditions)
    query_params.extend(date_params)

    # -----------------------------------------------------------------------------
    # 5) SQL WHERE/ORDER 구성
    # -----------------------------------------------------------------------------
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    order_clause = f"ORDER BY {base_ts_col} DESC, id DESC"

    # -----------------------------------------------------------------------------
    # 6) SQL 실행 및 테이블 누락 보정
    # -----------------------------------------------------------------------------
    try:
        rows = selectors.fetch_rows(
            sql=(
                """
                SELECT *
                FROM {table}
                {where_clause}
                {order_clause}
                """
            ).format(table=table_name, where_clause=where_clause, order_clause=order_clause),
            params=query_params,
        )
    except Exception as exc:  # 방어적 처리(커버리지 제외): pragma: no cover
        _raise_if_table_missing(exc, table_name)
        raise

    # -----------------------------------------------------------------------------
    # 7) drone_sop reason 별칭 보강
    # -----------------------------------------------------------------------------
    response_columns, response_rows = _append_drone_sop_reason_aliases(
        table_name=table_name,
        columns=column_names,
        rows=rows,
    )

    # -----------------------------------------------------------------------------
    # 8) 응답 페이로드 반환
    # -----------------------------------------------------------------------------
    return {
        "table": table_name,
        "cutoff": (
            "{col} BETWEEN NOW() - INTERVAL '{start} hours' AND NOW() - INTERVAL '{end} hours'"
        ).format(col=base_ts_col, start=recent_hours_start, end=recent_hours_end),
        "from": from_param or None,
        "to": to_param or None,
        "rowCount": len(response_rows),
        "columns": response_columns,
        "rows": response_rows,
    }
