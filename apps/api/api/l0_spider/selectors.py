from __future__ import annotations

from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.db import connection

import pandas as pd

DEFAULT_HARD_SPEC_DATA_ROOT = Path("/appdata/erd_stats_commonality")
DEFAULT_PRIORITY_PATH = Path("/appdata/abnormal_trend/pic/priority/priority.parquet")
DEFAULT_UNIT_MODEL_PATH = Path("/appdata/abnormal_trend/pic/unit_model.parquet")
DEFAULT_HARD_LIMIT_PATH = Path("/appdata/abnormal_trend/pic/HARD_LIMIT.parquet")


def get_hard_spec_data_root() -> Path:
    """FDC 통계 root 경로를 반환합니다."""

    return Path(getattr(settings, "FDC_HARD_SPEC_DATA_ROOT", DEFAULT_HARD_SPEC_DATA_ROOT))


def get_priority_path() -> Path:
    """priority parquet 경로를 반환합니다."""

    return Path(getattr(settings, "FDC_HARD_SPEC_PRIORITY_PATH", DEFAULT_PRIORITY_PATH))


def get_unit_model_path() -> Path:
    """unit_model parquet 경로를 반환합니다."""

    return Path(getattr(settings, "FDC_HARD_SPEC_UNIT_MODEL_PATH", DEFAULT_UNIT_MODEL_PATH))


def get_hard_limit_path() -> Path:
    """HARD_LIMIT parquet 경로를 반환합니다."""

    return Path(getattr(settings, "FDC_HARD_SPEC_HARD_LIMIT_PATH", DEFAULT_HARD_LIMIT_PATH))


def list_child_names(path: Path) -> list[str]:
    """디렉터리 하위 이름을 정렬해 반환합니다."""

    if not path.exists() or not path.is_dir():
        return []
    return sorted(child.name for child in path.iterdir() if child.name != "-")


def read_parquet(path: Path | str, columns: Iterable[str] | None = None) -> pd.DataFrame:
    """Parquet 파일 또는 디렉터리를 DataFrame으로 읽습니다."""

    return pd.read_parquet(path, columns=list(columns) if columns else None, engine="pyarrow")


def fetch_fdc_models(*, step_seq_like: str, eqp_models: list[str]) -> list[str]:
    """edisn.step_eqp_info에서 FDC model 목록을 조회합니다."""

    if not step_seq_like or not eqp_models:
        return []

    placeholders = ", ".join(["%s"] * len(eqp_models))
    sql = f"""
        SELECT DISTINCT fdc_model
        FROM edisn.step_eqp_info
        WHERE step_seq LIKE %s
          AND eqp_model IN ({placeholders})
        ORDER BY fdc_model
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [step_seq_like, *eqp_models])
        return [row[0] for row in cursor.fetchall() if row and row[0]]
