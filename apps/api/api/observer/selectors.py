# =============================================================================
# 모듈 설명: observer 데이터 셀렉터를 제공합니다.
# - 주요 함수: list_lines, list_sdwt_for_line, get_merged_logs 등
# - 불변 조건: 로그별 소유 selector/DB를 통해 조회합니다.
# =============================================================================

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import json
import re
from typing import Dict, List, Sequence
from urllib.parse import urlencode

from django.conf import settings
from django.db import connection

from api.data_movement.eqp_status_chg import selectors as eqp_status_chg_selectors
from api.data_movement.mi_tip_update_hist import selectors as mi_tip_update_hist_selectors
from api.data_movement.racb_list import selectors as racb_list_selectors
from api.drone import selectors as drone_selectors

DEFAULT_LOG_QUERY_DAYS = 60
MAX_LOG_LIMIT = 5000
TKIN_PREVENT_REGISTRATION_LEVELS = ("LEVEL1", "LEVEL2", "LEVEL3")
TKIN_PREVENT_LEVEL2_NAMES = {"LEVEL2", "LEVEL3"}

Row = Dict[str, object]
LogRows = List[Dict[str, object]]
LogFetcher = Callable[[str, object | None, object | None, int | None], LogRows]


# =============================================================================
# 내부 헬퍼
# =============================================================================


def _safe_text(value: object) -> str:
    """None 값을 안전하게 문자열로 정리합니다."""

    return "" if value is None else str(value)


def _period_date(days: int | None = None) -> str:
    """조회 기준일(YYYY-MM-DD)을 반환합니다."""

    query_days = (
        days
        if days is not None
        else getattr(settings, "OBSERVER_QUERY_DAYS", DEFAULT_LOG_QUERY_DAYS)
    )
    return datetime.strftime(datetime.now() - timedelta(days=query_days), "%Y-%m-%d")


def _fetch_all(query: str, params: Sequence[object] | None = None) -> List[Row]:
    """기본 DB에서 조회 결과를 dict 리스트로 반환합니다."""

    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        columns = [col[0] for col in (cursor.description or [])]
        rows = cursor.fetchall()

    return [dict(zip(columns, row)) for row in rows]


def _fetch_all_on_default(query: str, params: Sequence[object] | None = None) -> List[Row]:
    """기본 DB에서 조회 결과를 dict 리스트로 반환합니다."""

    return _fetch_all(query, params)


def _fetch_one(query: str, params: Sequence[object] | None = None) -> Row | None:
    """단일 행 조회를 반환합니다(없으면 None)."""

    rows = _fetch_all(query, params)
    return rows[0] if rows else None


def _normalize_filters(**values: str | None) -> Dict[str, str]:
    """조회 필터 값을 같은 규칙으로 정규화합니다."""

    return {key: normalize_id(value) for key, value in values.items()}


def _build_text_record(row: Row, field_map: Sequence[tuple[str, str]]) -> Dict[str, str]:
    """행 데이터를 응답 필드명 기준 문자열 dict로 변환합니다."""

    return {
        target_field: _safe_text(row.get(source_field))
        for target_field, source_field in field_map
    }


def _build_time_clause(
    field_name: str,
    *,
    start_at: object | None = None,
    end_at: object | None = None,
) -> tuple[str, List[object]]:
    """로그 조회 시간 조건과 파라미터를 생성합니다."""

    clause = f"{field_name} >= %s"
    params: List[object] = [start_at or _period_date()]
    if end_at is not None:
        clause += f" and {field_name} <= %s"
        params.append(end_at)
    return clause, params


def _build_limit_clause(limit: int | None = None) -> tuple[str, List[object]]:
    """선택적으로 SQL limit 절과 파라미터를 생성합니다."""

    if limit is None:
        return "", []
    return "limit %s", [limit]


# =============================================================================
# 공개 정규화 함수
# =============================================================================


