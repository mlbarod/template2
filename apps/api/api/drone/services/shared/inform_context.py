# =============================================================================
# 모듈: Drone SOP 알림 컨텍스트 구성
# 주요 기능: Jira/메일/메신저 공용 템플릿 컨텍스트 생성
# 주요 가정: target_user_sdwt_prod가 있으면 해당 값을 우선 사용합니다.
# =============================================================================
"""Drone SOP 알림 컨텍스트 구성 유틸리티."""

from __future__ import annotations

from typing import Any


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
    resolved_user_sdwt_prod = (
        str(row.get("target_user_sdwt_prod") or row.get("resolved_user_sdwt_prod") or row.get("user_sdwt_prod") or "")
        .strip()
    )
    comment_raw = str(row.get("comment") or "").split("$@$", 1)[0]
    # -------------------------------------------------------------------------
    # 2) 템플릿 컨텍스트 구성
    # -------------------------------------------------------------------------
    return {
        "main_step": row.get("main_step"),
        "ppid": row.get("ppid"),
        "eqp_cb": _build_eqp_cb(row),
        "lot_id": row.get("lot_id"),
        "knoxid": knoxid,
        "user_sdwt_prod": resolved_user_sdwt_prod,
        "ctttm_urls": _normalize_ctttm_urls(row.get("url")),
        "defect_url": row.get("defect_url"),
        "comment_raw": comment_raw,
    }


__all__ = ["build_inform_context"]
