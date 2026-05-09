"""Drone SOP Jira 이슈 fields 구성 helper."""

from __future__ import annotations

from typing import Any

from django.template import Context, Engine

from ..shared.inform_context import build_inform_context
from ..shared.utils import _truncate_text
from .config import DroneJiraConfig
from .templates.jira_template_registry import SUMMARY_BUILDERS, TEMPLATE_SOURCES

_TEMPLATE_ENGINE = Engine(autoescape=True)
_TEMPLATE_CACHE: dict[str, str] = {}


def build_jira_summary(
    *,
    row: dict[str, Any],
    template_key: str,
) -> str:
    """Jira 이슈 요약(summary)을 템플릿별로 생성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).
        template_key: 템플릿 키.

    반환:
        summary 문자열.

    부작용:
        없음. 순수 문자열 구성입니다.
    """

    summary_builder = SUMMARY_BUILDERS.get(template_key)
    if not callable(summary_builder):
        raise ValueError(f"Unsupported Jira summary template key: {template_key!r}")

    summary = summary_builder(row)
    if not isinstance(summary, str):
        summary = str(summary)
    return _truncate_text(summary.strip(), 255)


def load_template_source(template_key: str) -> str:
    """템플릿 키에 해당하는 HTML 소스를 로드합니다.

    인자:
        template_key: 템플릿 키.

    반환:
        템플릿 소스 문자열.

    부작용:
        내부 캐시를 갱신할 수 있습니다.

    오류:
        지원하지 않는 키이면 ValueError를 발생시킵니다.
    """

    if template_key in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[template_key]

    source = TEMPLATE_SOURCES.get(template_key)
    if not source:
        raise ValueError(f"Unsupported Jira template key: {template_key!r}")
    _TEMPLATE_CACHE[template_key] = source
    return source


def render_line_template(*, template_key: str, row: dict[str, Any]) -> str:
    """라인 템플릿을 렌더링합니다.

    인자:
        template_key: 템플릿 키.
        row: Drone SOP 행 dict(행 데이터).

    반환:
        렌더링된 HTML 문자열.

    부작용:
        템플릿 캐시를 갱신할 수 있습니다.
    """

    source = load_template_source(template_key)
    context = Context(build_inform_context(row))
    return _TEMPLATE_ENGINE.from_string(source).render(context)


def build_jira_description_html(*, row: dict[str, Any], template_key: str) -> str:
    """Jira description HTML을 생성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).
        template_key: 템플릿 키.

    반환:
        HTML 문자열.

    부작용:
        템플릿 렌더링이 발생합니다.
    """

    return render_line_template(template_key=template_key, row=row)


def build_jira_issue_fields(
    *,
    row: dict[str, Any],
    project_key: str,
    template_key: str,
    config: DroneJiraConfig,
) -> dict[str, Any]:
    """Jira 이슈 fields payload를 구성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).
        project_key: Jira 프로젝트 키.
        template_key: 템플릿 키.
        config: Jira 설정.

    반환:
        Jira API fields dict(Jira 필드 맵).

    부작용:
        없음. 순수 구성입니다.
    """

    return {
        "project": {"key": project_key},
        "issuetype": {"name": config.issue_type},
        "summary": build_jira_summary(row=row, template_key=template_key),
        "description": build_jira_description_html(row=row, template_key=template_key),
    }


__all__ = [
    "build_jira_description_html",
    "build_jira_issue_fields",
    "build_jira_summary",
]