def normalize_id(value: str | None) -> str:
    """입력 ID를 공백 제거 후 대문자로 정규화합니다.

    입력:
    - value: 원본 ID(None 허용)

    반환:
    - str: 정규화된 ID(없으면 빈 문자열)

    부작용:
    - 없음

    오류:
    - 없음
    """

    return (value or "").strip().upper()


# =============================================================================
# 기본 DB 기준 정보 조회
# =============================================================================


def list_lines() -> List[Dict[str, str]]:
    """Drone target 기준으로 Observer에서 선택 가능한 라인 목록을 반환합니다.

    입력:
    - 없음

    반환:
    - List[Dict[str, str]]: 라인 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    payload = drone_selectors.get_tip_status_line_sdwt_options_payload()
    rows = payload.get("lines") if isinstance(payload, dict) else []
    return [
        {"id": line_id, "name": line_id}
        for row in rows
        if isinstance(row, dict)
        for line_id in [_safe_text(row.get("lineId")).strip()]
        if line_id
    ]


def list_sdwt_for_line(*, line_id: str) -> List[Dict[str, str]]:
    """Drone target line 기준으로 station_master에 존재하는 user_sdwt_prod 목록을 반환합니다.

    입력:
    - line_id: 라인 ID

    반환:
    - List[Dict[str, str]]: SDWT 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(line_id=line_id)
    line_key = filters["line_id"]
    payload = drone_selectors.get_tip_status_line_sdwt_options_payload()
    rows = payload.get("lines") if isinstance(payload, dict) else []
    matched_line = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and normalize_id(_safe_text(row.get("lineId"))) == line_key
        ),
        {},
    )
    values = matched_line.get("userSdwtProds") if isinstance(matched_line, dict) else []

    return [
        {
            "id": value,
            "name": value,
            "lineId": line_key,
        }
        for raw_value in values
        for value in [_safe_text(raw_value).strip()]
        if value
    ]


def list_prc_groups(*, line_id: str, sdwt_id: str) -> List[Dict[str, str]]:
    """라인/SDWT 조합 기준 PRC 그룹 목록을 반환합니다.

    입력:
    - line_id: 라인 ID
    - sdwt_id: SDWT ID(설비/공정 식별자)

    반환:
    - List[Dict[str, str]]: PRC 그룹 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(line_id=line_id, sdwt_id=sdwt_id)
    sdwt_key = filters["sdwt_id"]
    rows = _fetch_all(
        """
        select distinct
            prc_group as id
        from station_master
        where sdwt_prod_lookup = %s
          and prc_group is not null
        order by prc_group
        """,
        [sdwt_key],
    )

    return [
        _build_text_record(row, (("id", "id"), ("name", "id")))
        for row in rows
        if row.get("id") is not None
    ]


def list_tkin_prevent_prc_groups(*, user_sdwt_prod: str) -> List[Dict[str, str]]:
    """m_tkin_prevent 조회에 사용할 PRC 그룹 목록을 반환합니다.

    입력:
    - user_sdwt_prod: account_affiliation.user_sdwt_prod에서 선택한 값

    반환:
    - List[Dict[str, str]]: PRC 그룹 option 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(user_sdwt_prod=user_sdwt_prod)
    rows = _fetch_all(
        """
        select distinct
            prc_group_lookup as id
        from station_master
        where sdwt_prod_lookup = %s
          and prc_group_lookup is not null
          and trim(prc_group_lookup) <> ''
        order by prc_group_lookup
        """,
        [filters["user_sdwt_prod"]],
    )

    return [
        _build_text_record(row, (("id", "id"), ("name", "id")))
        for row in rows
        if row.get("id") is not None
    ]


