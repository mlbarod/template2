# =============================================================================
# 모듈 설명: 라인 A용 Adaptive Card 템플릿 빌더를 제공합니다.
# - 주요 대상: TEMPLATE_KEY, build_card
# - 불변 조건: TEMPLATE_KEY는 "line_a"로 고정입니다.
# =============================================================================
"""라인 A 메신저 템플릿 정의 모음."""
from __future__ import annotations

from typing import Any

TEMPLATE_KEY = "line_a"


def build_card(*, context: dict[str, str], actions: list[dict[str, Any]]) -> dict[str, Any]:
    """라인 A용 Adaptive Card payload를 생성합니다.

    인자:
        context: 정규화된 컨텍스트 값.
        actions: OpenUrl 액션 목록.

    반환:
        Adaptive Card JSON dict.

    부작용:
        없음. 순수 변환입니다.
    """

    comment = context.get("comment_raw", "-")
    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": "Drone SOP Alert - Line A",
            "weight": "Bolder",
            "size": "Medium",
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "SOP ID", "value": context.get("sop_id", "-")},
                {"title": "Step", "value": context.get("main_step", "-")},
                {"title": "PPID", "value": context.get("ppid", "-")},
                {"title": "EQP", "value": context.get("eqp_cb", "-")},
                {"title": "Lot", "value": context.get("lot_id", "-")},
                {"title": "User", "value": context.get("user_sdwt_prod", "-")},
                {"title": "Knox", "value": context.get("knoxid", "-")},
            ],
        },
    ]

    if comment != "-":
        body.extend(
            [
                {"type": "TextBlock", "text": "Comment", "weight": "Bolder", "spacing": "Medium"},
                {"type": "TextBlock", "text": comment, "wrap": True},
            ]
        )

    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
        "actions": actions,
    }


__all__ = ["TEMPLATE_KEY", "build_card"]
