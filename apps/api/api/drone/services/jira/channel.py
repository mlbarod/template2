# =============================================================================
# 모듈: Drone SOP Jira 채널 매핑
# 주요 기능: target_user_sdwt_prod 기준 Jira 키/템플릿 해석
# 주요 가정: 채널 설정이 없으면 스킵, 설정 오류는 실패 처리 대상입니다.
# =============================================================================
"""Drone SOP Jira 채널 매핑 유틸리티."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JiraChannelPlan:
    """Jira 전송 계획(프로젝트/템플릿 매핑) 결과."""

    project_key_by_id: dict[int, str]
    template_key_by_id: dict[int, str]
    invalid_ids: list[int]
    skip_ids: list[int]
    disabled_ids: list[int]


def resolve_jira_channel_plan(
    *,
    rows: list[dict[str, Any]],
    channel_by_target: dict[str, dict[str, str | bool | None]],
    template_sources: dict[str, str],
) -> JiraChannelPlan:
    """Jira 전송을 위한 채널 매핑을 해석합니다.

    인자:
        rows: Drone SOP row 목록.
        channel_by_target: target_user_sdwt_prod별 채널 설정 맵.
        template_sources: Jira 템플릿 소스 맵.

    반환:
        JiraChannelPlan 인스턴스.

    부작용:
        없음. 순수 매핑 해석입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 초기화
    # -----------------------------------------------------------------------------
    project_key_by_id: dict[int, str] = {}
    template_key_by_id: dict[int, str] = {}
    invalid_ids: list[int] = []
    skip_ids: list[int] = []
    disabled_ids: list[int] = []

    # -----------------------------------------------------------------------------
    # 2) row별 채널 매핑 해석
    # -----------------------------------------------------------------------------
    for row in rows:
        row_id = row.get("id")
        if not isinstance(row_id, int):
            continue

        target = row.get("target_user_sdwt_prod")
        if not isinstance(target, str) or not target.strip():
            skip_ids.append(row_id)
            continue
        normalized_target = target.strip()
        config_row = channel_by_target.get(normalized_target)
        if not config_row:
            skip_ids.append(row_id)
            continue
        if not bool(config_row.get("jira_enabled", True)):
            disabled_ids.append(row_id)
            continue

        jira_key = config_row.get("jira_key")
        template_key = config_row.get("jira_template_key")
        if not isinstance(jira_key, str) or not jira_key.strip():
            invalid_ids.append(row_id)
            continue
        if not isinstance(template_key, str) or not template_key.strip():
            invalid_ids.append(row_id)
            continue

        normalized_template = template_key.strip()
        if normalized_template not in template_sources:
            invalid_ids.append(row_id)
            continue

        project_key_by_id[row_id] = jira_key.strip()
        template_key_by_id[row_id] = normalized_template

    return JiraChannelPlan(
        project_key_by_id=project_key_by_id,
        template_key_by_id=template_key_by_id,
        invalid_ids=invalid_ids,
        skip_ids=skip_ids,
        disabled_ids=disabled_ids,
    )


__all__ = ["JiraChannelPlan", "resolve_jira_channel_plan"]
