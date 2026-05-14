# =============================================================================
# 모듈: Drone SOP POP3 defect_json 파서
# 주요 기능: defect_json/defect_png_url 메타데이터 병합 및 직렬화
# 주요 가정: POP3 수집 row 저장 형식은 기존 defect_url JSON 문자열을 유지합니다.
# =============================================================================
"""Drone SOP defect_json 파싱 헬퍼 모듈입니다."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .utils import sanitize_url

_DEFECT_JSON_OBJECT_PATTERN = re.compile(r"\{.*?\}", re.DOTALL)
_DEFECT_JSON_META_FIELDS = {
    "line_id": "LINE_ID",
    "proc_id": "PROC_ID",
    "root_lot_id": "ROOT_LOT_ID",
    "lot_id": "LOT_ID",
    "step_seq": "STEP_SEQ",
    "step_desc": "STEP_DESC",
}


def _extract_json_string_field(*, raw: str, key: str) -> str | None:
    """JSON 유사 문자열에서 특정 문자열 필드를 추출합니다."""

    pattern = re.compile(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', re.IGNORECASE)
    matched = pattern.search(raw)
    if not matched:
        return None
    value = matched.group(1).strip()
    return value or None


def _strip_wrapping_quotes(value: Any) -> str:
    """태그 텍스트를 감싼 따옴표를 제거합니다."""

    cleaned = str(value or "").strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1].strip()
    return cleaned


def _is_no_data_defect_map_url(value: Any) -> bool:
    """Defect map URL의 No data placeholder 여부를 판정합니다."""

    normalized = " ".join(unquote(str(value or "")).strip().strip("/").casefold().split())
    if normalized in {"no data", "nodata"}:
        return True
    for scheme in ("http://", "https://"):
        if normalized.startswith(scheme):
            host_like = normalized.removeprefix(scheme).strip().strip("/")
            return host_like in {"no data", "nodata"}
    return False


def _extract_url_query_value(*, url: str, key: str) -> str:
    """URL query string에서 단일 값을 추출합니다."""

    parsed = urlparse(url)
    values = parse_qs(parsed.query).get(key)
    if not values:
        return ""
    return str(values[0] or "").strip()


def _extract_defect_map_file(map_url: str) -> str:
    """Defect map URL에서 file query 값을 추출합니다."""

    return _extract_url_query_value(url=map_url, key="file")


def _extract_defect_selected_row(image_url: str) -> int | None:
    """Defect image URL에서 selected_row 값을 추출합니다."""

    raw = _extract_url_query_value(url=image_url, key="selected_row")
    try:
        selected_row = int(raw)
    except (TypeError, ValueError):
        return None
    return selected_row if selected_row >= 0 else None


def _parse_defect_png_rows_by_file(value: Any) -> dict[str, list[int]]:
    """콤마 구분 defect_png_url에서 file별 selected_row 목록을 추출합니다."""

    raw = unescape(_strip_wrapping_quotes(value))
    if not raw:
        return {}

    rows_by_file: dict[str, set[int]] = {}
    for chunk in raw.split(","):
        image_url = sanitize_url(chunk)
        if not image_url:
            continue
        map_file = _extract_defect_map_file(image_url)
        selected_row = _extract_defect_selected_row(image_url)
        if not map_file or selected_row is None:
            continue
        rows_by_file.setdefault(map_file, set()).add(selected_row)

    return {map_file: sorted(rows) for map_file, rows in rows_by_file.items()}


def _get_defect_entry_value(entry: dict[str, Any], key: str) -> str:
    """defect_json entry에서 대소문자 변형을 허용해 값을 조회합니다."""

    value = entry.get(key)
    if value is None:
        value = entry.get(key.lower())
    if value is None:
        value = entry.get(key.upper())
    return str(value or "").strip()


def _resolve_defect_label(*, normalized: dict[str, object], map_file: str, map_url: str) -> str:
    """Defect map 링크 라벨을 우선순위에 따라 결정합니다."""

    return str(
        normalized.get("step_seq")
        or normalized.get("step_desc")
        or normalized.get("lot_id")
        or map_file
        or map_url
    )


def _normalize_defect_json_entry(
    entry: Any,
    *,
    image_rows_by_file: dict[str, list[int]],
) -> dict[str, object] | None:
    """defect_json 단일 항목을 저장 가능한 map metadata로 정규화합니다."""

    if not isinstance(entry, dict):
        return None

    map_url = sanitize_url(_get_defect_entry_value(entry, "DEFECT_MAP_URL"))
    if not map_url or _is_no_data_defect_map_url(map_url):
        return None

    map_file = _extract_defect_map_file(map_url)
    normalized: dict[str, object] = {"map_url": map_url}
    for output_key, source_key in _DEFECT_JSON_META_FIELDS.items():
        value = _get_defect_entry_value(entry, source_key)
        if value:
            normalized[output_key] = value
    if map_file:
        normalized["map_file"] = map_file
    normalized["image_rows"] = image_rows_by_file.get(map_file, [])
    normalized["label"] = _resolve_defect_label(
        normalized=normalized,
        map_file=map_file,
        map_url=map_url,
    )
    return normalized


def _normalize_defect_json_chunk(
    *,
    raw: str,
    image_rows_by_file: dict[str, list[int]],
) -> dict[str, object] | None:
    """JSON 파싱이 실패한 defect_json object chunk를 정규화합니다."""

    map_url = sanitize_url(_extract_json_string_field(raw=raw, key="DEFECT_MAP_URL"))
    if not map_url or _is_no_data_defect_map_url(map_url):
        return None

    map_file = _extract_defect_map_file(map_url)
    normalized: dict[str, object] = {"map_url": map_url}
    for output_key, source_key in _DEFECT_JSON_META_FIELDS.items():
        value = _extract_json_string_field(raw=raw, key=source_key)
        if value:
            normalized[output_key] = value
    if map_file:
        normalized["map_file"] = map_file
    normalized["image_rows"] = image_rows_by_file.get(map_file, [])
    normalized["label"] = _resolve_defect_label(
        normalized=normalized,
        map_file=map_file,
        map_url=map_url,
    )
    return normalized


def _parse_defect_json_entries(*, defect_json: Any, defect_png_url: Any) -> list[dict[str, object]]:
    """defect_json payload와 defect_png_url row 정보를 병합합니다."""

    if defect_json is None:
        return []
    raw = unescape(str(defect_json)).strip()
    if not raw:
        return []
    image_rows_by_file = _parse_defect_png_rows_by_file(defect_png_url)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        return [
            normalized
            for entry in parsed
            if (
                normalized := _normalize_defect_json_entry(
                    entry,
                    image_rows_by_file=image_rows_by_file,
                )
            )
            is not None
        ]
    if isinstance(parsed, dict):
        normalized = _normalize_defect_json_entry(
            parsed,
            image_rows_by_file=image_rows_by_file,
        )
        return [normalized] if normalized else []

    entries: list[dict[str, object]] = []
    for chunk in _DEFECT_JSON_OBJECT_PATTERN.findall(raw):
        normalized = _normalize_defect_json_chunk(
            raw=chunk,
            image_rows_by_file=image_rows_by_file,
        )
        if normalized is not None:
            entries.append(normalized)
    return entries


def serialize_defect_json_entries(*, defect_json: Any, defect_png_url: Any) -> str | None:
    """defect_json 항목을 defect_url 컬럼 저장 문자열로 변환합니다."""

    entries = _parse_defect_json_entries(
        defect_json=defect_json,
        defect_png_url=defect_png_url,
    )
    if not entries:
        return None
    return json.dumps(entries, ensure_ascii=False, separators=(",", ":"))


__all__ = ["serialize_defect_json_entries"]
