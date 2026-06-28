# =============================================================================
# 모듈: PM SPIDER 파일 셀렉터
# 주요 함수: iter_raw_files, iter_score_files, iter_decomp_files, collect_partition_options, read_parquet
# 주요 가정: data와 result는 PM_COMPARISON_DATA_ROOT 바로 아래에 위치합니다.
# =============================================================================
from __future__ import annotations

from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

from django.conf import settings

import pandas as pd
import pyarrow.parquet as pq

RAW_DIR_NAME = "data"
SCORE_DIR_NAME = "result"
SCORE_DATA_DIR_NAME = "score_data"
DECOMP_DATA_DIR_NAME = "decomp_data"

RAW_PARTITION_KEYS = [
    "line_id",
    "eqp_id",
    "fdc_bin",
    "dt",
    "type",
    "ppid",
    "recipe_id",
    "data_source",
    "trace_param_name",
]

RAW_OPTION_DEPENDENCIES = {
    "line_id": [],
    "eqp_id": ["line_id"],
    "fdc_bin": ["line_id", "eqp_id"],
    "dt": ["line_id", "eqp_id", "fdc_bin"],
    "type": ["line_id", "eqp_id", "fdc_bin", "dt"],
    "ppid": ["line_id", "eqp_id", "fdc_bin", "dt", "type"],
    "recipe_id": ["line_id", "eqp_id", "fdc_bin", "dt", "type", "ppid"],
    "data_source": ["line_id", "eqp_id", "fdc_bin", "dt", "type", "ppid", "recipe_id"],
    "trace_param_name": ["line_id", "eqp_id", "fdc_bin", "dt", "type", "ppid", "recipe_id", "data_source"],
}

SCORE_PARTITION_KEYS = [
    "line_id",
    "eqp_id",
    "chamber_id",
    "type",
    "data_type",
]

SCORE_OPTION_DEPENDENCIES = {
    "line_id": [],
    "eqp_id": ["line_id"],
    "chamber_id": ["line_id", "eqp_id"],
    "type": ["line_id", "eqp_id", "chamber_id"],
    "data_type": ["line_id", "eqp_id", "chamber_id", "type"],
}

# decomp_data: shape.parquet / jitter.parquet (DASHBOARD_SPEC §2)
DECOMP_PARTITION_KEYS = [
    "line_id",
    "eqp_id",
    "chamber_id",
    "type",
    "comp_dt",
    "param",
    "ch_step",
]

PARTITION_KEYS = sorted(set([*RAW_PARTITION_KEYS, *SCORE_PARTITION_KEYS, *DECOMP_PARTITION_KEYS]))

REQUEST_TO_RAW_PARTITION = {
    "lineId": "line_id",
    "eqpId": "eqp_id",
    "fdcBin": "fdc_bin",
    "type": "type",
    "ppid": "ppid",
    "recipeId": "recipe_id",
}

REQUEST_TO_SCORE_PARTITION = {
    "lineId": "line_id",
    "eqpId": "eqp_id",
    "chamberId": "chamber_id",
    "type": "type",
}

REQUEST_TO_DECOMP_PARTITION = {
    "lineId": "line_id",
    "eqpId": "eqp_id",
    "chamberId": "chamber_id",
    "type": "type",
}


def get_data_root() -> Path:
    """PM SPIDER 데이터 루트 경로를 반환합니다."""

    return Path(settings.PM_COMPARISON_DATA_ROOT).expanduser().resolve()


