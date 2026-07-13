# =============================================================================
# 모듈: L3 Spider 셀렉터
# 주요 함수: get_data_root, iter_data_files, read_parquet_columns, list_mail_rules_for_user
# 주요 가정: 파일시스템/DB 조회만 수행하며 쓰기 작업은 하지 않습니다.
# =============================================================================
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Sequence

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Q

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as pa_ds


def get_data_root() -> Path:
    """L3 Spider 데이터 루트 경로를 반환합니다."""

    return Path(settings.L3_SPIDER_DATA_ROOT).expanduser().resolve()


def ensure_data_root() -> Path:
    """데이터 루트가 존재하는지 확인하고 경로를 반환합니다."""

    root = get_data_root()
    if not root.exists():
        raise FileNotFoundError(f"L3 Spider 데이터 경로를 찾을 수 없습니다: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"L3 Spider 데이터 경로가 폴더가 아닙니다: {root}")
    return root


_INDEX_SCHEMA = "public"
_FILE_INDEX_NAME = "l3_spider_file_index"
_DAILY_RUN_STATS_NAME = "l3_spider_daily_run_stats"
_RUN_STATUS_NAME = "l3_spider_run_status"
_FILE_INDEX_TABLE = f'"{_INDEX_SCHEMA}"."{_FILE_INDEX_NAME}"'
_DAILY_RUN_STATS_TABLE = f'"{_INDEX_SCHEMA}"."{_DAILY_RUN_STATS_NAME}"'
_RUN_STATUS_TABLE = f'"{_INDEX_SCHEMA}"."{_RUN_STATUS_NAME}"'


def _fetchall(sql: str, params: Sequence[object] = ()) -> list[tuple]:
    """기본 PostgreSQL 연결에서 parameterized SQL을 실행합니다."""

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())


def _fetch_dicts(sql: str, params: Sequence[object] = ()) -> list[dict]:
    """PostgreSQL 조회 결과를 컬럼명 기반 dict 목록으로 반환합니다."""

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _table_columns(table_name: str) -> set[str]:
    """PostgreSQL public schema의 외부 적재 테이블 컬럼을 반환합니다."""

    rows = _fetchall(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        (_INDEX_SCHEMA, table_name),
    )
    if not rows:
        raise RuntimeError(f"PostgreSQL {_INDEX_SCHEMA}.{table_name} 테이블이 없습니다.")
    return {str(row[0]) for row in rows}


def _rebuild_container_path(root: Path, date, line_id, process_id, eds_step, filepath) -> Path:
    """인덱스에 저장된 filepath의 base(절대/상대/다른 호스트 무관)를 무시하고,
    현재 API 컨테이너의 데이터 루트 + 파티션 컬럼 + 파일명으로 실제 경로를 재구성합니다.

    알고리즘 서버가 filepath를 어떤 base로 저장했든({date}/... 상대경로든,
    /algo-host/.../daily_anomaly/... 절대경로든) 컨테이너 경로로 안전하게 매핑됩니다.
    파티션 컬럼은 조회 WHERE 조건에도 쓰이므로 항상 존재/정확이 보장됩니다.
    """
    return (
        root
        / str(date)
        / str(line_id)
        / str(process_id)
        / str(eds_step)
        / Path(str(filepath)).name
    )


