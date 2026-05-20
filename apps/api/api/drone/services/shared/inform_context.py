# =============================================================================
# 모듈: Drone SOP 알림 컨텍스트 구성
# 주요 기능: Jira/메일/메신저 공용 템플릿 컨텍스트 생성
# 주요 가정: target_user_sdwt_prod가 있으면 해당 값을 우선 사용합니다.
# =============================================================================
"""Drone SOP 알림 컨텍스트 구성 유틸리티."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

_DEFECT_IMAGE_PATH = "/map/api/map-image/v3/defect-map"
_DEFECT_IMAGE_STATIC_QUERY = (
    ("profileid", "DEFAULT"),
    ("themeid", "DEFAULT"),
    ("width", "500"),
    ("height", "500"),
    ("site", "GH"),
    ("targetDB", "APP"),
    ("useCache", "true"),
    ("includeCoordinate", "false"),
)


def _build_eqp_cb(row: dict[str, Any]) -> str:
    """장비/챔버 식별 문자열을 생성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).

    반환:
        "eqp_id-chamber_ids" 형태의 문자열.

    부작용:
        없음. 순수 문자열 구성입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 장비/챔버 값 정규화
    # -------------------------------------------------------------------------
    eqp_id = (str(row.get("eqp_id") or "-") or "-").strip()
    chamber_ids = (str(row.get("chamber_ids") or "-") or "-").strip()
    return f"{eqp_id}-{chamber_ids}"


def _normalize_ctttm_urls(value: Any) -> list[dict[str, str]]:
    """CTTTM URL 입력을 통일된 리스트 형태로 정규화합니다.

    인자:
        value: 문자열 또는 dict 리스트 입력.

    반환:
        {"url","label"} 형태의 리스트.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 문자열 입력 처리
    # -------------------------------------------------------------------------
    urls: list[dict[str, str]] = []
    if isinstance(value, str):
        if value.strip():
            urls.append({"url": value.strip(), "label": value.strip()})
        return urls
    # -------------------------------------------------------------------------
    # 2) 리스트 입력 처리
    # -------------------------------------------------------------------------
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            link = item.get("url")
            if not link:
                continue
            label = item.get("eqp_id") or link
            urls.append({"url": str(link), "label": str(label)})
    return urls


def _normalize_defect_url_entry(*, entry: Any, lot_id: Any = None) -> dict[str, Any] | None:
    """Defect map 항목을 템플릿용 dict로 정규화합니다."""

    if not isinstance(entry, dict):
        return None
    map_url = str(entry.get("map_url") or "").strip()
    if not map_url:
        return None
    step_seq = str(entry.get("step_seq") or "").strip()
    label = str(step_seq or entry.get("label") or lot_id or map_url).strip()
    map_file = str(entry.get("map_file") or "").strip()
    normalized_image_rows = _normalize_defect_image_rows(entry)
    return {
        "map_url": map_url,
        "label": label or map_url,
        "step_seq": step_seq,
        "step_desc": str(entry.get("step_desc") or "").strip(),
        "map_file": map_file,
        "image_rows": normalized_image_rows,
        "image_urls": _build_defect_image_urls(
            map_url=map_url,
            map_file=map_file,
            image_rows=normalized_image_rows,
        ),
    }


def _normalize_defect_image_rows(entry: dict[str, Any]) -> list[Any]:
    """Defect JSON의 image_rows/images_rows 값을 호환 정규화합니다."""

    image_rows = entry.get("image_rows")
    if image_rows is None:
        image_rows = entry.get("images_rows")
    return image_rows if isinstance(image_rows, list) else []


def _build_defect_image_url(*, map_url: str, map_file: str, selected_row: int) -> str | None:
    """Defect map URL의 origin을 유지해 메일 본문용 image URL을 생성합니다."""

    parsed = urlparse(map_url)
    if not parsed.scheme or not parsed.netloc or not map_file:
        return None
    query = [
        ("file", map_file),
        ("selected_row", str(selected_row)),
        *_DEFECT_IMAGE_STATIC_QUERY,
    ]
    return urlunparse(
        (parsed.scheme, parsed.netloc, _DEFECT_IMAGE_PATH, "", urlencode(query), "")
    )


def _build_defect_image_urls(*, map_url: str, map_file: str, image_rows: list[Any]) -> list[str]:
    """Defect map metadata의 selected_row 목록을 이미지 URL 목록으로 변환합니다."""

    image_urls: list[str] = []
    for row in image_rows:
        try:
            selected_row = int(row)
        except (TypeError, ValueError):
            continue
        if selected_row < 0:
            continue
        image_url = _build_defect_image_url(
            map_url=map_url,
            map_file=map_file,
            selected_row=selected_row,
        )
        if image_url:
            image_urls.append(image_url)
    return image_urls


def _normalize_defect_urls(*, value: Any, lot_id: Any = None) -> list[dict[str, Any]]:
    """JSON 문자열을 Defect map 리스트로 정규화합니다."""

    if value is None:
        return []

    if isinstance(value, list):
        return [
            normalized
            for entry in value
            if (normalized := _normalize_defect_url_entry(entry=entry, lot_id=lot_id)) is not None
        ]

    raw = str(value).strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        return [
            normalized
            for entry in parsed
            if (normalized := _normalize_defect_url_entry(entry=entry, lot_id=lot_id)) is not None
        ]
    if isinstance(parsed, dict):
        normalized = _normalize_defect_url_entry(entry=parsed, lot_id=lot_id)
        return [normalized] if normalized else []

    return []


def build_inform_context(row: dict[str, Any]) -> dict[str, Any]:
    """알림 템플릿 렌더링에 사용할 컨텍스트를 구성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).

    반환:
        템플릿 컨텍스트 dict.

    부작용:
        없음. 순수 구성입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 주요 필드 정규화
    # -------------------------------------------------------------------------
    knoxid = str(row.get("knox_id") or row.get("knoxid") or "").strip()
    resolved_user_sdwt_prod = str(row.get("user_sdwt_prod") or "").strip()
    lot_id = row.get("lot_id")
    comment_raw = str(row.get("comment") or "").split("$@$", 1)[0]
    # -------------------------------------------------------------------------
    # 2) 템플릿 컨텍스트 구성
    # -------------------------------------------------------------------------
    return {
        "main_step": row.get("main_step"),
        "ppid": row.get("ppid"),
        "eqp_cb": _build_eqp_cb(row),
        "lot_id": lot_id,
        "knoxid": knoxid,
        "user_sdwt_prod": resolved_user_sdwt_prod,
        "ctttm_urls": _normalize_ctttm_urls(row.get("url")),
        "defect_urls": _normalize_defect_urls(
            value=row.get("defect_urls") if "defect_urls" in row else row.get("defect_url"),
            lot_id=lot_id,
        ),
        "comment_raw": comment_raw,
    }


__all__ = ["build_inform_context"]