def ensure_data_root() -> Path:
    """데이터 루트가 조회 가능한 디렉터리인지 확인합니다."""

    root = get_data_root()
    if not root.exists():
        raise FileNotFoundError(f"PM SPIDER 데이터 경로를 찾을 수 없습니다: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"PM SPIDER 데이터 경로가 폴더가 아닙니다: {root}")
    return root


def ensure_dataset_root(dataset_name: str) -> Path:
    """data 또는 result 데이터셋 루트를 반환합니다."""

    root = ensure_data_root() / dataset_name
    if not root.exists():
        raise FileNotFoundError(f"PM SPIDER {dataset_name} 경로를 찾을 수 없습니다: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"PM SPIDER {dataset_name} 경로가 폴더가 아닙니다: {root}")
    return root


def _existing_child_root(parent: Path, child_name: str) -> Path | None:
    """부모 디렉터리 아래 선택적 데이터셋 루트를 반환합니다."""

    root = parent / child_name
    if root.exists() and root.is_dir():
        return root
    return None


def _is_ignored_path(path: Path) -> bool:
    """Jupyter checkpoint 등 탐색 제외 경로인지 확인합니다."""

    return ".ipynb_checkpoints" in path.parts


def parse_partition_values(path: Path) -> dict[str, str]:
    """경로에서 key=value partition 값을 추출합니다."""

    values: dict[str, str] = {}
    for part in path.parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key in PARTITION_KEYS and value:
            values[key] = value
    return values


def _safe_relative_file(path: Path, root: Path) -> Path | None:
    """루트 내부 일반 파일만 반환합니다."""

    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    if _is_ignored_path(resolved):
        return None
    if not resolved.is_file():
        return None
    return resolved


def _segment(key: str, value: str | None) -> str:
    """partition glob segment를 생성합니다."""

    if value:
        return f"{key}={value}"
    return f"{key}=*"


def _partition_filters(selection: dict[str, object], mapping: dict[str, str]) -> dict[str, str | None]:
    """요청 필드를 partition key 기준 필터로 변환합니다."""

    filters: dict[str, str | None] = {}
    for request_key, partition_key in mapping.items():
        raw_value = selection.get(request_key)
        filters[partition_key] = str(raw_value) if raw_value else None
    return filters


def _iter_partition_files(
    root: Path,
    partition_keys: Sequence[str],
    filters: dict[str, str | None],
    *,
    max_files: int,
) -> Iterable[Path]:
    """partition key 순서와 필터에 맞는 Parquet 후보 파일을 순회합니다."""

    partition_pattern = "/".join(_segment(key, filters.get(key)) for key in partition_keys)
    leaf_patterns = ["*.parquet", "*/*.parquet", "*/*/*.parquet"]
    seen: set[Path] = set()
    for leaf_pattern in leaf_patterns:
        for path in root.glob(f"{partition_pattern}/{leaf_pattern}"):
            safe_path = _safe_relative_file(path, root)
            if safe_path is None or safe_path in seen:
                continue
            seen.add(safe_path)
            yield safe_path
            if len(seen) >= max_files:
                return


def _plain_segment(value: str | None) -> str:
    """plain layout glob segment를 생성합니다."""

    return value or "*"


def _plain_dt_segments(value: str | None) -> list[str]:
    """plain layout dt 폴더 후보 glob segment를 생성합니다."""

    if not value:
        return ["*"]
    segments = [value]
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        segments.extend([f"{value} *", f"{value}T*"])
    return list(dict.fromkeys(segments))


def _iter_plain_raw_files(
    root: Path,
    filters: dict[str, str | None],
    *,
    data_source: str,
    dt_candidates: Sequence[str | None],
    trace_candidates: Sequence[str | None],
    max_files: int,
) -> Iterable[Path]:
    """BASE_DATA/{LINE_ID}/{EQP_ID}/{CHAMBER_ID}/... plain layout 파일을 순회합니다."""

    line_id = _plain_segment(filters.get("line_id"))
    eqp_id = _plain_segment(filters.get("eqp_id"))
    chamber_id = _plain_segment(filters.get("fdc_bin"))
    type_segment = _segment("type", filters.get("type"))
    ppid_segment = _segment("ppid", filters.get("ppid"))
    recipe_segment = _segment("recipe_id", filters.get("recipe_id"))
    seen: set[Path] = set()

    source_dir = "trace" if data_source == "trace" else "oes" if data_source.startswith("oes") else data_source
    for dt_value in dt_candidates:
        for dt_segment in _plain_dt_segments(dt_value):
            if source_dir == "trace":
                for trace_value in trace_candidates:
                    param_segment = _segment("trace_param_name", trace_value)
                    pattern = (
                        f"{line_id}/{eqp_id}/{chamber_id}/{dt_segment}/trace/"
                        f"{type_segment}/{ppid_segment}/{recipe_segment}/priority=*/{param_segment}"
                    )
                    leaf_patterns = ["*.parquet", "*/*.parquet", "*/*/*.parquet", "*/*/*/*.parquet"]
                    for leaf_pattern in leaf_patterns:
                        for path in root.glob(f"{pattern}/{leaf_pattern}"):
                            safe_path = _safe_relative_file(path, root)
                            if safe_path is None or safe_path in seen:
                                continue
                            seen.add(safe_path)
                            yield safe_path
                            if len(seen) >= max_files:
                                return
                continue

            if source_dir == "oes":
                pattern = (
                    f"{line_id}/{eqp_id}/{chamber_id}/{dt_segment}/oes/"
                    f"{_plain_segment(filters.get('type'))}/*/"
                    f"{_plain_segment(filters.get('ppid'))}/{_plain_segment(filters.get('recipe_id'))}"
                )
                leaf_patterns = ["*/*/*.parquet", "*/*/*/*.parquet"]
                for leaf_pattern in leaf_patterns:
                    for path in root.glob(f"{pattern}/{leaf_pattern}"):
                        safe_path = _safe_relative_file(path, root)
                        if safe_path is None or safe_path in seen:
                            continue
                        seen.add(safe_path)
                        yield safe_path
                        if len(seen) >= max_files:
                            return


def iter_raw_files(
    selection: dict[str, object],
    *,
    data_source: str,
    trace_param_names: Sequence[str] | None = None,
) -> Iterable[Path]:
    """data 아래에서 요청 조건에 맞는 Parquet 후보 파일을 순회합니다."""

    try:
        root = ensure_dataset_root(RAW_DIR_NAME)
    except (FileNotFoundError, NotADirectoryError):
        return
    filters = _partition_filters(selection, REQUEST_TO_RAW_PARTITION)
    filters["data_source"] = data_source

    dt_values = [str(value) for value in selection.get("dtValues", []) if value]
    trace_values = [str(value) for value in trace_param_names or [] if value]
    dt_candidates = dt_values or [None]
    trace_candidates = trace_values or [None]
    max_files = int(getattr(settings, "PM_COMPARISON_MAX_FILES", 400))
    seen: set[Path] = set()

    for dt_value in dt_candidates:
        filters["dt"] = dt_value
        for trace_value in trace_candidates:
            filters["trace_param_name"] = trace_value
            for path in _iter_partition_files(root, RAW_PARTITION_KEYS, filters, max_files=max_files):
                if path in seen:
                    continue
                seen.add(path)
                yield path
                if len(seen) >= max_files:
                    return

    for path in _iter_plain_raw_files(
        root,
        filters,
        data_source=data_source,
        dt_candidates=dt_candidates,
        trace_candidates=trace_candidates,
        max_files=max_files,
    ):
        if path in seen:
            continue
        seen.add(path)
        yield path
        if len(seen) >= max_files:
            return


def iter_score_files(selection: dict[str, object], *, data_type: str) -> Iterable[Path]:
    """result 아래에서 요청 조건에 맞는 Parquet 후보 파일을 순회합니다."""

    result_root = ensure_dataset_root(SCORE_DIR_NAME)
    score_data_root = _existing_child_root(result_root, SCORE_DATA_DIR_NAME)
    roots = [root for root in [score_data_root, result_root] if root is not None]
    filters = _partition_filters(selection, REQUEST_TO_SCORE_PARTITION)
    # fdcBin과 chamber_id는 동일하므로 chamberId 미지정 시 fdcBin으로 대체합니다.
    inferred_chamber_id = False
    if not filters.get("chamber_id"):
        fdc_bin = selection.get("fdcBin")
        if fdc_bin:
            filters["chamber_id"] = str(fdc_bin)
            inferred_chamber_id = True
    filters["data_type"] = data_type
    max_files = int(getattr(settings, "PM_COMPARISON_MAX_FILES", 400))
    seen: set[Path] = set()
    key_variants = [SCORE_PARTITION_KEYS]
    if not filters.get("chamber_id") or inferred_chamber_id:
        key_variants.append([key for key in SCORE_PARTITION_KEYS if key != "chamber_id"])
    for root in roots:
        for partition_keys in key_variants:
            for path in _iter_partition_files(root, partition_keys, filters, max_files=max_files):
                if path in seen:
                    continue
                seen.add(path)
                yield path
                if len(seen) >= max_files:
                    return


def iter_decomp_files(
    selection: dict[str, object],
    *,
    comp_dt: str | None = None,
    param_names: Sequence[str] | None = None,
    file_name: str = "shape.parquet",
) -> Iterable[Path]:
    """decomp_data 아래에서 shape.parquet / jitter.parquet 파일을 순회합니다.

    DASHBOARD_SPEC §2 경로:
      decomp_data/line_id={}/eqp_id={}/chamber_id={}/type={}/comp_dt={}/param={}/ch_step={}/{file_name}
    """

    try:
        result_root = ensure_dataset_root(SCORE_DIR_NAME)
    except (FileNotFoundError, NotADirectoryError):
        return
    root = _existing_child_root(result_root, DECOMP_DATA_DIR_NAME)
    if root is None:
        return

    filters = _partition_filters(selection, REQUEST_TO_DECOMP_PARTITION)
    filters["comp_dt"] = comp_dt or None
    max_files = int(getattr(settings, "PM_COMPARISON_MAX_FILES", 400))
    seen: set[Path] = set()

    param_values = [str(p) for p in (param_names or []) if p]
    param_candidates = param_values or [None]

    for param in param_candidates:
        filters["param"] = param
        for path in _iter_partition_files(root, DECOMP_PARTITION_KEYS, filters, max_files=max_files):
            if path in seen:
                continue
            if path.name != file_name:
                continue
            seen.add(path)
            yield path
            if len(seen) >= max_files:
                return


def _scan_partition_dirs(root: Path, keys: list[str], max_dirs: int) -> dict[str, set[str]]:
    """디렉터리 트리에서 key=value partition 값을 수집합니다."""

    options: dict[str, set[str]] = {key: set() for key in keys}
    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    visited = 0
    while queue and visited < max_dirs:
        current, depth = queue.popleft()
        if depth >= len(keys):
            continue
        try:
            children = sorted(path for path in current.iterdir() if path.is_dir() and not _is_ignored_path(path))
        except OSError:
            continue
        visited += len(children)
        for child in children:
            partition = parse_partition_values(child)
            for key, value in partition.items():
                if key in options:
                    options[key].add(value)
            queue.append((child, depth + 1))
            if visited >= max_dirs:
                break
    return options


def date_partition_candidates(value: object) -> list[str]:
    """날짜 선택값과 raw partition 폴더명 후보를 함께 반환합니다."""

    if not value:
        return []
    text = str(value).strip()
    if not text:
        return []
    candidates = [text]
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        candidates.append(text[:10])
        candidates.append(text[:10].replace("-", ""))
    elif len(text) == 8 and text.isdigit():
        candidates.append(f"{text[:4]}-{text[4:6]}-{text[6:8]}")
    return list(dict.fromkeys(candidates))


def _matches_filter_value(key: str, value: str | None, expected_values: set[str]) -> bool:
    """선택 필터와 partition 값의 일치 여부를 확인합니다."""

    if value in expected_values:
        return True
    if key != "dt" or not value:
        return False
    for expected in expected_values:
        if len(expected) == 10 and expected[4] == "-" and expected[7] == "-":
            if value.startswith(f"{expected} ") or value.startswith(f"{expected}T"):
                return True
    return False


def _meta_filters(selection: dict[str, object] | None) -> dict[str, set[str]]:
    """메타 조회 선택값을 partition key 기준 필터로 변환합니다."""

    if not selection:
        return {}
    mapping = {
        "lineId": "line_id",
        "eqpId": "eqp_id",
        "fdcBin": "fdc_bin",
        "type": "type",
        "ppid": "ppid",
        "recipeId": "recipe_id",
        "traceDataSource": "data_source",
    }
    filters: dict[str, set[str]] = {}
    for request_key, partition_key in mapping.items():
        value = selection.get(request_key)
        if value:
            filters[partition_key] = {str(value)}
    dt_values = [*date_partition_candidates(selection.get("pmTimestamp"))]
    for value in selection.get("dtValues") or []:
        dt_values.extend(date_partition_candidates(value))
    if dt_values:
        filters["dt"] = set(dt_values)
    return filters


def _score_meta_filters(selection: dict[str, object] | None) -> dict[str, set[str]]:
    """메타 조회 선택값을 score partition key 기준 필터로 변환합니다."""

    if not selection:
        return {}
    filters = _meta_filters(selection)
    score_filters: dict[str, set[str]] = {}
    for raw_key, score_key in [("line_id", "line_id"), ("eqp_id", "eqp_id"), ("fdc_bin", "chamber_id"), ("type", "type")]:
        value = filters.get(raw_key)
        if value:
            score_filters[score_key] = value
    return score_filters


def _matches_dependencies(
    values: dict[str, str],
    filters: dict[str, set[str]],
    dependencies_by_key: dict[str, list[str]],
    key: str,
) -> bool:
    """옵션 key보다 상위 선택값이 path 값과 일치하는지 확인합니다."""

    for dependency in dependencies_by_key.get(key, []):
        expected = filters.get(dependency)
        if expected and not _matches_filter_value(dependency, values.get(dependency), expected):
            return False
    return True


def _should_descend_for_key(filters: dict[str, set[str]], key: str, value: str) -> bool:
    """선택된 partition 값과 일치할 때만 하위 단계로 내려갑니다."""

    expected = filters.get(key)
    if expected:
        return _matches_filter_value(key, value, expected)
    return bool(filters.get("fdc_bin") and key in {"dt", "type", "ppid", "recipe_id", "data_source"})


def _scan_hive_raw_dirs(root: Path, max_dirs: int, filters: dict[str, set[str]]) -> dict[str, set[str]]:
    """key=value raw layout에서 cascade 옵션을 수집합니다."""

    options: dict[str, set[str]] = {key: set() for key in RAW_PARTITION_KEYS}
    queue: deque[tuple[Path, int, dict[str, str]]] = deque([(root, 0, {})])
    visited = 0
    while queue and visited < max_dirs:
        current, depth, parent_values = queue.popleft()
        if depth >= len(RAW_PARTITION_KEYS):
            continue
        expected_key = RAW_PARTITION_KEYS[depth]
        try:
            children = sorted(path for path in current.iterdir() if path.is_dir() and not _is_ignored_path(path))
        except OSError:
            continue
        visited += len(children)
        for child in children:
            child_values = parse_partition_values(child)
            value = child_values.get(expected_key)
            if not value:
                continue
            partition = {**parent_values, expected_key: value}
            if _matches_dependencies(partition, filters, RAW_OPTION_DEPENDENCIES, expected_key):
                options[expected_key].add(value)
            if _should_descend_for_key(filters, expected_key, value):
                queue.append((child, depth + 1, partition))
            if visited >= max_dirs:
                break
    return options


def _scan_plain_raw_dirs(root: Path, max_dirs: int, filters: dict[str, set[str]]) -> dict[str, set[str]]:
    """plain raw layout에서 주요 선택값을 수집합니다."""

    options: dict[str, set[str]] = {key: set() for key in RAW_PARTITION_KEYS}
    visited = 0

    for line_dir in _candidate_plain_dirs(root, "line_id", filters):
        if "=" in line_dir.name:
            continue
        options["line_id"].add(line_dir.name)
        if not _should_descend_for_key(filters, "line_id", line_dir.name):
            continue
        visited += 1
        if visited >= max_dirs:
            break
        for eqp_dir in _candidate_plain_dirs(line_dir, "eqp_id", filters):
            options["eqp_id"].add(eqp_dir.name)
            if not _should_descend_for_key(filters, "eqp_id", eqp_dir.name):
                continue
            visited += 1
            if visited >= max_dirs:
                break
            for chamber_dir in _candidate_plain_dirs(eqp_dir, "fdc_bin", filters):
                options["fdc_bin"].add(chamber_dir.name)
                if not _should_descend_for_key(filters, "fdc_bin", chamber_dir.name):
                    continue
                visited += 1
                if visited >= max_dirs:
                    break
                for dt_dir in _candidate_plain_dirs(chamber_dir, "dt", filters):
                    options["dt"].add(dt_dir.name)
                    if not _should_descend_for_key(filters, "dt", dt_dir.name):
                        continue
                    visited += 1
                    if visited >= max_dirs:
                        break
                    for source_name in ("trace", "oes"):
                        source_root = dt_dir / source_name
                        if source_root.is_dir():
                            options["data_source"].add(source_name)
                    trace_root = dt_dir / "trace"
                    if trace_root.is_dir():
                        base_values = {
                            "line_id": line_dir.name,
                            "eqp_id": eqp_dir.name,
                            "fdc_bin": chamber_dir.name,
                            "dt": dt_dir.name,
                            "data_source": "trace",
                        }
                        visited = _scan_plain_trace_options(
                            trace_root,
                            max_dirs,
                            visited,
                            base_values,
                            filters,
                            options,
                        )
                        if visited >= max_dirs:
                            break
                if visited >= max_dirs:
                    break
            if visited >= max_dirs:
                break
        if visited >= max_dirs:
            break

    return options


def _child_dirs(path: Path) -> list[Path]:
    """직계 하위 디렉터리만 정렬해서 반환합니다."""

    try:
        return sorted(child for child in path.iterdir() if child.is_dir() and not _is_ignored_path(child))
    except OSError:
        return []


def _candidate_plain_dirs(parent: Path, key: str, filters: dict[str, set[str]]) -> list[Path]:
    """선택값이 있으면 해당 후보 디렉터리만 반환합니다."""

    expected_values = filters.get(key)
    if not expected_values:
        return _child_dirs(parent)

    candidates: list[Path] = []
    seen: set[Path] = set()
    for expected in expected_values:
        direct = parent / expected
        if direct.is_dir() and not _is_ignored_path(direct):
            candidates.append(direct)
            seen.add(direct)
        if key != "dt" or not (len(expected) == 10 and expected[4] == "-" and expected[7] == "-"):
            continue
        for child in _cached_dt_prefix_dirs(str(parent), _raw_records_signature(parent), expected):
            if child in seen or not child.is_dir() or _is_ignored_path(child):
                continue
            candidates.append(child)
            seen.add(child)
    return candidates


@lru_cache(maxsize=512)
def _cached_dt_prefix_dirs(parent_text: str, signature: int, date_prefix: str) -> tuple[Path, ...]:
    """날짜만 선택된 경우 매칭되는 dt 폴더 후보를 캐시합니다."""

    parent = Path(parent_text)
    try:
        children = parent.iterdir()
    except OSError:
        return tuple()
    return tuple(
        child
        for child in children
        if child.is_dir()
        and not _is_ignored_path(child)
        and (child.name.startswith(f"{date_prefix} ") or child.name.startswith(f"{date_prefix}T"))
    )


def _partition_dir_value(path: Path, key: str) -> str | None:
    """partition 디렉터리명에서 값을 읽고 plain 이름도 보조로 허용합니다."""

    value = parse_partition_values(path).get(key)
    if value:
        return value
    if "=" not in path.name:
        return path.name
    return None


def _add_plain_option(
    options: dict[str, set[str]],
    partition: dict[str, str],
    filters: dict[str, set[str]],
    key: str,
) -> None:
    """현재 partition이 dependency를 만족하면 옵션에 추가합니다."""

    value = partition.get(key)
    if value and _matches_dependencies(partition, filters, RAW_OPTION_DEPENDENCIES, key):
        options[key].add(value)


def _scan_plain_trace_options(
    trace_root: Path,
    max_dirs: int,
    visited: int,
    base_values: dict[str, str],
    filters: dict[str, set[str]],
    options: dict[str, set[str]],
) -> int:
    """plain trace layout을 필요한 계층까지만 순회합니다."""

    for type_dir in _child_dirs(trace_root):
        visited += 1
        type_value = _partition_dir_value(type_dir, "type")
        if not type_value:
            continue
        type_partition = {**base_values, "type": type_value}
        _add_plain_option(options, type_partition, filters, "type")
        if not _should_descend_for_key(filters, "type", type_value):
            if visited >= max_dirs:
                break
            continue

        for ppid_dir in _child_dirs(type_dir):
            visited += 1
            ppid_value = _partition_dir_value(ppid_dir, "ppid")
            if not ppid_value:
                continue
            ppid_partition = {**type_partition, "ppid": ppid_value}
            _add_plain_option(options, ppid_partition, filters, "ppid")
            if not _should_descend_for_key(filters, "ppid", ppid_value):
                if visited >= max_dirs:
                    break
                continue

            for recipe_dir in _child_dirs(ppid_dir):
                visited += 1
                recipe_value = _partition_dir_value(recipe_dir, "recipe_id")
                if not recipe_value:
                    continue
                recipe_partition = {**ppid_partition, "recipe_id": recipe_value}
                _add_plain_option(options, recipe_partition, filters, "recipe_id")
                if not _should_descend_for_key(filters, "recipe_id", recipe_value):
                    if visited >= max_dirs:
                        break
                    continue
                data_source_filters = filters.get("data_source")
                if not data_source_filters or not _matches_filter_value("data_source", "trace", data_source_filters):
                    continue

                for priority_dir in _child_dirs(recipe_dir):
                    visited += 1
                    for trace_param_dir in _child_dirs(priority_dir):
                        visited += 1
                        trace_param_value = _partition_dir_value(trace_param_dir, "trace_param_name")
                        if trace_param_value:
                            trace_param_partition = {
                                **recipe_partition,
                                "data_source": "trace",
                                "trace_param_name": trace_param_value,
                            }
                            _add_plain_option(options, trace_param_partition, filters, "trace_param_name")
                            if visited >= max_dirs:
                                break
                    if visited >= max_dirs:
                        break
                if visited >= max_dirs:
                    break
            if visited >= max_dirs:
                break
        if visited >= max_dirs:
            break
    return visited


def _scan_score_dirs(root: Path, max_dirs: int, filters: dict[str, set[str]]) -> dict[str, set[str]]:
    """score layout에서 cascade 옵션을 수집합니다."""

    options: dict[str, set[str]] = {key: set() for key in SCORE_PARTITION_KEYS}
    queue: deque[tuple[Path, int, dict[str, str]]] = deque([(root, 0, {})])
    visited = 0
    while queue and visited < max_dirs:
        current, depth, parent_values = queue.popleft()
        if depth >= len(SCORE_PARTITION_KEYS):
            continue
        expected_key = SCORE_PARTITION_KEYS[depth]
        try:
            children = sorted(path for path in current.iterdir() if path.is_dir() and not _is_ignored_path(path))
        except OSError:
            continue
        visited += len(children)
        for child in children:
            child_values = parse_partition_values(child)
            value = child_values.get(expected_key)
            if not value:
                continue
            partition = {**parent_values, expected_key: value}
            if _matches_dependencies(partition, filters, SCORE_OPTION_DEPENDENCIES, expected_key):
                options[expected_key].add(value)
            if _should_descend_for_key(filters, expected_key, value):
                queue.append((child, depth + 1, partition))
            if visited >= max_dirs:
                break
    return options


def _raw_records_signature(root: Path) -> int:
    """metadata 캐시 무효화를 위한 루트 mtime을 반환합니다."""

    try:
        return root.stat().st_mtime_ns
    except OSError:
        return 0


def _filters_cache_key(filters: dict[str, set[str]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """선택값별 metadata 캐시 key를 생성합니다."""

    return tuple((key, tuple(sorted(values))) for key, values in sorted(filters.items()))


def _filters_from_cache_key(cache_key: tuple[tuple[str, tuple[str, ...]], ...]) -> dict[str, set[str]]:
    """캐시 key를 scan 함수용 필터로 복원합니다."""

    return {key: set(values) for key, values in cache_key}


@lru_cache(maxsize=128)
def _cached_raw_options(
    root_text: str,
    max_dirs: int,
    signature: int,
    filters_key: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """현재 선택 범위에 필요한 metadata만 스캔하고 캐시합니다."""

    root = Path(root_text)
    filters = _filters_from_cache_key(filters_key)
    options = _scan_hive_raw_dirs(root, max_dirs, filters)
    plain_options = _scan_plain_raw_dirs(root, max_dirs, filters)
    for key, values in plain_options.items():
        options.setdefault(key, set()).update(values)
    return tuple((key, tuple(sorted(values))) for key, values in sorted(options.items()))


def _options_from_cache_value(cache_value: tuple[tuple[str, tuple[str, ...]], ...]) -> dict[str, set[str]]:
    """캐시된 metadata option tuple을 set dict로 복원합니다."""

    return {key: set(values) for key, values in cache_value}


def collect_partition_options(selection: dict[str, object] | None = None) -> dict[str, list[str]]:
    """data 아래 partition 값을 수집하고 없으면 result score partition 값으로 대체합니다."""

    max_dirs = int(getattr(settings, "PM_COMPARISON_MAX_META_DIRS", 5000))
    filters = _meta_filters(selection)
    try:
        raw_root = ensure_dataset_root(RAW_DIR_NAME)
        cache_value = _cached_raw_options(
            str(raw_root),
            max_dirs,
            _raw_records_signature(raw_root),
            _filters_cache_key(filters),
        )
        options = _options_from_cache_value(cache_value)
    except (FileNotFoundError, NotADirectoryError):
        # data가 없으면 result/score_data 또는 result partition 값으로 대체합니다.
        options = {key: set() for key in RAW_PARTITION_KEYS}
        try:
            result_root = ensure_dataset_root(SCORE_DIR_NAME)
            score_root = _existing_child_root(result_root, SCORE_DATA_DIR_NAME) or result_root
            score_opts = _scan_score_dirs(score_root, max_dirs, _score_meta_filters(selection))
            # score chamber_id → fdc_bin 으로 노출
            options["line_id"].update(score_opts.get("line_id", set()))
            options["eqp_id"].update(score_opts.get("eqp_id", set()))
            options["fdc_bin"].update(score_opts.get("chamber_id", set()))
        except (FileNotFoundError, NotADirectoryError):
            pass

    return {key: sorted(values) for key, values in options.items()}


@lru_cache(maxsize=4096)
def _parquet_columns(path_text: str, mtime_ns: int, size: int) -> tuple[str, ...]:
    """Parquet schema에서 컬럼명만 빠르게 읽어 캐시합니다."""

    return tuple(pq.read_schema(path_text).names)


def parquet_columns(path: Path) -> tuple[str, ...]:
    """Parquet 파일의 컬럼명을 반환합니다."""

    stat = path.stat()
    return _parquet_columns(str(path), stat.st_mtime_ns, stat.st_size)


def read_parquet(
    path: Path,
    columns: Sequence[str] | None = None,
    *,
    filters: Sequence[tuple[str, str, Any]] | None = None,
) -> pd.DataFrame:
    """Parquet 파일을 읽고 요청 컬럼/filter가 실패하면 안전하게 fallback합니다."""

    if columns:
        try:
            return pd.read_parquet(path, engine="pyarrow", columns=list(columns), filters=filters)
        except Exception:
            try:
                frame = pd.read_parquet(path, engine="pyarrow", filters=filters)
            except Exception:
                frame = pd.read_parquet(path, engine="pyarrow")
            available = [column for column in columns if column in frame.columns]
            if available:
                return frame[available]
            return frame
    try:
        return pd.read_parquet(path, engine="pyarrow", filters=filters)
    except Exception:
        if filters:
            return pd.read_parquet(path, engine="pyarrow")
        raise
