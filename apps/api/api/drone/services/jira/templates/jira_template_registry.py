# =============================================================================
# 모듈 설명: Drone SOP Jira 템플릿 정의를 등록합니다.
# - 주요 대상: TEMPLATE_SOURCES, SUMMARY_BUILDERS
# - 불변 조건: 템플릿 키는 사전에 정의된 문자열이어야 함
# =============================================================================

"""Drone SOP Jira 템플릿 레지스트리 모음."""
from __future__ import annotations

from .jira_template_line_a import (
    TEMPLATE_KEY as LINE_A_KEY,
    DESCRIPTION_TEMPLATE as LINE_A_DESCRIPTION_TEMPLATE,
    build_summary as build_line_a_summary,
)
from .jira_template_line_b import (
    TEMPLATE_KEY as LINE_B_KEY,
    DESCRIPTION_TEMPLATE as LINE_B_DESCRIPTION_TEMPLATE,
    build_summary as build_line_b_summary,
)

TEMPLATE_SOURCES = {
    LINE_A_KEY: LINE_A_DESCRIPTION_TEMPLATE,
    LINE_B_KEY: LINE_B_DESCRIPTION_TEMPLATE,
}

SUMMARY_BUILDERS = {
    LINE_A_KEY: build_line_a_summary,
    LINE_B_KEY: build_line_b_summary,
}

__all__ = ["SUMMARY_BUILDERS", "TEMPLATE_SOURCES"]
