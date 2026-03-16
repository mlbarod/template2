# =============================================================================
# 모듈: Drone SOP 멀티 채널 알림 서비스
# 주요 기능: Jira/메신저/메일 동시 전송
# 주요 가정: target_user_sdwt_prod 기준으로 채널 설정을 해석합니다.
# =============================================================================
"""Drone SOP 멀티 채널 알림 서비스 모음."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Sequence

from django.db import transaction
from django.db.models import Case, DateTimeField, F, Value, When
from django.utils import timezone

from api.messenger import services as messenger_services

from ... import selectors
from ...models import DroneSOP
from ..channels.user_sdwt_channel import upsert_drone_sop_user_sdwt_channel
from ..jira.config import DroneCtttmConfig
from ..jira.delivery import _enrich_rows_with_ctttm_urls
from ..jira.sop_jira import run_drone_sop_jira_create_from_rows
from ..mail.mail_sender import DroneMailConfig, send_drone_sop_mail
from ..messenger.messenger_api import DroneMessengerConfig, send_drone_sop_messenger_message
from ..shared.channels import (
    REASON_FIELD_BY_SEND_FIELD,
    SEND_FIELD_BY_CHANNEL,
)
from ..shared.utils import _advisory_lock, _parse_int
from ..shared.notify_resolver import resolve_target_user_sdwt_prod_values
from ..shared.policy import (
    REASON_CHANNEL_CONFIG_INVALID,
    REASON_CHANNEL_CONFIG_MISSING,
    REASON_CONFIG_MISSING,
    REASON_DISABLED_BY_POLICY,
    REASON_RECEIVER_NOT_FOUND,
    REASON_SEND_FAILED,
    REASON_TEMPLATE_MISSING,
    mark_missing_target_as_failed,
    mark_pending_channels_as_disabled,
    mark_pending_channels_as_failed,
)

logger = logging.getLogger(__name__)

ChannelConfig = dict[str, str | bool | int | None]
PendingChannelRow = tuple[dict[str, Any], int, ChannelConfig]
_PIPELINE_CHANNEL_FIELDS: tuple[str, ...] = (
    SEND_FIELD_BY_CHANNEL["jira"],
    SEND_FIELD_BY_CHANNEL["messenger"],
    SEND_FIELD_BY_CHANNEL["mail"],
)


def _normalize_positive_ids(values: Sequence[int]) -> list[int]:
    """양의 정수 ID 목록을 중복 없이 정규화합니다."""

    normalized: list[int] = []
    seen: set[int] = set()
    for value in values:
        if not isinstance(value, int) or value <= 0:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _extract_row_id(row: dict[str, Any]) -> int | None:
    """row에서 양의 정수 id를 추출합니다."""

    row_id = row.get("id")
    if isinstance(row_id, int) and row_id > 0:
        return row_id
    return None


def _collect_pending_channel_rows(
    *,
    rows: list[dict[str, Any]],
    channel_by_target: dict[str, ChannelConfig],
    send_field: str,
    enabled_field: str,
) -> tuple[list[PendingChannelRow], list[int], list[int]]:
    """채널 전송 대기 행을 분류합니다.

    반환:
        - ready_rows: (row, sop_id, config_row) 목록
        - disabled_ids: 채널 비활성화로 스킵할 SOP ID 목록
        - missing_config_ids: 채널 설정이 없는 SOP ID 목록
    """

    ready_rows: list[PendingChannelRow] = []
    disabled_ids: list[int] = []
    missing_config_ids: list[int] = []

    for row in rows:
        row_id = _extract_row_id(row)
        if row_id is None:
            continue
        if _normalize_int_flag(row.get(send_field)) != 0:
            continue

        config_row = _resolve_channel_config(row=row, channel_by_target=channel_by_target)
        if not config_row:
            missing_config_ids.append(row_id)
            continue
        if not bool(config_row.get(enabled_field, True)):
            disabled_ids.append(row_id)
            continue

        ready_rows.append((row, row_id, config_row))

    return (
        ready_rows,
        _normalize_positive_ids(disabled_ids),
        _normalize_positive_ids(missing_config_ids),
    )


def _mark_pending_disabled(
    *,
    sop_ids: Sequence[int],
    channel_fields: Sequence[str],
) -> None:
    """대기 상태 채널을 비활성화 사유로 기록합니다."""

    normalized_ids = _normalize_positive_ids(sop_ids)
    if not normalized_ids:
        return
    mark_pending_channels_as_disabled(
        sop_ids=normalized_ids,
        channel_fields=channel_fields,
        disable_reason=REASON_DISABLED_BY_POLICY,
    )


def _mark_pending_failed(
    *,
    sop_ids: Sequence[int],
    channel_fields: Sequence[str],
    failure_reason: str,
) -> None:
    """대기 상태 채널을 실패 사유로 기록합니다."""

    normalized_ids = _normalize_positive_ids(sop_ids)
    if not normalized_ids:
        return
    mark_pending_channels_as_failed(
        sop_ids=normalized_ids,
        channel_fields=channel_fields,
        failure_reason=failure_reason,
    )


def _mark_reason_group_failures(
    *,
    reason_groups: dict[str, list[int]],
    channel_fields: Sequence[str],
) -> None:
    """사유별 실패 그룹을 일괄 반영합니다."""

    for reason, ids in reason_groups.items():
        _mark_pending_failed(
            sop_ids=ids,
            channel_fields=channel_fields,
            failure_reason=reason,
        )


def _mark_channel_success(
    *,
    sop_ids: Sequence[int],
    send_field: str,
) -> None:
    """채널 전송 성공 상태를 저장합니다."""

    normalized_ids = _normalize_positive_ids(sop_ids)
    if not normalized_ids:
        return

    now = timezone.now()
    updates: dict[str, Any] = {
        send_field: 1,
        "informed_at": Case(
            When(informed_at__isnull=True, then=Value(now)),
            default=F("informed_at"),
            output_field=DateTimeField(),
        ),
    }
    reason_field = REASON_FIELD_BY_SEND_FIELD.get(send_field)
    if reason_field:
        updates[reason_field] = None

    with transaction.atomic():
        DroneSOP.objects.filter(id__in=normalized_ids).update(**updates)


@dataclass(frozen=True)
class DroneSopInformResult:
    """Drone SOP 멀티 채널 알림 실행 결과."""

    candidates: int = 0
    jira_created: int = 0
    jira_updated_rows: int = 0
    messenger_sent: int = 0
    mail_sent: int = 0
    skipped: bool = False
    skip_reason: str | None = None


def _normalize_int_flag(value: Any) -> int:
    """상태 플래그를 정수로 정규화합니다."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _resolve_channel_config(
    *,
    row: dict[str, Any],
    channel_by_target: dict[str, ChannelConfig],
) -> ChannelConfig | None:
    """row 기준 채널 설정을 조회합니다."""

    target = _normalize_target_lookup_key(row.get("target_user_sdwt_prod"))
    if not target:
        return None
    return channel_by_target.get(target)


