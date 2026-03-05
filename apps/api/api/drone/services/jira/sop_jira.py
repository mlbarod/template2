# =============================================================================
# 모듈: Drone SOP Jira 연동 서비스
# 주요 기능: Jira 이슈 생성(배치) 및 즉시인폼 체크, 템플릿 렌더링
# 주요 가정: Jira/CTTTM 설정은 settings/env에서 주입됩니다.
# =============================================================================
"""Drone SOP Jira 연동 헬퍼 모듈입니다."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

from django.db import transaction
from django.db.models import Case, CharField, DateTimeField, F, Value, When
from django.utils import timezone

from ... import selectors
from ...models import DroneSOP
from ..shared.notify_resolver import resolve_target_user_sdwt_prod_values
from ..shared.policy import (
    REASON_CHANNEL_CONFIG_INVALID,
    REASON_CHANNEL_CONFIG_MISSING,
    REASON_CONFIG_MISSING,
    REASON_DISABLED_BY_POLICY,
    mark_missing_target_as_failed,
    mark_pending_channels_as_disabled,
    mark_pending_channels_as_failed,
)
from ..shared.utils import _advisory_lock
from .channel import resolve_jira_channel_plan
from .client import _jira_session
from .config import DroneCtttmConfig, DroneJiraConfig
from .delivery import (
    _bulk_create_jira_issues,
    _enrich_rows_with_ctttm_urls,
    _single_create_jira_issues,
)
from .templates.jira_template_registry import TEMPLATE_SOURCES

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
        "jira_reason": None,
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
    # 4) 데이터베이스 업데이트 실행
    # -------------------------------------------------------------------------
    with transaction.atomic():
        updated = DroneSOP.objects.filter(id__in=list(done_ids)).update(**updates)
    return int(updated or 0)


def _collect_rows_to_send(
    *,
    rows: Sequence[dict[str, Any]],
    project_key_by_id: dict[int, str],
    template_key_by_id: dict[int, str],
) -> list[dict[str, Any]]:
    """채널 매핑이 유효한 Jira 전송 대상 row만 반환합니다."""

    rows_to_send: list[dict[str, Any]] = []
    for row in rows:
        row_id = row.get("id")
        if not isinstance(row_id, int):
            continue
        if row_id not in project_key_by_id:
            continue
        if row_id not in template_key_by_id:
            continue
        rows_to_send.append(row)
    return rows_to_send


def _run_jira_create_api(
    *,
    rows: Sequence[dict[str, Any]],
    config: DroneJiraConfig,
    project_key_by_id: dict[int, str],
    template_key_by_id: dict[int, str],
) -> tuple[list[int], dict[int, str]]:
    """Jira 생성 API(벌크/단건)를 실행합니다."""

    session = _jira_session(config)
    try:
        if config.use_bulk_api:
            return _bulk_create_jira_issues(
                rows=rows,
                config=config,
                session=session,
                project_key_by_id=project_key_by_id,
                template_key_by_id=template_key_by_id,
            )
        return _single_create_jira_issues(
            rows=rows,
            config=config,
            session=session,
            project_key_by_id=project_key_by_id,
            template_key_by_id=template_key_by_id,
        )
    finally:
        session.close()


def _mark_pending_jira_when_disabled(
    *,
    rows: Sequence[dict[str, Any]],
    channel_by_target: dict[str, dict[str, str | bool | int | None]],
) -> None:
    """Jira 설정 미구성 상태에서 대기 행을 비활성/실패로 마킹합니다."""

    disabled_ids: list[int] = []
    failed_ids: list[int] = []

    for row in rows:
        row_id = row.get("id")
        if not isinstance(row_id, int):
            continue
        target = row.get("target_user_sdwt_prod")
        config_row = channel_by_target.get(target.strip()) if isinstance(target, str) and target.strip() else None
        if config_row and not bool(config_row.get("jira_enabled", True)):
            disabled_ids.append(row_id)
            continue
        failed_ids.append(row_id)

    if disabled_ids:
        mark_pending_channels_as_disabled(
            sop_ids=disabled_ids,
            channel_fields=["send_jira"],
            disable_reason=REASON_DISABLED_BY_POLICY,
        )
    if failed_ids:
        mark_pending_channels_as_failed(
            sop_ids=failed_ids,
            channel_fields=["send_jira"],
            failure_reason=REASON_CONFIG_MISSING,
        )


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
        - comment/instant_inform 상태 업데이트(필요 시)

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
            if sop.instant_inform is None or int(sop.instant_inform) != 1:
                sop.instant_inform = 1
                updated_fields["instant_inform"] = 1
                update_fields.append("instant_inform")
            else:
                updated_fields["instant_inform"] = sop.instant_inform

            if update_fields:
                sop.save(update_fields=[*update_fields, "updated_at"])
            updated_fields["send_jira"] = sop.send_jira
            updated_fields["jira_key"] = sop.jira_key
            updated_fields["inform_step"] = sop.inform_step
            updated_fields["informed_at"] = sop.informed_at.isoformat() if sop.informed_at else None
            return DroneSopInstantInformResult(
                already_informed=True,
                jira_key=sop.jira_key,
                updated_fields=updated_fields,
            )

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


def _is_pending_send_jira(value: Any) -> bool:
    """send_jira가 미전송(0/NULL) 상태인지 확인합니다."""

    if value is None:
        return True
    try:
        return int(value) == 0
    except (TypeError, ValueError):
        return False


def _run_drone_sop_jira_create_with_rows(
    *,
    rows: list[dict[str, Any]],
    config: DroneJiraConfig,
) -> DroneSopJiraCreateResult:
    """락 획득 후 Jira 생성 로직 본체를 실행합니다."""

    # ---------------------------------------------------------------------
    # 1) 대상 행 유효성 확인
    # ---------------------------------------------------------------------
    if not rows:
        return DroneSopJiraCreateResult(
            candidates=0,
            created=0,
            updated_rows=0,
            skipped=True,
            skip_reason="no_candidates",
        )
    candidate_count = len(rows)

    # ---------------------------------------------------------------------
    # 2) target_user_sdwt_prod 해석 및 채널 설정 조회
    # ---------------------------------------------------------------------
    target_values, missing_ids = resolve_target_user_sdwt_prod_values(rows=rows)
    if missing_ids:
        mark_missing_target_as_failed(
            sop_ids=missing_ids,
            channel_fields=["send_jira"],
        )
        missing_id_set = set(missing_ids)
        rows = [
            row
            for row in rows
            if isinstance(row.get("id"), int) and row.get("id") not in missing_id_set
        ]
    if not rows:
        return DroneSopJiraCreateResult(
            candidates=candidate_count,
            created=0,
            updated_rows=0,
            skipped=True,
            skip_reason="no_valid_targets",
        )

    channel_by_target = selectors.list_drone_sop_user_sdwt_channels_by_targets(
        target_user_sdwt_prod_values=target_values,
    )

    # ---------------------------------------------------------------------
    # 3) Jira 설정 미구성 상태 처리
    # ---------------------------------------------------------------------
    if not config.base_url:
        _mark_pending_jira_when_disabled(
            rows=rows,
            channel_by_target=channel_by_target,
        )
        return DroneSopJiraCreateResult(
            candidates=candidate_count,
            created=0,
            updated_rows=0,
            skipped=True,
            skip_reason="jira_disabled",
        )

    # ---------------------------------------------------------------------
    # 4) 채널 계획 해석 및 유효 대상 필터링
    # ---------------------------------------------------------------------
    plan = resolve_jira_channel_plan(
        rows=rows,
        channel_by_target=channel_by_target,
        template_sources=TEMPLATE_SOURCES,
    )
    if plan.skip_ids:
        logger.info("Mark Jira rows without channel config as failed: %s", len(plan.skip_ids))
    mark_pending_channels_as_failed(
        sop_ids=plan.skip_ids,
        channel_fields=["send_jira"],
        failure_reason=REASON_CHANNEL_CONFIG_MISSING,
    )
    if plan.invalid_ids:
        logger.warning("Invalid Jira config for %s drone_sop rows", len(plan.invalid_ids))
    mark_pending_channels_as_failed(
        sop_ids=plan.invalid_ids,
        channel_fields=["send_jira"],
        failure_reason=REASON_CHANNEL_CONFIG_INVALID,
    )
    mark_pending_channels_as_disabled(
        sop_ids=plan.disabled_ids,
        channel_fields=["send_jira"],
        disable_reason=REASON_DISABLED_BY_POLICY,
    )

    rows_to_send = _collect_rows_to_send(
        rows=rows,
        project_key_by_id=plan.project_key_by_id,
        template_key_by_id=plan.template_key_by_id,
    )
    if not rows_to_send:
        return DroneSopJiraCreateResult(candidates=candidate_count, created=0, updated_rows=0)

    _enrich_rows_with_ctttm_urls(rows=rows_to_send, config=DroneCtttmConfig.from_settings())

    # ---------------------------------------------------------------------
    # 5) Jira API 호출
    # ---------------------------------------------------------------------
    done_ids, key_by_id = _run_jira_create_api(
        rows=rows_to_send,
        config=config,
        project_key_by_id=plan.project_key_by_id,
        template_key_by_id=plan.template_key_by_id,
    )

    # ---------------------------------------------------------------------
    # 6) 상태 업데이트 및 결과 반환
    # ---------------------------------------------------------------------
    updated_rows = _update_drone_sop_jira_status(done_ids=done_ids, rows=rows_to_send, key_by_id=key_by_id)
    return DroneSopJiraCreateResult(
        candidates=candidate_count,
        created=len(done_ids),
        updated_rows=updated_rows,
    )


def run_drone_sop_jira_create_from_rows(*, rows: Sequence[dict[str, Any]]) -> DroneSopJiraCreateResult:
    """전달받은 row 목록으로 Jira 생성 파이프라인을 실행합니다.

    인자:
        rows: Jira 후보 row 목록(미전송 상태만 처리).

    반환:
        DroneSopJiraCreateResult 결과 객체.

    부작용:
        - advisory lock 획득
        - Jira API 호출 및 drone_sop 상태 업데이트
    """

    # ---------------------------------------------------------------------
    # 1) 미전송 Jira 후보만 선별
    # ---------------------------------------------------------------------
    pending_rows = [
        row
        for row in rows
        if isinstance(row, dict) and _is_pending_send_jira(row.get("send_jira"))
    ]
    if not pending_rows:
        return DroneSopJiraCreateResult(
            candidates=0,
            created=0,
            updated_rows=0,
            skipped=True,
            skip_reason="no_candidates",
        )

    # ---------------------------------------------------------------------
    # 2) 공통 락으로 실행
    # ---------------------------------------------------------------------
    config = DroneJiraConfig.from_settings()
    with _advisory_lock("drone_sop_jira_create") as acquired:
        if not acquired:
            return DroneSopJiraCreateResult(skipped=True, skip_reason="already_running")
        return _run_drone_sop_jira_create_with_rows(rows=pending_rows, config=config)


def run_drone_sop_jira_create_from_env(*, limit: int | None = None) -> DroneSopJiraCreateResult:
    """send_jira=0 이면서 (needtosend=1 & status=COMPLETE 또는 instant_inform=1)인 대상 Jira 이슈를 생성합니다.

    인자:
        limit: 최대 처리 건수(옵션).

    반환:
        DroneSopJiraCreateResult 결과 객체.

    부작용:
        - Jira API 호출
        - drone_sop 상태 컬럼(send_jira/inform_step/jira_key/informed_at) 업데이트

    오류:
        - Jira API 호출 실패 등 예외가 발생할 수 있습니다.
    """

    # -------------------------------------------------------------------------
    # 1) 설정/락 검증
    # -------------------------------------------------------------------------
    config = DroneJiraConfig.from_settings()
    with _advisory_lock("drone_sop_jira_create") as acquired:
        if not acquired:
            return DroneSopJiraCreateResult(skipped=True, skip_reason="already_running")

        # ---------------------------------------------------------------------
        # 2) 대상 행 조회 후 공통 실행 로직 호출
        # ---------------------------------------------------------------------
        rows = selectors.list_drone_sop_jira_candidates(limit=limit)
        return _run_drone_sop_jira_create_with_rows(rows=rows, config=config)


__all__ = [
    "DroneSopInstantInformResult",
    "DroneSopJiraCreateResult",
    "_jira_session",
    "_update_drone_sop_jira_status",
    "enqueue_drone_sop_jira_instant_inform",
    "run_drone_sop_jira_create_from_env",
    "run_drone_sop_jira_create_from_rows",
]
