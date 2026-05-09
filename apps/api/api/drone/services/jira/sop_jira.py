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
from django.utils import timezone

from ... import selectors
from ...models import DroneSOP, DroneSopChannelDelivery, DroneSopTarget
from ..shared.delivery_state import (
    ensure_channel_delivery_snapshots_for_rows,
    filter_delivery_ids_for_config_failure,
    mark_channel_delivery_status,
    normalize_positive_ids,
)
from ..shared.policy import (
    REASON_CONFIG_MISSING,
    REASON_SEND_FAILED,
    mark_missing_target_as_failed,
)
from ..shared.utils import _advisory_lock
from .client import _jira_session
from .config import DroneCtttmConfig, DroneJiraConfig
from .delivery import (
    _bulk_create_jira_issues,
    _enrich_rows_with_ctttm_urls,
    _single_create_jira_issues,
)
from .delivery_preparation import collect_jira_delivery_rows as _collect_jira_delivery_rows

logger = logging.getLogger(__name__)


def _normalize_string_value(value: Any) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


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


def _update_drone_sop_jira_summary(
    *,
    delivery_ids: Sequence[int],
    key_by_delivery_id: dict[int, str] | None = None,
    step_by_delivery_id: dict[int, str] | None = None,
) -> int:
    """Jira delivery 성공 메타데이터를 delivery row에 반영합니다."""

    # -------------------------------------------------------------------------
    # 1) delivery → SOP 매핑 확인
    # -------------------------------------------------------------------------
    normalized_delivery_ids = normalize_positive_ids(delivery_ids)
    if not normalized_delivery_ids:
        return 0

    delivery_rows = list(
        DroneSopChannelDelivery.objects.filter(id__in=normalized_delivery_ids).values("id", "sop_id")
    )
    if not delivery_rows:
        return 0

    # -------------------------------------------------------------------------
    # 2) 단계/키 매핑 구성
    # -------------------------------------------------------------------------
    step_source = step_by_delivery_id or {}
    sop_ids: list[int] = []
    step_by_id: dict[int, str] = {}
    for row in delivery_rows:
        delivery_id = row.get("id")
        sop_id = row.get("sop_id")
        if not isinstance(delivery_id, int) or not isinstance(sop_id, int):
            continue
        if sop_id not in sop_ids:
            sop_ids.append(sop_id)
        step = step_source.get(delivery_id)
        if isinstance(step, str) and step.strip():
            step_by_id[delivery_id] = step.strip()
    if not sop_ids:
        return 0

    # -------------------------------------------------------------------------
    # 3) delivery별 step snapshot 보정
    # -------------------------------------------------------------------------
    with transaction.atomic():
        for delivery_id, sent_step in step_by_id.items():
            DroneSopChannelDelivery.objects.filter(id=delivery_id).update(
                sent_step=sent_step,
                updated_at=timezone.now(),
            )
    return len(sop_ids)


def _update_drone_sop_jira_status(
    *,
    done_ids: Sequence[int],
    rows: Sequence[dict[str, Any]],
    key_by_id: dict[int, str],
) -> int:
    """Jira 생성 완료된 SOP의 Jira delivery를 성공으로 표시합니다."""

    normalized_done_ids = normalize_positive_ids(list(done_ids))
    if not normalized_done_ids:
        return 0

    candidate_rows = [row for row in rows if isinstance(row.get("id"), int) and int(row["id"]) in normalized_done_ids]
    if not candidate_rows:
        return 0

    ensure_channel_delivery_snapshots_for_rows(
        rows=list(candidate_rows),
        channels=[DroneSopChannelDelivery.Channels.JIRA],
    )
    pending_delivery_rows = list(
        DroneSopChannelDelivery.objects.filter(
            sop_id__in=normalized_done_ids,
            channel=DroneSopChannelDelivery.Channels.JIRA,
        )
        .exclude(status=DroneSopChannelDelivery.Statuses.SUCCESS)
        .order_by("sop_id", "id")
        .values("id", "sop_id")
    )
    if not pending_delivery_rows:
        legacy_target = DroneSopTarget.get_or_create_by_name(target_user_sdwt_prod="__legacy_target__")
        DroneSopChannelDelivery.objects.bulk_create(
            [
                DroneSopChannelDelivery(
                    sop_id=sop_id,
                    target=legacy_target,
                    channel=DroneSopChannelDelivery.Channels.JIRA,
                    status=DroneSopChannelDelivery.Statuses.PENDING,
                )
                for sop_id in normalized_done_ids
            ],
            ignore_conflicts=True,
        )
        pending_delivery_rows = list(
            DroneSopChannelDelivery.objects.filter(
                sop_id__in=normalized_done_ids,
                channel=DroneSopChannelDelivery.Channels.JIRA,
            )
            .exclude(status=DroneSopChannelDelivery.Statuses.SUCCESS)
            .order_by("sop_id", "id")
            .values("id", "sop_id")
        )
    if not pending_delivery_rows:
        return 0

    delivery_ids = [int(row["id"]) for row in pending_delivery_rows if isinstance(row.get("id"), int)]
    key_by_delivery_id = {
        int(row["id"]): key_by_id[int(row["sop_id"])]
        for row in pending_delivery_rows
        if isinstance(row.get("id"), int)
        and isinstance(row.get("sop_id"), int)
        and isinstance(key_by_id.get(int(row["sop_id"])), str)
    }
    step_by_sop_id: dict[int, str] = {}
    for row in candidate_rows:
        sop_id = int(row["id"])
        step = _normalize_string_value(row.get("metro_current_step"))
        if step:
            step_by_sop_id[sop_id] = step
    step_by_delivery_id = {
        int(row["id"]): step_by_sop_id[int(row["sop_id"])]
        for row in pending_delivery_rows
        if isinstance(row.get("id"), int)
        and isinstance(row.get("sop_id"), int)
        and int(row["sop_id"]) in step_by_sop_id
    }

    mark_channel_delivery_status(
        delivery_ids=delivery_ids,
        status=DroneSopChannelDelivery.Statuses.SUCCESS,
        external_key_by_id=key_by_delivery_id,
    )
    return _update_drone_sop_jira_summary(
        delivery_ids=delivery_ids,
        key_by_delivery_id=key_by_delivery_id,
        step_by_delivery_id=step_by_delivery_id,
    )


