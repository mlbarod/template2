# =============================================================================
# 모듈: Drone SOP 메신저 템플릿 렌더링
# 주요 기능: 템플릿 입력용 컨텍스트/액션 생성
# 주요 가정: 템플릿별 전송은 messenger_api에서 처리합니다.
# =============================================================================
"""Drone SOP 메신저 템플릿 렌더러."""

from __future__ import annotations

from typing import Any

from ..shared.inform_context import build_inform_context


def _normalize_value(value: Any) -> str:
    """값을 문자열로 정규화합니다."""

    if value is None:
        return "-"
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed if trimmed else "-"
    trimmed = str(value).strip()
    return trimmed if trimmed else "-"


def _build_actions(context: dict[str, Any]) -> list[dict[str, Any]]:
    """메신저 템플릿용 OpenUrl 액션 목록을 구성합니다."""

    actions: list[dict[str, Any]] = []
    ctttm_urls = context.get("ctttm_urls")
    if isinstance(ctttm_urls, list):
        for item in ctttm_urls:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            label = str(item.get("label") or item.get("eqp_id") or "CTTTM").strip() or "CTTTM"
            actions.append({"type": "Action.OpenUrl", "title": label, "url": url})

    defect_url = str(context.get("defect_url") or "").strip()
    if defect_url:
        actions.append({"type": "Action.OpenUrl", "title": "Defect", "url": defect_url})

    return actions


def _build_context(row: dict[str, Any]) -> dict[str, Any]:
    """Drone SOP 메시지 컨텍스트를 구성합니다."""

    target_user_sdwt_prod = (
        str(row.get("target_user_sdwt_prod") or row.get("resolved_user_sdwt_prod") or row.get("user_sdwt_prod") or "")
        .strip()
    )
    context = build_inform_context(row)
    context.update(
        {
            "sop_id": row.get("id"),
            "sdwt_prod": row.get("sdwt_prod"),
            "user_sdwt_prod": target_user_sdwt_prod,
        }
    )
    return context


def build_drone_sop_messenger_template_inputs(*, row: dict[str, Any]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Drone SOP 메신저 템플릿 입력(정규화 컨텍스트/액션)을 구성합니다.

    인자:
        row: Drone SOP 행 dict.

    반환:
        (정규화 컨텍스트, OpenUrl 액션 목록) 튜플.

    부작용:
        없음. 순수 변환입니다.
    """

    context = _build_context(row)
    normalized_context = {
        "sop_id": _normalize_value(context.get("sop_id")),
        "sdwt_prod": _normalize_value(context.get("sdwt_prod")),
        "user_sdwt_prod": _normalize_value(context.get("user_sdwt_prod")),
        "main_step": _normalize_value(context.get("main_step")),
        "ppid": _normalize_value(context.get("ppid")),
        "eqp_cb": _normalize_value(context.get("eqp_cb")),
        "lot_id": _normalize_value(context.get("lot_id")),
        "knoxid": _normalize_value(context.get("knoxid")),
        "comment_raw": _normalize_value(context.get("comment_raw")),
    }
    actions = _build_actions(context)
    return normalized_context, actions


__all__ = ["build_drone_sop_messenger_template_inputs"]
