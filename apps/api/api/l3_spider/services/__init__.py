# =============================================================================
# 모듈: L3 Spider 서비스
# 주요 함수: get_meta, get_summary, get_data
# 주요 가정: Parquet 원본 컬럼은 snake_case이고 API 응답은 camelCase입니다.
# =============================================================================
from __future__ import annotations

import fnmatch
import logging
import functools
import hashlib
import html
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime as dt_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

import numpy as np
import pandas as pd

from api.common.services import send_knox_mail_api
from api.l3_spider import selectors

from . import line_name_rules

SUMMARY_COLUMNS = ["step_seq", "ppid", "eqp_id", "eqc", "bin_name", "display_status"]
# 파일명에서 step_seq/ppid 파싱 성공 시 파일에서 읽을 컬럼 (절반으로 감소)
_SUMMARY_COLUMNS_SLIM = ["eqc", "bin_name", "display_status"]
_SUMMARY_DEDUP_KEYS = ["step_seq", "ppid", "eqc", "bin_name", "display_status"]
# daily summary: 카운트 집계용 — dedup 없이 전체 행을 읽습니다.
_DAILY_SUMMARY_COLUMNS = ["step_seq", "ppid", "eqc", "bin_name", "display_status", "lot_id"]
_DAILY_SUMMARY_COLUMNS_SLIM = ["step_seq", "eqc", "bin_name", "display_status", "lot_id"]
_STATS_COLUMNS = ["eqc", "bin_name", "display_status", "tkin_time"]
MAIL_EVENT_COLUMNS = ["step_seq", "ppid", "eqc", "bin_name", "display_status", "tkin_time"]
CHART_COLUMNS = [
    "tkin_time",
    "tkout_time",
    "owning",
    "step_seq",
    "ppid",
    "root_lot_id",
    "lot_id",
    "wafer_id",
    "eqp_id",
    "chamber_id",
    "eqc",
    "bin_name",
    "bin_value",
    "prop_over_50",
    "q1",
    "q3",
    "iqr",
    "lsl",
    "usl",
    "seq_idx",
    "risk_score",
    "display_status",
    "comment",
]
ANOMALY_STATUSES = {"Warning", "High Risk Chamber"}
MAIL_SEVERITY_STATUSES = {
    "high_risk": {"High Risk Chamber"},
    "warning_or_high_risk": ANOMALY_STATUSES,
}
_MAX_PARALLEL_WORKERS = 8
_MAIL_DIGEST_PREVIEW_LIMIT = 50


class _SimpleCache:
    """스레드 안전한 TTL 인메모리 캐시."""

    def __init__(self, ttl: float = 600.0) -> None:
        self._ttl = ttl
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.monotonic() - ts > self._ttl:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.monotonic(), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_meta_cache = _SimpleCache(ttl=600.0)
_structure_cache = _SimpleCache(ttl=600.0)
_stats_cache = _SimpleCache(ttl=600.0)
_daily_summary_cache = _SimpleCache(ttl=300.0)
# 파일시스템 스캔 결과만 따로 캐싱: 사용자별 exclusion 규칙과 분리해
# 여러 사용자/워커 간에 스캔 비용을 공유합니다.
_raw_file_rows_cache = _SimpleCache(ttl=600.0)
_RAW_FILE_ROWS_KEY = "raw"
_line_groups_cache = _SimpleCache(ttl=600.0)
_LINE_GROUPS_KEY = "groups"


