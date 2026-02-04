# =============================================================================
# 모듈: Drone SOP Jira 연동 서비스
# 주요 기능: Jira 이슈 생성(배치) 및 즉시인폼 체크, 템플릿 렌더링
# 주요 가정: Jira/CTTTM 설정은 settings/env에서 주입됩니다.
# =============================================================================
"""Drone SOP Jira 연동 헬퍼 모듈입니다."""

from __future__ import annotations
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from django.conf import settings
from django.db import transaction
from django.template import Context, Engine
from django.db.models import Case, CharField, DateTimeField, F, Value, When
from django.utils import timezone

from .. import selectors
from ..models import DroneSOP
from .utils import (
    _first_defined,
    _lock_key,
    _parse_bool,
    _parse_int,
    _release_advisory_lock,
    _try_advisory_lock,
)
from .jira_template_registry import SUMMARY_BUILDERS, TEMPLATE_SOURCES

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class DroneSopJiraCreateResult:
    """Drone SOP Jira 생성 실행 결과."""

    candidates: int = 0
    created: int = 0
    updated_rows: int = 0
    skipped: bool = False
    skip_reason: str | None = None


@dataclass(frozen=True)
class DroneSopInstantInformResult:
    """Drone SOP 단건 즉시인폼 요청 결과."""

    already_informed: bool = False
    queued: bool = False
    jira_key: str | None = None
    updated_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DroneJiraConfig:
    """Jira 연동 설정."""

    base_url: str
    token: str
    issue_type: str = "Task"
    use_bulk_api: bool = True
    bulk_size: int = 20
    connect_timeout: int = 5
    read_timeout: int = 20
    verify_ssl: bool = True
    user: str = ""

    @classmethod
    def from_settings(cls) -> "DroneJiraConfig":
        """settings/env에서 Jira 연동 설정을 로드합니다.

        반환:
            DroneJiraConfig 인스턴스.

        부작용:
            settings/env 값을 조회합니다.
        """

        # -------------------------------------------------------------------------
        # 1) 기본 설정 값 로드
        # -------------------------------------------------------------------------
        base_url = (getattr(settings, "DRONE_JIRA_BASE_URL", "") or os.getenv("DRONE_JIRA_BASE_URL") or "").strip()
        token = (getattr(settings, "DRONE_JIRA_TOKEN", "") or os.getenv("DRONE_JIRA_TOKEN") or "").strip()
        user = (getattr(settings, "DRONE_JIRA_USER", "") or os.getenv("DRONE_JIRA_USER") or "").strip()
        verify_ssl = _parse_bool(
            _first_defined(
                getattr(settings, "DRONE_JIRA_VERIFY_SSL", None),
                os.getenv("DRONE_JIRA_VERIFY_SSL"),
            ),
            True,
        )
        issue_type = (
            getattr(settings, "DRONE_JIRA_ISSUE_TYPE", "") or os.getenv("DRONE_JIRA_ISSUE_TYPE") or "Task"
        ).strip() or "Task"
        use_bulk_api = _parse_bool(
            _first_defined(
                getattr(settings, "DRONE_JIRA_USE_BULK_API", None),
                os.getenv("DRONE_JIRA_USE_BULK_API"),
            ),
            True,
        )
        bulk_size = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_JIRA_BULK_SIZE", None),
                os.getenv("DRONE_JIRA_BULK_SIZE"),
            ),
            20,
        )
        connect_timeout = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_JIRA_CONNECT_TIMEOUT", None),
                os.getenv("DRONE_JIRA_CONNECT_TIMEOUT"),
            ),
            5,
        )
        read_timeout = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_JIRA_READ_TIMEOUT", None),
                os.getenv("DRONE_JIRA_READ_TIMEOUT"),
            ),
            20,
        )
        # -------------------------------------------------------------------------
        # 2) 최소값 보정 후 반환
        # -------------------------------------------------------------------------
        return cls(
            base_url=base_url,
            token=token,
            issue_type=issue_type,
            use_bulk_api=use_bulk_api,
            bulk_size=max(1, bulk_size),
            connect_timeout=max(1, connect_timeout),
            read_timeout=max(1, read_timeout),
            verify_ssl=verify_ssl,
            user=user,
        )

    @property
    def create_url(self) -> str:
        """Jira 단건 생성 URL을 반환합니다."""

        return f"{self.base_url.rstrip('/')}/rest/api/2/issue?sendEvent=true"

    @property
    def bulk_url(self) -> str:
        """Jira 벌크 생성 URL을 반환합니다."""

        return f"{self.base_url.rstrip('/')}/rest/api/2/issue/bulk?sendEvent=true"