def update_drone_sop_jira_status(
    *,
    done_ids: Sequence[int],
    rows: Sequence[dict[str, Any]],
    key_by_id: dict[int, str],
) -> int:
    """Jira 생성 완료된 DroneSOP 상태를 업데이트하는 공개 함수입니다."""

    return _update_drone_sop_jira_status(
        done_ids=done_ids,
        rows=rows,
        key_by_id=key_by_id,
    )


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

        success_delivery = sop.channel_deliveries.filter(
            channel=DroneSopChannelDelivery.Channels.JIRA,
            status=DroneSopChannelDelivery.Statuses.SUCCESS,
        ).order_by("id").first()
        if success_delivery is not None:
            if sop.instant_inform is None or int(sop.instant_inform) != 1:
                sop.instant_inform = 1
                updated_fields["instant_inform"] = 1
                update_fields.append("instant_inform")
            else:
                updated_fields["instant_inform"] = sop.instant_inform

            if update_fields:
                sop.save(update_fields=[*update_fields, "updated_at"])
            jira_key = success_delivery.external_key
            updated_fields["jira_key"] = jira_key
            updated_fields["inform_step"] = success_delivery.sent_step
            informed_at = success_delivery.sent_at
            updated_fields["informed_at"] = informed_at.isoformat() if informed_at else None
            return DroneSopInstantInformResult(
                already_informed=True,
                jira_key=jira_key,
                updated_fields=updated_fields,
            )

        if sop.instant_inform is None or int(sop.instant_inform) != 1:
            sop.instant_inform = 1
            updated_fields["instant_inform"] = 1
            update_fields.append("instant_inform")

        if update_fields:
            sop.save(update_fields=[*update_fields, "updated_at"])

        ensure_channel_delivery_snapshots_for_rows(
            rows=[
                {
                    "id": int(sop.id),
                    "sdwt_prod": sop.sdwt_prod,
                    "user_sdwt_prod": sop.user_sdwt_prod,
                    "status": sop.status,
                    "needtosend": sop.needtosend,
                    "instant_inform": sop.instant_inform,
                }
            ]
        )

    return DroneSopInstantInformResult(
        queued=True,
        updated_fields=updated_fields,
    )