def query_indexed_files(
    date: Optional[str] = None,
    line_id: Optional[str] = None,
    process_id: Optional[str] = None,
    eds_step: Optional[str] = None,
    eqp_id: Optional[str] = None,
    chamber_id: Optional[str] = None,
    high_risk_only: bool = False,
) -> list[Path]:
    """PostgreSQL file_index에서 조건에 맞는 filepath 목록을 조회합니다.

    반환된 Path 리스트는 기존 pd.read_parquet() 에 그대로 넘길 수 있습니다.
    """
    conditions: list[str] = []
    params: list = []

    if date is not None:
        conditions.append("date = %s")
        params.append(date)
    if line_id is not None:
        conditions.append("line_id = %s")
        params.append(line_id)
    if process_id is not None:
        conditions.append("process_id = %s")
        params.append(process_id)
    if eds_step is not None:
        conditions.append("eds_step = %s")
        params.append(eds_step)
    if high_risk_only:
        conditions.append("has_high_risk = 1")
    if eqp_id is not None:
        conditions.append(
            "EXISTS (SELECT 1 FROM jsonb_array_elements_text("
            "COALESCE(NULLIF(eqp_ids::text, ''), '[]')::jsonb) AS item(value) "
            "WHERE item.value = %s)"
        )
        params.append(eqp_id)
    if chamber_id is not None:
        conditions.append(
            "EXISTS (SELECT 1 FROM jsonb_array_elements_text("
            "COALESCE(NULLIF(chamber_ids::text, ''), '[]')::jsonb) AS item(value) "
            "WHERE item.value = %s)"
        )
        params.append(chamber_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = (
        "SELECT date, line_id, process_id, eds_step, filepath "
        f"FROM {_FILE_INDEX_TABLE} {where}"
    )
    rows = _fetchall(query, params)

    root = get_data_root()
    return [_rebuild_container_path(root, *row) for row in rows]


def query_indexed_files_by_range(
    date_from: str,
    date_to: str,
    line_id: Optional[str] = None,
    process_id: Optional[str] = None,
    eds_step: Optional[str] = None,
    eqp_id: Optional[str] = None,
    chamber_id: Optional[str] = None,
    high_risk_only: bool = False,
) -> list[Path]:
    """PostgreSQL에서 날짜 범위로 filepath 목록을 조회합니다.

    양 끝 포함(inclusive). 'YYYY-MM-DD' 형식.
    """
    conditions = ["date >= %s", "date <= %s"]
    params: list = [date_from, date_to]

    if line_id is not None:
        conditions.append("line_id = %s")
        params.append(line_id)
    if process_id is not None:
        conditions.append("process_id = %s")
        params.append(process_id)
    if eds_step is not None:
        conditions.append("eds_step = %s")
        params.append(eds_step)
    if high_risk_only:
        conditions.append("has_high_risk = 1")
    if eqp_id is not None:
        conditions.append(
            "EXISTS (SELECT 1 FROM jsonb_array_elements_text("
            "COALESCE(NULLIF(eqp_ids::text, ''), '[]')::jsonb) AS item(value) "
            "WHERE item.value = %s)"
        )
        params.append(eqp_id)
    if chamber_id is not None:
        conditions.append(
            "EXISTS (SELECT 1 FROM jsonb_array_elements_text("
            "COALESCE(NULLIF(chamber_ids::text, ''), '[]')::jsonb) AS item(value) "
            "WHERE item.value = %s)"
        )
        params.append(chamber_id)

    query = (
        "SELECT date, line_id, process_id, eds_step, filepath "
        f"FROM {_FILE_INDEX_TABLE} WHERE {' AND '.join(conditions)}"
    )
    rows = _fetchall(query, params)

    root = get_data_root()
    return [_rebuild_container_path(root, *row) for row in rows]


def iter_data_files_legacy(selection: dict[str, object]) -> list[Path]:
    """디렉토리 직접 스캔 방식 (인덱스 미사용) — iter_data_files의 폴백."""
    ensure_data_root()
    root = get_data_root()
    root_resolved = root.resolve()
    files: list[Path] = []
    for date in selection.get("dates", []):
        for line_id in selection.get("lineIds", []):
            for process_id in selection.get("processIds", []):
                for eds_step in selection.get("edsSteps", []):
                    dir_path = root / date / line_id / process_id / eds_step
                    try:
                        dir_path.resolve().relative_to(root_resolved)
                    except ValueError as exc:
                        raise ValueError("데이터 경로가 루트 밖으로 벗어났습니다.") from exc
                    if not dir_path.exists() or not dir_path.is_dir():
                        continue
                    for path in dir_path.iterdir():
                        if path.is_file():
                            files.append(path)
    return files


def iter_data_files(selection: dict[str, object]) -> list[Path]:
    """선택 조건에 해당하는 Parquet 파일 목록을 반환합니다.

    (date, line_id, process_id, eds_step) 조합별로 인덱스를 조회하고,
    결과가 빈 조합만 기존 디렉토리 스캔으로 폴백합니다.
    """
    files: list[Path] = []
    for date in selection.get("dates", []):
        for line_id in selection.get("lineIds", []):
            for process_id in selection.get("processIds", []):
                for eds_step in selection.get("edsSteps", []):
                    found = query_indexed_files(
                        date=date,
                        line_id=line_id,
                        process_id=process_id,
                        eds_step=eds_step,
                    )
                    if found:
                        files.extend(found)
                    else:
                        files.extend(iter_data_files_legacy({
                            "dates": [date],
                            "lineIds": [line_id],
                            "processIds": [process_id],
                            "edsSteps": [eds_step],
                        }))
    return files


def iter_date_files_legacy(date: str) -> list[Path]:
    """특정 날짜 하위의 모든 파일을 디렉토리 스캔합니다 (인덱스 미사용 폴백)."""
    ensure_data_root()
    root = get_data_root()
    root_resolved = root.resolve()
    date_dir = root / date
    try:
        date_dir.resolve().relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("데이터 경로가 루트 밖으로 벗어났습니다.") from exc
    if not date_dir.exists() or not date_dir.is_dir():
        return []
    # 구조: {date}/{line_id}/{process_id}/{eds_step}/{file}
    return [path for path in date_dir.glob("*/*/*/*") if path.is_file()]


def iter_date_files(date: str) -> list[Path]:
    """특정 날짜의 모든 Parquet 파일을 반환합니다 (line/process/eds 무관 전체).

    인덱스 조회 결과가 비어 있으면 기존 디렉토리 스캔으로 폴백합니다.
    """
    found = query_indexed_files(date=date)
    if found:
        return found
    return iter_date_files_legacy(date)


# {date}/{line_id}/{process_id}/{eds_step}/{file} — 디렉토리 3단계를 파티션 컬럼으로 매핑
_DATE_PARTITIONING = pa_ds.DirectoryPartitioning(
    pa.schema([("line_id", pa.string()), ("process_id", pa.string()), ("eds_step", pa.string())])
)


def read_date_dataset(date: str, columns: Sequence[str]) -> pd.DataFrame:
    """특정 날짜 디렉토리를 pyarrow.dataset 단일 스캔으로 읽습니다.

    파일별 개별 read_parquet(수백~수천 개) 대신 한 번의 스캔으로 필요한 컬럼만 로드하고,
    line/process/eds는 디렉토리 경로에서 파티션 컬럼으로 자동 매핑합니다. 작은 파일이 많을수록 큰 이점.
    step_seq/ppid는 파일명에만 있어 포함되지 않습니다(호출부에서 필요 시 파일별 경로 사용).
    주의: 쓰는 중인 부분 파일을 만나면 예외가 날 수 있음 → 호출부에서 파일별 읽기로 폴백하세요.
    """
    ensure_data_root()
    root = get_data_root()
    root_resolved = root.resolve()
    date_dir = root / date
    try:
        date_dir.resolve().relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("데이터 경로가 루트 밖으로 벗어났습니다.") from exc
    if not date_dir.exists() or not date_dir.is_dir():
        return pd.DataFrame()

    dataset = pa_ds.dataset(str(date_dir), format="parquet", partitioning=_DATE_PARTITIONING)
    available = set(dataset.schema.names)
    want: list[str] = []
    for col in columns:
        if col in available:
            want.append(col)
        elif col == "display_status" and "display status" in available:
            want.append("display status")  # 공백 변형 컬럼도 수용 (호출부에서 정규화)
    for part_col in ("line_id", "process_id", "eds_step"):
        if part_col in available and part_col not in want:
            want.append(part_col)
    if not want:
        return pd.DataFrame()
    return dataset.to_table(columns=want).to_pandas()


def iter_filter_candidate_files(
    dates: list[str],
    line_ids: list[str],
    process_ids: list[str],
    eds_step: str,
    step_seq: str,
    ppid: str,
) -> Iterable[Path]:
    """step_seq#ppid#* 패턴에 해당하는 파일만 순회합니다."""

    root = ensure_data_root()
    root_resolved = root.resolve()
    prefix = f"{step_seq}#{ppid}#"

    for date in dates:
        for line_id in line_ids:
            for process_id in process_ids:
                dir_path = root / date / line_id / process_id / eds_step
                try:
                    dir_path.resolve().relative_to(root_resolved)
                except ValueError:
                    continue
                if not dir_path.exists() or not dir_path.is_dir():
                    continue
                for path in dir_path.iterdir():
                    if path.is_file() and path.name.startswith(prefix):
                        yield path


def _query_all_line_process_step_legacy() -> list[tuple[str, str, str]]:
    """인덱스 미사용: 파일명 스캔으로 (line_id, process_id, step_seq) 조합을 수집합니다."""
    root = get_data_root()
    if not root.exists():
        return []
    combos: set[tuple[str, str, str]] = set()
    for path in root.glob("*/*/*/*/*"):  # 날짜/line_id/process_id/eds_step/파일
        if not path.is_file():
            continue
        parts = path.relative_to(root).parts
        if len(parts) < 5:
            continue
        line_id, process_id = parts[1], parts[2]
        name = parts[4]
        step_seq = name.split("#", 1)[0] if "#" in name else ""
        combos.add((line_id, process_id, step_seq))
    return sorted(combos)


def query_all_date_line_process_eds_step() -> list[tuple[str, str, str, str, str]]:
    """PostgreSQL daily_run_stats의 모든 분석 조합을 반환합니다.

    날짜별 line_name 가용성(lineNameAvailability) 계산용. line_name은 step_seq로 결정되므로,
    특정 날짜에 어떤 line_name→process→eds가 '실제로' 존재하는지 알려면 date+eds+step_seq가
    함께 필요합니다.
    """
    rows = _fetchall(
        "SELECT DISTINCT date, line_id, process_id, eds_step, step_seq "
        f"FROM {_DAILY_RUN_STATS_TABLE}"
    )
    return [(str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4])) for r in rows]


