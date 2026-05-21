# =============================================================================
# 모듈: L3 Spider 파일 셀렉터
# 주요 함수: get_data_root, iter_data_files, read_parquet_columns
# 주요 가정: 파일시스템 조회만 수행하며 쓰기 작업은 하지 않습니다.
# =============================================================================
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from django.conf import settings

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


def iter_data_files(selection: dict[str, object]) -> Iterable[Path]:
    """선택 조건에 해당하는 Parquet 파일 목록을 순회합니다."""

    root = ensure_data_root()
    root_resolved = root.resolve()
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
                            yield path


def iter_all_data_files() -> Iterable[Path]:
    """데이터 루트 아래의 모든 일반 파일을 순회합니다."""

    root = ensure_data_root()
    for path in root.glob("*/*/*/*/*"):
        if path.is_file():
            yield path


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
