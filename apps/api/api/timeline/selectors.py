# =============================================================================
# 모듈 설명: timeline DB 데이터 셀렉터를 제공합니다.
# - 주요 함수: list_lines, list_sdwt_for_line, get_merged_logs 등
# - 불변 조건: timeline 전용 DB에서 조회하며, 드론 로그는 기본 DB를 사용합니다.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Dict, List, Sequence

from django.conf import settings
from django.db import connections

TIMELINE_DB_ALIAS = "timeline"
TIMELINE_DB_ENGINE = "django.db.backends.postgresql"
TIMELINE_DB_NAME = "timeline"
TIMELINE_DB_USER = "airflow"
TIMELINE_DB_PASSWORD = "airflow"
TIMELINE_DB_HOST = "10.172.117.91"
TIMELINE_DB_PORT = "8010"
TIMELINE_DB_CONN_MAX_AGE = 60
TIMELINE_QUERY_DAYS = 30


# =============================================================================
# 내부 헬퍼
# =============================================================================


def _safe_text(value: object) -> str:
    """None 값을 안전하게 문자열로 정리합니다."""

    return "" if value is None else str(value)


def _period_date(days: int = TIMELINE_QUERY_DAYS) -> str:
    """조회 기준일(YYYY-MM-DD)을 반환합니다."""

    return datetime.strftime(datetime.now() - timedelta(days=days), "%Y-%m-%d")

def _get_timeline_connection():
    """타임라인 DB 연결 설정을 갱신하고 연결 객체를 반환합니다."""

    desired = {
        "ENGINE": TIMELINE_DB_ENGINE,
        "NAME": TIMELINE_DB_NAME,
        "USER": TIMELINE_DB_USER,
        "PASSWORD": TIMELINE_DB_PASSWORD,
        "HOST": TIMELINE_DB_HOST,
        "PORT": TIMELINE_DB_PORT,
        "CONN_MAX_AGE": TIMELINE_DB_CONN_MAX_AGE,
    }
    connection = connections[TIMELINE_DB_ALIAS]
    if any(connection.settings_dict.get(key) != value for key, value in desired.items()):
        connection.close()
        connection.settings_dict.update(desired)
    return connection


def _fetch_all(query: str, params: Sequence[object] | None = None) -> List[Dict[str, object]]:
    """타임라인 DB에서 조회 결과를 dict 리스트로 반환합니다."""

    with _get_timeline_connection().cursor() as cursor:
        cursor.execute(query, params or [])
        columns = [col[0] for col in (cursor.description or [])]
        rows = cursor.fetchall()

    return [dict(zip(columns, row)) for row in rows]


def _fetch_all_on_default(query: str, params: Sequence[object] | None = None) -> List[Dict[str, object]]:
    """기본 DB에서 조회 결과를 dict 리스트로 반환합니다."""

    with connections["default"].cursor() as cursor:
        cursor.execute(query, params or [])
        columns = [col[0] for col in (cursor.description or [])]
        rows = cursor.fetchall()

    return [dict(zip(columns, row)) for row in rows]


def _fetch_one(query: str, params: Sequence[object] | None = None) -> Dict[str, object] | None:
    """단일 행 조회를 반환합니다(없으면 None)."""

    rows = _fetch_all(query, params)
    return rows[0] if rows else None


# =============================================================================
# 공개 함수
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


def list_lines() -> List[Dict[str, str]]:
    """라인 목록을 반환합니다.

    입력:
    - 없음

    반환:
    - List[Dict[str, str]]: 라인 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    rows = _fetch_all(
        """
        select
            line_id as id,
            name as name
        from line_list
        order by name
        """
    )
    results: List[Dict[str, str]] = []
    for row in rows:
        if row.get("id") is None:
            continue
        results.append(
            {
                "id": _safe_text(row.get("id")),
                "name": _safe_text(row.get("name")),
            }
        )
    return results


def list_sdwt_for_line(*, line_id: str) -> List[Dict[str, str]]:
    """라인 기준 SDWT 목록을 반환합니다.

    입력:
    - line_id: 라인 ID

    반환:
    - List[Dict[str, str]]: SDWT 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    line_key = normalize_id(line_id)
    rows = _fetch_all(
        """
        select distinct
            sdwt_prod as id
        from sdwt_eqp
        where line_id = %s
          and sdwt_prod is not null
        order by sdwt_prod
        """,
        [line_key],
    )

    results: List[Dict[str, str]] = []
    for row in rows:
        if row.get("id") is None:
            continue
        results.append(
            {
                "id": _safe_text(row.get("id")),
                "lineId": line_key,
                "name": _safe_text(row.get("id")),
            }
        )
    return results


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

    line_key = normalize_id(line_id)
    sdwt_key = normalize_id(sdwt_id)
    rows = _fetch_all(
        """
        select distinct
            prc_group as id
        from sdwt_eqp
        where upper(line_id) = %s
          and upper(sdwt_prod) = %s
          and prc_group is not null
        order by prc_group
        """,
        [line_key, sdwt_key],
    )

    results: List[Dict[str, str]] = []
    for row in rows:
        if row.get("id") is None:
            continue
        results.append(
            {
                "id": _safe_text(row.get("id")),
                "name": _safe_text(row.get("id")),
            }
        )
    return results


