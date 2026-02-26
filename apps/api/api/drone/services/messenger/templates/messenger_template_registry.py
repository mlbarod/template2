# =============================================================================
# 모듈 설명: Drone SOP 메신저 템플릿 정의를 등록합니다.
# - 주요 대상: CARD_TEMPLATE_BUILDERS
# - 불변 조건: 템플릿 키는 사전에 정의된 문자열이어야 함
# =============================================================================
"""Drone SOP 메신저 템플릿 레지스트리 모음."""
from __future__ import annotations

from .messenger_template_line_a import TEMPLATE_KEY as LINE_A_KEY, build_card as build_line_a_card
from .messenger_template_line_b import TEMPLATE_KEY as LINE_B_KEY, build_card as build_line_b_card

CARD_TEMPLATE_BUILDERS = {
    LINE_A_KEY: build_line_a_card,
    LINE_B_KEY: build_line_b_card,
}

__all__ = ["CARD_TEMPLATE_BUILDERS"]