def _normalize_string_value(value: Any) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _normalize_target_lookup_key(value: Any) -> str | None:
    """대소문자 비구분 채널 조회용 target 키를 정규화합니다."""

    cleaned = _normalize_string_value(value)
    if not cleaned:
        return None
    return cleaned.casefold()


def _normalize_chatroom_id(value: Any) -> int | None:
    """채팅룸 ID 값을 정수로 정규화합니다."""

    parsed = _parse_int(value, 0)
    if parsed <= 0:
        return None
    return parsed


def _normalize_unique_strings(values: list[str]) -> list[str]:
    """문자열 목록을 공백 제거 후 중복 없이 정규화합니다."""

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _normalize_string_value(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _build_drone_sop_chatroom_title(*, target_user_sdwt_prod: str) -> str:
    """Drone SOP 메신저 채팅방 제목을 생성합니다."""

    return f"Drone SOP - {target_user_sdwt_prod}"


def _get_or_create_chatroom_id(
    *,
    row: dict[str, Any],
    config_row: ChannelConfig,
    channel_by_target: dict[str, ChannelConfig],
    messenger_config: DroneMessengerConfig,
) -> tuple[int | None, str | None]:
    """chatroom_id가 비어 있을 때 채팅방을 생성하고 ID를 저장합니다.

    인자:
        row: Drone SOP 행 dict.
        config_row: target_user_sdwt_prod 기준 채널 설정 dict.
        channel_by_target: target_user_sdwt_prod별 채널 설정 캐시.
        messenger_config: 메신저 설정 객체.

    반환:
        (생성/조회된 chatroom_id, 실패 사유 코드) 튜플.

    부작용:
        - Knox API로 userID 조회/채팅방 생성 호출이 발생합니다.
        - 생성 성공 시 drone_sop_user_sdwt_channel.chatroom_id를 갱신합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 소속/기존 ID 확인
    # -----------------------------------------------------------------------------
    target = _normalize_string_value(row.get("target_user_sdwt_prod"))
    if not target:
        return None, REASON_CHANNEL_CONFIG_MISSING

    existing_chatroom_id = _normalize_chatroom_id(config_row.get("chatroom_id"))
    if existing_chatroom_id:
        return existing_chatroom_id, None

    # -----------------------------------------------------------------------------
    # 2) 수신자 knox_id 조회
    # -----------------------------------------------------------------------------
    receiver_knox_ids = selectors.list_messenger_receiver_knox_ids_for_user_sdwt_prod(
        user_sdwt_prod=target,
    )
    normalized_knox_ids = _normalize_unique_strings(receiver_knox_ids)
    if not normalized_knox_ids:
        logger.info("Skip messenger room create: receiver knox_id not found (target=%s)", target)
        return None, REASON_RECEIVER_NOT_FOUND

    # -----------------------------------------------------------------------------
    # 3) Knox userID 해석
    # -----------------------------------------------------------------------------
    resolved_user_ids = messenger_services.resolve_user_ids_by_single_ids(
        single_ids=normalized_knox_ids,
        config=messenger_config.knox_config,
    )
    normalized_user_ids = _normalize_unique_strings(resolved_user_ids)
    if not normalized_user_ids:
        logger.info("Skip messenger room create: receiver userID not found (target=%s)", target)
        return None, REASON_RECEIVER_NOT_FOUND

    # -----------------------------------------------------------------------------
    # 4) 채팅방 생성
    # -----------------------------------------------------------------------------
    chatroom_id = messenger_services.create_chatroom(
        user_ids=normalized_user_ids,
        title=_build_drone_sop_chatroom_title(target_user_sdwt_prod=target),
        config=messenger_config.knox_config,
    )

    # -----------------------------------------------------------------------------
    # 5) 채널 설정 영속화 + 캐시 갱신
    # -----------------------------------------------------------------------------
    upsert_drone_sop_user_sdwt_channel(
        target_user_sdwt_prod=target,
        chatroom_id=chatroom_id,
    )
    # ready_rows가 기존 config_row 참조를 들고 있으므로, 같은 target 재처리 시
    # 즉시 재사용되도록 in-place 갱신합니다.
    config_row["chatroom_id"] = chatroom_id
    channel_by_target[target] = config_row
    return chatroom_id, None


def _filter_rows_by_excluded_ids(*, rows: list[dict[str, Any]], excluded_ids: Sequence[int]) -> list[dict[str, Any]]:
    """제외할 SOP ID를 기준으로 row 목록을 필터링합니다."""

    excluded_set = set(_normalize_positive_ids(excluded_ids))
    if not excluded_set:
        return rows
    return [
        row
        for row in rows
        if (row_id := _extract_row_id(row)) is not None and row_id not in excluded_set
    ]


def _run_jira_inform(
    *,
    rows: list[dict[str, Any]],
    pre_resolved_targets: tuple[set[str], list[int]] | None = None,
) -> tuple[int, int]:
    """Jira 채널 전송을 처리합니다.

    - Jira 실행 경로는 `sop_jira.run_drone_sop_jira_create_from_rows`로 단일화합니다.
    - Jira 채널 예외가 발생해도 메신저/메일 채널은 계속 진행할 수 있도록 격리합니다.
    """

    jira_rows = [row for row in rows if _normalize_int_flag(row.get("send_jira")) == 0]
    if not jira_rows:
        return 0, 0

    try:
        result = run_drone_sop_jira_create_from_rows(
            rows=jira_rows,
            pre_resolved_targets=pre_resolved_targets,
        )
    except Exception:
        # Jira 상태 갱신 책임은 sop_jira 서비스에 두고, inform은 채널 격리만 담당합니다.
        logger.exception("Drone SOP Jira pipeline failed during inform run")
        return 0, 0

    return int(result.created or 0), int(result.updated_rows or 0)


def _run_messenger_inform(
    *,
    rows: list[dict[str, Any]],
    channel_by_target: dict[str, ChannelConfig],
) -> int:
    """메신저 채널 전송을 처리합니다."""

    messenger_config = DroneMessengerConfig.from_settings()
    ready_rows, disabled_ids, missing_config_ids = _collect_pending_channel_rows(
        rows=rows,
        channel_by_target=channel_by_target,
        send_field="send_messenger",
        enabled_field="messenger_enabled",
    )

    if not messenger_config.is_ready():
        _mark_pending_disabled(sop_ids=disabled_ids, channel_fields=["send_messenger"])
        _mark_pending_failed(
            sop_ids=[*missing_config_ids, *[row_id for _, row_id, _ in ready_rows]],
            channel_fields=["send_messenger"],
            failure_reason=REASON_CONFIG_MISSING,
        )
        logger.info("Skip messenger send: KNOX_MESSENGER_API_BASE_URL/AUTHORIZATION/SYSTEM_ID 미설정")
        return 0

    success_ids: list[int] = []
    failed_reason_groups: dict[str, list[int]] = {}
    if missing_config_ids:
        failed_reason_groups[REASON_CHANNEL_CONFIG_MISSING] = [*missing_config_ids]

    for row, row_id, config_row in ready_rows:
        messenger_template_key = _normalize_string_value(config_row.get("messenger_template_key"))
        if not messenger_template_key:
            failed_reason_groups.setdefault(REASON_TEMPLATE_MISSING, []).append(row_id)
            continue

        chatroom_id = _normalize_chatroom_id(config_row.get("chatroom_id"))
        create_reason: str | None = None
        if not chatroom_id:
            try:
                chatroom_id, create_reason = _get_or_create_chatroom_id(
                    row=row,
                    config_row=config_row,
                    channel_by_target=channel_by_target,
                    messenger_config=messenger_config,
                )
            except Exception:
                logger.exception("Messenger room create failed (sop_id=%s)", row_id)
                chatroom_id = None
                create_reason = REASON_SEND_FAILED

        if not chatroom_id:
            failed_reason_groups.setdefault(create_reason or REASON_CHANNEL_CONFIG_INVALID, []).append(row_id)
            continue

        try:
            send_drone_sop_messenger_message(
                row=row,
                chatroom_id=chatroom_id,
                messenger_template_key=messenger_template_key,
                config=messenger_config,
            )
            success_ids.append(row_id)
        except Exception:
            logger.exception("Messenger send failed (sop_id=%s)", row_id)
            failed_reason_groups.setdefault(REASON_SEND_FAILED, []).append(row_id)

    _mark_channel_success(sop_ids=success_ids, send_field="send_messenger")
    _mark_pending_disabled(sop_ids=disabled_ids, channel_fields=["send_messenger"])
    _mark_reason_group_failures(
        reason_groups=failed_reason_groups,
        channel_fields=["send_messenger"],
    )
    return len(_normalize_positive_ids(success_ids))


def _run_mail_inform(
    *,
    rows: list[dict[str, Any]],
    channel_by_target: dict[str, ChannelConfig],
) -> int:
    """메일 채널 전송을 처리합니다."""

    mail_config = DroneMailConfig.from_settings()
    ready_rows, disabled_ids, missing_config_ids = _collect_pending_channel_rows(
        rows=rows,
        channel_by_target=channel_by_target,
        send_field="send_mail",
        enabled_field="mail_enabled",
    )

    if not mail_config.sender_email:
        _mark_pending_disabled(sop_ids=disabled_ids, channel_fields=["send_mail"])
        _mark_pending_failed(
            sop_ids=[*missing_config_ids, *[row_id for _, row_id, _ in ready_rows]],
            channel_fields=["send_mail"],
            failure_reason=REASON_CONFIG_MISSING,
        )
        logger.info("Skip mail send: DRONE_MAIL_SENDER 미설정")
        return 0

    success_ids: list[int] = []
    failed_reason_groups: dict[str, list[int]] = {}
    if missing_config_ids:
        failed_reason_groups[REASON_CHANNEL_CONFIG_MISSING] = [*missing_config_ids]

    for row, row_id, config_row in ready_rows:
        template_key = _normalize_string_value(config_row.get("mail_template_key"))
        if not template_key:
            failed_reason_groups.setdefault(REASON_TEMPLATE_MISSING, []).append(row_id)
            continue

        target_user_sdwt_prod = _normalize_string_value(row.get("target_user_sdwt_prod")) or ""
        receiver_emails = selectors.list_mail_receiver_emails_for_user_sdwt_prod(
            user_sdwt_prod=target_user_sdwt_prod,
        )
        if not receiver_emails:
            failed_reason_groups.setdefault(REASON_RECEIVER_NOT_FOUND, []).append(row_id)
            continue

        try:
            send_drone_sop_mail(
                row=row,
                template_key=template_key,
                receiver_emails=receiver_emails,
                config=mail_config,
            )
            success_ids.append(row_id)
        except Exception:
            logger.exception("Mail send failed (sop_id=%s)", row_id)
            failed_reason_groups.setdefault(REASON_SEND_FAILED, []).append(row_id)

    _mark_channel_success(sop_ids=success_ids, send_field="send_mail")
    _mark_pending_disabled(sop_ids=disabled_ids, channel_fields=["send_mail"])
    _mark_reason_group_failures(
        reason_groups=failed_reason_groups,
        channel_fields=["send_mail"],
    )
    return len(_normalize_positive_ids(success_ids))


def has_drone_sop_pipeline_candidates() -> bool:
    """통합 파이프라인 대상 Drone SOP 후보 존재 여부를 반환합니다."""

    return selectors.has_drone_sop_pipeline_candidates()


def run_drone_sop_pipeline_from_env(
    *,
    limit: int | None = None,
) -> DroneSopInformResult:
    """Jira/메신저/메일 고정 채널로 Drone SOP 파이프라인을 실행합니다."""

    channel_fields = _PIPELINE_CHANNEL_FIELDS

    # -------------------------------------------------------------------------
    # 1) 락 확보
    # -------------------------------------------------------------------------
    with _advisory_lock("drone_sop_pipeline_create") as acquired:
        if not acquired:
            return DroneSopInformResult(skipped=True, skip_reason="already_running")

        # ---------------------------------------------------------------------
        # 2) 통합 채널 기준 후보 조회
        # ---------------------------------------------------------------------
        rows = selectors.list_drone_sop_pipeline_candidates(limit=limit)
        if not rows:
            return DroneSopInformResult(candidates=0, skipped=True, skip_reason="no_candidates")

        candidate_count = len(rows)

        # ---------------------------------------------------------------------
        # 3) target_user_sdwt_prod 해석/저장 및 누락 처리
        # ---------------------------------------------------------------------
        targets, missing_ids = resolve_target_user_sdwt_prod_values(rows=rows, persist=True)
        if missing_ids:
            mark_missing_target_as_failed(
                sop_ids=missing_ids,
                channel_fields=channel_fields,
            )
            rows = _filter_rows_by_excluded_ids(rows=rows, excluded_ids=missing_ids)
        if not rows:
            return DroneSopInformResult(
                candidates=candidate_count,
                skipped=True,
                skip_reason="no_valid_targets",
            )

        # ---------------------------------------------------------------------
        # 4) Jira 채널 처리
        # ---------------------------------------------------------------------
        jira_created, jira_updated_rows = _run_jira_inform(
            rows=rows,
            pre_resolved_targets=(targets, []),
        )

        # ---------------------------------------------------------------------
        # 5) 메신저/메일 공통 컨텍스트 처리
        # ---------------------------------------------------------------------
        channel_by_target = selectors.list_drone_sop_user_sdwt_channels_by_targets(
            target_user_sdwt_prod_values=targets,
        )
        _enrich_rows_with_ctttm_urls(rows=rows, config=DroneCtttmConfig.from_settings())

        # ---------------------------------------------------------------------
        # 6) 메신저/메일 채널 처리(예외 격리)
        # ---------------------------------------------------------------------
        messenger_sent = 0
        try:
            messenger_sent = _run_messenger_inform(
                rows=rows,
                channel_by_target=channel_by_target,
            )
        except Exception:
            logger.exception("Drone SOP messenger pipeline failed during pipeline run")

        mail_sent = 0
        try:
            mail_sent = _run_mail_inform(
                rows=rows,
                channel_by_target=channel_by_target,
            )
        except Exception:
            logger.exception("Drone SOP mail pipeline failed during pipeline run")

        # ---------------------------------------------------------------------
        # 7) 결과 반환
        # ---------------------------------------------------------------------
        return DroneSopInformResult(
            candidates=candidate_count,
            jira_created=jira_created,
            jira_updated_rows=jira_updated_rows,
            messenger_sent=messenger_sent,
            mail_sent=mail_sent,
        )


__all__ = [
    "DroneSopInformResult",
    "has_drone_sop_pipeline_candidates",
    "run_drone_sop_pipeline_from_env",
]