class L3SpiderServiceError(Exception):
    """L3 Spider 서비스 오류를 HTTP 상태와 함께 표현합니다."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _snake_to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _camelize_mapping(row: dict[str, Any]) -> dict[str, Any]:
    return {_snake_to_camel(key): _json_safe_value(value) for key, value in row.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return _json_safe_value(value.item())
    return value


def _normalize_display_status(frame: pd.DataFrame) -> pd.DataFrame:
    if "display status" in frame.columns and "display_status" not in frame.columns:
        frame = frame.rename(columns={"display status": "display_status"})
    if "display_status" in frame.columns:
        frame["display_status"] = frame["display_status"].replace({"Single Spike": "Warning"})
    return frame


def _empty_stats() -> dict[str, int]:
    return {
        "total": 0,
        "normal": 0,
        "warning": 0,
        "risk": 0,
        "anomalySteps": 0,
        "highRiskEqpchs": 0,
    }


def _has_required_selection(selection: dict[str, object]) -> bool:
    return all(selection.get(key) for key in ("dates", "lineIds", "processIds", "edsSteps"))


def _make_selection_cache_key(selection: dict) -> str:
    return json.dumps({
        "dates": sorted(selection.get("dates") or []),
        "lineIds": sorted(selection.get("lineIds") or []),
        "lineNames": sorted(selection.get("lineNames") or []),
        "processIds": sorted(selection.get("processIds") or []),
        "edsSteps": sorted(selection.get("edsSteps") or []),
    }, sort_keys=True)


def _parse_filename_key(path: Path) -> tuple[str, str] | None:
    """파일명에서 (step_seq, ppid)를 파싱합니다."""
    try:
        name = path.name
        if name.endswith(".parquet"):
            name = name[: -len(".parquet")]
        parts = name.split("#")
        if len(parts) == 3 and parts[0] and parts[1]:
            return parts[0], parts[1]
    except Exception:
        pass
    return None


def _add_path_context(frame: pd.DataFrame, path: Path, *, override_filename_keys: bool = False) -> pd.DataFrame:
    relative_parts = path.relative_to(selectors.get_data_root()).parts
    # parts: (date, line_id, process_id, eds_step, filename)
    if len(relative_parts) >= 1:
        frame["date"] = relative_parts[0]
    if len(relative_parts) >= 2:
        frame["line_id"] = relative_parts[1]
    if len(relative_parts) >= 3:
        frame["process_id"] = relative_parts[2]
    if len(relative_parts) >= 4:
        frame["eds_step"] = relative_parts[3]

    parsed = _parse_filename_key(path)
    if not parsed:
        return frame

    step_seq, ppid = parsed
    if override_filename_keys or "step_seq" not in frame.columns:
        frame["step_seq"] = step_seq
    else:
        frame["step_seq"] = frame["step_seq"].fillna(step_seq)
    if override_filename_keys or "ppid" not in frame.columns:
        frame["ppid"] = ppid
    else:
        frame["ppid"] = frame["ppid"].fillna(ppid)
    return frame


# ─── 병렬 파일 읽기 ──────────────────────────────────────────────────────────

def _read_summary_file(path: Path) -> pd.DataFrame | None:
    """summary 읽기 단일 파일 처리 (ThreadPoolExecutor용)."""
    try:
        parsed = _parse_filename_key(path)
        cols = _SUMMARY_COLUMNS_SLIM if parsed else SUMMARY_COLUMNS
        frame = selectors.read_parquet_columns(path, cols)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path, override_filename_keys=bool(parsed))
        available_dedup = [c for c in _SUMMARY_DEDUP_KEYS if c in frame.columns]
        return frame.drop_duplicates(subset=available_dedup) if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider summary read failed: {path}: {exc}")
        return None


def _read_daily_summary_file(path: Path) -> pd.DataFrame | None:
    """daily summary 읽기: 카운트 집계용으로 dedup 없이 전체 행을 반환합니다."""
    try:
        parsed = _parse_filename_key(path)
        cols = _DAILY_SUMMARY_COLUMNS_SLIM if parsed else _DAILY_SUMMARY_COLUMNS
        frame = selectors.read_parquet_columns(path, cols)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path, override_filename_keys=bool(parsed))
        return frame if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider daily summary read failed: {path}: {exc}")
        return None


def _read_stats_file(path: Path) -> pd.DataFrame | None:
    """stats 읽기: 3컬럼만 읽고 파일명에서 eds_step/step_seq/ppid 추가."""
    try:
        parsed = _parse_filename_key(path)
        frame = selectors.read_parquet_columns(path, _STATS_COLUMNS)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path, override_filename_keys=bool(parsed))
        return frame if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider stats read failed: {path}: {exc}")
        return None


def _read_mail_event_file(path: Path) -> pd.DataFrame | None:
    """메일 알림 후보 이벤트를 읽기 위한 단일 파일 처리."""

    try:
        frame = selectors.read_parquet_columns(path, MAIL_EVENT_COLUMNS)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path)
        return frame if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider mail event read failed: {path}: {exc}")
        return None


def _read_chart_file(path: Path, columns: list[str]) -> pd.DataFrame | None:
    """차트 읽기 단일 파일 처리 (ThreadPoolExecutor용)."""
    try:
        frame = selectors.read_parquet_columns(path, columns)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path)
        return frame if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider parquet read failed: {path}: {exc}")
        return None


def _parallel_read(files: list[Path], reader_fn) -> list[pd.DataFrame]:
    """파일 목록을 ThreadPoolExecutor로 병렬 읽습니다."""
    if not files:
        return []
    if len(files) == 1:
        result = reader_fn(files[0])
        return [result] if result is not None else []
    max_workers = min(_MAX_PARALLEL_WORKERS, len(files))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(reader_fn, f) for f in files]
        results = [fut.result() for fut in futures]
    return [df for df in results if df is not None]


def _read_frames(selection: dict[str, object], columns: list[str]) -> list[pd.DataFrame]:
    """선택된 파일들을 DataFrame 목록으로 읽습니다 (병렬)."""
    try:
        files = list(selectors.iter_data_files(selection))
    except FileNotFoundError as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise L3SpiderServiceError(str(exc), status_code=400) from exc
    return _parallel_read(files, functools.partial(_read_chart_file, columns=columns))


def _read_summary_frames(selection: dict[str, object]) -> list[pd.DataFrame]:
    """summary 전용 최적화 읽기 (병렬)."""
    try:
        files = list(selectors.iter_data_files(selection))
    except FileNotFoundError as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise L3SpiderServiceError(str(exc), status_code=400) from exc
    return _parallel_read(files, _read_summary_file)


def _sample_chart_points(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    """차트 패널별 최대 표시 점 수를 제한합니다."""
    max_points = getattr(settings, "L3_SPIDER_MAX_CHART_POINTS_PER_PANEL", 2000)
    if max_points <= 0 or frame.empty:
        return frame

    sampled: list[pd.DataFrame] = []
    available_group_columns = [column for column in group_columns if column in frame.columns]
    if not available_group_columns:
        return frame.head(max_points)

    for _, group in frame.groupby(available_group_columns, sort=False, dropna=False):
        if len(group) <= max_points:
            sampled.append(group)
            continue

        if "display_status" in group.columns:
            anomaly = group[group["display_status"].isin(ANOMALY_STATUSES)]
        else:
            anomaly = group.iloc[0:0]
        remaining_slots = max_points - len(anomaly)
        if remaining_slots <= 0:
            sampled.append(anomaly)
            continue

        others = group[~group.index.isin(anomaly.index)]
        sampled.append(
            pd.concat(
                [
                    anomaly,
                    others.sample(n=min(remaining_slots, len(others)), random_state=42),
                ]
            )
        )

    return pd.concat(sampled, ignore_index=True) if sampled else frame.iloc[0:0]


# ─── 컬럼 기반 직렬화 ────────────────────────────────────────────────────────

def _dataframe_to_columnar(merged: pd.DataFrame) -> dict[str, object]:
    """DataFrame을 컬럼 기반 응답 포맷으로 변환합니다.

    {"cols": ["binValue", ...], "colData": [[val, ...], ...]}
    row 포맷 대비 JSON 크기 ~60% 절감 (컬럼명 N회 반복 제거).
    """
    # float32 → float64
    float32_cols = merged.select_dtypes(include=["float32"]).columns
    if len(float32_cols):
        merged = merged.copy()
        merged[float32_cols] = merged[float32_cols].astype("float64")

    # inf → NaN
    merged = merged.replace([np.inf, -np.inf], np.nan)

    cols = [_snake_to_camel(c) for c in merged.columns]
    col_data: list[list] = []

    for col in merged.columns:
        series = merged[col]
        if pd.api.types.is_float_dtype(series):
            # float NaN → None (v != v 은 NaN에서만 True: IEEE 754)
            raw = series.tolist()
            col_data.append([None if v != v else v for v in raw])
        elif pd.api.types.is_integer_dtype(series):
            col_data.append(series.tolist())
        else:
            # object / string: pd.isna 기반 None 치환
            col_data.append([None if pd.isna(v) else v for v in series])

    return {"cols": cols, "colData": col_data}


# ─── 서비스 함수 ─────────────────────────────────────────────────────────────

def _get_raw_file_rows() -> list[dict[str, str]]:
    """전체 파일 트리를 스캔하여 (date, line_id, process_id, eds_step) 행 목록을 반환합니다.

    결과를 별도 캐시에 저장하여 사용자별 exclusion 규칙 계산과 분리합니다.
    같은 워커 내 여러 사용자가 스캔 비용을 공유하고, 필터 변경 시에도 재스캔하지 않습니다.
    """
    cached = _raw_file_rows_cache.get(_RAW_FILE_ROWS_KEY)
    if cached is not None:
        return cached

    try:
        files = list(selectors.iter_all_data_files())
    except FileNotFoundError as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise L3SpiderServiceError(str(exc), status_code=400) from exc

    root = selectors.get_data_root()
    rows: list[dict[str, str]] = []
    for path in files:
        parts = path.relative_to(root).parts
        if len(parts) != 5:
            continue
        date, line_id, process_id, eds_step = parts[:4]
        rows.append({
            "date": date,
            "line_id": line_id,
            "process_id": process_id,
            "eds_step": eds_step,
        })

    _raw_file_rows_cache.set(_RAW_FILE_ROWS_KEY, rows)
    return rows


def _build_line_groups_from_index() -> list[dict]:
    """file_index의 (line_id, process_id, step_seq) 조합 + _meta/line_name_rules.csv
    규칙으로 lineGroups(line_name 기준)를 동적 생성합니다.

    결과는 TTL 캐시에 보관합니다. 규칙 미매칭 조합은 line_id 로 폴백됩니다.
    """
    cached = _line_groups_cache.get(_LINE_GROUPS_KEY)
    if cached is not None:
        return cached

    try:
        groups = _build_line_groups_impl()
    except Exception:
        groups = []

    _line_groups_cache.set(_LINE_GROUPS_KEY, groups)
    return groups


def _filter_files_by_line_names(files: list, selection: dict[str, object]) -> list:
    """선택된 line_name(들)이 있으면 파일 목록을 line_name 기준으로 필터합니다.

    각 파일의 line_name = resolve(line_id, process_id, step_seq)입니다.
    필요한 값은 전부 경로/파일명에서 얻으므로 Parquet를 읽지 않습니다.

    계약: daily_anomaly 파일명은 항상 {step_seq}#{ppid}#{index} 형식이라 step_seq가 파일명에
    반드시 존재합니다(알고리즘 서버 보장). 따라서 파일 단위로 line_name이 하나로 정해집니다.
    파일명에서 step_seq를 못 읽으면 계약 위반이므로, 조용히 유실하지 않고 경고 후 제외합니다.
    """
    line_names = {str(v) for v in (selection.get("lineNames") or []) if v}
    if not line_names:
        return list(files)
    root = selectors.get_data_root()
    filtered: list = []
    for path in files:
        parsed = _parse_filename_key(path)
        if not parsed:
            print(f"[WARN] L3 Spider lineNames 필터: step_seq 없는 파일명(계약 위반) 제외: {path}")
            continue
        step_seq, _ppid = parsed
        parts = path.relative_to(root).parts
        if len(parts) < 4:
            continue
        line_id, process_id = parts[1], parts[2]
        if line_name_rules.resolve_line_name(line_id, process_id, step_seq) in line_names:
            filtered.append(path)
    return filtered


def _build_line_groups_impl() -> list[dict]:
    # 규칙 기반: file_index의 (line_id, process_id, eds_step, step_seq) 조합을 resolve_line_name으로
    # line_name에 매핑해 집계합니다(eqc·parquet·Postgres 불필요). step_seq마다 line_name이
    # 달라질 수 있어(예: EndFab override) 한 (line_id, process)가 여러 line_name에 나타날 수 있고,
    # 그 line_name이 실제로 존재하는 eds도 step_seq에 따라 갈립니다. 그래서 (line_name, line_id)별로
    # procEds(process→[eds])를 함께 계산해, 프론트 패널이 '해당 line_name에 없는 eds'를
    # 선택지로 내놓아 하위가 비는(죽은 옵션) 문제를 없앱니다.
    combos = selectors.query_all_line_process_eds_step()
    if not combos:
        return []

    # line_name -> line_id -> {process_id -> set(eds_step)}
    result: dict[str, dict[str, dict[str, set[str]]]] = {}
    for line_id, process_id, eds_step, step_seq in combos:
        line_name = line_name_rules.resolve_line_name(line_id, process_id, step_seq)
        result.setdefault(line_name, {}).setdefault(str(line_id), {}) \
              .setdefault(str(process_id), set()).add(str(eds_step))

    return [
        {
            "lineName": ln,
            "lineId": lid,
            "processIds": sorted(proc_eds),
            "procEds": {p: sorted(es) for p, es in sorted(proc_eds.items())},
        }
        for ln in sorted(result)
        for lid, proc_eds in sorted(result[ln].items())
    ]


def get_meta(*, user: Any | None = None) -> dict[str, object]:
    """사용 가능한 날짜/라인/프로세스/EDS step 메타데이터를 반환합니다.

    활성 제외 필터의 경로 필드(line_id, process_id, eds_step)를 적용하여
    완전히 제외된 항목은 DataSelector에 표시되지 않습니다.
    """
    rules = _get_exclusion_rules(user=user)
    rules_hash = str(hash(tuple(sorted(str(r) for r in rules))))
    cached = _meta_cache.get(rules_hash)
    if cached is not None:
        return cached

    # 파일 스캔 결과는 공유 캐시에서 가져옴 (exclusion 규칙과 독립적)
    file_rows = _get_raw_file_rows()

    if file_rows:
        df = pd.DataFrame(file_rows).drop_duplicates()
        # step_seq·ppid·eqc·bin_name 컬럼 없음 → 해당 필드 규칙은 자동으로 무시
        df = _apply_exclusion_filters_with_rules(df, rules)
    else:
        df = pd.DataFrame(columns=["date", "line_id", "process_id", "eds_step"])

    dates: set[str] = set()
    line_ids: set[str] = set()
    process_ids: set[str] = set()
    eds_steps: set[str] = set()
    availability: dict[str, dict[str, dict[str, set[str]]]] = {}

    for row in df.itertuples(index=False):
        dates.add(row.date)
        line_ids.add(row.line_id)
        process_ids.add(row.process_id)
        eds_steps.add(row.eds_step)
        availability.setdefault(row.date, {}).setdefault(row.line_id, {}).setdefault(row.process_id, set()).add(row.eds_step)

    result = {
        "dates": sorted(dates),
        "lineIds": sorted(line_ids),
        "processIds": sorted(process_ids),
        "edsSteps": sorted(eds_steps),
        "availability": {
            date: {
                line_id: {
                    process_id: sorted(process_eds_steps)
                    for process_id, process_eds_steps in sorted(processes.items())
                }
                for line_id, processes in sorted(lines.items())
            }
            for date, lines in sorted(availability.items())
        },
        "lineGroups": _build_line_groups_from_index(),
    }
    _meta_cache.set(rules_hash, result)
    return result


def _matches_pattern(value: str, pattern: str) -> bool:
    """와일드카드 패턴 매칭 (* 또는 % 를 임의 문자열로, 대소문자 무시)."""
    if pattern == "*":
        return True
    return fnmatch.fnmatch(str(value).lower(), pattern.replace("%", "*").lower())


def _get_exclusion_rules(*, user: Any | None = None) -> list[dict]:
    """사용자 소유 활성 제외 필터 규칙을 DB에서 조회합니다.

    multi-worker 환경에서 캐시 불일치를 방지하기 위해 항상 DB를 직접 읽습니다.
    rules 테이블은 소규모이므로 쿼리 비용이 무시할 수준입니다.
    """
    user_id = getattr(user, "id", None)
    if not user_id:
        return []

    try:
        from ..models import L3SpiderExclusionFilter
        return list(
            L3SpiderExclusionFilter.objects.filter(
                is_active=True,
                created_by_id=user_id,
            ).values(
                "line_id", "process_id", "eds_step", "step_seq",
                "ppid", "eqpch", "bin_name", "date_from", "date_to",
            )
        )
    except Exception as exc:
        print(f"[WARN] L3 Spider exclusion rules load failed: {exc}")
        return []


def _require_user_id(user: Any) -> int:
    """인증 사용자 ID를 반환하고 없으면 권한 오류를 발생시킵니다."""

    user_id = getattr(user, "id", None)
    if not user_id:
        raise L3SpiderServiceError("Authentication required", status_code=401)
    return int(user_id)


def _serialize_exclusion_filter(row) -> dict[str, object]:
    """제외 필터 모델을 API 응답 형태로 변환합니다."""

    created_by = None
    if row.created_by:
        created_by = row.created_by.get_full_name() or row.created_by.username

    return {
        "id": row.id,
        "lineId": row.line_id,
        "processId": row.process_id,
        "edsStep": row.eds_step,
        "stepSeq": row.step_seq,
        "ppid": row.ppid,
        "eqpch": row.eqpch,
        "binName": row.bin_name,
        "dateTo": row.date_to.isoformat() if row.date_to else None,
        "isActive": row.is_active,
        "memo": row.memo,
        "createdBy": created_by,
        "createdAt": row.created_at.strftime("%Y-%m-%d %H:%M"),
        "updatedAt": row.updated_at.strftime("%Y-%m-%d %H:%M"),
    }


def list_exclusion_filters(*, user: Any) -> list[dict[str, object]]:
    """요청 사용자가 소유한 제외 필터 목록을 최신 등록순으로 조회합니다."""

    from ..models import L3SpiderExclusionFilter

    user_id = _require_user_id(user)
    filters = L3SpiderExclusionFilter.objects.select_related("created_by").filter(
        created_by_id=user_id,
    )
    return [_serialize_exclusion_filter(row) for row in filters]


def create_exclusion_filter(data: dict[str, object], *, user) -> dict[str, int]:
    """제외 필터를 생성하고 관련 캐시를 무효화합니다."""

    from ..models import L3SpiderExclusionFilter

    user_id = _require_user_id(user)
    row = L3SpiderExclusionFilter.objects.create(
        line_id=data["line_id"],
        process_id=data["process_id"],
        eds_step=data["eds_step"],
        step_seq=data["step_seq"],
        ppid=data["ppid"],
        eqpch=data["eqpch"],
        bin_name=data["bin_name"],
        date_from=data.get("date_from"),
        date_to=data.get("date_to"),
        is_active=data["is_active"],
        memo=data.get("memo", ""),
        created_by_id=user_id,
    )
    invalidate_exclusion_cache()
    return {"id": row.id}


def update_exclusion_filter(
    filter_id: int,
    data: dict[str, object],
    *,
    user: Any,
) -> dict[str, int]:
    """사용자 소유 제외 필터를 부분 수정하고 관련 캐시를 무효화합니다."""

    from ..models import L3SpiderExclusionFilter

    user_id = _require_user_id(user)
    try:
        row = L3SpiderExclusionFilter.objects.get(pk=filter_id, created_by_id=user_id)
    except L3SpiderExclusionFilter.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc

    field_map = {
        "line_id": "line_id",
        "process_id": "process_id",
        "eds_step": "eds_step",
        "step_seq": "step_seq",
        "ppid": "ppid",
        "eqpch": "eqpch",
        "bin_name": "bin_name",
        "date_from": "date_from",
        "date_to": "date_to",
        "is_active": "is_active",
        "memo": "memo",
    }
    for source, target in field_map.items():
        if source in data:
            setattr(row, target, data[source])
    row.save()
    invalidate_exclusion_cache()
    return {"id": row.id}


def delete_exclusion_filter(filter_id: int, *, user: Any) -> None:
    """사용자 소유 제외 필터를 삭제하고 관련 캐시를 무효화합니다."""

    from ..models import L3SpiderExclusionFilter

    user_id = _require_user_id(user)
    try:
        row = L3SpiderExclusionFilter.objects.get(pk=filter_id, created_by_id=user_id)
    except L3SpiderExclusionFilter.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc

    row.delete()
    invalidate_exclusion_cache()


def invalidate_exclusion_cache() -> None:
    """필터 변경 시 meta·stats·structure 캐시를 무효화합니다."""
    _meta_cache.clear()
    _stats_cache.clear()
    _structure_cache.clear()


def _display_user_name(user: Any) -> str:
    """사용자 표시 이름을 일관된 우선순위로 반환합니다."""

    if not user:
        return ""
    return (
        user.get_full_name()
        or getattr(user, "username", "")
        or getattr(user, "email", "")
        or getattr(user, "sabun", "")
        or str(user)
    )


def _display_user_email(user: Any) -> str:
    """사용자 email 표시값을 반환합니다."""

    return str(getattr(user, "email", "") or "").strip()


def _serialize_mail_rule_permission(row) -> dict[str, object]:
    """메일 rule 공유 권한 모델을 API 응답 형태로 변환합니다."""

    user = row.user
    return {
        "id": row.id,
        "userId": user.id,
        "user": _display_user_email(user) or getattr(user, "username", "") or getattr(user, "sabun", ""),
        "displayName": _display_user_name(user),
        "email": _display_user_email(user),
        "username": getattr(user, "username", "") or "",
        "sabun": getattr(user, "sabun", "") or "",
        "accessLevel": row.access_level,
        "createdAt": row.created_at.strftime("%Y-%m-%d %H:%M"),
        "updatedAt": row.updated_at.strftime("%Y-%m-%d %H:%M"),
    }


def _mail_rule_access(row, *, user_id: int) -> dict[str, object]:
    """현재 사용자의 rule 접근 권한을 계산합니다."""

    if row.created_by_id == user_id:
        return {
            "accessLevel": "owner",
            "isOwner": True,
            "canWrite": True,
            "canManage": True,
        }

    from ..models import L3SpiderMailRulePermission

    for permission in row.permissions.all():
        if permission.user_id != user_id:
            continue
        can_write = permission.access_level == L3SpiderMailRulePermission.AccessLevels.WRITE
        return {
            "accessLevel": permission.access_level,
            "isOwner": False,
            "canWrite": can_write,
            "canManage": False,
        }

    return {
        "accessLevel": None,
        "isOwner": False,
        "canWrite": False,
        "canManage": False,
    }


def _serialize_mail_rule(row, *, user_id: int | None = None) -> dict[str, object]:
    """메일 알림 규칙 모델을 API 응답 형태로 변환합니다."""

    created_by = row.created_by.get_full_name() or row.created_by.username
    access = _mail_rule_access(row, user_id=user_id) if user_id else {
        "accessLevel": "owner",
        "isOwner": True,
        "canWrite": True,
        "canManage": True,
    }
    permissions = []
    if access["canManage"]:
        permissions = [
            _serialize_mail_rule_permission(permission)
            for permission in row.permissions.all()
        ]

    return {
        "id": row.id,
        "name": row.name,
        "lineId": row.line_id,
        "processId": row.process_id,
        "edsStep": row.eds_step,
        "stepSeq": row.step_seq,
        "ppid": row.ppid,
        "eqpch": row.eqpch,
        "binName": row.bin_name,
        "dateTo": row.date_to.isoformat() if row.date_to else None,
        "severityMode": row.severity_mode,
        "receiverEmails": list(row.receiver_emails or []),
        "scheduleType": row.schedule_type,
        "sendTime": row.send_time.strftime("%H:%M") if row.send_time else "09:00",
        "timezone": row.timezone,
        "isActive": row.is_active,
        "memo": row.memo,
        "lastSentAt": row.last_sent_at.strftime("%Y-%m-%d %H:%M") if row.last_sent_at else None,
        "lastCheckedAt": row.last_checked_at.strftime("%Y-%m-%d %H:%M") if row.last_checked_at else None,
        "accessLevel": access["accessLevel"],
        "isOwner": access["isOwner"],
        "canWrite": access["canWrite"],
        "canManage": access["canManage"],
        "ownerName": _display_user_name(row.created_by),
        "ownerEmail": _display_user_email(row.created_by),
        "permissions": permissions,
        "createdBy": created_by,
        "createdAt": row.created_at.strftime("%Y-%m-%d %H:%M"),
        "updatedAt": row.updated_at.strftime("%Y-%m-%d %H:%M"),
    }


def list_mail_rules(*, user: Any) -> list[dict[str, object]]:
    """요청 사용자가 소유한 메일 알림 규칙 목록을 조회합니다."""

    user_id = _require_user_id(user)
    rules = selectors.list_mail_rules_for_user(user_id)
    return [_serialize_mail_rule(row, user_id=user_id) for row in rules]


def create_mail_rule(data: dict[str, object], *, user: Any) -> dict[str, int]:
    """메일 알림 규칙을 생성합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    row = L3SpiderMailRule.objects.create(
        name=data["name"],
        line_id=data["line_id"],
        process_id=data["process_id"],
        eds_step=data["eds_step"],
        step_seq=data["step_seq"],
        ppid=data["ppid"],
        eqpch=data["eqpch"],
        bin_name=data["bin_name"],
        date_to=data.get("date_to"),
        severity_mode=data["severity_mode"],
        receiver_emails=data["receiver_emails"],
        schedule_type=data["schedule_type"],
        send_time=data["send_time"],
        timezone=data["timezone"],
        is_active=data["is_active"],
        memo=data.get("memo", ""),
        created_by_id=user_id,
    )
    return {"id": row.id}