@dataclass(frozen=True)
class DroneCtttmConfig:
    """CTTTM 조회 및 URL 생성 설정."""

    table_name: str = ""
    base_url: str = ""

    @classmethod
    def from_settings(cls) -> "DroneCtttmConfig":
        """settings/env에서 CTTTM 설정을 로드합니다.

        반환:
            DroneCtttmConfig 인스턴스.

        부작용:
            settings/env 값을 조회합니다.
        """

        # -------------------------------------------------------------------------
        # 1) 테이블/URL 설정 로드
        # -------------------------------------------------------------------------
        table_name = (
            getattr(settings, "DRONE_CTTTM_TABLE_NAME", "")
            or os.getenv("DRONE_CTTTM_TABLE_NAME")
            or ""
        ).strip()
        base_url = (
            getattr(settings, "DRONE_CTTTM_BASE_URL", "")
            or os.getenv("DRONE_CTTTM_BASE_URL")
            or ""
        ).strip()
        return cls(table_name=table_name, base_url=base_url)


def _truncate(value: str, max_len: int) -> str:
    """문자열을 최대 길이로 자릅니다.

    인자:
        value: 원본 문자열.
        max_len: 최대 길이.

    반환:
        제한 길이를 적용한 문자열.

    부작용:
        없음. 순수 문자열 처리입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 길이 조건에 따라 자르기
    # -------------------------------------------------------------------------
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return value[:max_len]
    return value[: max_len - 3] + "..."


def _build_jira_summary(*, row: dict[str, Any], template_key: str) -> str:
    """Jira 이슈 요약(summary)을 템플릿별로 생성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).
        template_key: 템플릿 키.

    반환:
        summary 문자열.

    부작용:
        없음. 순수 문자열 구성입니다.
    """

    # -------------------------------------------------------------------------
    # 1) summary 빌더 선택
    # -------------------------------------------------------------------------
    summary_builder = SUMMARY_BUILDERS.get(template_key)
    if not callable(summary_builder):
        raise ValueError(f"Unsupported Jira summary template key: {template_key!r}")
    # -------------------------------------------------------------------------
    # 2) summary 생성
    # -------------------------------------------------------------------------
    summary = summary_builder(row)
    if not isinstance(summary, str):
        summary = str(summary)
    summary = summary.strip()
    # -------------------------------------------------------------------------
    # 3) 길이 제한 적용
    # -------------------------------------------------------------------------
    return _truncate(summary, 255)


# =============================================================================
# 템플릿/렌더링 상수
# =============================================================================
_TEMPLATE_ENGINE = Engine(autoescape=True)
_TEMPLATE_CACHE: dict[str, str] = {}


def _build_eqp_cb(row: dict[str, Any]) -> str:
    """장비/챔버 식별 문자열을 생성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).

    반환:
        "eqp_id-chamber_ids" 형태의 문자열.

    부작용:
        없음. 순수 문자열 구성입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 장비/챔버 값 정규화
    # -------------------------------------------------------------------------
    eqp_id = (str(row.get("eqp_id") or "-") or "-").strip()
    chamber_ids = (str(row.get("chamber_ids") or "-") or "-").strip()
    return f"{eqp_id}-{chamber_ids}"


