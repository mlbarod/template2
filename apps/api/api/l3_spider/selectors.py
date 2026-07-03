# =============================================================================
# 모듈: L3 Spider 셀렉터
# 주요 함수: get_data_root, iter_data_files, read_parquet_columns, list_mail_rules_for_user
# 주요 가정: 파일시스템/DB 조회만 수행하며 쓰기 작업은 하지 않습니다.
# =============================================================================
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional, Sequence

from django.conf import settings
from django.contrib.auth import get_user_model
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


def _get_index_db_path() -> Path:
    """SQLite 인덱스 파일 경로를 반환합니다."""
    return get_data_root() / "_meta" / "index.sqlite3"


def _connect_ro() -> sqlite3.Connection:
    """인덱스 DB에 읽기 전용으로 연결합니다.
    알고리즘 서버가 쓰는 중이어도 WAL 모드라면 커밋된 상태만 보여 안전합니다.
    """
    uri = f"file:{_get_index_db_path()}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=10)


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
    """SQLite 인덱스에서 조건에 맞는 filepath 목록을 조회합니다.

    인덱스 파일이 없으면 빈 리스트를 반환합니다 — 호출부에서 legacy fallback으로 처리하세요.
    반환된 Path 리스트는 기존 pd.read_parquet() 에 그대로 넘길 수 있습니다.
    """
    if not _get_index_db_path().exists():
        return []

    conditions: list[str] = []
    params: list = []

    if date is not None:
        conditions.append("date = ?")
        params.append(date)
    if line_id is not None:
        conditions.append("line_id = ?")
        params.append(line_id)
    if process_id is not None:
        conditions.append("process_id = ?")
        params.append(process_id)
    if eds_step is not None:
        conditions.append("eds_step = ?")
        params.append(eds_step)
    if high_risk_only:
        conditions.append("has_high_risk = 1")
    if eqp_id is not None:
        conditions.append("EXISTS (SELECT 1 FROM json_each(eqp_ids) WHERE value = ?)")
        params.append(eqp_id)
    if chamber_id is not None:
        conditions.append("EXISTS (SELECT 1 FROM json_each(chamber_ids) WHERE value = ?)")
        params.append(chamber_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT date, line_id, process_id, eds_step, filepath FROM file_index {where}"

    conn = _connect_ro()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

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
    """날짜 범위(date_from ≤ date ≤ date_to)로 filepath 목록을 조회합니다.

    양 끝 포함(inclusive). 'YYYY-MM-DD' 형식.
    인덱스 파일이 없으면 빈 리스트를 반환합니다.
    """
    if not _get_index_db_path().exists():
        return []

    conditions = ["date >= ?", "date <= ?"]
    params: list = [date_from, date_to]

    if line_id is not None:
        conditions.append("line_id = ?")
        params.append(line_id)
    if process_id is not None:
        conditions.append("process_id = ?")
        params.append(process_id)
    if eds_step is not None:
        conditions.append("eds_step = ?")
        params.append(eds_step)
    if high_risk_only:
        conditions.append("has_high_risk = 1")
    if eqp_id is not None:
        conditions.append("EXISTS (SELECT 1 FROM json_each(eqp_ids) WHERE value = ?)")
        params.append(eqp_id)
    if chamber_id is not None:
        conditions.append("EXISTS (SELECT 1 FROM json_each(chamber_ids) WHERE value = ?)")
        params.append(chamber_id)

    query = f"SELECT date, line_id, process_id, eds_step, filepath FROM file_index WHERE {' AND '.join(conditions)}"

    conn = _connect_ro()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    root = get_data_root()
    return [_rebuild_container_path(root, *row) for row in rows]


def iter_data_files_legacy(selection: dict[str, object]) -> list[Path]:
    """디렉토리 직접 스캔 방식 (인덱스 미사용) — iter_data_files의 fallback."""
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
    결과가 빈 조합만 legacy 디렉토리 스캔으로 fallback합니다.
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
    """특정 날짜 하위의 모든 파일을 디렉토리 스캔합니다 (인덱스 미사용 fallback)."""
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

    인덱스 조회 결과가 비어 있으면 legacy 디렉토리 스캔으로 fallback합니다.
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
    for path in root.glob("*/*/*/*/*"):  # date/line_id/process_id/eds_step/file
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


def query_all_line_process_step() -> list[tuple[str, str, str]]:
    """file_index의 모든 (line_id, process_id, step_seq) 조합을 반환합니다.

    규칙 기반 line_name 매핑(lineGroups)용. 인덱스가 없거나 조회 실패 시
    legacy 디렉토리 스캔으로 fallback합니다.
    """
    if _get_index_db_path().exists():
        conn = _connect_ro()
        try:
            rows = conn.execute(
                "SELECT DISTINCT line_id, process_id, step_seq FROM file_index"
            ).fetchall()
        except sqlite3.OperationalError:
            rows = None
        finally:
            conn.close()
        if rows is not None:
            return [(str(r[0]), str(r[1]), str(r[2])) for r in rows]
    return _query_all_line_process_step_legacy()


def iter_all_data_files_legacy() -> list[Path]:
    """glob 직접 스캔 방식 (인덱스 미사용) — iter_all_data_files의 fallback."""
    ensure_data_root()
    root = get_data_root()
    return [path for path in root.glob("*/*/*/*/*") if path.is_file()]


def iter_all_data_files() -> list[Path]:
    """데이터 루트 아래의 모든 일반 파일 목록을 반환합니다.

    인덱스 조회 결과가 비어 있으면 legacy glob 스캔으로 fallback합니다.
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