def _query_all_date_line_process_eds_step_legacy() -> list[tuple[str, str, str, str, str]]:
    """인덱스 미사용: 파일명 스캔으로 (date, line_id, process_id, eds_step, step_seq) 조합 수집."""
    root = get_data_root()
    if not root.exists():
        return []
    combos: set[tuple[str, str, str, str, str]] = set()
    for path in root.glob("*/*/*/*/*"):  # date/line_id/process_id/eds_step/file
        if not path.is_file():
            continue
        parts = path.relative_to(root).parts
        if len(parts) < 5:
            continue
        date, line_id, process_id, eds_step = parts[0], parts[1], parts[2], parts[3]
        name = parts[4]
        step_seq = name.split("#", 1)[0] if "#" in name else ""
        combos.add((date, line_id, process_id, eds_step, step_seq))
    return sorted(combos)


def query_date_file_index(date: str) -> list[dict]:
    """PostgreSQL file_index의 특정 날짜 파일별 집계를 반환합니다.

    high_risk_cnt/warning_cnt/normal_cnt 가 있으면 요약을 parquet 없이 집계할 수 있습니다.
    카운트 컬럼이 없는 구 테이블이면 빈 리스트를 반환해 Parquet 집계로 전환합니다.
    """
    available = _table_columns(_FILE_INDEX_NAME)
    if "high_risk_cnt" not in available:
        return []
    wanted = [
        "filepath", "line_id", "process_id", "eds_step", "step_seq", "ppid",
        "bin_names", "row_cnt", "high_risk_cnt", "warning_cnt", "normal_cnt",
        "high_risk_eqcs",  # 있으면 이상 EQPCH까지 인덱스로 집계
        "total_bin_cnt",   # 있으면 이상 여부 무관 전체 bin 수(= 분석 그룹)까지 인덱스로 집계
    ]
    columns = [column for column in wanted if column in available]
    return _fetch_dicts(
        f"SELECT {', '.join(columns)} FROM {_FILE_INDEX_TABLE} WHERE date = %s",
        (date,),
    )