def _normalize_ctttm_urls(value: Any) -> list[dict[str, str]]:
    """CTTTM URL 입력을 통일된 리스트 형태로 정규화합니다.

    인자:
        value: 문자열 또는 dict 리스트 입력.

    반환:
        {"url","label"} 형태의 리스트.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 문자열 입력 처리
    # -------------------------------------------------------------------------
    urls: list[dict[str, str]] = []
    if isinstance(value, str):
        if value.strip():
            urls.append({"url": value.strip(), "label": value.strip()})
        return urls
    # -------------------------------------------------------------------------
    # 2) 리스트 입력 처리
    # -------------------------------------------------------------------------
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            link = item.get("url")
            if not link:
                continue
            label = item.get("eqp_id") or link
            urls.append({"url": str(link), "label": str(label)})
    return urls


def _build_template_context(row: dict[str, Any]) -> dict[str, Any]:
    """Jira 템플릿 렌더링에 사용할 컨텍스트를 구성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).

    반환:
        템플릿 컨텍스트 dict.

    부작용:
        없음. 순수 구성입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 주요 필드 정규화
    # -------------------------------------------------------------------------
    knoxid = str(row.get("knox_id") or row.get("knoxid") or "").strip()
    user_sdwt_prod = str(row.get("user_sdwt_prod") or "").strip()
    comment_raw = str(row.get("comment") or "").split("$@$", 1)[0]
    # -------------------------------------------------------------------------
    # 2) 템플릿 컨텍스트 구성
    # -------------------------------------------------------------------------
    return {
        "main_step": row.get("main_step"),
        "ppid": row.get("ppid"),
        "eqp_cb": _build_eqp_cb(row),
        "lot_id": row.get("lot_id"),
        "knoxid": knoxid,
        "user_sdwt_prod": user_sdwt_prod,
        "ctttm_urls": _normalize_ctttm_urls(row.get("url")),
        "defect_url": row.get("defect_url"),
        "comment_raw": comment_raw,
    }


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

    # -------------------------------------------------------------------------
    # 1) 캐시 확인
    # -------------------------------------------------------------------------
    if template_key in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[template_key]
    # -------------------------------------------------------------------------
    # 2) 템플릿 소스 확보
    # -------------------------------------------------------------------------
    source = TEMPLATE_SOURCES.get(template_key)
    if not source:
        raise ValueError(f"Unsupported Jira template key: {template_key!r}")
    # -------------------------------------------------------------------------
    # 3) 캐시 저장 및 반환
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # 1) 템플릿 소스/컨텍스트 구성
    # -------------------------------------------------------------------------
    source = _load_template_source(template_key)
    context = Context(_build_template_context(row))
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

    # -------------------------------------------------------------------------
    # 1) 쿼리 파라미터 병합
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # 1) 입력/설정 확인
    # -------------------------------------------------------------------------
    if not rows:
        return
    if not config.table_name or not config.base_url:
        return

    # -------------------------------------------------------------------------
    # 2) sop_id 목록 구성
    # -------------------------------------------------------------------------
    sop_ids: list[int] = []
    for row in rows:
        rid = row.get("id")
        if isinstance(rid, int) and rid > 0:
            sop_ids.append(rid)
    if not sop_ids:
        return

    # -------------------------------------------------------------------------
    # 3) workorder 맵 로드
    # -------------------------------------------------------------------------
    try:
        workorders_by_id = selectors.load_drone_sop_ctttm_workorders_map(sop_ids=sop_ids, ctttm_table=config.table_name)
    except Exception:
        logger.exception("Failed to load CTTTM workorders (table=%r)", config.table_name)
        return

    # -------------------------------------------------------------------------
    # 4) row별 URL 항목 보강
    # -------------------------------------------------------------------------
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