def update_mail_rule(
    rule_id: int,
    data: dict[str, object],
    *,
    user: Any,
) -> dict[str, int]:
    """사용자 소유 메일 알림 규칙을 부분 수정합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    try:
        row = selectors.get_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc
    if not _mail_rule_access(row, user_id=user_id)["canWrite"]:
        raise L3SpiderServiceError("Write permission required", status_code=403)

    field_map = {
        "name": "name",
        "line_id": "line_id",
        "process_id": "process_id",
        "eds_step": "eds_step",
        "step_seq": "step_seq",
        "ppid": "ppid",
        "eqpch": "eqpch",
        "bin_name": "bin_name",
        "date_to": "date_to",
        "severity_mode": "severity_mode",
        "receiver_emails": "receiver_emails",
        "schedule_type": "schedule_type",
        "send_time": "send_time",
        "timezone": "timezone",
        "is_active": "is_active",
        "memo": "memo",
    }
    for source, target in field_map.items():
        if source in data:
            setattr(row, target, data[source])
    row.save()
    return {"id": row.id}


def delete_mail_rule(rule_id: int, *, user: Any) -> None:
    """사용자 소유 메일 알림 규칙을 삭제합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    try:
        row = selectors.get_owned_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc
    row.delete()


def list_mail_rule_permissions(rule_id: int, *, user: Any) -> list[dict[str, object]]:
    """owner가 메일 rule 공유 권한 목록을 조회합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    try:
        selectors.get_owned_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc
    return [
        _serialize_mail_rule_permission(permission)
        for permission in selectors.list_mail_rule_permissions(rule_id=rule_id)
    ]


def replace_mail_rule_permissions(
    rule_id: int,
    permissions: list[dict[str, str]],
    *,
    user: Any,
) -> dict[str, object]:
    """owner가 메일 rule 공유 권한 목록을 전체 교체합니다."""

    from ..models import L3SpiderMailRule, L3SpiderMailRulePermission

    user_id = _require_user_id(user)
    try:
        row = selectors.get_owned_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc

    resolved: list[tuple[Any, str]] = []
    resolved_user_ids: set[int] = set()
    for item in permissions:
        target_user = selectors.find_user_for_mail_rule_permission(item["user"])
        if target_user is None:
            raise L3SpiderServiceError(
                f"사용자를 찾을 수 없습니다: {item['user']}",
                status_code=400,
            )
        if target_user.id == row.created_by_id:
            raise L3SpiderServiceError("owner는 별도 권한 항목으로 추가할 수 없습니다.", status_code=400)
        if target_user.id in resolved_user_ids:
            raise L3SpiderServiceError("같은 사용자를 중복 입력할 수 없습니다.", status_code=400)
        resolved_user_ids.add(target_user.id)
        resolved.append((target_user, item["access_level"]))

    with transaction.atomic():
        L3SpiderMailRulePermission.objects.filter(rule=row).delete()
        L3SpiderMailRulePermission.objects.bulk_create([
            L3SpiderMailRulePermission(
                rule=row,
                user=target_user,
                access_level=access_level,
                granted_by_id=user_id,
            )
            for target_user, access_level in resolved
        ])

    return {
        "id": row.id,
        "permissions": [
            _serialize_mail_rule_permission(permission)
            for permission in selectors.list_mail_rule_permissions(rule_id=rule_id)
        ],
    }


def _mail_rule_to_pattern_dict(rule) -> dict[str, object]:
    """메일 rule 모델에서 패턴 적용에 필요한 dict를 생성합니다."""

    return {
        "line_id": rule.line_id,
        "process_id": rule.process_id,
        "eds_step": rule.eds_step,
        "step_seq": rule.step_seq,
        "ppid": rule.ppid,
        "eqpch": rule.eqpch,
        "bin_name": rule.bin_name,
        "date_to": rule.date_to,
    }


def _filter_frame_for_mail_rule(merged: pd.DataFrame, rule) -> pd.DataFrame:
    """메일 알림 rule의 패턴과 심각도 조건에 맞는 row만 남깁니다."""

    if merged.empty:
        return merged
    allowed_statuses = MAIL_SEVERITY_STATUSES.get(rule.severity_mode, {"High Risk Chamber"})
    if "display_status" not in merged.columns:
        return merged.iloc[0:0]

    filtered = merged[merged["display_status"].isin(allowed_statuses)]
    if filtered.empty:
        return filtered

    rule_dict = _mail_rule_to_pattern_dict(rule)
    field_columns = [
        ("line_id", "line_id"),
        ("process_id", "process_id"),
        ("eds_step", "eds_step"),
        ("step_seq", "step_seq"),
        ("ppid", "ppid"),
        ("eqpch", "eqc"),
        ("bin_name", "bin_name"),
    ]
    mask = pd.Series(True, index=filtered.index)
    for field, column in field_columns:
        pattern = rule_dict.get(field) or "*"
        if pattern == "*":
            continue
        if column not in filtered.columns:
            return filtered.iloc[0:0]
        mask = mask & filtered[column].astype(str).apply(lambda v, p=pattern: _matches_pattern(v, p))

    return filtered[mask]


def _safe_string(value: Any) -> str:
    """메일 이벤트 키와 HTML 생성에 사용할 문자열로 정규화합니다."""

    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value)


def _build_mail_event_key(event: dict[str, object]) -> str:
    """이상감지 이벤트를 중복 판정용 안정 키로 변환합니다."""

    key_payload = {
        key: _safe_string(event.get(key))
        for key in (
            "date",
            "line_id",
            "process_id",
            "eds_step",
            "step_seq",
            "ppid",
            "eqc",
            "bin_name",
            "display_status",
        )
    }
    raw_key = json.dumps(key_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _resolve_mail_rule_files(rule, *, today: str) -> list[Path]:
    """오늘 날짜 파일만 인덱스로 조회합니다. line/process/eds_step이 정확한 값이면 추가 필터링합니다."""

    def _is_exact(val: Any) -> bool:
        s = str(val) if val is not None else ""
        return bool(s) and s != "*" and "*" not in s and "?" not in s

    kwargs: dict[str, str] = {}
    if _is_exact(rule.line_id):
        kwargs["line_id"] = rule.line_id
    if _is_exact(rule.process_id):
        kwargs["process_id"] = rule.process_id
    if _is_exact(rule.eds_step):
        kwargs["eds_step"] = rule.eds_step

    files = selectors.query_indexed_files_by_range(date_from=today, date_to=today, **kwargs)
    if not files:
        # 인덱스 없거나 결과 없으면 날짜 디렉터리 직접 스캔
        files = selectors.iter_date_files(today)
    return files


def _collect_mail_rule_events(rule, *, today: str) -> list[dict[str, object]]:
    """메일 알림 rule에 매칭되는 오늘 날짜 이상감지 이벤트 목록을 수집합니다."""

    try:
        files = _resolve_mail_rule_files(rule, today=today)
    except FileNotFoundError as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise L3SpiderServiceError(str(exc), status_code=400) from exc

    frames = _parallel_read(files, _read_mail_event_file)
    if not frames:
        return []

    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    merged = _filter_frame_for_mail_rule(merged, rule)
    if merged.empty:
        return []

    group_columns = [
        "date",
        "line_id",
        "process_id",
        "eds_step",
        "step_seq",
        "ppid",
        "eqc",
        "bin_name",
        "display_status",
    ]
    available_group_columns = [column for column in group_columns if column in merged.columns]
    grouped = merged.groupby(available_group_columns, sort=True, dropna=False)
    events: list[dict[str, object]] = []
    for keys, group in grouped:
        key_values = keys if isinstance(keys, tuple) else (keys,)
        event = {
            column: _safe_string(value)
            for column, value in zip(available_group_columns, key_values)
        }
        if "tkin_time" in group.columns:
            tkin = pd.to_datetime(group["tkin_time"], errors="coerce").dropna()
            event["latest_tkin_time"] = tkin.max().strftime("%Y-%m-%d %H:%M:%S") if not tkin.empty else ""
        event["row_count"] = int(len(group))
        event["event_key"] = _build_mail_event_key(event)
        events.append(event)
    return events


def _rule_local_today(rule, *, now: dt_datetime) -> "date":
    """rule 타임존 기준 오늘 날짜를 반환합니다."""
    try:
        tz = ZoneInfo(rule.timezone or "Asia/Seoul")
    except Exception:
        tz = ZoneInfo("Asia/Seoul")
    return now.astimezone(tz).date()


def _is_mail_rule_due(rule, *, now: dt_datetime) -> bool:
    """현재 시각 기준으로 rule 발송 시간이 되었는지 판단합니다."""

    try:
        tz = ZoneInfo(rule.timezone or "Asia/Seoul")
    except Exception:
        tz = ZoneInfo("Asia/Seoul")
    local_now = now.astimezone(tz)
    local_today = local_now.date()
    # date_to 만료 체크
    if rule.date_to and local_today > rule.date_to:
        return False
    if local_now.time().replace(second=0, microsecond=0) < rule.send_time:
        return False
    checked_at = rule.last_checked_at or rule.last_sent_at
    if not checked_at:
        return True
    return checked_at.astimezone(tz).date() < local_today


def _mark_mail_rule_checked(rule, *, sent: bool = False) -> None:
    """메일 rule의 일일 처리 시각을 갱신합니다."""

    checked_at = timezone.now()
    rule.last_checked_at = checked_at
    update_fields = ["last_checked_at", "updated_at"]
    if sent:
        rule.last_sent_at = checked_at
        update_fields.append("last_sent_at")
    rule.save(update_fields=update_fields)


def _resolve_l3_mail_sender() -> str:
    """L3 Spider 메일 발신자 주소를 settings/env에서 조회합니다."""

    return (
        getattr(settings, "L3_SPIDER_MAIL_SENDER", "")
        or getattr(settings, "DRONE_MAIL_SENDER", "")
        or ""
    ).strip()


def _build_l3_mail_subject(rule, events: list[dict[str, object]]) -> str:
    """L3 Spider 메일 제목을 생성합니다."""

    return f"[L3 Spider] 이상감지 {len(events)}건 - {rule.name}".strip()[:255]


def _resolve_l3_spider_mail_url() -> str:
    """메일 본문에 넣을 L3 Spider 화면 URL을 settings/env에서 생성합니다."""

    configured = str(getattr(settings, "L3_SPIDER_MAIL_TARGET_URL", "") or "").strip()
    if configured:
        return configured

    frontend_base = str(getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
    if not frontend_base:
        return ""
    return f"{frontend_base.rstrip('/')}/l3_spider"


def _build_l3_spider_event_url(base_url: str, event: dict[str, object]) -> str:
    """메일 이벤트 정보를 L3 Spider deep link query로 변환합니다."""

    if not base_url:
        return ""

    query_fields = [
        ("date", "date"),
        ("lineId", "line_id"),
        ("processId", "process_id"),
        ("edsStep", "eds_step"),
        ("stepSeq", "step_seq"),
        ("ppid", "ppid"),
        ("eqpch", "eqc"),
        ("binName", "bin_name"),
    ]
    event_query = [
        (query_name, value)
        for query_name, event_key in query_fields
        if (value := _safe_string(event.get(event_key)))
    ]
    if not event_query:
        return base_url

    parsed = urlparse(base_url)
    existing_query = parse_qsl(parsed.query, keep_blank_values=True)
    return urlunparse(parsed._replace(query=urlencode([*existing_query, *event_query])))


def _build_l3_mail_body(rule, events: list[dict[str, object]]) -> str:
    """L3 Spider 이상감지 digest HTML 본문을 생성합니다."""

    target_url = _resolve_l3_spider_mail_url()
    rows = []
    for event in events[:_MAIL_DIGEST_PREVIEW_LIMIT]:
        cells = [
            event.get("date"),
            event.get("line_id"),
            event.get("process_id"),
            event.get("eds_step"),
            event.get("step_seq"),
            event.get("ppid"),
            event.get("eqc"),
            event.get("bin_name"),
            event.get("display_status"),
            event.get("latest_tkin_time"),
        ]
        event_url = _build_l3_spider_event_url(target_url, event)
        action_cell = (
            f'<td><a href="{html.escape(event_url, quote=True)}" '
            'target="_blank" rel="noopener noreferrer">열기</a></td>'
            if event_url
            else "<td></td>"
        )
        rows.append(
            "<tr>"
            + "".join(f"<td>{html.escape(_safe_string(value))}</td>" for value in cells)
            + action_cell
            + "</tr>"
        )

    remaining = max(0, len(events) - _MAIL_DIGEST_PREVIEW_LIMIT)
    remaining_text = f"<p>외 {remaining}건은 L3 Spider 화면에서 확인하세요.</p>" if remaining else ""
    action_html = ""
    if target_url:
        primary_url = _build_l3_spider_event_url(target_url, events[0]) if events else target_url
        escaped_url = html.escape(primary_url, quote=True)
        action_html = f"""
    <p>
      <a href="{escaped_url}" target="_blank" rel="noopener noreferrer"
         style="display:inline-block;padding:10px 14px;background:#2563eb;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">
        L3 Spider에서 확인
      </a>
    </p>
