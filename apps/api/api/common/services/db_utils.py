# 공용 DB 유틸
"""데이터베이스 스키마 및 쿼리 관련 헬퍼 함수 모음."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from api.common import selectors as common_selectors
from .constants import (
    DATE_COLUMN_CANDIDATES,
    DEFAULT_TABLE,
    LINE_SDWT_TABLE_NAME,
)
from .normalization import sanitize_identifier


def find_column(column_names: Iterable[str], target: str) -> Optional[str]:
    """컬럼 목록에서 대소문자 무시 일치 항목을 찾습니다."""
    target_lower = target.lower()
    for name in column_names:
        if isinstance(name, str) and name.lower() == target_lower:
            return name
    return None


def pick_base_timestamp_column(column_names: Sequence[str]) -> Optional[str]:
    """통계/필터의 기준이 되는 타임스탬프 컬럼을 선택합니다."""
    for candidate in DATE_COLUMN_CANDIDATES:
        found = find_column(column_names, candidate)
        if found:
            return found
    return None


def build_line_filters(column_names: Sequence[str], line_id: Optional[str]) -> Dict[str, Any]:
    """lineId 기반 필터 SQL 조각을 생성합니다."""
    filters: List[str] = []
    params: List[Any] = []

    if not line_id:
        return {"filters": filters, "params": params}

    sdwt_col = find_column(column_names, "sdwt_prod")
    if sdwt_col:
        filters.append(
            "{col} IN ("
            "SELECT user_sdwt_prod FROM {table} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")".format(col=sdwt_col, table=LINE_SDWT_TABLE_NAME)
        )
        params.append(line_id)
        return {"filters": filters, "params": params}

    user_sdwt_col = find_column(column_names, "user_sdwt_prod")
    if user_sdwt_col:
        filters.append(
            "{col} IN ("
            "SELECT user_sdwt_prod FROM {table} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")".format(col=user_sdwt_col, table=LINE_SDWT_TABLE_NAME)
        )
        params.append(line_id)
        return {"filters": filters, "params": params}

    line_col = find_column(column_names, "line_id")
    if line_col:
        filters.append(f"{line_col} = %s")
        params.append(line_id)

    return {"filters": filters, "params": params}


@dataclass(frozen=True)
class TableSchema:
    """테이블 스키마 정보를 묶어 전달하는 데이터 클래스."""
    name: str
    columns: List[str]
    timestamp_column: Optional[str] = None


def resolve_table_schema(
    table_param: Any, *, default_table: Optional[str] = DEFAULT_TABLE, require_timestamp: bool = False
) -> TableSchema:
    """테이블 이름을 검증하고 컬럼/타임스탬프 컬럼 정보를 반환합니다."""
    table_name = sanitize_identifier(table_param, default_table)
    if not table_name:
        raise ValueError("Invalid table name")

    columns = common_selectors.list_table_columns(table_name)
    if not columns:
        raise LookupError(f'Table "{table_name}" has no columns')

    timestamp_column = None
    if require_timestamp:
        timestamp_column = pick_base_timestamp_column(columns)
        if not timestamp_column:
            expected = ", ".join(DATE_COLUMN_CANDIDATES)
            raise LookupError(f'No timestamp-like column found in "{table_name}". Expected one of: {expected}.')

    return TableSchema(name=table_name, columns=columns, timestamp_column=timestamp_column)


__all__ = [
    "find_column",
    "pick_base_timestamp_column",
    "build_line_filters",
    "TableSchema",
    "resolve_table_schema",
]