def _jira_session(config: DroneJiraConfig) -> requests.Session:
    """Jira API 호출용 requests.Session을 구성합니다.

    인자:
        config: Jira 설정.

    반환:
        requests.Session 인스턴스.

    부작용:
        세션 객체가 생성됩니다.
    """

    # -------------------------------------------------------------------------
    # 1) 세션 기본 설정
    # -------------------------------------------------------------------------
    sess = requests.Session()
    sess.trust_env = False
    sess.proxies = {}
    sess.verify = bool(config.verify_ssl)

    # -------------------------------------------------------------------------
    # 2) 인증 헤더/인증 정보 설정
    # -------------------------------------------------------------------------
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Atlassian-Token": "no-check",
    }
    if config.user and config.token:
        sess.auth = (config.user, config.token)
    elif config.token:
        headers["Authorization"] = f"Bearer {config.token}"
    sess.headers.update(headers)

    # -------------------------------------------------------------------------
    # 3) 재시도 정책 설정
    # -------------------------------------------------------------------------
    retry = Retry(
        total=5,
        connect=5,
        read=3,
        backoff_factor=2,
        status_forcelist=[403, 502, 503, 504],
        allowed_methods=frozenset({"POST"}),
    )
    sess.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20))
    return sess


def _safe_json(response: requests.Response) -> dict[str, Any]:
    """응답을 안전하게 JSON dict로 변환합니다.

    인자:
        response: requests.Response 객체.

    반환:
        dict 형태의 JSON(실패 시 빈 dict).

    부작용:
        없음. 순수 파싱입니다.
    """

    # -------------------------------------------------------------------------
    # 1) JSON 파싱 시도
    # -------------------------------------------------------------------------
    try:
        parsed = response.json()
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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
        project_key_by_id: sop_id → project_key (SOP ID별 프로젝트 키).
        template_key_by_id: sop_id → template_key (SOP ID별 템플릿 키).

    반환:
        (완료된 sop_id 목록, sop_id → jira_key 매핑) 튜플.

    부작용:
        Jira API 호출이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 청크 단위로 요청 구성
    # -------------------------------------------------------------------------
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
        # ---------------------------------------------------------------------
        # 2) Jira 벌크 API 호출
        # ---------------------------------------------------------------------
        resp = session.post(
            config.bulk_url,
            json={"issueUpdates": issue_updates},
            timeout=(config.connect_timeout, config.read_timeout),
        )
        if resp.status_code != 201:
            logger.error("Jira bulk create failed %s: %s", resp.status_code, resp.text[:300])
            continue

        # ---------------------------------------------------------------------
        # 3) 응답 파싱 및 결과 매핑
        # ---------------------------------------------------------------------
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
        project_key_by_id: sop_id → project_key (SOP ID별 프로젝트 키).
        template_key_by_id: sop_id → template_key (SOP ID별 템플릿 키).

    반환:
        (완료된 sop_id 목록, sop_id → jira_key 매핑) 튜플.

    부작용:
        Jira API 호출이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) row 단위로 요청 수행
    # -------------------------------------------------------------------------
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
        if resp.status_code != 201:
            logger.error("Jira create failed id=%s %s: %s", rid, resp.status_code, resp.text[:300])
            continue
        # ---------------------------------------------------------------------
        # 2) 응답 파싱 및 결과 매핑
        # ---------------------------------------------------------------------
        data = _safe_json(resp)
        key = data.get("key")
        if isinstance(key, str) and key.strip():
            key_by_id[rid] = key.strip()
        done_ids.append(rid)

    return done_ids, key_by_id


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
        "labels": ["drone", "drone_sop"],
    }


