# =============================================================================
# 모듈: Drone 테이블 스키마/필터 유틸
# 주요 기능: 테이블 식별자 검증, 컬럼 조회, 라인/날짜 필터 조합
# 주요 가정: line-dashboard 테이블 조회/집계 서비스에서 공통으로 사용합니다.
# =============================================================================
"""Drone 테이블 스키마/필터 공통 유틸리티."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from api.common.services.db import run_query
from .table_filters import (
    DRONE_TARGET_MAPPING_TABLE_NAME,
    DRONE_TARGET_TABLE_NAME,
    LINE_FILTER_MODE_LEGACY,
    LINE_FILTER_MODE_SDWT,
    LINE_FILTER_MODE_TARGET_USER_SDWT,
    LINE_FILTER_MODE_USER_SDWT,
    build_date_range_filters,
    build_line_filters,
    ensure_date_bounds,
    find_column,
    normalize_date_only,
    normalize_line_filter_mode,
    normalize_line_id,
)

DEFAULT_TABLE = "drone_sop"
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")
DATE_COLUMN_CANDIDATES = [
    "created_at",
    "updated_at",
    "timestamp",
    "ts",
    "date",
]


@dataclass(frozen=True)
class TableSchema:
    """테이블 스키마 정보를 전달하는 데이터 클래스입니다."""

    name: str
    columns: list[str]
    timestamp_column: Optional[str] = None


def _sanitize_identifier_value(value: Any) -> Optional[str]:
    """식별자 후보 문자열을 안전한 패턴으로 검증합니다."""

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if SAFE_IDENTIFIER.match(candidate) else None


def sanitize_identifier(value: Any, fallback: Optional[str] = None) -> Optional[str]:
    """식별자 문자열을 정규화합니다."""

    normalized = _sanitize_identifier_value(value)
    if normalized:
        return normalized
    return _sanitize_identifier_value(fallback)


def list_table_columns(table_name: str) -> list[str]:
    """현재 스키마에서 주어진 테이블의 컬럼 목록을 조회합니다."""

    rows = run_query(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND LOWER(table_name) = %s
        ORDER BY ordinal_position
        """,
        [table_name.lower()],
    )

    column_names: list[str] = []
    for row in rows:
        value: Optional[str] = None
        for key in ("column_name", "COLUMN_NAME", "Field"):
            raw = row.get(key)
            if isinstance(raw, str) and raw.strip():
                value = raw.strip()
                break
        if value:
            column_names.append(value)
    return column_names


def _pick_base_timestamp_column(column_names: Sequence[str]) -> Optional[str]:
    """통계/필터 기준 타임스탬프 컬럼을 선택합니다."""

    for candidate in DATE_COLUMN_CANDIDATES:
        found = find_column(column_names, candidate)
        if found:
            return found
    return None


def resolve_table_schema(
    table_param: Any,
    *,
    default_table: Optional[str] = DEFAULT_TABLE,
    require_timestamp: bool = False,
) -> TableSchema:
    """테이블 이름을 검증하고 컬럼/타임스탬프 정보를 반환합니다."""

    table_name = sanitize_identifier(table_param, default_table)
    if not table_name:
        raise ValueError("Invalid table name")

    columns = list_table_columns(table_name)
    if not columns:
        raise LookupError(f'Table "{table_name}" has no columns')

    timestamp_column = None
    if require_timestamp:
        timestamp_column = _pick_base_timestamp_column(columns)
        if not timestamp_column:
            expected = ", ".join(DATE_COLUMN_CANDIDATES)
            raise LookupError(f'No timestamp-like column found in "{table_name}". Expected one of: {expected}.')

    return TableSchema(name=table_name, columns=columns, timestamp_column=timestamp_column)


__all__ = [
    "DATE_COLUMN_CANDIDATES",
    "DEFAULT_TABLE",
    "DRONE_TARGET_MAPPING_TABLE_NAME",
    "DRONE_TARGET_TABLE_NAME",
    "SAFE_IDENTIFIER",
    "TableSchema",
    "build_date_range_filters",
    "build_line_filters",
    "ensure_date_bounds",
    "find_column",
    "list_table_columns",
    "normalize_date_only",
    "normalize_line_filter_mode",
    "normalize_line_id",
    "resolve_table_schema",
    "sanitize_identifier",
    "LINE_FILTER_MODE_LEGACY",
    "LINE_FILTER_MODE_SDWT",
    "LINE_FILTER_MODE_USER_SDWT",
    "LINE_FILTER_MODE_TARGET_USER_SDWT",
]
