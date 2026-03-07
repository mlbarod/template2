# =============================================================================
# 모듈 설명: Drone SOP Jira 템플릿 정의를 등록합니다.
# - 주요 대상: TEMPLATE_SOURCES, SUMMARY_BUILDERS
# - 불변 조건: 템플릿 키는 사전에 정의된 문자열이어야 함
# =============================================================================

"""Drone SOP Jira 템플릿 레지스트리 모음."""
from __future__ import annotations

from .jira_template_common import (
    TEMPLATE_KEY as COMMON_KEY,
    DESCRIPTION_TEMPLATE as COMMON_DESCRIPTION_TEMPLATE,
    build_summary as build_common_summary,
)
from .jira_template_h1 import (
    TEMPLATE_KEY as H1_KEY,
    DESCRIPTION_TEMPLATE as H1_DESCRIPTION_TEMPLATE,
    build_summary as build_h1_summary,
)

TEMPLATE_SOURCES = {
    COMMON_KEY: COMMON_DESCRIPTION_TEMPLATE,
    H1_KEY: H1_DESCRIPTION_TEMPLATE,
}

SUMMARY_BUILDERS = {
    COMMON_KEY: build_common_summary,
    H1_KEY: build_h1_summary,
}

__all__ = ["SUMMARY_BUILDERS", "TEMPLATE_SOURCES"]
