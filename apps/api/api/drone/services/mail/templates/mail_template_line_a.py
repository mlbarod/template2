# =============================================================================
# 모듈 설명: 라인 A용 메일 본문 템플릿을 제공합니다.
# - 주요 대상: TEMPLATE_KEY, BODY_TEMPLATE
# - 불변 조건: Jira 라인 A 템플릿 HTML을 그대로 재사용합니다.
# =============================================================================

"""라인 A 메일 템플릿 정의 모음."""
from __future__ import annotations

from ...jira.templates.jira_template_line_a import DESCRIPTION_TEMPLATE as BODY_TEMPLATE
from ...jira.templates.jira_template_line_a import TEMPLATE_KEY


__all__ = ["TEMPLATE_KEY", "BODY_TEMPLATE"]