def query_trend_data() -> list[dict]:
    """PostgreSQL file_index에서 날짜별 위험 집계를 반환합니다.

    file_index의 카운트 컬럼으로 날짜별·라인별 트렌드를 계산합니다.
    """
    available = _table_columns(_FILE_INDEX_NAME)
    if "high_risk_cnt" not in available:
        return []
    rows = _fetchall(
        "SELECT date, line_id, process_id, step_seq, "
        "SUM(COALESCE(high_risk_cnt, 0)) AS hr, "
        "SUM(COALESCE(warning_cnt, 0)) AS wn "
        f"FROM {_FILE_INDEX_TABLE} "
        "GROUP BY date, line_id, process_id, step_seq ORDER BY date"
    )
    return [
        {"date": str(r[0]), "line_id": str(r[1]), "process_id": str(r[2]),
         "step_seq": str(r[3]), "hr": int(r[4] or 0), "wn": int(r[5] or 0)}
        for r in rows
    ]


def query_run_stats(dates: list[str]) -> dict:
    """PostgreSQL daily_run_stats에서 알고리즘 실행 통계를 반환합니다.

    `_details`는 service의 line_name별 분석 step 집계에만 사용하고 API 응답 전에 제거합니다.
    """
    if not dates:
        return {"totalRows": 0, "combinations": 0, "byLine": [], "_details": []}
    placeholders = ",".join(["%s"] * len(dates))
    total, combinations = _fetchall(
        "SELECT COALESCE(SUM(row_cnt), 0), COUNT(*) "
        f"FROM {_DAILY_RUN_STATS_TABLE} WHERE date IN ({placeholders})",
        dates,
    )[0]
    by_line_rows = _fetchall(
        "SELECT line_id, COUNT(DISTINCT step_seq), COALESCE(SUM(row_cnt), 0) "
        f"FROM {_DAILY_RUN_STATS_TABLE} WHERE date IN ({placeholders}) "
        "GROUP BY line_id ORDER BY line_id",
        dates,
    )
    detail_rows = _fetchall(
        "SELECT date, line_id, process_id, eds_step, step_seq, COALESCE(SUM(row_cnt), 0) "
        f"FROM {_DAILY_RUN_STATS_TABLE} WHERE date IN ({placeholders}) "
        "GROUP BY date, line_id, process_id, eds_step, step_seq",
        dates,
    )
    return {
        "totalRows": int(total or 0),
        "combinations": int(combinations or 0),
        "byLine": [
            {"lineId": str(row[0]), "stepSeqCount": int(row[1]), "rowCnt": int(row[2])}
            for row in by_line_rows
        ],
        "_details": [
            {
                "date": str(row[0]),
                "line_id": str(row[1]),
                "process_id": str(row[2]),
                "eds_step": str(row[3]),
                "step_seq": str(row[4]),
                "row_cnt": int(row[5]),
            }
            for row in detail_rows
        ],
    }


