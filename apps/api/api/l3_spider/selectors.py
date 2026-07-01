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
    query = f"SELECT filepath FROM file_index {where}"

    conn = _connect_ro()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    root = get_data_root()
    return [Path(r[0]) if Path(r[0]).is_absolute() else root / r[0] for r in rows]


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

    query = f"SELECT filepath FROM file_index WHERE {' AND '.join(conditions)}"

    conn = _connect_ro()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    root = get_data_root()
    return [Path(r[0]) if Path(r[0]).is_absolute() else root / r[0] for r in rows]


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


def query_eqc_for_process(line_id: str, process_id: str) -> list[str]:
    """(line_id, process_id)에 실제로 존재하는 전체 eqc 목록을 반환합니다.

    eqp_index 테이블(원본 tkin 기반, 이상 감지 여부 무관)을 조회하므로
    해당 조합의 설비 전체를 빠짐없이 반환합니다.
    """
    if not _get_index_db_path().exists():
        return []
    conn = _connect_ro()
    try:
        rows = conn.execute(
            "SELECT DISTINCT eqc FROM eqp_index WHERE line_id = ? AND process_id = ? ORDER BY eqc",
            (line_id, process_id),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [r[0] for r in rows]


def query_all_line_process_combos() -> list[tuple[str, str]]:
    """eqp_index에 기록된 모든 (line_id, process_id) 조합 목록을 반환합니다."""
    if not _get_index_db_path().exists():
        return []
    conn = _connect_ro()
    try:
        rows = conn.execute(
            "SELECT DISTINCT line_id, process_id FROM eqp_index ORDER BY line_id, process_id"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [(r[0], r[1]) for r in rows]


def query_all_eqcs_by_combo() -> dict[tuple[str, str], list[str]]:
    """eqp_index의 모든 (line_id, process_id) → eqc 목록을 한 번에 조회합니다.

    get_meta()에서 LINE_NAME 결정 시 N번 왕복 없이 한 번에 가져오기 위한 배치 버전.
    """
    if not _get_index_db_path().exists():
        return {}
    conn = _connect_ro()
    try:
        rows = conn.execute(
            "SELECT DISTINCT line_id, process_id, eqc FROM eqp_index ORDER BY line_id, process_id, eqc"
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    result: dict[tuple[str, str], list[str]] = {}
    for line_id, process_id, eqc in rows:
        result.setdefault((line_id, process_id), []).append(eqc)
    return result


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