def list_equipments(
    *,
    line_id: str,
    sdwt_id: str,
    prc_group: str,
) -> List[Dict[str, str]]:
    """라인/SDWT/PRC 조합 기준 설비 목록을 반환합니다.

    입력:
    - line_id: 라인 ID
    - sdwt_id: SDWT ID(설비/공정 식별자)
    - prc_group: PRC 그룹 코드

    반환:
    - List[Dict[str, str]]: 설비 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(
        line_id=line_id,
        sdwt_id=sdwt_id,
        prc_group=prc_group,
    )
    sdwt_key = filters["sdwt_id"]
    prc_key = filters["prc_group"]
    sql = """
        select distinct on (station.station)
            station.station as id,
            mapping.gpm_line_name as line_id,
            station.sdwt_prod as sdwt_prod,
            station.prc_group as prc_group
        from station_master station
        left join mes_line_mapping_info mapping
          on mapping.msg_line_id = station.floor_line_id
         and mapping.gbm_name = 'MEMORY'
         and mapping.use_yn = 'Y'
         and mapping.del_yn = 'N'
        where station.prc_group_lookup = %s
          and station.station is not null
    """
    params: List[object] = [prc_key]

    if sdwt_key:
        sql += " and station.sdwt_prod_lookup = %s"
        params.append(sdwt_key)

    sql += " order by station.station, mapping.gpm_line_name"
    rows = _fetch_all(sql, params)

    equipments: List[Dict[str, str]] = []
    seen_ids: set[str] = set()
    for row in rows:
        eqp_id = row.get("id")
        if eqp_id is None:
            continue
        normalized_eqp_id = str(eqp_id)
        if normalized_eqp_id in seen_ids:
            continue
        seen_ids.add(normalized_eqp_id)
        equipments.append(
            _build_text_record(
                row,
                (
                    ("id", "id"),
                    ("lineId", "line_id"),
                    ("sdwtId", "sdwt_prod"),
                    ("prcGroup", "prc_group"),
                    ("name", "id"),
                ),
            )
        )
    return equipments


# =============================================================================
# m_tkin_prevent 대시보드 조회
# =============================================================================


def _target_tkin_eqp_cte() -> str:
    """m_tkin_prevent 조회 대상 eqp 목록 CTE를 반환합니다."""

    return """
        with target_eqp as (
            select distinct
                station.ch_main as eqp_id
            from station_master station
            where station.sdwt_prod_lookup = %s
              and station.prc_group_lookup = %s
              and station.ch_main is not null
              and trim(station.ch_main) <> ''
        )
    """


def _tkin_scope_params(
    *,
    user_sdwt_prod: str,
    prc_group: str,
) -> List[object]:
    """m_tkin_prevent scope 필터 파라미터를 정규화합니다."""

    filters = _normalize_filters(
        user_sdwt_prod=user_sdwt_prod,
        prc_group=prc_group,
    )
    return [filters["user_sdwt_prod"], filters["prc_group"]]


def _tkin_registration_level_clause() -> str:
    """TIP 상태 조회 대상 registration_level 조건을 반환합니다."""

    placeholders = ", ".join(["%s"] * len(TKIN_PREVENT_REGISTRATION_LEVELS))
    return f"and upper(trim(prevent.registration_level)) in ({placeholders})"


def _tkin_registration_level_params() -> List[object]:
    """TIP 상태 조회 대상 registration_level 파라미터를 반환합니다."""

    return list(TKIN_PREVENT_REGISTRATION_LEVELS)


def _build_tkin_option(row: Row, field_name: str) -> Dict[str, str]:
    """dropdown option 응답을 생성합니다."""

    return _build_text_record(row, (("id", field_name), ("name", field_name)))


def list_tkin_prevent_processes(
    *,
    user_sdwt_prod: str,
    prc_group: str,
) -> List[Dict[str, str]]:
    """m_tkin_prevent process_id 목록을 반환합니다.

    입력:
    - user_sdwt_prod: account_affiliation.user_sdwt_prod에서 선택한 값
    - prc_group: PRC 그룹

    반환:
    - List[Dict[str, str]]: process_id option 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    rows = _fetch_all(
        f"""
        {_target_tkin_eqp_cte()}
        select distinct
            prevent.process_id as process_id
        from m_tkin_prevent prevent
        join target_eqp
          on upper(trim(prevent.eqp_id)) = upper(trim(target_eqp.eqp_id))
        where prevent.process_id is not null
          and trim(prevent.process_id) <> ''
          {_tkin_registration_level_clause()}
        order by prevent.process_id
        """,
        [
            *_tkin_scope_params(user_sdwt_prod=user_sdwt_prod, prc_group=prc_group),
            *_tkin_registration_level_params(),
        ],
    )
    return [
        _build_tkin_option(row, "process_id")
        for row in rows
        if row.get("process_id") is not None
    ]