def _run_drone_sop_jira_create_with_rows(
    *,
    rows: list[dict[str, Any]],
    config: DroneJiraConfig,
    pre_resolved_targets: tuple[set[str], list[int]] | None = None,
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
    # 2) delivery snapshot 준비 및 채널 설정 조회
    # ---------------------------------------------------------------------
    snapshot = ensure_channel_delivery_snapshots_for_rows(rows=rows)
    if pre_resolved_targets is None:
        target_values, missing_ids = snapshot.target_user_sdwt_prods, snapshot.missing_sop_ids
    else:
        target_values, missing_ids = pre_resolved_targets

    if missing_ids:
        mark_missing_target_as_failed(
            sop_ids=missing_ids,
            channels=[DroneSopChannelDelivery.Channels.JIRA],
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
    # 3) target/channel delivery 준비
    # ---------------------------------------------------------------------
    prepared = _collect_jira_delivery_rows(
        rows=rows,
        channel_by_target=channel_by_target,
    )

    # ---------------------------------------------------------------------
    # 4) Jira 설정 미구성 상태 처리
    # ---------------------------------------------------------------------
    if not config.base_url:
        mark_channel_delivery_status(
            delivery_ids=filter_delivery_ids_for_config_failure(delivery_ids=prepared.delivery_ids),
            status=DroneSopChannelDelivery.Statuses.FAILED,
            reason=REASON_CONFIG_MISSING,
        )
        return DroneSopJiraCreateResult(
            candidates=candidate_count,
            created=0,
            updated_rows=0,
            skipped=True,
            skip_reason="jira_disabled",
        )

    if not prepared.rows_to_send:
        return DroneSopJiraCreateResult(candidates=candidate_count, created=0, updated_rows=0)

    _enrich_rows_with_ctttm_urls(rows=prepared.rows_to_send, config=DroneCtttmConfig.from_settings())

    # ---------------------------------------------------------------------
    # 5) Jira API 호출
    # ---------------------------------------------------------------------
    done_delivery_ids, key_by_delivery_id = _run_jira_create_api(
        rows=prepared.rows_to_send,
        config=config,
        project_key_by_id=prepared.project_key_by_delivery_id,
        template_key_by_id=prepared.template_key_by_delivery_id,
    )
    normalized_done_delivery_ids = normalize_positive_ids(done_delivery_ids)
    attempted_delivery_ids = normalize_positive_ids(
        [int(row["delivery_id"]) for row in prepared.rows_to_send if isinstance(row.get("delivery_id"), int)]
    )
    failed_delivery_ids = [delivery_id for delivery_id in attempted_delivery_ids if delivery_id not in normalized_done_delivery_ids]
    mark_channel_delivery_status(
        delivery_ids=failed_delivery_ids,
        status=DroneSopChannelDelivery.Statuses.FAILED,
        reason=REASON_SEND_FAILED,
    )
    mark_channel_delivery_status(
        delivery_ids=normalized_done_delivery_ids,
        status=DroneSopChannelDelivery.Statuses.SUCCESS,
        external_key_by_id=key_by_delivery_id,
    )

    # ---------------------------------------------------------------------
    # 6) 상태 업데이트 및 결과 반환
    # ---------------------------------------------------------------------
    _update_drone_sop_jira_summary(
        delivery_ids=normalized_done_delivery_ids,
        key_by_delivery_id=key_by_delivery_id,
        step_by_delivery_id=prepared.step_by_delivery_id,
    )
    updated_rows = len(
        {
            prepared.sop_id_by_delivery_id[delivery_id]
            for delivery_id in normalized_done_delivery_ids
            if delivery_id in prepared.sop_id_by_delivery_id
        }
    )
    return DroneSopJiraCreateResult(
        candidates=candidate_count,
        created=len(normalized_done_delivery_ids),
        updated_rows=updated_rows,
    )


def run_drone_sop_jira_create_from_rows(
    *,
    rows: Sequence[dict[str, Any]],
    pre_resolved_targets: tuple[set[str], list[int]] | None = None,
) -> DroneSopJiraCreateResult:
    """전달받은 row 목록으로 Jira 생성 파이프라인을 실행합니다.

    인자:
        rows: Jira 후보 row 목록(delivery pending 기준).
        pre_resolved_targets: 상위 레이어에서 계산한
            (target_user_sdwt_prod 집합, 누락 sop_id 목록) 튜플(옵션).

    반환:
        DroneSopJiraCreateResult 결과 객체.

    부작용:
        - advisory lock 획득
        - Jira API 호출 및 delivery/legacy 요약 상태 업데이트
    """

    # ---------------------------------------------------------------------
    # 1) 전달된 후보 row 정규화
    # ---------------------------------------------------------------------
    pending_rows = [row for row in rows if isinstance(row, dict)]
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
        return _run_drone_sop_jira_create_with_rows(
            rows=pending_rows,
            config=config,
            pre_resolved_targets=pre_resolved_targets,
        )


def run_drone_sop_jira_create_from_env(*, limit: int | None = None) -> DroneSopJiraCreateResult:
    """Jira delivery pending 또는 snapshot 미생성 대상 이슈를 생성합니다.

    인자:
        limit: 최대 처리 건수(옵션).

    반환:
        DroneSopJiraCreateResult 결과 객체.

    부작용:
        - Jira API 호출
        - delivery 상태 및 표시용 Jira 요약 컬럼 업데이트

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
        return _run_drone_sop_jira_create_with_rows(
            rows=selectors.list_drone_sop_jira_candidates(limit=limit),
            config=config,
        )


__all__ = [
    "DroneSopInstantInformResult",
    "DroneSopJiraCreateResult",
    "enqueue_drone_sop_jira_instant_inform",
    "run_drone_sop_jira_create_from_env",
    "run_drone_sop_jira_create_from_rows",
    "update_drone_sop_jira_status",
]