def _update_drone_sop_jira_status(
    *,
    done_ids: Sequence[int],
    rows: Sequence[dict[str, Any]],
    key_by_id: dict[int, str],
) -> int:
    """Jira 생성 완료된 DroneSOP 상태를 업데이트합니다.

    인자:
        done_ids: Jira 생성 성공 SOP ID 목록.
        rows: 원본 row 목록.
        key_by_id: sop_id → jira_key 매핑.

    반환:
        업데이트된 row 수.

    부작용:
        drone_sop 테이블 업데이트가 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 업데이트 대상 확인
    # -------------------------------------------------------------------------
    if not done_ids:
        return 0

    # -------------------------------------------------------------------------
    # 2) 단계/키 매핑 구성
    # -------------------------------------------------------------------------
    step_by_id: dict[int, str] = {}
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int) or rid not in done_ids:
            continue
        step = row.get("metro_current_step")
        if isinstance(step, str) and step.strip():
            step_by_id[rid] = step.strip()

    now = timezone.now()
    step_whens = [When(id=rid, then=Value(step)) for rid, step in sorted(step_by_id.items())]
    key_whens = [When(id=rid, then=Value(key)) for rid, key in sorted(key_by_id.items())]

    # -------------------------------------------------------------------------
    # 3) 업데이트 절 구성
    # -------------------------------------------------------------------------
    updates: dict[str, Any] = {
        "send_jira": 1,
        "informed_at": Case(
            When(informed_at__isnull=True, then=Value(now)),
            default=F("informed_at"),
            output_field=DateTimeField(),
        ),
    }
    if step_whens:
        updates["inform_step"] = Case(*step_whens, default=F("inform_step"), output_field=CharField())
    if key_whens:
        updates["jira_key"] = Case(*key_whens, default=F("jira_key"), output_field=CharField())

    # -------------------------------------------------------------------------
    # 4) DB 업데이트 실행
    # -------------------------------------------------------------------------
    with transaction.atomic():
        updated = DroneSOP.objects.filter(id__in=list(done_ids)).update(**updates)
    return int(updated or 0)


def enqueue_drone_sop_jira_instant_inform(
    *,
    sop_id: int,
    comment: str | None = None,
) -> DroneSopInstantInformResult:
    """Drone SOP 단건 즉시인폼 체크를 요청합니다.

    인자:
        sop_id: DroneSOP ID(드론 SOP ID).
        comment: 덮어쓸 코멘트(옵션).

    반환:
        DroneSopInstantInformResult 결과 객체(queued/already_informed/updated_fields 포함).

    부작용:
        - comment/instant_inform/send_jira 상태 업데이트(필요 시)

    오류:
        입력 검증 실패 시 ValueError를 발생시킵니다.
    """

    # -------------------------------------------------------------------------
    # 1) 입력 검증
    # -------------------------------------------------------------------------
    if sop_id <= 0:
        raise ValueError("sop_id must be a positive integer")

    updated_fields: dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # 2) 상태 업데이트(체크 + 코멘트)
    # -------------------------------------------------------------------------
    with transaction.atomic():
        sop = selectors.get_drone_sop_for_update(sop_id=sop_id)
        if sop is None:
            raise ValueError("DroneSOP not found")

        update_fields: list[str] = []
        if comment is not None:
            sop.comment = comment
            updated_fields["comment"] = sop.comment
            update_fields.append("comment")

        send_jira_value = int(sop.send_jira or 0)
        if send_jira_value > 0:
            if update_fields:
                sop.save(update_fields=[*update_fields, "updated_at"])
            updated_fields["send_jira"] = sop.send_jira
            updated_fields["instant_inform"] = sop.instant_inform
            updated_fields["jira_key"] = sop.jira_key
            updated_fields["inform_step"] = sop.inform_step
            updated_fields["informed_at"] = sop.informed_at.isoformat() if sop.informed_at else None
            return DroneSopInstantInformResult(
                already_informed=True,
                jira_key=sop.jira_key,
                updated_fields=updated_fields,
            )

        if sop.send_jira is not None and int(sop.send_jira) < 0:
            sop.send_jira = 0
            updated_fields["send_jira"] = 0
            update_fields.append("send_jira")

        if sop.instant_inform is None or int(sop.instant_inform) != 1:
            sop.instant_inform = 1
            updated_fields["instant_inform"] = 1
            update_fields.append("instant_inform")

        if update_fields:
            sop.save(update_fields=[*update_fields, "updated_at"])

    return DroneSopInstantInformResult(
        queued=True,
        updated_fields=updated_fields,
    )


def run_drone_sop_jira_create_from_env(*, limit: int | None = None) -> DroneSopJiraCreateResult:
    """send_jira=0 이면서 (needtosend=1 & status=COMPLETE 또는 instant_inform=1)인 대상 Jira 이슈를 생성합니다.

    인자:
        limit: 최대 처리 건수(옵션).

    반환:
        DroneSopJiraCreateResult 결과 객체.

    부작용:
        - Jira API 호출
        - drone_sop 상태 컬럼(send_jira/inform_step/jira_key/informed_at) 업데이트
        - 즉시인폼 실패 시 instant_inform=-1 업데이트

    오류:
        설정 누락 시 ValueError가 발생할 수 있습니다.
    """

    # -------------------------------------------------------------------------
    # 1) 설정/락 검증
    # -------------------------------------------------------------------------
    config = DroneJiraConfig.from_settings()
    if not config.base_url:
        raise ValueError("DRONE_JIRA_BASE_URL 미설정")

    lock_id = _lock_key("drone_sop_jira_create")
    acquired = _try_advisory_lock(lock_id)
    if not acquired:
        return DroneSopJiraCreateResult(skipped=True, skip_reason="already_running")

    try:
        # ---------------------------------------------------------------------
        # 2) 대상 row 조회
        # ---------------------------------------------------------------------
        rows = selectors.list_drone_sop_jira_candidates(limit=limit)
        if not rows:
            return DroneSopJiraCreateResult(candidates=0, created=0, updated_rows=0)

        # ---------------------------------------------------------------------
        # 3) 프로젝트 키/템플릿 키 해석
        # ---------------------------------------------------------------------
        project_key_by_id, missing_ids = _resolve_project_keys_for_rows(rows=rows)
        if missing_ids:
            missing_id_set = set(missing_ids)
            missing_user_sdwt = sorted(
                {
                    row.get("user_sdwt_prod", "").strip()
                    for row in rows
                    if row.get("id") in missing_id_set
                    and isinstance(row.get("user_sdwt_prod"), str)
                    and row.get("user_sdwt_prod").strip()
                }
            )
            logger.warning(
                "Missing Jira project key mapping for %s drone_sop rows (user_sdwt_prod=%s)",
                len(missing_ids),
                ",".join(missing_user_sdwt[:10]) if missing_user_sdwt else "-",
            )
            with transaction.atomic():
                DroneSOP.objects.filter(id__in=missing_ids).update(send_jira=-1)
                DroneSOP.objects.filter(id__in=missing_ids, instant_inform=1).update(instant_inform=-1)

        template_key_by_id, missing_template_ids = _resolve_template_keys_for_rows(rows=rows)
        if missing_template_ids:
            missing_id_set = set(missing_template_ids)
            missing_user_sdwt = sorted(
                {
                    row.get("user_sdwt_prod", "").strip()
                    for row in rows
                    if row.get("id") in missing_id_set
                    and isinstance(row.get("user_sdwt_prod"), str)
                    and row.get("user_sdwt_prod").strip()
                }
            )
            logger.warning(
                "Missing Jira template mapping for %s drone_sop rows (user_sdwt_prod=%s)",
                len(missing_template_ids),
                ",".join(missing_user_sdwt[:10]) if missing_user_sdwt else "-",
            )
            with transaction.atomic():
                DroneSOP.objects.filter(id__in=missing_template_ids).update(send_jira=-1)
                DroneSOP.objects.filter(id__in=missing_template_ids, instant_inform=1).update(instant_inform=-1)

        # ---------------------------------------------------------------------
        # 4) 전송 대상 필터링 및 CTTTM URL 보강
        # ---------------------------------------------------------------------
        rows_to_send = [
            row
            for row in rows
            if isinstance(row.get("id"), int)
            and row.get("id") in project_key_by_id
            and row.get("id") in template_key_by_id
        ]
        if not rows_to_send:
            return DroneSopJiraCreateResult(candidates=len(rows), created=0, updated_rows=0)

        _enrich_rows_with_ctttm_urls(rows=rows_to_send, config=DroneCtttmConfig.from_settings())

        # ---------------------------------------------------------------------
        # 5) Jira API 호출(벌크/단건)
        # ---------------------------------------------------------------------
        instant_inform_ids: list[int] = []
        for row in rows_to_send:
            rid = row.get("id")
            if isinstance(rid, int) and row.get("instant_inform") == 1:
                instant_inform_ids.append(rid)

        try:
            sess = _jira_session(config)
            if config.use_bulk_api:
                done_ids, key_by_id = _bulk_create_jira_issues(
                    rows=rows_to_send,
                    config=config,
                    session=sess,
                    project_key_by_id=project_key_by_id,
                    template_key_by_id=template_key_by_id,
                )
            else:
                done_ids, key_by_id = _single_create_jira_issues(
                    rows=rows_to_send,
                    config=config,
                    session=sess,
                    project_key_by_id=project_key_by_id,
                    template_key_by_id=template_key_by_id,
                )
        except Exception:
            if instant_inform_ids:
                with transaction.atomic():
                    DroneSOP.objects.filter(id__in=instant_inform_ids, instant_inform=1).update(instant_inform=-1)
            raise

        # ---------------------------------------------------------------------
        # 6) 실패한 즉시인폼 상태 반영
        # ---------------------------------------------------------------------
        if instant_inform_ids:
            done_id_set = set(done_ids)
            failed_instant_ids = [rid for rid in instant_inform_ids if rid not in done_id_set]
            if failed_instant_ids:
                with transaction.atomic():
                    DroneSOP.objects.filter(id__in=failed_instant_ids, instant_inform=1).update(instant_inform=-1)

        # ---------------------------------------------------------------------
        # 7) 상태 업데이트 및 결과 반환
        # ---------------------------------------------------------------------
        updated = _update_drone_sop_jira_status(done_ids=done_ids, rows=rows_to_send, key_by_id=key_by_id)
        return DroneSopJiraCreateResult(
            candidates=len(rows),
            created=len(done_ids),
            updated_rows=updated,
        )
    finally:
        # ---------------------------------------------------------------------
        # 8) advisory lock 해제
        # ---------------------------------------------------------------------
        if acquired:
            _release_advisory_lock(lock_id)


def _resolve_project_keys_for_rows(
    *,
    rows: Sequence[dict[str, Any]],
) -> tuple[dict[int, str], list[int]]:
    """DroneSOP row 목록에 대해 Jira project key를 해석합니다.

    - drone_sop_jira_user_template.user_sdwt_prod 매핑이 존재해야 합니다.
    - project key는 DroneSopJiraUserTemplate.jira_key에서 가져옵니다.
    - 매핑이 없으면 해당 row id를 missing_ids로 반환합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 입력 값 수집
    # -------------------------------------------------------------------------
    user_sdwt_prod_values: set[str] = set()
    for row in rows:
        user_sdwt_prod = row.get("user_sdwt_prod")
        if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
            user_sdwt_prod_values.add(user_sdwt_prod.strip())

    # -------------------------------------------------------------------------
    # 2) 프로젝트 키 매핑 조회
    # -------------------------------------------------------------------------
    jira_keys_by_user_sdwt = selectors.list_drone_sop_jira_project_keys_by_user_sdwt_prod(
        user_sdwt_prod_values=user_sdwt_prod_values,
    )

    project_key_by_id: dict[int, str] = {}
    missing_ids: list[int] = []

    # -------------------------------------------------------------------------
    # 3) row별 project_key 해석
    # -------------------------------------------------------------------------
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int):
            continue
        project_key = _resolve_project_key_for_row(
            row=row,
            jira_keys_by_user_sdwt=jira_keys_by_user_sdwt,
        )
        if not project_key:
            missing_ids.append(rid)
            continue
        project_key_by_id[rid] = project_key

    return project_key_by_id, missing_ids


