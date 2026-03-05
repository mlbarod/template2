# =============================================================================
# 모듈: Drone SOP Jira 전송/템플릿 유틸
# 주요 기능: 템플릿 렌더링, CTTTM URL 보강, Jira 생성 API 호출
# 주요 가정: 이 모듈은 부작용(외부 API 호출/템플릿 캐시)을 포함합니다.
# =============================================================================
"""Drone SOP Jira 전송 보조 유틸리티 모음."""

from __future__ import annotations

import logging
from typing import Any, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from django.template import Context, Engine

from ... import selectors
from ..shared.inform_context import build_inform_context
from ..shared.utils import _truncate_text
from .config import DroneCtttmConfig, DroneJiraConfig
from .templates.jira_template_registry import SUMMARY_BUILDERS, TEMPLATE_SOURCES

logger = logging.getLogger(__name__)

# =============================================================================
# 템플릿/렌더링 상수
# =============================================================================
_TEMPLATE_ENGINE = Engine(autoescape=True)
_TEMPLATE_CACHE: dict[str, str] = {}


def _build_jira_summary(
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


def _load_template_source(template_key: str) -> str:
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


def _render_line_template(*, template_key: str, row: dict[str, Any]) -> str:
    """라인 템플릿을 렌더링합니다.

    인자:
        template_key: 템플릿 키.
        row: Drone SOP 행 dict(행 데이터).

    반환:
        렌더링된 HTML 문자열.

    부작용:
        템플릿 캐시를 갱신할 수 있습니다.
    """

    source = _load_template_source(template_key)
    context = Context(build_inform_context(row))
    return _TEMPLATE_ENGINE.from_string(source).render(context)


def _build_jira_description_html(*, row: dict[str, Any], template_key: str) -> str:
    """Jira description HTML을 생성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).
        template_key: 템플릿 키.

    반환:
        HTML 문자열.

    부작용:
        템플릿 렌더링이 발생합니다.
    """

    return _render_line_template(template_key=template_key, row=row)


def _build_ctttm_url(*, base_url: str, workorder_id: str, line_id: str) -> str:
    """CTTTM URL을 구성합니다.

    인자:
        base_url: 기본 URL.
        workorder_id: 작업 지시 ID.
        line_id: 라인 ID.

    반환:
        쿼리 파라미터가 반영된 URL 문자열.

    부작용:
        없음. 순수 문자열 구성입니다.
    """

    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"wono": workorder_id, "lineId": line_id})
    return urlunparse(parsed._replace(query=urlencode(query)))


def _enrich_rows_with_ctttm_urls(*, rows: Sequence[dict[str, Any]], config: DroneCtttmConfig) -> None:
    """rows에 CTTTM URL 정보를 보강합니다.

    인자:
        rows: Drone SOP row 목록.
        config: CTTTM 설정.

    부작용:
        rows dict에 "url" 필드를 추가할 수 있습니다.
    """

    if not rows:
        return
    if not config.table_name or not config.base_url:
        return

    sop_ids: list[int] = []
    for row in rows:
        rid = row.get("id")
        if isinstance(rid, int) and rid > 0:
            sop_ids.append(rid)
    if not sop_ids:
        return

    try:
        workorders_by_id = selectors.load_drone_sop_ctttm_workorders_map(
            sop_ids=sop_ids,
            ctttm_table=config.table_name,
        )
    except Exception:
        logger.exception("Failed to load CTTTM workorders (table=%r)", config.table_name)
        return

    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int) or rid <= 0:
            continue
        entries = workorders_by_id.get(rid) or []
        url_entries: list[dict[str, str]] = []
        for entry in entries:
            eqp_id = str(entry.get("eqp_id") or "").strip()
            workorder_id = str(entry.get("workorder_id") or "").strip()
            line_id = str(entry.get("line_id") or "").strip()
            if not eqp_id or not workorder_id or not line_id:
                continue
            url_entries.append(
                {
                    "eqp_id": eqp_id,
                    "url": _build_ctttm_url(base_url=config.base_url, workorder_id=workorder_id, line_id=line_id),
                }
            )
        if url_entries:
            row["url"] = url_entries


def _safe_json(response: requests.Response) -> dict[str, Any]:
    """응답을 안전하게 JSON dict로 변환합니다.

    인자:
        response: requests.Response 객체.

    반환:
        dict 형태의 JSON(실패 시 빈 dict).

    부작용:
        없음. 순수 파싱입니다.
    """

    try:
        parsed = response.json()
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_jira_issue_fields(
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
        "summary": _build_jira_summary(row=row, template_key=template_key),
        "description": _build_jira_description_html(row=row, template_key=template_key),
    }


