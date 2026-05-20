# =============================================================================
# 모듈 설명: common용 메일 본문 템플릿을 제공합니다.
# - 주요 대상: TEMPLATE_KEY, BODY_TEMPLATE
# - 불변 조건: summary/template key는 Jira common과 동일하게 유지합니다.
# =============================================================================

"""common 메일 템플릿 정의 모음."""
from __future__ import annotations

from ...jira.templates.jira_template_common import TEMPLATE_KEY
from .mail_template_body import BODY_TEMPLATE


__all__ = ["TEMPLATE_KEY", "BODY_TEMPLATE"]
