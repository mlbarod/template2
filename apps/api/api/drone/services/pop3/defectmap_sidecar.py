# =============================================================================
# 모듈: Drone SOP defectmap 임시 사이드카
# 주요 기능: defect_png_url 존재 시 defectmap API POST 전송
# 주요 가정: 본 기능은 부가 기능이며 실패해도 메인 ingest 흐름은 계속됩니다.
# =============================================================================
"""Drone SOP defectmap 임시 연동 사이드카 모듈입니다."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests

from django.utils import timezone

from .config import DroneSopPop3Config

logger = logging.getLogger(__name__)
_KST_TZ = timezone.get_fixed_timezone(540)


def _sanitize_url(value: Any) -> str | None:
    """URL 문자열을 정리하고 비어 있으면 None을 반환합니다.

    인자:
        value: 원본 URL 값.

    반환:
        정리된 URL 문자열 또는 None.

    부작용:
        없음. 순수 정규화입니다.
    """

    if value is None:
        return None
    cleaned = str(value).replace('"', "").strip()
    return cleaned or None


def _format_scandate_at_kst(*, scanned_at: datetime) -> str:
    """파싱 시점을 KST 기준 `YYYY-MM-DD HH:MM:SS.mmm +0900`로 포맷합니다.

    인자:
        scanned_at: 파싱 시점 datetime.

    반환:
        KST 기준 scandate 문자열.

    부작용:
        없음. 순수 포맷팅입니다.
    """

    normalized = scanned_at
    if timezone.is_naive(normalized):
        normalized = timezone.make_aware(normalized, _KST_TZ)
    localized = timezone.localtime(normalized, _KST_TZ)
    milliseconds = localized.microsecond // 1000
    return f"{localized:%Y-%m-%d %H:%M:%S}.{milliseconds:03d} {localized:%z}"


def post_defect_png_sidecar_if_needed(
    *,
    row: dict[str, Any],
    config: DroneSopPop3Config,
    scanned_at: datetime,
    error_label: str,
) -> None:
    """임시 부가기능으로 defectmap POST를 수행합니다.

    인자:
        row: 파싱된 Drone SOP row dict.
        config: POP3 수집 설정.
        scanned_at: 파싱 시점 시각.
        error_label: 로그 식별용 라벨.

    반환:
        없음.

    부작용:
        조건 충족 시 외부 HTTP POST 요청이 발생합니다.
        요청 실패는 로그만 남기고 예외를 전파하지 않습니다.
    """

    # -------------------------------------------------------------------------
    # 1) 실행 조건 점검
    # -------------------------------------------------------------------------
    endpoint = str(config.defectmap_url or "").strip()
    if not endpoint:
        return

    defect_png_url = _sanitize_url(row.get("defect_png_url"))
    if not defect_png_url:
        return

    # -------------------------------------------------------------------------
    # 2) payload 구성
    # -------------------------------------------------------------------------
    payload = {
        "lot_id": str(row.get("lot_id") or "").strip(),
        "scandate": _format_scandate_at_kst(scanned_at=scanned_at),
        "step": str(row.get("metro_current_step") or "").strip(),
        "data": defect_png_url,
    }

    # -------------------------------------------------------------------------
    # 3) POST 전송 (실패 시 메인 흐름에 영향 없음)
    # -------------------------------------------------------------------------
    try:
        response = requests.post(endpoint, json=payload, timeout=config.timeout)
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to post defectmap payload for %s", error_label)


__all__ = ["post_defect_png_sidecar_if_needed"]