def list_tkin_prevent_step_seqs(
    *,
    user_sdwt_prod: str,
    prc_group: str,
    process_id: str,
) -> List[Dict[str, str]]:
    """m_tkin_prevent step_seq 목록을 반환합니다.

    입력:
    - user_sdwt_prod: account_affiliation.user_sdwt_prod에서 선택한 값
    - prc_group: PRC 그룹
    - process_id: process_id

    반환:
    - List[Dict[str, str]]: step_seq option 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    process_key = normalize_id(process_id)
    rows = _fetch_all(
        f"""
        {_target_tkin_eqp_cte()}
        select distinct
            prevent.step_seq as step_seq
        from m_tkin_prevent prevent
        join target_eqp
          on upper(trim(prevent.eqp_id)) = upper(trim(target_eqp.eqp_id))
        where upper(trim(prevent.process_id)) = %s
          and prevent.step_seq is not null
          and trim(prevent.step_seq) <> ''
          {_tkin_registration_level_clause()}
        order by prevent.step_seq
        """,
        [
            *_tkin_scope_params(user_sdwt_prod=user_sdwt_prod, prc_group=prc_group),
            process_key,
            *_tkin_registration_level_params(),
        ],
    )
    return [
        _build_tkin_option(row, "step_seq")
        for row in rows
        if row.get("step_seq") is not None
    ]


def _format_tkin_count(value: object) -> str:
    """float count 값을 화면 표시용 문자열로 변환합니다."""

    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_tkin_status(row: Row) -> str:
    """m_tkin_prevent row를 matrix cell 표시값으로 변환합니다."""

    prevent_type = normalize_id(_safe_text(row.get("tkin_prevent_type")))
    registration_level = _safe_text(row.get("registration_level")).strip()
    registration_level_key = normalize_id(registration_level)
    restrc_lot_count = _format_tkin_count(row.get("tkin_restrc_lot_count"))
    lot_count = _format_tkin_count(row.get("tkin_lot_count"))

    if prevent_type == "DOING":
        return "DOING"

    if prevent_type == "PREVENT":
        level_label = registration_level or "PREVENT"
        if registration_level_key in TKIN_PREVENT_LEVEL2_NAMES:
            level2_count = _format_tkin_count(row.get("level2_restrc_lot_count"))
            return f"{level_label}({level2_count}/{restrc_lot_count}/{lot_count})"
        return f"{level_label}({restrc_lot_count}/{lot_count})"

    return prevent_type or "-"


def get_tkin_prevent_matrix(
    *,
    user_sdwt_prod: str,
    prc_group: str,
    process_id: str,
    step_seq: str,
) -> Dict[str, object]:
    """m_tkin_prevent matrix 데이터를 반환합니다.

    입력:
    - user_sdwt_prod: account_affiliation.user_sdwt_prod에서 선택한 값
    - prc_group: PRC 그룹
    - process_id: process_id
    - step_seq: step_seq

    반환:
    - Dict[str, object]: columns/rows/cell payload

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(process_id=process_id, step_seq=step_seq)
    rows = _fetch_all(
        f"""
        {_target_tkin_eqp_cte()}
        select
            prevent.ppid,
            prevent.eqp_id,
            prevent.tkin_prevent_chamber_id,
            prevent.tkin_prevent_type,
            prevent.registration_level,
            prevent.tkin_restrc_lot_count,
            prevent.tkin_lot_count,
            prevent.level2_restrc_lot_count
        from m_tkin_prevent prevent
        join target_eqp
          on upper(trim(prevent.eqp_id)) = upper(trim(target_eqp.eqp_id))
        where upper(trim(prevent.process_id)) = %s
          and upper(trim(prevent.step_seq)) = %s
          and prevent.ppid is not null
          and trim(prevent.ppid) <> ''
          {_tkin_registration_level_clause()}
        order by prevent.ppid, prevent.eqp_id, prevent.tkin_prevent_chamber_id
        """,
        [
            *_tkin_scope_params(user_sdwt_prod=user_sdwt_prod, prc_group=prc_group),
            filters["process_id"],
            filters["step_seq"],
            *_tkin_registration_level_params(),
        ],
    )

    columns_by_id: Dict[str, Dict[str, str]] = {}
    rows_by_ppid: Dict[str, Dict[str, object]] = {}
    seen_values: Dict[tuple[str, str], set[str]] = {}

    for row in rows:
        ppid = _safe_text(row.get("ppid")).strip()
        eqp_id = _safe_text(row.get("eqp_id")).strip()
        chamber_id = _safe_text(row.get("tkin_prevent_chamber_id")).strip() or "-"
        if not ppid or not eqp_id:
            continue

        column_id = f"{eqp_id}-{chamber_id}"
        columns_by_id.setdefault(
            column_id,
            {
                "id": column_id,
                "eqpId": eqp_id,
                "chamberId": chamber_id,
                "label": column_id,
            },
        )
        matrix_row = rows_by_ppid.setdefault(ppid, {"ppid": ppid, "cells": {}})
        cells = matrix_row["cells"]
        if not isinstance(cells, dict):
            continue

        cell_key = (ppid, column_id)
        seen_values.setdefault(cell_key, set())
        status = _format_tkin_status(row)
        if status in seen_values[cell_key]:
            continue
        seen_values[cell_key].add(status)
        cells.setdefault(column_id, []).append(
            {
                "status": status,
                "type": _safe_text(row.get("tkin_prevent_type")),
                "registrationLevel": _safe_text(row.get("registration_level")),
            }
        )

    return {
        "columns": list(columns_by_id.values()),
        "rows": list(rows_by_ppid.values()),
        "totalRows": len(rows_by_ppid),
        "totalColumns": len(columns_by_id),
    }