def list_equipments(*, line_id: str, sdwt_id: str, prc_group: str) -> List[Dict[str, str]]:
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

    line_key = normalize_id(line_id)
    sdwt_key = normalize_id(sdwt_id)
    prc_key = normalize_id(prc_group)
    sql = """
        select distinct
            eqp_cb as id,
            line_id as line_id,
            sdwt_prod as sdwt_prod,
            prc_group as prc_group
        from sdwt_eqp
        where upper(line_id) = %s
          and eqp_cb is not null
    """
    params: List[object] = [line_key]

    if sdwt_key:
        sql += " and upper(sdwt_prod) = %s"
        params.append(sdwt_key)

    if prc_key:
        sql += " and upper(prc_group) = %s"
        params.append(prc_key)

    sql += " order by eqp_cb"
    rows = _fetch_all(sql, params)

    results: List[Dict[str, str]] = []
    for row in rows:
        if row.get("id") is None:
            continue
        results.append(
            {
                "id": _safe_text(row.get("id")),
                "lineId": _safe_text(row.get("line_id")),
                "sdwtId": _safe_text(row.get("sdwt_prod")),
                "prcGroup": _safe_text(row.get("prc_group")),
                "name": _safe_text(row.get("id")),
            }
        )
    return results


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

    eqp_key = normalize_id(eqp_id)
    row = _fetch_one(
        """
        select distinct
            eqp_cb as id,
            line_id as line_id,
            sdwt_prod as sdwt_prod,
            prc_group as prc_group
        from sdwt_eqp
        where eqp_cb = %s
        limit 1
        """,
        [eqp_key],
    )

    if not row:
        return None

    return {
        "id": _safe_text(row.get("id")),
        "lineId": _safe_text(row.get("line_id")),
        "sdwtId": _safe_text(row.get("sdwt_prod")),
        "prcGroup": _safe_text(row.get("prc_group")),
    }


def _fetch_eqp_logs(*, eqp_id: str) -> List[Dict[str, object]]:
    query_date = _period_date()
    rows = _fetch_all(
        """
        select
            concat('EQP-', row_number() over (order by event_time)) as id,
            eqp_cb as eqp_cb,
            'EQP' as log_type,
            event_type as event_type,
            event_time as event_time,
            operator as operator,
            comment as comment
        from eqp_status_hist
        where event_time > %s
          and eqp_cb = %s
        order by event_time
        """,
        [query_date, eqp_id],
    )

    return [
        {
            "id": row.get("id"),
            "eqpId": row.get("eqp_cb"),
            "logType": row.get("log_type"),
            "eventType": row.get("event_type"),
            "eventTime": row.get("event_time"),
            "operator": row.get("operator"),
            "comment": row.get("comment"),
        }
        for row in rows
    ]


def _fetch_tip_logs(*, eqp_id: str) -> List[Dict[str, object]]:
    query_date = _period_date()
    rows = _fetch_all(
        """
        select
            concat('TIP-', row_number() over (order by gpm_update_date)) as id,
            eqp_cb as eqp_cb,
            'TIP' as log_type,
            event_type as event_type,
            gpm_update_date as event_time,
            split_part(register_name, '-', 1) as operator,
            tip_comment as comment,
            line_id as line_id,
            process_id as process,
            step_seq as step,
            ppid as ppid
        from gpm_tip_hist
        where gpm_update_date > %s
          and eqp_cb = %s
        order by gpm_update_date
        """,
        [query_date, eqp_id],
    )

    return [
        {
            "id": row.get("id"),
            "eqpId": row.get("eqp_cb"),
            "logType": row.get("log_type"),
            "eventType": row.get("event_type"),
            "eventTime": row.get("event_time"),
            "operator": row.get("operator"),
            "comment": row.get("comment"),
            "lineId": row.get("line_id"),
            "process": row.get("process"),
            "step": row.get("step"),
            "ppid": row.get("ppid"),
        }
        for row in rows
    ]


def _fetch_ctttm_logs(*, eqp_id: str) -> List[Dict[str, object]]:
    period = _period_date()
    base_url = getattr(settings, "DRONE_CTTTM_BASE_URL", "")
    rows = _fetch_all(
        """
        select
            workorder_id as id,
            eqp_id as eqp_id,
            'CTTTM' as log_type,
            work_type as event_type,
            inprg_date as event_time,
            null as operator,
            description as comment,
            concat(%s, workorder_id, '&lineId=', line_id) as url
        from ctttm_workorder_list
        where eqp_id = %s
          and inprg_date > %s
        order by inprg_date
        """,
        [base_url, eqp_id, period],
    )

    if not rows:
        return []

    workorder_ids = list({row.get("id") for row in rows if row.get("id") is not None})
    summary_rows: List[Dict[str, object]] = []
    if workorder_ids:
        summary_rows = _fetch_all(
            """
            select
                workorder_id as id,
                llm_summary_body as summary
            from llm_ctttm
            where workorder_id = any(%s)
            """,
            [workorder_ids],
        )
    summary_map = {
        row.get("id"): row.get("summary")
        for row in summary_rows
        if row.get("id") is not None
    }

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
            "summary": summary_map.get(row.get("id")),
        }
        for row in rows
    ]