def query_completed_dates() -> Optional[set[str]]:
    """알고리즘 런이 '완전히' 끝난 날짜 집합을 반환합니다.

    PostgreSQL run_status 테이블(status='completed')을 읽습니다. 알고리즘 서버가
    해당 날짜의 마지막 그룹까지 저장한 뒤 한 번만 'completed'로 표시하는 것을 전제로 합니다.
    """
    rows = _fetchall(
        f"SELECT date FROM {_RUN_STATUS_TABLE} WHERE status = 'completed'"
    )
    return {str(row[0]) for row in rows}


def query_all_line_process_step() -> list[tuple[str, str, str]]:
    """PostgreSQL daily_run_stats의 모든 line/process/step 조합을 반환합니다.

    규칙 기반 line_name 매핑(lineGroups)용입니다.
    """
    rows = _fetchall(
        "SELECT DISTINCT line_id, process_id, step_seq "
        f"FROM {_DAILY_RUN_STATS_TABLE}"
    )
    return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]


def query_line_rule_candidates() -> list[dict[str, object]]:
    """daily_run_stats의 line name 규칙 점검용 분석 조합을 반환합니다."""

    rows = _fetchall(
        "SELECT line_id, process_id, step_seq, MIN(date), MAX(date), "
        "COUNT(DISTINCT date) "
        f"FROM {_DAILY_RUN_STATS_TABLE} "
        "GROUP BY line_id, process_id, step_seq "
        "ORDER BY line_id, process_id, step_seq"
    )
    return [
        {
            "line_id": str(row[0]),
            "process_id": str(row[1]),
            "step_seq": str(row[2]),
            "first_seen_date": str(row[3]),
            "last_seen_date": str(row[4]),
            "date_count": int(row[5]),
        }
        for row in rows
    ]


def list_active_line_name_rules() -> list[dict[str, object]]:
    """활성 L3 Spider line name 규칙을 적용 우선순위대로 반환합니다."""

    from .models import L3SpiderLineNameRule

    return list(
        L3SpiderLineNameRule.objects.filter(is_active=True)
        .order_by("priority", "id")
        .values(
            "rule_type",
            "line_id",
            "process_id",
            "step_seq",
            "line_name",
        )
    )