def _resolve_template_keys_for_rows(
    *,
    rows: Sequence[dict[str, Any]],
) -> tuple[dict[int, str], list[int]]:
    """DroneSOP row 목록에 대해 Jira 템플릿 키를 해석합니다."""

    # -------------------------------------------------------------------------
    # 1) 입력 값 수집
    # -------------------------------------------------------------------------
    user_sdwt_prod_values: set[str] = set()
    for row in rows:
        user_sdwt_prod = row.get("user_sdwt_prod")
        if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
            user_sdwt_prod_values.add(user_sdwt_prod.strip())

    # -------------------------------------------------------------------------
    # 2) 템플릿 매핑 조회
    # -------------------------------------------------------------------------
    template_keys_by_user_sdwt = selectors.list_drone_sop_jira_templates_by_user_sdwt_prods(
        user_sdwt_prod_values=user_sdwt_prod_values,
    )

    template_key_by_id: dict[int, str] = {}
    missing_ids: list[int] = []

    # -------------------------------------------------------------------------
    # 3) row별 템플릿 키 해석
    # -------------------------------------------------------------------------
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int):
            continue
        template_key = _resolve_template_key_for_row(
            row=row,
            template_keys_by_user_sdwt=template_keys_by_user_sdwt,
        )
        if not template_key:
            missing_ids.append(rid)
            continue
        template_key_by_id[rid] = template_key

    return template_key_by_id, missing_ids


