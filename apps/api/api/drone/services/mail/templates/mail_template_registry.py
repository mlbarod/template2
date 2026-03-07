# =============================================================================
# 모듈 설명: Drone SOP 메일 템플릿 정의를 등록합니다.
# - 주요 대상: MAIL_TEMPLATE_SOURCES
# - 불변 조건: 템플릿 키는 사전에 정의된 문자열이어야 함
# =============================================================================

"""Drone SOP 메일 템플릿 레지스트리 모음."""
from __future__ import annotations

from .mail_template_common import BODY_TEMPLATE as COMMON_BODY_TEMPLATE, TEMPLATE_KEY as COMMON_KEY
from .mail_template_h1 import BODY_TEMPLATE as H1_BODY_TEMPLATE, TEMPLATE_KEY as H1_KEY

MAIL_TEMPLATE_SOURCES = {
    COMMON_KEY: COMMON_BODY_TEMPLATE,
    H1_KEY: H1_BODY_TEMPLATE,
}

__all__ = ["MAIL_TEMPLATE_SOURCES"]