"""
    return f"""
<html>
  <body>
    <h3>L3 Spider 이상감지 알림</h3>
    <p>규칙: {html.escape(rule.name)}</p>
    <p>조건: {html.escape(rule.severity_mode)}</p>
    {action_html}
    <table border="1" cellspacing="0" cellpadding="4">
      <thead>
        <tr>
          <th>Date</th><th>Line</th><th>Process</th><th>EDS Step</th><th>Step</th>
          <th>PPID</th><th>EQPCH</th><th>Bin</th><th>Status</th><th>Last TKin</th><th>Link</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    {remaining_text}
  </body>
</html>
"""


def _claim_mail_events(rule, events: list[dict[str, object]]) -> list[dict[str, object]]:
    """발송 전 delivery row를 생성해 이번 trigger가 처리할 이벤트만 선점합니다."""

    from ..models import L3SpiderMailDelivery

    claimed: list[dict[str, object]] = []
    for event in events:
        try:
            with transaction.atomic():
                L3SpiderMailDelivery.objects.create(
                    rule=rule,
                    event_key=event["event_key"],
                    status=L3SpiderMailDelivery.Statuses.PENDING,
                    event_date=_safe_string(event.get("date")),
                    display_status=_safe_string(event.get("display_status")),
                    receiver_emails=list(rule.receiver_emails or []),
                    payload_snapshot=event,
                )
            claimed.append(event)
        except IntegrityError:
            continue
    return claimed


def _mark_claimed_mail_events(
    *,
    rule,
    events: list[dict[str, object]],
    status: str,
    error_message: str = "",
) -> None:
    """선점한 delivery row의 최종 발송 상태를 갱신합니다."""

    from ..models import L3SpiderMailDelivery

    event_keys = [event["event_key"] for event in events]
    update_fields: dict[str, object] = {
        "status": status,
        "error_message": error_message[:2000],
    }
    if status == L3SpiderMailDelivery.Statuses.SENT:
        update_fields["sent_at"] = timezone.now()
    L3SpiderMailDelivery.objects.filter(
        rule=rule,
        event_key__in=event_keys,
        status=L3SpiderMailDelivery.Statuses.PENDING,
    ).update(**update_fields)


def _process_mail_rule(rule, *, now: dt_datetime) -> dict[str, object]:
    """단일 메일 rule의 due 여부 확인, 이벤트 수집, digest 발송을 처리합니다."""

    from ..models import L3SpiderMailDelivery

    if not _is_mail_rule_due(rule, now=now):
        return {"ruleId": rule.id, "status": "not_due", "claimed": 0, "sent": 0}

    today = _rule_local_today(rule, now=now).isoformat()
    events = _collect_mail_rule_events(rule, today=today)
    if not events:
        _mark_mail_rule_checked(rule)
        return {"ruleId": rule.id, "status": "no_events", "claimed": 0, "sent": 0}

    claimed_events = _claim_mail_events(rule, events)
    if not claimed_events:
        _mark_mail_rule_checked(rule)
        return {"ruleId": rule.id, "status": "already_sent", "claimed": 0, "sent": 0}

    sender = _resolve_l3_mail_sender()
    if not sender:
        _mark_claimed_mail_events(
            rule=rule,
            events=claimed_events,
            status=L3SpiderMailDelivery.Statuses.FAILED,
            error_message="L3_SPIDER_MAIL_SENDER 미설정",
        )
        return {"ruleId": rule.id, "status": "failed", "claimed": len(claimed_events), "sent": 0}

    try:
        send_knox_mail_api(
            sender_email=sender,
            receiver_emails=rule.receiver_emails,
            subject=_build_l3_mail_subject(rule, claimed_events),
            html_content=_build_l3_mail_body(rule, claimed_events),
        )
    except Exception as exc:
        _mark_claimed_mail_events(
            rule=rule,
            events=claimed_events,
            status=L3SpiderMailDelivery.Statuses.FAILED,
            error_message=str(exc),
        )
        return {"ruleId": rule.id, "status": "failed", "claimed": len(claimed_events), "sent": 0}

    _mark_claimed_mail_events(
        rule=rule,
        events=claimed_events,
        status=L3SpiderMailDelivery.Statuses.SENT,
    )
    _mark_mail_rule_checked(rule, sent=True)
    return {
        "ruleId": rule.id,
        "status": "sent",
        "claimed": len(claimed_events),
        "sent": len(claimed_events),
    }


def send_mail_rule_test(rule_id: int, *, user: Any) -> dict[str, object]:
    """메일 rule을 정기 발송 이력과 분리해 단발성으로 테스트 발송합니다."""

    from ..models import L3SpiderMailRule

    user_id = _require_user_id(user)
    try:
        rule = selectors.get_mail_rule_for_user(rule_id=rule_id, user_id=user_id)
    except L3SpiderMailRule.DoesNotExist as exc:
        raise L3SpiderServiceError("Not found", status_code=404) from exc
    if not _mail_rule_access(rule, user_id=user_id)["canWrite"]:
        raise L3SpiderServiceError("Write permission required", status_code=403)
    if not rule.receiver_emails:
        raise L3SpiderServiceError("수신자가 없습니다.", status_code=400)

    today = _rule_local_today(rule, now=timezone.now()).isoformat()
    events = _collect_mail_rule_events(rule, today=today)
    if not events:
        return {
            "ruleId": rule.id,
            "status": "no_events",
            "sent": 0,
            "eventCount": 0,
            "receiverCount": len(rule.receiver_emails),
        }

    sender = _resolve_l3_mail_sender()
    if not sender:
        raise L3SpiderServiceError("L3_SPIDER_MAIL_SENDER 미설정", status_code=400)

    try:
        send_knox_mail_api(
            sender_email=sender,
            receiver_emails=rule.receiver_emails,
            subject=f"[TEST] {_build_l3_mail_subject(rule, events)}"[:255],
            html_content=_build_l3_mail_body(rule, events),
        )
    except Exception as exc:
        raise L3SpiderServiceError(f"테스트 메일 발송 실패: {exc}", status_code=502) from exc

    return {
        "ruleId": rule.id,
        "status": "sent",
        "sent": len(events),
        "eventCount": len(events),
        "receiverCount": len(rule.receiver_emails),
    }


def trigger_due_mail_rules(*, limit: int = 20, now: dt_datetime | None = None) -> dict[str, object]:
    """발송 시간이 된 활성 L3 Spider 메일 rule을 처리합니다.

    입력:
        limit: 한 번에 처리할 최대 rule 수.
        now: 테스트용 기준 시각. 없으면 현재 시각을 사용합니다.
    반환:
        처리 rule 수와 발송 결과 요약.
    부작용:
        L3SpiderMailDelivery 생성/갱신 및 외부 Mail API 호출이 발생합니다.
    """

    current = now or timezone.now()
    rules = list(selectors.list_active_mail_rules_for_trigger(limit=limit))
    results = [_process_mail_rule(rule, now=current) for rule in rules]
    return {
        "processed": len(results),
        "sent": sum(int(result.get("sent", 0)) for result in results),
        "claimed": sum(int(result.get("claimed", 0)) for result in results),
        "results": results,
    }


def _apply_exclusion_filters_with_rules(merged: pd.DataFrame, rules: list[dict]) -> pd.DataFrame:
    """주어진 rules를 DataFrame에 적용합니다."""
    if not rules:
        return merged

    _FIELD_COL = [
        ("line_id", "line_id"),
        ("process_id", "process_id"),
        ("eds_step", "eds_step"),
        ("step_seq", "step_seq"),
        ("ppid", "ppid"),
        ("eqpch", "eqc"),
        ("bin_name", "bin_name"),
    ]

    exclude_mask = pd.Series(False, index=merged.index)

    for rule in rules:
        row_mask = pd.Series(True, index=merged.index)

        for field, col in _FIELD_COL:
            pattern = rule.get(field) or "*"
            if pattern == "*":
                continue
            if col not in merged.columns:
                row_mask = pd.Series(False, index=merged.index)
                break
            row_mask = row_mask & merged[col].astype(str).apply(
                lambda v, p=pattern: _matches_pattern(v, p)
            )

        # 파일 경로 date 폴더명 기준 날짜 범위 (선택 날짜와 동일 기준)
        date_from = rule.get("date_from")
        date_to = rule.get("date_to")
        if (date_from or date_to) and "date" in merged.columns:
            date_col = merged["date"].astype(str)
            if date_from:
                row_mask = row_mask & (date_col >= date_from.isoformat() if hasattr(date_from, "isoformat") else date_col >= str(date_from))
            if date_to:
                row_mask = row_mask & (date_col <= date_to.isoformat() if hasattr(date_to, "isoformat") else date_col <= str(date_to))

        exclude_mask = exclude_mask | row_mask

    return merged[~exclude_mask]


def _apply_exclusion_filters(merged: pd.DataFrame, *, user: Any | None = None) -> pd.DataFrame:
    """활성 제외 필터를 DB에서 읽어 적용합니다 (get_data 전용)."""
    return _apply_exclusion_filters_with_rules(merged, _get_exclusion_rules(user=user))


def get_structure(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """파일명 스캔만으로 edsStepSeqs·edsStepPpids를 즉시 반환합니다 (Parquet 읽기 없음).

    제외 필터의 경로 필드(line_id, process_id, eds_step, step_seq, ppid)를 적용합니다.
    EQPCH·bin_name 기준 규칙은 Parquet 데이터 없이 판단 불가하므로 자동으로 무시됩니다.
    """
    empty: dict[str, object] = {"edsStepSeqs": {}, "edsStepPpids": {}}
    if not _has_required_selection(selection):
        return empty

    rules = _get_exclusion_rules(user=user)
    rules_hash = str(hash(tuple(sorted(str(r) for r in rules))))
    cache_key = f"{rules_hash}:{_make_selection_cache_key(selection)}"
    cached = _structure_cache.get(cache_key)
    if cached is not None:
        return cached

    line_names = {str(v) for v in (selection.get("lineNames") or []) if v}

    # 파일명 스캔만으로 처리(Parquet 읽기 없음). line_name은 (line_id, process_id, step_seq)로
    # 파일마다 결정되므로 스캔 중 바로 필터합니다.
    root = selectors.get_data_root()
    file_rows: list[dict[str, str]] = []
    try:
        for path in selectors.iter_data_files(selection):
            parsed = _parse_filename_key(path)
            if not parsed:
                # 계약상 daily_anomaly 파일명엔 step_seq가 항상 있음. structure는 파일명 스캔만
                # 하므로(Parquet 미읽음) step_seq를 못 읽는 파일은 다룰 수 없어 제외.
                continue
            step_seq, ppid = parsed
            relative_parts = path.relative_to(root).parts
            if len(relative_parts) < 5:
                continue
            date, line_id, process_id, eds_step = relative_parts[:4]
            if line_names and line_name_rules.resolve_line_name(line_id, process_id, step_seq) not in line_names:
                continue
            file_rows.append({
                "date": date,
                "line_id": line_id,
                "process_id": process_id,
                "eds_step": eds_step,
                "step_seq": step_seq,
                "ppid": ppid,
            })
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    if not file_rows:
        _structure_cache.set(cache_key, empty)
        return empty
    df = pd.DataFrame(file_rows).drop_duplicates()
    # eqc·bin_name 컬럼이 없으므로 해당 필드가 있는 규칙은 자동으로 제외 대상 없음 처리됨
    df = _apply_exclusion_filters_with_rules(df, rules)

    eds_step_seqs: dict[str, set[str]] = {}
    eds_step_ppids: dict[str, set[str]] = {}

    if not df.empty and {"eds_step", "step_seq", "ppid"}.issubset(df.columns):
        for _, row in df[["eds_step", "step_seq", "ppid"]].drop_duplicates().iterrows():
            eds_step = str(row["eds_step"])
            step_seq = str(row["step_seq"])
            ppid_val = str(row["ppid"])
            eds_step_seqs.setdefault(eds_step, set()).add(step_seq)
            eds_step_ppids.setdefault(f"{eds_step}|||{step_seq}", set()).add(ppid_val)

    result: dict[str, object] = {
        "edsStepSeqs": {eds: sorted(steps) for eds, steps in sorted(eds_step_seqs.items())},
        "edsStepPpids": {key: sorted(ppids) for key, ppids in sorted(eds_step_ppids.items())},
    }
    _structure_cache.set(cache_key, result)
    return result


def get_stats(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """슬림 Parquet 읽기로 stats + PPID별 last_tkin_time을 반환합니다."""
    empty: dict[str, object] = {"stats": _empty_stats(), "ppidLastTkinTime": {}}
    if not _has_required_selection(selection):
        return empty

    # rules hash를 포함한 cache key: 필터 변경 시 자동으로 다른 key가 사용됨
    rules = _get_exclusion_rules(user=user)
    rules_hash = str(hash(tuple(sorted(str(r) for r in rules))))
    cache_key = f"{rules_hash}:{_make_selection_cache_key(selection)}"
    cached = _stats_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        files = list(selectors.iter_data_files(selection))
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc

    files = _filter_files_by_line_names(files, selection)
    frames = _parallel_read(files, _read_stats_file)
    if not frames:
        _stats_cache.set(cache_key, empty)
        return empty

    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    # rules는 이미 읽었으므로 직접 적용 (DB 재조회 방지)
    merged = _apply_exclusion_filters_with_rules(merged, rules)

    if "display_status" not in merged.columns:
        _stats_cache.set(cache_key, empty)
        return empty

    status = merged["display_status"]
    anomaly_mask = status.isin(ANOMALY_STATUSES)
    high_risk_mask = status == "High Risk Chamber"

    stats = {
        "total": int(len(merged)),
        "normal": int((status == "Normal (Ref)").sum()),
        "warning": int((status == "Warning").sum()),
        "risk": int(high_risk_mask.sum()),
        "anomalySteps": int(merged.loc[anomaly_mask, "step_seq"].dropna().nunique())
            if "step_seq" in merged.columns else 0,
        "highRiskEqpchs": int(merged.loc[high_risk_mask, "eqc"].dropna().nunique())
            if "eqc" in merged.columns else 0,
    }

    ppid_last_tkin_time: dict[str, str] = {}
    if {"eds_step", "step_seq", "ppid", "tkin_time"}.issubset(merged.columns):
        try:
            tkin = merged[["eds_step", "step_seq", "ppid", "tkin_time"]].copy()
            tkin["tkin_time"] = pd.to_datetime(tkin["tkin_time"], errors="coerce")
            tkin = tkin.dropna(subset=["tkin_time"])
            if not tkin.empty:
                grouped = tkin.groupby(["eds_step", "step_seq", "ppid"], sort=False)["tkin_time"].max()
                for (eds, step, ppid), ts in grouped.items():
                    ppid_last_tkin_time[f"{eds}|||{step}|||{ppid}"] = ts.strftime("%Y-%m-%d %H:%M")
        except Exception as exc:
            print(f"[WARN] L3 Spider ppidLastTkinTime compute failed: {exc}")

    result = {"stats": stats, "ppidLastTkinTime": ppid_last_tkin_time}
    _stats_cache.set(cache_key, result)
    return result


def get_summary(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """선택 조건의 이상감지 요약 정보를 반환합니다."""
    empty = {"stats": _empty_stats(), "edsStepSeqs": {}, "edsStepPpids": {}, "stepPpids": {}, "ppidEqcs": {}, "ppidHighRiskEqcs": {}, "ppidBins": {}, "eqcBins": {}, "eqcAnomalyBins": {}, "eqcHighRiskBins": {}, "bins": [], "anomalies": []}
    if not _has_required_selection(selection):
        return empty

    frames = _read_summary_frames(selection)
    if not frames:
        return empty

    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    merged = _apply_exclusion_filters(merged, user=user)
    if merged.empty:
        return empty
    if "display_status" not in merged.columns:
        return empty

    status = merged["display_status"]
    anomaly_mask = status.isin(ANOMALY_STATUSES)
    high_risk_mask = status == "High Risk Chamber"
    stats = {
        "total": int(len(merged)),
        "normal": int((status == "Normal (Ref)").sum()),
        "warning": int((status == "Warning").sum()),
        "risk": int(high_risk_mask.sum()),
        "anomalySteps": int(merged.loc[anomaly_mask, "step_seq"].dropna().nunique())
        if "step_seq" in merged.columns
        else 0,
        "highRiskEqpchs": int(merged.loc[high_risk_mask, "eqc"].dropna().nunique())
        if "eqc" in merged.columns
        else 0,
    }

    eds_step_seqs: dict[str, list[str]] = {}
    if {"eds_step", "step_seq"}.issubset(merged.columns):
        pairs = merged[["eds_step", "step_seq"]].drop_duplicates().sort_values(["eds_step", "step_seq"])
        eds_step_seqs = {
            str(eds): sorted(group["step_seq"].dropna().astype(str).tolist())
            for eds, group in pairs.groupby("eds_step", sort=True)
        }

    eds_step_ppids: dict[str, list[str]] = {}
    if {"eds_step", "step_seq", "ppid"}.issubset(merged.columns):
        pairs = merged[["eds_step", "step_seq", "ppid"]].drop_duplicates().sort_values(
            ["eds_step", "step_seq", "ppid"]
        )
        eds_step_ppids = {
            f"{str(eds)}|||{str(step)}": sorted(group["ppid"].dropna().astype(str).tolist())
            for (eds, step), group in pairs.groupby(["eds_step", "step_seq"], sort=True)
        }

    step_ppids: dict[str, list[str]] = {}
    if {"step_seq", "ppid"}.issubset(merged.columns):
        pairs = merged[["step_seq", "ppid"]].drop_duplicates().sort_values(["step_seq", "ppid"])
        step_ppids = {
            str(step): group["ppid"].dropna().astype(str).tolist()
            for step, group in pairs.groupby("step_seq", sort=True)
        }

    anomalies: list[dict[str, Any]] = []
    anomaly_columns = ["eds_step", "step_seq", "ppid", "eqc", "bin_name"]
    if all(column in merged.columns for column in anomaly_columns):
        anomalies = [
            _camelize_mapping(row)
            for row in (
                merged.loc[high_risk_mask, anomaly_columns]
                .drop_duplicates()
                .sort_values(anomaly_columns)
                .astype(str)
                .to_dict(orient="records")
            )
        ]

    ppid_eqcs: dict[str, list[str]] = {}
    if {"ppid", "eqc"}.issubset(merged.columns):
        pairs = merged[["ppid", "eqc"]].drop_duplicates().sort_values(["ppid", "eqc"])
        ppid_eqcs = {
            str(ppid): sorted(group["eqc"].dropna().astype(str).tolist())
            for ppid, group in pairs.groupby("ppid", sort=True)
        }

    ppid_high_risk_eqcs: dict[str, list[str]] = {}
    if {"ppid", "eqc", "display_status"}.issubset(merged.columns):
        high_risk_pairs = (
            merged.loc[high_risk_mask, ["ppid", "eqc"]]
            .drop_duplicates()
            .sort_values(["ppid", "eqc"])
        )
        ppid_high_risk_eqcs = {
            str(ppid): sorted(group["eqc"].dropna().astype(str).tolist())
            for ppid, group in high_risk_pairs.groupby("ppid", sort=True)
        }

    ppid_bins: dict[str, list[str]] = {}
    if {"ppid", "bin_name"}.issubset(merged.columns):
        pairs = merged[["ppid", "bin_name"]].drop_duplicates().sort_values(["ppid", "bin_name"])
        ppid_bins = {
            str(ppid): sorted(group["bin_name"].dropna().astype(str).tolist())
            for ppid, group in pairs.groupby("ppid", sort=True)
        }

    eqc_bins: dict[str, list[str]] = {}
    if {"eqc", "bin_name"}.issubset(merged.columns):
        pairs = merged[["eqc", "bin_name"]].drop_duplicates().sort_values(["eqc", "bin_name"])
        eqc_bins = {
            str(eqc): sorted(group["bin_name"].dropna().astype(str).tolist())
            for eqc, group in pairs.groupby("eqc", sort=True)
        }

    eqc_anomaly_bins: dict[str, list[str]] = {}
    if {"eqc", "bin_name", "display_status"}.issubset(merged.columns):
        anomaly_pairs = (
            merged.loc[merged["display_status"].isin(ANOMALY_STATUSES), ["eqc", "bin_name"]]
            .drop_duplicates()
            .sort_values(["eqc", "bin_name"])
        )
        eqc_anomaly_bins = {
            str(eqc): sorted(group["bin_name"].dropna().astype(str).tolist())
            for eqc, group in anomaly_pairs.groupby("eqc", sort=True)
        }

    eqc_high_risk_bins: dict[str, list[str]] = {}
    if {"eqc", "bin_name", "display_status"}.issubset(merged.columns):
        high_risk_bin_pairs = (
            merged.loc[high_risk_mask, ["eqc", "bin_name"]]
            .drop_duplicates()
            .sort_values(["eqc", "bin_name"])
        )
        eqc_high_risk_bins = {
            str(eqc): sorted(group["bin_name"].dropna().astype(str).tolist())
            for eqc, group in high_risk_bin_pairs.groupby("eqc", sort=True)
        }

    bins = (
        sorted(merged["bin_name"].dropna().astype(str).unique().tolist())
        if "bin_name" in merged.columns
        else []
    )
    return {
        "stats": stats,
        "edsStepSeqs": eds_step_seqs,
        "edsStepPpids": eds_step_ppids,
        "stepPpids": step_ppids,
        "ppidEqcs": ppid_eqcs,
        "ppidHighRiskEqcs": ppid_high_risk_eqcs,
        "ppidBins": ppid_bins,
        "eqcBins": eqc_bins,
        "eqcAnomalyBins": eqc_anomaly_bins,
        "eqcHighRiskBins": eqc_high_risk_bins,
        "bins": bins,
        "anomalies": anomalies,
    }


def _empty_daily_summary() -> dict[str, object]:
    return {
        "dates": [],
        "headline": {
            "groups": 0, "binNames": 0, "stepSeqs": 0, "lines": 0, "processes": 0,
            "edsSteps": 0, "ppids": 0, "lots": 0, "totalRows": 0,
            "anomalies": 0, "highRisk": 0, "warning": 0, "anomalyGroups": 0,
            "anomalyEqpchs": 0, "highRiskEqpchs": 0, "warningEqpchs": 0,
        },
        "matrix": {"lines": [], "processes": [], "edsSteps": [], "cells": []},
    }


def _parse_json_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    try:
        parsed = json.loads(value)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except Exception:
        return []


def _daily_file_df_from_index(index_rows: list[dict], date: str, root: Path) -> tuple[pd.DataFrame, list[Path]]:
    """file_index 행 → 파일별 집계 프레임(카운트 있는 파일) + 카운트 NULL 파일 경로 목록."""
    counted: list[dict] = []
    uncounted_paths: list[Path] = []
    for r in index_rows:
        if r.get("high_risk_cnt") is None:  # 구 데이터 → parquet 폴백 대상
            uncounted_paths.append(
                root / date / str(r.get("line_id")) / str(r.get("process_id"))
                / str(r.get("eds_step")) / Path(str(r.get("filepath"))).name
            )
            continue
        counted.append({
            "line_id": str(r.get("line_id") or ""),
            "process_id": str(r.get("process_id") or ""),
            "eds_step": str(r.get("eds_step") or ""),
            "step_seq": str(r.get("step_seq") or ""),
            "ppid": str(r.get("ppid") or ""),
            "hr": int(r.get("high_risk_cnt") or 0),
            "wn": int(r.get("warning_cnt") or 0),
            "row_cnt": int(r.get("row_cnt") or 0),
            "bins": _parse_json_list(r.get("bin_names")),
            "hr_eqcs": _parse_json_list(r.get("high_risk_eqcs")),
        })
    return pd.DataFrame(counted), uncounted_paths


def _daily_file_df_from_parquet(paths: list[Path], rules: list[dict] | None) -> pd.DataFrame:
    """Parquet 파일들을 읽어(제외필터 옵션) 파일별 집계 프레임으로 변환합니다."""
    if not paths:
        return pd.DataFrame()
    frames = _parallel_read(list(paths), _read_daily_summary_file)
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    if rules:
        merged = _apply_exclusion_filters_with_rules(merged, rules)
    if merged.empty or "display_status" not in merged.columns:
        return pd.DataFrame()
    for col in ("line_id", "process_id", "eds_step", "step_seq", "ppid", "bin_name"):
        if col not in merged.columns:
            merged[col] = ""
        merged[col] = merged[col].fillna("").astype(str)
    if "eqc" not in merged.columns:
        merged["eqc"] = ""
    merged["eqc"] = merged["eqc"].fillna("").astype(str)
    status = merged["display_status"].astype(str)
    merged["_hr"] = (status == "High Risk Chamber").astype(int)
    merged["_wn"] = (status == "Warning").astype(int)
    records: list[dict] = []
    for (lid, pid, eds, sseq, ppid), group in merged.groupby(
        ["line_id", "process_id", "eds_step", "step_seq", "ppid"], sort=False
    ):
        hr_eqcs = sorted(
            e for e in group.loc[group["_hr"] == 1, "eqc"].unique().tolist() if e
        )
        records.append({
            "line_id": lid, "process_id": pid, "eds_step": eds, "step_seq": sseq, "ppid": ppid,
            "hr": int(group["_hr"].sum()), "wn": int(group["_wn"].sum()), "row_cnt": int(len(group)),
            "bins": sorted(group["bin_name"].dropna().astype(str).unique().tolist()),
            "hr_eqcs": hr_eqcs,
        })
    return pd.DataFrame(records)


def _aggregate_daily(file_df: pd.DataFrame, dates: list) -> dict:
    """파일별 집계 프레임 → 일별 요약(line_name 기준 매트릭스 + 헤드라인)."""
    if file_df.empty:
        return {**_empty_daily_summary(), "dates": sorted(dates)}
    for col in ("line_id", "process_id", "eds_step", "step_seq", "ppid"):
        if col not in file_df.columns:
            file_df[col] = ""
        file_df[col] = file_df[col].fillna("").astype(str)
    for col in ("hr", "wn", "row_cnt"):
        if col not in file_df.columns:
            file_df[col] = 0
        file_df[col] = file_df[col].fillna(0).astype(int)
    if "bins" not in file_df.columns:
        file_df["bins"] = [[] for _ in range(len(file_df))]
    if "hr_eqcs" not in file_df.columns:
        file_df["hr_eqcs"] = [[] for _ in range(len(file_df))]

    name_map = {
        (lid, pid, sseq): line_name_rules.resolve_line_name(lid, pid, sseq)
        for lid, pid, sseq in file_df[["line_id", "process_id", "step_seq"]].drop_duplicates().itertuples(index=False)
    }
    file_df["line_name"] = [
        name_map[(lid, pid, sseq)]
        for lid, pid, sseq in zip(file_df["line_id"], file_df["process_id"], file_df["step_seq"])
    ]

    cells: list[dict] = []
    for (line_name, pid, eds), group in file_df.groupby(["line_name", "process_id", "eds_step"], sort=True):
        hr_c = int(group["hr"].sum())
        wn_c = int(group["wn"].sum())
        bins: set = set()
        for bin_list in group["bins"]:
            if bin_list:
                bins.update(bin_list)
        hr_step_seqs = {s for s in group.loc[group["hr"] > 0, "step_seq"] if s}
        cell_hr_eqcs: set = set()
        for eqc_list in group["hr_eqcs"]:
            if eqc_list:
                cell_hr_eqcs.update(eqc_list)
        cells.append({
            "line": line_name, "process": pid, "edsStep": eds,
            "highRisk": hr_c, "warning": wn_c, "total": hr_c + wn_c, "bins": len(bins),
            "hrStepSeqs": len(hr_step_seqs),  # High Risk 발생 step_seq 수
            "hrEqpchs": len(cell_hr_eqcs),    # High Risk 발생 EQPCH 수
        })

    # 분석 그룹 = 알고리즘이 처리한 distinct (line_name, process, eds, step_seq, bin)
    # 이상 EQPCH = 그날 High Risk Chamber가 난 고유 EQC(EQPCH)
    analysis_groups: set = set()
    hr_eqc_set: set = set()
    for row in file_df.itertuples(index=False):
        for bin_name in (row.bins or []):
            analysis_groups.add((row.line_name, row.process_id, row.eds_step, row.step_seq, bin_name))
        for eqc in (row.hr_eqcs or []):
            hr_eqc_set.add(eqc)

    total_hr = int(file_df["hr"].sum())
    total_wn = int(file_df["wn"].sum())
    headline = {
        "groups": len(analysis_groups),  # 분석 그룹: line_name×process×eds×step_seq×bin
        "binNames": len({t[4] for t in analysis_groups}),
        "stepSeqs": int(file_df["step_seq"].nunique()),
        "lines": int(file_df["line_name"].nunique()),
        "processes": int(file_df["process_id"].nunique()),
        "edsSteps": int(file_df["eds_step"].nunique()),
        "ppids": int(file_df["ppid"].nunique()),
        "lots": 0,
        "totalRows": int(file_df["row_cnt"].sum()),
        "anomalies": total_hr + total_wn,
        "highRisk": total_hr,
        "warning": total_wn,
        "anomalyGroups": 0,
        "anomalyEqpchs": 0,
        "highRiskEqpchs": len(hr_eqc_set),  # 그날 High Risk 난 distinct EQPCH
        "warningEqpchs": 0,
    }
    matrix = {
        "lines": sorted(file_df["line_name"].unique().tolist()),
        "processes": sorted(file_df["process_id"].unique().tolist()),
        "edsSteps": sorted(file_df["eds_step"].unique().tolist()),
        "cells": cells,
    }
    return {"dates": sorted(dates), "headline": headline, "matrix": matrix}


def get_daily_summary(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """선택한 날짜 전체의 line_name×process×eds_step 기준 이상감지 요약을 반환합니다.

    Chart 조회와 달리 line/process/eds 선택과 무관하게 해당 날짜의 모든 그룹을 집계합니다.
    """
    dates = [str(d) for d in (selection.get("dates") or []) if d]
    if not dates:
        return _empty_daily_summary()

    rules = _get_exclusion_rules(user=user)
    rules_hash = str(hash(tuple(sorted(str(r) for r in rules))))
    cache_key = f"{rules_hash}:{json.dumps(sorted(dates))}"
    cached = _daily_summary_cache.get(cache_key)
    if cached is not None:
        return cached

    # 제외필터가 있으면 행 단위 정확 필터가 필요 → 전량 Parquet.
    # 없으면 file_index의 상태 카운트로 집계(초고속). 카운트 NULL(구 데이터) 파일만 Parquet 폴백.
    file_frames: list[pd.DataFrame] = []
    try:
        if rules:
            paths: list[Path] = []
            for date in dates:
                paths.extend(selectors.iter_date_files(date))
            frame = _daily_file_df_from_parquet(paths, rules)
            if not frame.empty:
                file_frames.append(frame)
        else:
            index_rows_by_date = [(date, selectors.query_date_file_index(date)) for date in dates]
            all_rows = [r for _, rows in index_rows_by_date for r in rows]
            # 인덱스로 완전 집계하려면 카운트 + high_risk_eqcs(이상 EQPCH용) 컬럼이 모두 있어야 함
            index_full = bool(all_rows) and ("high_risk_eqcs" in all_rows[0])
            if index_full:
                root = selectors.get_data_root()
                uncounted_paths: list[Path] = []
                for date, rows in index_rows_by_date:
                    counted_df, uncounted = _daily_file_df_from_index(rows, date, root)
                    if not counted_df.empty:
                        file_frames.append(counted_df)
                    uncounted_paths.extend(uncounted)
                if uncounted_paths:  # 카운트 NULL 파일만 Parquet 폴백
                    frame = _daily_file_df_from_parquet(uncounted_paths, None)
                    if not frame.empty:
                        file_frames.append(frame)
            else:
                # 인덱스가 카운트/EQC를 완전히 못 주면 전량 Parquet(모든 지표 정확)
                paths = []
                for date in dates:
                    paths.extend(selectors.iter_date_files(date))
                frame = _daily_file_df_from_parquet(paths, None)
                if not frame.empty:
                    file_frames.append(frame)
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc

    file_df = pd.concat(file_frames, ignore_index=True) if file_frames else pd.DataFrame()
    result = _aggregate_daily(file_df, dates)
    _daily_summary_cache.set(cache_key, result)
    return result


def get_data(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """선택 조건과 필터에 맞는 차트 행 데이터를 반환합니다."""
    _empty = {"cols": [], "colData": []}

    if not _has_required_selection(selection):
        return _empty

    selected_eqcs = set(selection.get("selectedEqcs") or [])
    selected_step_bins = set(selection.get("selectedStepBins") or [])
    selected_ppid_bins = set(selection.get("selectedPpidBins") or [])
    selected_steps = set(selection.get("selectedSteps") or [])
    checked_eds_steps = set(selection.get("checkedEdsSteps") or [])
    checked_ppids = set(selection.get("checkedPpids") or [])
    checked_bins = set(selection.get("checkedBins") or [])

    if not selected_eqcs and not selected_step_bins and not selected_ppid_bins and not selected_steps:
        return _empty

    # ── 파일 타겟팅 ──────────────────────────────────────────────────────────
    # eds_step + step_seq + ppid 가 단일 값이면 해당 파일만 정확히 읽음
    # (전체 디렉토리 읽기 대비 최대 10~20x 적은 I/O)
    try:
        if len(checked_eds_steps) == 1 and len(selected_steps) == 1 and len(checked_ppids) == 1:
            files = list(selectors.iter_filter_candidate_files(
                dates=selection.get("dates") or [],
                line_ids=selection.get("lineIds") or [],
                process_ids=selection.get("processIds") or [],
                eds_step=next(iter(checked_eds_steps)),
                step_seq=next(iter(selected_steps)),
                ppid=next(iter(checked_ppids)),
            ))
        else:
            files = list(selectors.iter_data_files(selection))
    except FileNotFoundError as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise L3SpiderServiceError(str(exc), status_code=400) from exc

    files = _filter_files_by_line_names(files, selection)

    # ── 병렬 읽기 ────────────────────────────────────────────────────────────
    raw_frames = _parallel_read(files, functools.partial(_read_chart_file, columns=CHART_COLUMNS))

    frames = []
    for frame in raw_frames:
        if checked_eds_steps and "eds_step" in frame.columns:
            frame = frame[frame["eds_step"].isin(checked_eds_steps)]
        if checked_ppids and "ppid" in frame.columns:
            frame = frame[frame["ppid"].isin(checked_ppids)]
        if checked_bins and "bin_name" in frame.columns:
            frame = frame[frame["bin_name"].isin(checked_bins)]
        if selected_eqcs and "eqc" in frame.columns:
            frame = frame[frame["eqc"].isin(selected_eqcs)]
        if selected_steps and "step_seq" in frame.columns:
            frame = frame[frame["step_seq"].isin(selected_steps)]
        if selected_step_bins and {"step_seq", "bin_name"}.issubset(frame.columns):
            step_bin = frame["step_seq"].astype(str) + "|||" + frame["bin_name"].astype(str)
            frame = frame[step_bin.isin(selected_step_bins)]
        if selected_ppid_bins and {"step_seq", "ppid", "bin_name"}.issubset(frame.columns):
            ppid_bin = (
                frame["step_seq"].astype(str)
                + "|||"
                + frame["ppid"].astype(str)
                + "|||"
                + frame["bin_name"].astype(str)
            )
            frame = frame[ppid_bin.isin(selected_ppid_bins)]
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return _empty

    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    merged = _apply_exclusion_filters(merged, user=user)

    if merged.empty:
        return _empty

    if selected_eqcs:
        merged = _sample_chart_points(merged, ["step_seq", "bin_name"])
    elif checked_bins or selected_step_bins or selected_ppid_bins:
        merged = _sample_chart_points(merged, ["eqc"])

    if "comment" not in merged.columns:
        merged["comment"] = None

    for column in ["tkin_time", "tkout_time"]:
        if column in merged.columns:
            try:
                merged[column] = merged[column].dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                merged[column] = merged[column].astype(str)

    # ── 컬럼 기반 직렬화 (JSON 크기 ~60% 절감 + orjson 인코딩) ───────────────
    return _dataframe_to_columnar(merged)


def get_filter_candidates(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """PPID 선택 경로(date/line/process/eds_step/step_seq#ppid#*)에서 High Risk EQPCH·Bin 후보를 반환합니다."""
    dates = selection.get("dates") or []
    line_ids = selection.get("lineIds") or []
    process_ids = selection.get("processIds") or []
    eds_step = selection.get("edsStep", "")
    step_seq = selection.get("stepSeq", "")
    ppid = selection.get("ppid", "")

    if not all([dates, line_ids, process_ids, eds_step, step_seq, ppid]):
        return {"eqcHighRiskBins": {}}

    try:
        files = list(selectors.iter_filter_candidate_files(dates, line_ids, process_ids, eds_step, step_seq, ppid))
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc

    files = _filter_files_by_line_names(files, selection)

    def _read_candidate_file(path: Path) -> pd.DataFrame | None:
        try:
            frame = selectors.read_parquet_columns(path, ["eqc", "bin_name", "display_status"])
            frame = _normalize_display_status(frame)
            frame = _add_path_context(frame, path)
            return frame
        except Exception as exc:
            print(f"[WARN] L3 Spider filter-candidates read failed: {path}: {exc}")
            return None

    frames = _parallel_read(files, _read_candidate_file)
    if not frames:
        return {"eqcHighRiskBins": {}}

    merged = pd.concat(frames, ignore_index=True)
    merged = _apply_exclusion_filters(merged, user=user)

    eqc_high_risk_bins: dict[str, list[str]] = {}
    if {"eqc", "bin_name", "display_status"}.issubset(merged.columns):
        high_risk_mask = merged["display_status"] == "High Risk Chamber"
        pairs = (
            merged.loc[high_risk_mask, ["eqc", "bin_name"]]
            .drop_duplicates()
            .sort_values(["eqc", "bin_name"])
        )
        eqc_high_risk_bins = {
            str(eqc): sorted(group["bin_name"].dropna().astype(str).tolist())
            for eqc, group in pairs.groupby("eqc", sort=True)
        }

    return {"eqcHighRiskBins": eqc_high_risk_bins}