def _resolve_template_key_for_row(
    *,
    row: dict[str, Any],
    template_keys_by_user_sdwt: dict[str, str],
) -> str | None:
    """단일 DroneSOP row에 대한 Jira 템플릿 키를 반환합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).
        template_keys_by_user_sdwt: user_sdwt_prod → template_key (소속별 템플릿 키).

    반환:
        template_key 문자열 또는 None.

    부작용:
        없음. 순수 조회입니다.
    """

    # -------------------------------------------------------------------------
    # 1) user_sdwt_prod 우선 적용
    # -------------------------------------------------------------------------
    user_sdwt_prod = row.get("user_sdwt_prod")
    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        normalized_user = user_sdwt_prod.strip()
        template_key = template_keys_by_user_sdwt.get(normalized_user)
        if isinstance(template_key, str) and template_key.strip():
            normalized_key = template_key.strip()
            if normalized_key in TEMPLATE_SOURCES:
                return normalized_key
            return None

    # -------------------------------------------------------------------------
    # 2) 매핑 누락 시 None 반환
    # -------------------------------------------------------------------------
    return None


def _resolve_project_key_for_row(
    *,
    row: dict[str, Any],
    jira_keys_by_user_sdwt: dict[str, str | None],
) -> str | None:
    """단일 DroneSOP row에 대한 Jira project key를 반환합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).
        jira_keys_by_user_sdwt: user_sdwt_prod → jira_key (프로젝트 키).

    반환:
        jira_key 문자열 또는 None.

    부작용:
        없음. 순수 조회입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 필수 필드 검증
    # -------------------------------------------------------------------------
    user_sdwt_prod = row.get("user_sdwt_prod")
    if not isinstance(user_sdwt_prod, str) or not user_sdwt_prod.strip():
        return None

    # -------------------------------------------------------------------------
    # 2) 매핑 조회
    # -------------------------------------------------------------------------
    normalized_user_sdwt_prod = user_sdwt_prod.strip()
    project_key = jira_keys_by_user_sdwt.get(normalized_user_sdwt_prod)
    if not isinstance(project_key, str) or not project_key.strip():
        return None
    return project_key.strip()