def _fetch_racb_logs(*, eqp_id: str) -> List[Dict[str, object]]:
    period = _period_date()
    rows = _fetch_all(
        """
        select
            CONCAT(line_id, '-', eqp_cb, '-' , create_date, '-', 'update_date' ) as id,
            racb_type_cd as event_type,
            create_date as event_time,
            user_name as operator,
            title as comment,
            line_id as line_id,
            eqp_cb as eqp_cb
        from racb_list
        where eqp_cb = %s
          and create_date > %s
        order by create_date
        """,
        [eqp_id, period],
    )

    return [
        {
            "id": row.get("id"),
            "logType": "RACB",
            "eventType": row.get("event_type"),
            "eventTime": row.get("event_time"),
            "operator": row.get("operator"),
            "comment": row.get("comment"),
            "lineId": row.get("line_id"),
            "eqpId": row.get("eqp_id"),
        }
        for row in rows
    ]


def _fetch_drone_logs(*, eqp_id: str) -> List[Dict[str, object]]:
    period = _period_date()
    base_eqp = eqp_id
    chamber_candidates: List[str] = []
    if "-" in eqp_id:
        base_eqp, suffix = eqp_id.split("-", 1)
        digits = re.findall(r"\d", suffix)
        if digits:
            seen = set()
            chamber_candidates = [d for d in digits if not (d in seen or seen.add(d))]
        else:
            seen = set()
            chamber_candidates = [
                ch for ch in suffix.strip() if ch and not (ch in seen or seen.add(ch))
            ]

    if chamber_candidates:
        like_clauses = " or ".join(["chamber_ids like %s"] * len(chamber_candidates))
        match_clause = f" and ({like_clauses})"
        match_params: List[object] = [f"%{ch}%" for ch in chamber_candidates]
    else:
        match_clause = ""
        match_params = []

    rows = _fetch_all_on_default(
        f"""
        select
            id as id,
            sample_type as event_type,
            created_at as event_time,
            user_sdwt_prod as operator,
            status as status,
            comment as comment,
            jira_key as jira_key,
            line_id as line_id,
            eqp_id as eqp_id
        from drone_sop
        where created_at > %s
          and eqp_id = %s
          {match_clause}
        order by created_at
        """,
        [period, base_eqp, *match_params],
    )

    return [
        {
            "id": row.get("id"),
            "logType": "DRONE",
            "eventType": row.get("event_type"),
            "eventTime": row.get("event_time"),
            "operator": row.get("operator"),
            "status": row.get("status"),
            "comment": row.get("comment"),
            "jiraKey": row.get("jira_key"),
            "lineId": row.get("line_id"),
            "eqpId": row.get("eqp_id"),
        }
        for row in rows
    ]


def get_logs_for_equipment(*, eqp_id: str) -> Dict[str, List[Dict[str, object]]]:
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
        "eqp": _fetch_eqp_logs(eqp_id=eqp_key),
        "tip": _fetch_tip_logs(eqp_id=eqp_key),
        "ctttm": _fetch_ctttm_logs(eqp_id=eqp_key),
        "racb": _fetch_racb_logs(eqp_id=eqp_key),
        "jira": _fetch_drone_logs(eqp_id=eqp_key),
        "event": [],
    }


def get_logs_by_type(*, eqp_id: str, log_key: str) -> List[Dict[str, object]]:
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

    if type_key == "eqp":
        return _fetch_eqp_logs(eqp_id=eqp_key)
    if type_key == "tip":
        return _fetch_tip_logs(eqp_id=eqp_key)
    if type_key == "ctttm":
        return _fetch_ctttm_logs(eqp_id=eqp_key)
    if type_key == "racb":
        return _fetch_racb_logs(eqp_id=eqp_key)
    if type_key == "jira":
        return _fetch_drone_logs(eqp_id=eqp_key)

    return []


def get_merged_logs(*, eqp_id: str) -> List[Dict[str, object]]:
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
    for key in ("eqp", "tip", "ctttm", "racb", "jira", "event"):
        merged.extend(get_logs_by_type(eqp_id=eqp_key, log_key=key))

    merged.sort(key=lambda log: str(log.get("eventTime") or ""))
    return merged


__all__ = [
    "get_equipment_info",
    "get_logs_by_type",
    "get_logs_for_equipment",
    "get_merged_logs",
    "list_equipments",
    "list_lines",
    "list_prc_groups",
    "list_sdwt_for_line",
    "normalize_id",
]
