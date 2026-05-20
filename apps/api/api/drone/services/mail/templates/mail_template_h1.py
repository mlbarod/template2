# =============================================================================
# 모듈 설명: H1용 메일 본문 템플릿을 제공합니다.
# - 주요 대상: TEMPLATE_KEY, BODY_TEMPLATE
# - 불변 조건: summary/template key는 Jira H1과 동일하게 유지합니다.
# =============================================================================

"""H1 메일 템플릿 정의 모음."""
from __future__ import annotations

from ...jira.templates.jira_template_h1 import SUMMARY_TEMPLATE
from ...jira.templates.jira_template_h1 import TEMPLATE_KEY
from ...jira.templates.jira_template_h1 import build_summary, find_layer
from .mail_template_body import BODY_TEMPLATE


__all__ = ["TEMPLATE_KEY", "BODY_TEMPLATE", "SUMMARY_TEMPLATE", "build_summary", "find_layer"]