def list_configured_line_names() -> list[str]:
    """활성 DB 규칙에 설정된 line name 고유 목록을 반환합니다."""

    from .models import L3SpiderLineNameRule

    return list(
        L3SpiderLineNameRule.objects.filter(is_active=True)
        .order_by("line_name")
        .values_list("line_name", flat=True)
        .distinct()
    )


def iter_all_data_files_legacy() -> list[Path]:
    """glob 직접 스캔 방식 (인덱스 미사용) — iter_all_data_files의 폴백."""
    ensure_data_root()
    root = get_data_root()
    return [path for path in root.glob("*/*/*/*/*") if path.is_file()]


def iter_all_data_files() -> list[Path]:
    """데이터 루트 아래의 모든 일반 파일 목록을 반환합니다.

    인덱스 조회 결과가 비어 있으면 기존 glob 스캔으로 폴백합니다.
    """
    found = query_indexed_files()  # 필터 없음 = 전체
    return found if found else iter_all_data_files_legacy()


def read_parquet_columns(path: Path, columns: Sequence[str]) -> pd.DataFrame:
    """필요 컬럼만 우선 읽고, 누락 컬럼이 있으면 가능한 컬럼만 반환합니다."""

    try:
        return pd.read_parquet(path, engine="pyarrow", columns=list(columns))
    except Exception:
        frame = pd.read_parquet(path, engine="pyarrow")
        if "display status" in frame.columns and "display_status" not in frame.columns:
            frame = frame.rename(columns={"display status": "display_status"})
        available_columns = [column for column in columns if column in frame.columns]
        return frame[available_columns]


def list_mail_rules_for_user(user_id: int):
    """사용자가 읽을 수 있는 L3 Spider 메일 rule 목록을 조회합니다."""

    from .models import L3SpiderMailRule

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .prefetch_related("permissions__user")
        .filter(Q(created_by_id=user_id) | Q(permissions__user_id=user_id))
        .distinct()
    )


def get_mail_rule_for_user(*, rule_id: int, user_id: int):
    """사용자가 읽을 수 있는 L3 Spider 메일 rule 단건을 조회합니다."""

    from .models import L3SpiderMailRule

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .prefetch_related("permissions__user")
        .filter(Q(created_by_id=user_id) | Q(permissions__user_id=user_id))
        .distinct()
        .get(pk=rule_id)
    )


def get_writable_mail_rule_for_user(*, rule_id: int, user_id: int):
    """사용자가 수정할 수 있는 L3 Spider 메일 rule 단건을 조회합니다."""

    from .models import L3SpiderMailRule, L3SpiderMailRulePermission

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .prefetch_related("permissions__user")
        .filter(
            Q(created_by_id=user_id)
            | Q(
                permissions__user_id=user_id,
                permissions__access_level=L3SpiderMailRulePermission.AccessLevels.WRITE,
            )
        )
        .distinct()
        .get(pk=rule_id)
    )


def get_owned_mail_rule_for_user(*, rule_id: int, user_id: int):
    """사용자가 owner인 L3 Spider 메일 rule 단건을 조회합니다."""

    from .models import L3SpiderMailRule

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .prefetch_related("permissions__user")
        .get(pk=rule_id, created_by_id=user_id)
    )


def list_mail_rule_permissions(*, rule_id: int):
    """메일 rule의 공유 권한 목록을 조회합니다."""

    from .models import L3SpiderMailRulePermission

    return (
        L3SpiderMailRulePermission.objects.select_related("user", "granted_by")
        .filter(rule_id=rule_id)
        .order_by("user__username", "user__sabun", "id")
    )


def find_user_for_mail_rule_permission(identifier: str):
    """메일 rule 권한 부여 대상 사용자를 식별자로 조회합니다."""

    user_model = get_user_model()
    value = str(identifier or "").strip()
    if not value:
        return None

    query = Q(sabun=value)
    lowered = value.lower()
    query |= Q(email__iexact=lowered)
    query |= Q(username__iexact=value)
    query |= Q(knox_id__iexact=value)
    return user_model.objects.filter(query).order_by("id").first()


def list_active_mail_rules_for_trigger(*, limit: int):
    """Airflow trigger가 처리할 활성 메일 rule 목록을 조회합니다."""

    from .models import L3SpiderMailRule

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .filter(is_active=True)
        .order_by("send_time", "id")[:limit]
    )