def _bulk_create_jira_issues(
    *,
    rows: Sequence[dict[str, Any]],
    config: DroneJiraConfig,
    session: requests.Session,
    project_key_by_id: dict[int, str],
    template_key_by_id: dict[int, str],
) -> tuple[list[int], dict[int, str]]:
    """Jira 벌크 생성 API로 이슈를 생성합니다.

    인자:
        rows: Drone SOP row 목록.
        config: Jira 설정.
        session: Jira 세션.
        project_key_by_id: sop_id → project_key 매핑.
        template_key_by_id: sop_id → template_key 매핑.
    """

    done_ids: list[int] = []
    key_by_id: dict[int, str] = {}

    for st in range(0, len(rows), config.bulk_size):
        chunk = list(rows[st : st + config.bulk_size])
        issue_updates: list[dict[str, Any]] = []
        valid_chunk: list[dict[str, Any]] = []
        for row in chunk:
            rid = row.get("id")
            if not isinstance(rid, int):
                continue
            project_key = project_key_by_id.get(rid)
            if not project_key:
                continue
            template_key = template_key_by_id.get(rid)
            if not template_key:
                continue
            issue_updates.append(
                {
                    "fields": _build_jira_issue_fields(
                        row=row,
                        project_key=project_key,
                        template_key=template_key,
                        config=config,
                    )
                }
            )
            valid_chunk.append(row)
        if not issue_updates:
            continue

        try:
            resp = session.post(
                config.bulk_url,
                json={"issueUpdates": issue_updates},
                timeout=(config.connect_timeout, config.read_timeout),
            )
        except requests.RequestException:
            logger.exception(
                "Jira bulk create request failed(start=%s, size=%s)",
                st,
                len(valid_chunk),
            )
            continue
        if resp.status_code != 201:
            logger.error("Jira bulk create failed %s: %s", resp.status_code, resp.text[:300])
            continue

        data = _safe_json(resp)
        issues = data.get("issues") or []
        if not isinstance(issues, list):
            continue

        for index, row in enumerate(valid_chunk):
            rid = row.get("id")
            if not isinstance(rid, int):
                continue
            if index >= len(issues):
                continue
            issue = issues[index]
            if not isinstance(issue, dict):
                continue
            key = issue.get("key")
            if isinstance(key, str) and key.strip():
                key_by_id[rid] = key.strip()
                done_ids.append(rid)

    return done_ids, key_by_id


def _single_create_jira_issues(
    *,
    rows: Sequence[dict[str, Any]],
    config: DroneJiraConfig,
    session: requests.Session,
    project_key_by_id: dict[int, str],
    template_key_by_id: dict[int, str],
) -> tuple[list[int], dict[int, str]]:
    """Jira 단건 생성 API로 이슈를 생성합니다.

    인자:
        rows: Drone SOP row 목록.
        config: Jira 설정.
        session: Jira 세션.
        project_key_by_id: sop_id → project_key 매핑.
        template_key_by_id: sop_id → template_key 매핑.
    """

    done_ids: list[int] = []
    key_by_id: dict[int, str] = {}

    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int):
            continue
        project_key = project_key_by_id.get(rid)
        if not project_key:
            continue
        template_key = template_key_by_id.get(rid)
        if not template_key:
            continue
        try:
            resp = session.post(
                config.create_url,
                json={
                    "fields": _build_jira_issue_fields(
                        row=row,
                        project_key=project_key,
                        template_key=template_key,
                        config=config,
                    )
                },
                timeout=(config.connect_timeout, config.read_timeout),
            )
        except requests.RequestException:
            logger.exception("Jira create request failed id=%s", rid)
            continue
        if resp.status_code != 201:
            logger.error("Jira create failed id=%s %s: %s", rid, resp.status_code, resp.text[:300])
            continue
        data = _safe_json(resp)
        key = data.get("key")
        if isinstance(key, str) and key.strip():
            key_by_id[rid] = key.strip()
        done_ids.append(rid)

    return done_ids, key_by_id


__all__ = [
    "_bulk_create_jira_issues",
    "_build_jira_description_html",
    "_build_jira_issue_fields",
    "_build_jira_summary",
    "_enrich_rows_with_ctttm_urls",
    "_single_create_jira_issues",
]