def get_equipment_info(*, eqp_id: str) -> Dict[str, str] | None:
    """eqpId 기준 설비 메타데이터를 반환합니다.

    입력:
    - eqp_id: 설비 ID

    반환:
    - Dict[str, str] | None: 설비 메타데이터(없으면 None)

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(eqp_id=eqp_id)
    eqp_key = filters["eqp_id"]
    row = _fetch_one(
        """
        select distinct
            station.station as id,
            mapping.gpm_line_name as line_id,
            station.sdwt_prod as sdwt_prod,
            station.prc_group as prc_group
        from station_master station
        join mes_line_mapping_info mapping
          on mapping.msg_line_id = station.floor_line_id
        where station.station_lookup = %s
          and mapping.gbm_name = 'MEMORY'
          and mapping.use_yn = 'Y'
          and mapping.del_yn = 'N'
        limit 1
        """,
        [eqp_key],
    )

    if not row:
        return None

    return _build_text_record(
        row,
        (
            ("id", "id"),
            ("lineId", "line_id"),
            ("sdwtId", "sdwt_prod"),
            ("prcGroup", "prc_group"),
        ),
    )


# =============================================================================
# 기본 DB 로그 조회
# =============================================================================


def _fetch_eqp_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    resolved_start_at = start_at or _period_date()
    return eqp_status_chg_selectors.fetch_eqp_timeline_logs(
        eqp_id=eqp_id,
        start_at=resolved_start_at,
        end_at=end_at,
        limit=limit,
    )


def _fetch_tip_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    resolved_start_at = start_at or _period_date()
    return mi_tip_update_hist_selectors.fetch_tip_timeline_logs(
        eqp_id=eqp_id,
        start_at=resolved_start_at,
        end_at=end_at,
        limit=limit,
    )


def _fetch_ctttm_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    base_url = getattr(settings, "DRONE_CTTTM_BASE_URL", "")
    time_clause, time_params = _build_time_clause(
        "workorder.inprg_date",
        start_at=start_at,
        end_at=end_at,
    )
    limit_clause, limit_params = _build_limit_clause(limit)
    rows = _fetch_all_on_default(
        f"""
        select
            workorder.workorder_id as id,
            workorder.eqp_id as eqp_id,
            'CTTTM' as log_type,
            workorder.work_type as event_type,
            workorder.inprg_date as event_time,
            null as operator,
            workorder.description as comment,
            concat(%s, workorder.workorder_id, '&lineId=', workorder.line_id) as url,
            comment.llm_summary as summary
        from ctttm_workorder_list workorder
        left join ct_process_comment comment
          on comment.workorder_id = workorder.workorder_id
        where workorder.eqp_id_lookup = %s
          and {time_clause}
        order by workorder.inprg_date desc
        {limit_clause}
        """,
        [base_url, eqp_id, *time_params, *limit_params],
    )

    return [
        {
            "id": row.get("id"),
            "eqpId": row.get("eqp_id"),
            "logType": row.get("log_type"),
            "eventType": row.get("event_type"),
            "eventTime": row.get("event_time"),
            "operator": row.get("operator"),
            "comment": row.get("comment"),
            "url": row.get("url"),
            "summary": row.get("summary"),
        }
        for row in rows
    ]


def _fetch_racb_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    resolved_start_at = start_at or _period_date()
    return racb_list_selectors.fetch_racb_timeline_logs(
        eqp_id=eqp_id,
        start_at=resolved_start_at,
        end_at=end_at,
        limit=limit,
    )


# =============================================================================
# 기본 DB ESOP 로그 조회
# =============================================================================


def _unique_sequence(values: Sequence[str]) -> List[str]:
    """입력 순서를 유지하면서 중복 문자열을 제거합니다."""

    seen: set[str] = set()
    return [
        value
        for value in values
        if value and not (value in seen or seen.add(value))
    ]


DEFECT_IMAGE_PATH = "/map/api/map-image/v3/defect-map"
DEFECT_IMAGE_STATIC_PARAMS = {
    "profileid": "DEFAULT",
    "themeid": "DEFAULT",
    "width": "500",
    "height": "500",
    "site": "GH",
    "targetDB": "APP",
    "useCache": "true",
    "includeCoordinate": "false",
}


def _to_http_url(value: object) -> str:
    """URL 값에 프로토콜이 없으면 https 기준 URL로 정규화합니다."""

    if value is None:
        return ""
    url = str(value).strip()
    if not url:
        return ""
    if re.match(r"^https?://", url, flags=re.IGNORECASE):
        return url
    return f"https://{url}"


def _normalize_defect_image_row(value: object) -> int | None:
    """defect map 이미지 행 번호를 정수로 정규화합니다."""

    try:
        selected_row = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return selected_row if selected_row >= 0 else None


def _build_esop_defect_image_urls(entry: Dict[str, object], map_url: str) -> List[str]:
    """ESOP defect_url JSON에서 defect map 이미지 URL 목록을 생성합니다."""

    raw_image_urls = entry.get("image_urls")
    if isinstance(raw_image_urls, list):
        image_urls = [_to_http_url(url) for url in raw_image_urls]
        return [url for url in image_urls if url]

    map_file = str(entry.get("map_file") or "").strip()
    raw_rows = entry.get("image_rows")
    if raw_rows is None:
        raw_rows = entry.get("images_rows")
    if not map_url or not map_file or not isinstance(raw_rows, list):
        return []

    match = re.match(r"^(https?://[^/]+)", map_url, flags=re.IGNORECASE)
    if not match:
        return []

    origin = match.group(1)
    seen_rows: set[int] = set()
    image_urls: List[str] = []
    for raw_row in raw_rows:
        selected_row = _normalize_defect_image_row(raw_row)
        if selected_row is None or selected_row in seen_rows:
            continue
        seen_rows.add(selected_row)

        params = {
            "file": map_file,
            "selected_row": str(selected_row),
            **DEFECT_IMAGE_STATIC_PARAMS,
        }
        query = urlencode(params)
        image_urls.append(f"{origin}{DEFECT_IMAGE_PATH}?{query}")

    return image_urls


def _normalize_esop_defect_maps(value: object) -> List[Dict[str, object]]:
    """ESOP defect_url 저장값을 화면용 링크 목록으로 정규화합니다."""

    if not value:
        return []

    entries: object
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError:
            if not raw.startswith("http"):
                return []
            return [{"label": "Defect Map", "url": raw, "imageUrls": []}]
    else:
        entries = value

    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return []

    maps: List[Dict[str, object]] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            continue
        url = _to_http_url(entry.get("map_url") or entry.get("url"))
        if not url:
            continue
        label = str(
            entry.get("label") or entry.get("step_seq") or f"Defect Map {index}"
        ).strip()
        maps.append(
            {
                "label": label or f"Defect Map {index}",
                "url": url,
                "imageUrls": _build_esop_defect_image_urls(entry, url),
            }
        )
    return maps


def _build_esop_chamber_filters(eqp_id: str) -> tuple[str, str, List[object]]:
    """ESOP 조회용 기본 설비 ID와 chamber 조건을 구성합니다."""

    if "-" not in eqp_id:
        return eqp_id, "", []

    base_eqp, suffix = eqp_id.split("-", 1)
    digits = re.findall(r"\d", suffix)
    chamber_candidates = _unique_sequence(digits or list(suffix.strip()))
    if not chamber_candidates:
        return base_eqp, "", []

    like_clauses = " or ".join(["sop.chamber_ids like %s"] * len(chamber_candidates))
    return (
        base_eqp,
        f" and ({like_clauses})",
        [f"%{ch}%" for ch in chamber_candidates],
    )


def _fetch_esop_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    base_eqp, match_clause, match_params = _build_esop_chamber_filters(eqp_id)
    time_clause, time_params = _build_time_clause(
        "sop.created_at",
        start_at=start_at,
        end_at=end_at,
    )
    limit_clause, limit_params = _build_limit_clause(limit)

    rows = _fetch_all_on_default(
        f"""
        select
            sop.id as id,
            sop.sample_type as event_type,
            sop.created_at as event_time,
            sop.knox_id as operator,
            sop.status as status,
            sop.comment as comment,
            sop.line_id as line_id,
            sop.eqp_id as eqp_id,
            sop.chamber_ids as chamber_ids,
            sop.lot_id as lot_id,
            sop.defect_url as defect_url
        from drone_sop as sop
        where {time_clause}
          and sop.eqp_id_lookup = %s
          {match_clause}
        order by sop.created_at desc
        {limit_clause}
        """,
        [*time_params, base_eqp, *match_params, *limit_params],
    )

    return [
        {
            "id": row.get("id"),
            "logType": "ESOP",
            "eventType": row.get("event_type"),
            "eventTime": row.get("event_time"),
            "operator": row.get("operator"),
            "status": row.get("status"),
            "comment": row.get("comment"),
            "lineId": row.get("line_id"),
            "eqpId": row.get("eqp_id"),
            "eqpCb": f"{row.get('eqp_id') or '-'}-{row.get('chamber_ids') or '-'}",
            "lotId": row.get("lot_id"),
            "defectMaps": _normalize_esop_defect_maps(row.get("defect_url")),
        }
        for row in rows
    ]


OBSERVER_LOG_FETCHERS: Dict[str, LogFetcher] = {
    "eqp": lambda eqp_key, start_at, end_at, limit: _fetch_eqp_logs(
        eqp_id=eqp_key,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    ),
    "tip": lambda eqp_key, start_at, end_at, limit: _fetch_tip_logs(
        eqp_id=eqp_key,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    ),
    "ctttm": lambda eqp_key, start_at, end_at, limit: _fetch_ctttm_logs(
        eqp_id=eqp_key,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    ),
    "racb": lambda eqp_key, start_at, end_at, limit: _fetch_racb_logs(
        eqp_id=eqp_key,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    ),
    "esop": lambda eqp_key, start_at, end_at, limit: _fetch_esop_logs(
        eqp_id=eqp_key,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    ),
}
OBSERVER_LOG_KEYS = ("eqp", "tip", "ctttm", "racb", "esop")


def _fetch_logs_by_type_normalized(
    *,
    eqp_key: str,
    type_key: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> LogRows:
    """정규화가 끝난 설비 ID로 타입별 로그를 조회합니다."""

    fetcher = OBSERVER_LOG_FETCHERS.get(type_key)
    if fetcher is None:
        return []
    return fetcher(eqp_key, start_at, end_at, limit)


# =============================================================================
# 공개 로그 조합 함수
# =============================================================================


def get_logs_for_equipment(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> Dict[str, List[Dict[str, object]]]:
    """설비 로그(타입별)를 반환합니다.

    입력:
    - eqp_id: 설비 ID

    반환:
    - Dict[str, List[Dict[str, object]]]: 타입별 로그 묶음

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    eqp_key = normalize_id(eqp_id)
    return {
        key: _fetch_logs_by_type_normalized(
            eqp_key=eqp_key,
            type_key=key,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
        for key in OBSERVER_LOG_KEYS
    }


def get_logs_by_type(
    *,
    eqp_id: str,
    log_key: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    """특정 타입 로그만 반환합니다.

    입력:
    - eqp_id: 설비 ID
    - log_key: 로그 타입 키(eqp, tip 등)

    반환:
    - List[Dict[str, object]]: 타입별 로그 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    eqp_key = normalize_id(eqp_id)
    type_key = (log_key or "").strip().lower()
    return _fetch_logs_by_type_normalized(
        eqp_key=eqp_key,
        type_key=type_key,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )


def get_merged_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    """모든 타입 로그를 합쳐 정렬된 목록으로 반환합니다.

    입력:
    - eqp_id: 설비 ID

    반환:
    - List[Dict[str, object]]: eventTime 기준 정렬된 로그 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    eqp_key = normalize_id(eqp_id)
    merged: List[Dict[str, object]] = []
    for key in OBSERVER_LOG_KEYS:
        merged.extend(
            _fetch_logs_by_type_normalized(
                eqp_key=eqp_key,
                type_key=key,
                start_at=start_at,
                end_at=end_at,
                limit=limit,
            )
        )

    merged.sort(key=lambda log: str(log.get("eventTime") or ""), reverse=True)
    if limit is None:
        return merged
    return merged[:limit]


__all__ = [
    "get_equipment_info",
    "get_logs_by_type",
    "get_logs_for_equipment",
    "get_merged_logs",
    "list_equipments",
    "list_lines",
    "list_prc_groups",
    "list_sdwt_for_line",
    "list_tkin_prevent_prc_groups",
    "DEFAULT_LOG_QUERY_DAYS",
    "MAX_LOG_LIMIT",
    "normalize_id",
]
