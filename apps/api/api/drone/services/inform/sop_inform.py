# =============================================================================
# 모듈: Drone SOP 멀티 채널 알림 서비스
# 주요 기능: Jira/메신저/메일 동시 전송
# 주요 가정: target_user_sdwt_prod 기준으로 채널 설정을 해석합니다.
# =============================================================================
"""Drone SOP 멀티 채널 알림 서비스 모음."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Sequence

import api.common.services as messenger_services

from ... import selectors
from ...models import DroneSopChannelDelivery, DroneSopChannelRecipient
from ..channels.user_sdwt_channel import upsert_drone_sop_user_sdwt_channel
from ..jira.config import DroneCtttmConfig
from ..jira.delivery import _enrich_rows_with_ctttm_urls
from ..jira.sop_jira import run_drone_sop_jira_create_from_rows
from ..mail.mail_sender import DroneMailConfig, send_drone_sop_mail
from ..messenger.messenger_api import DroneMessengerConfig, send_drone_sop_messenger_message
from ..shared.delivery_state import (
    ensure_channel_delivery_snapshots_for_rows,
    filter_delivery_ids_for_config_failure as _filter_delivery_ids_for_config_failure,
    mark_channel_delivery_status as _mark_delivery_status,
    normalize_positive_ids as _normalize_positive_ids,
)
from ..shared.policy import (
    REASON_CHANNEL_CONFIG_INVALID,
    REASON_CHANNEL_CONFIG_MISSING,
    REASON_CONFIG_MISSING,
    REASON_RECEIVER_NOT_FOUND,
    REASON_SEND_FAILED,
    REASON_TEMPLATE_MISSING,
    mark_missing_target_as_failed,
)
from ..shared.utils import _advisory_lock, _parse_int
from .delivery_preparation import (
    ChannelConfig,
    collect_pending_channel_deliveries as _collect_pending_channel_deliveries,
    extract_row_id as _extract_row_id,
    normalize_string_value as _normalize_string_value,
    normalize_target_lookup_key as _normalize_target_lookup_key,
)

logger = logging.getLogger(__name__)

_PIPELINE_CHANNELS: tuple[str, ...] = (
    DroneSopChannelDelivery.Channels.JIRA,
    DroneSopChannelDelivery.Channels.MESSENGER,
    DroneSopChannelDelivery.Channels.MAIL,
)


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
        # target_user_sdwt_prod는 운영상 라인별 고유값으로 관리되므로,
        # 기존 chatroom_id는 target 단위로 재사용합니다.
        return existing_chatroom_id, None

    # -----------------------------------------------------------------------------
    # 2) 수신자 knox_id 조회
    # -----------------------------------------------------------------------------
    line_id = _normalize_string_value(row.get("line_id"))
    receiver_knox_ids = selectors.list_messenger_receiver_knox_ids_for_user_sdwt_prod(
        line_id=line_id,
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
    target_lookup = _normalize_target_lookup_key(target)
    if target_lookup:
        channel_by_target[target_lookup] = config_row
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


def _mark_delivery_failed(*, delivery_id: int, reason: str) -> None:
    """단일 delivery 실패 상태 기록을 한 곳에서 수행합니다."""

    _mark_delivery_status(
        delivery_ids=[delivery_id],
        status=DroneSopChannelDelivery.Statuses.FAILED,
        reason=reason,
    )


def _mark_successful_deliveries(*, delivery_ids: Sequence[int]) -> None:
    """성공 delivery ID 목록을 한 번에 성공 상태로 기록합니다."""

    _mark_delivery_status(
        delivery_ids=delivery_ids,
        status=DroneSopChannelDelivery.Statuses.SUCCESS,
    )


def _run_count_channel_safely(*, channel_label: str, runner: Callable[[], int]) -> int:
    """채널별 예외를 격리하고 실패 시 0건 처리로 이어갑니다."""

    try:
        return int(runner() or 0)
    except Exception:
        logger.exception("Drone SOP %s pipeline failed during pipeline run", channel_label)
        return 0


def _run_jira_inform(
    *,
    rows: list[dict[str, Any]],
    pre_resolved_targets: tuple[set[str], list[int]] | None = None,
) -> tuple[int, int]:
    """Jira 채널 전송을 처리합니다.

    - Jira 실행 경로는 `sop_jira.run_drone_sop_jira_create_from_rows`로 단일화합니다.
    - Jira 채널 예외가 발생해도 메신저/메일 채널은 계속 진행할 수 있도록 격리합니다.
    """

    if not rows:
        return 0, 0

    try:
        result = run_drone_sop_jira_create_from_rows(
            rows=rows,
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
    ready_deliveries, delivery_ids = _collect_pending_channel_deliveries(
        rows=rows,
        channel_by_target=channel_by_target,
        enabled_field="messenger_enabled",
        channel=DroneSopChannelRecipient.Channels.MESSENGER,
    )

    if not messenger_config.is_ready():
        _mark_delivery_status(
            delivery_ids=_filter_delivery_ids_for_config_failure(delivery_ids=delivery_ids),
            status=DroneSopChannelDelivery.Statuses.FAILED,
            reason=REASON_CONFIG_MISSING,
        )
        logger.info("Skip messenger send: KNOX_MESSENGER_API_BASE_URL/AUTHORIZATION/SYSTEM_ID 미설정")
        return 0

    success_delivery_ids: list[int] = []
    sent_count = 0
    for delivery in ready_deliveries:
        messenger_template_key = _normalize_string_value(delivery.config.get("messenger_template_key"))
        if not messenger_template_key:
            _mark_delivery_failed(delivery_id=delivery.delivery_id, reason=REASON_TEMPLATE_MISSING)
            continue

        delivery_row = delivery.as_delivery_row()
        chatroom_id = _normalize_chatroom_id(delivery.config.get("chatroom_id"))
        create_reason: str | None = None
        if not chatroom_id:
            try:
                chatroom_id, create_reason = _get_or_create_chatroom_id(
                    row=delivery_row,
                    config_row=delivery.config,
                    channel_by_target=channel_by_target,
                    messenger_config=messenger_config,
                )
            except Exception:
                logger.exception("Messenger room create failed (sop_id=%s)", delivery.sop_id)
                chatroom_id = None
                create_reason = REASON_SEND_FAILED

        if not chatroom_id:
            _mark_delivery_failed(
                delivery_id=delivery.delivery_id,
                reason=create_reason or REASON_CHANNEL_CONFIG_INVALID,
            )
            continue

        try:
            send_drone_sop_messenger_message(
                row=delivery_row,
                chatroom_id=chatroom_id,
                messenger_template_key=messenger_template_key,
                config=messenger_config,
            )
            success_delivery_ids.append(delivery.delivery_id)
            sent_count += 1
        except Exception:
            logger.exception("Messenger send failed (sop_id=%s)", delivery.sop_id)
            _mark_delivery_failed(delivery_id=delivery.delivery_id, reason=REASON_SEND_FAILED)

    _mark_successful_deliveries(delivery_ids=success_delivery_ids)
    return sent_count


def _run_mail_inform(
    *,
    rows: list[dict[str, Any]],
    channel_by_target: dict[str, ChannelConfig],
) -> int:
    """메일 채널 전송을 처리합니다."""

    mail_config = DroneMailConfig.from_settings()
    ready_deliveries, delivery_ids = _collect_pending_channel_deliveries(
        rows=rows,
        channel_by_target=channel_by_target,
        enabled_field="mail_enabled",
        channel=DroneSopChannelRecipient.Channels.MAIL,
    )

    if not mail_config.sender_email:
        _mark_delivery_status(
            delivery_ids=_filter_delivery_ids_for_config_failure(delivery_ids=delivery_ids),
            status=DroneSopChannelDelivery.Statuses.FAILED,
            reason=REASON_CONFIG_MISSING,
        )
        logger.info("Skip mail send: DRONE_MAIL_SENDER 미설정")
        return 0

    success_delivery_ids: list[int] = []
    sent_count = 0
    for delivery in ready_deliveries:
        template_key = _normalize_string_value(delivery.config.get("mail_template_key"))
        if not template_key:
            _mark_delivery_failed(delivery_id=delivery.delivery_id, reason=REASON_TEMPLATE_MISSING)
            continue

        line_id = _normalize_string_value(delivery.row.get("line_id")) or ""
        receiver_emails = selectors.list_mail_receiver_emails_for_user_sdwt_prod(
            line_id=line_id,
            user_sdwt_prod=delivery.target_user_sdwt_prod,
        )
        if not receiver_emails:
            _mark_delivery_failed(delivery_id=delivery.delivery_id, reason=REASON_RECEIVER_NOT_FOUND)
            continue

        delivery_row = delivery.as_delivery_row()
        try:
            send_drone_sop_mail(
                row=delivery_row,
                template_key=template_key,
                receiver_emails=receiver_emails,
                config=mail_config,
            )
            success_delivery_ids.append(delivery.delivery_id)
            sent_count += 1
        except Exception:
            logger.exception("Mail send failed (sop_id=%s)", delivery.sop_id)
            _mark_delivery_failed(delivery_id=delivery.delivery_id, reason=REASON_SEND_FAILED)

    _mark_successful_deliveries(delivery_ids=success_delivery_ids)
    return sent_count


def has_drone_sop_pipeline_candidates() -> bool:
    """통합 파이프라인 대상 Drone SOP 후보 존재 여부를 반환합니다."""

    return selectors.has_drone_sop_pipeline_candidates()


def run_drone_sop_pipeline_from_env(
    *,
    limit: int | None = None,
) -> DroneSopInformResult:
    """Jira/메신저/메일 고정 채널로 Drone SOP 파이프라인을 실행합니다."""

    channels = _PIPELINE_CHANNELS

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
        # 3) delivery snapshot 준비 및 target 누락 처리
        # ---------------------------------------------------------------------
        snapshot = ensure_channel_delivery_snapshots_for_rows(rows=rows)
        if snapshot.missing_sop_ids:
            mark_missing_target_as_failed(
                sop_ids=snapshot.missing_sop_ids,
                channels=channels,
            )
            rows = _filter_rows_by_excluded_ids(rows=rows, excluded_ids=snapshot.missing_sop_ids)
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
            pre_resolved_targets=(snapshot.target_user_sdwt_prods, []),
        )

        # ---------------------------------------------------------------------
        # 5) 메신저/메일 공통 컨텍스트 처리
        # ---------------------------------------------------------------------
        channel_by_target = selectors.list_drone_sop_user_sdwt_channels_by_targets(
            target_user_sdwt_prod_values=snapshot.target_user_sdwt_prods,
        )
        _enrich_rows_with_ctttm_urls(rows=rows, config=DroneCtttmConfig.from_settings())

        # ---------------------------------------------------------------------
        # 6) 메신저/메일 채널 처리(예외 격리)
        # ---------------------------------------------------------------------
        messenger_sent = _run_count_channel_safely(
            channel_label="messenger",
            runner=lambda: _run_messenger_inform(
                rows=rows,
                channel_by_target=channel_by_target,
            ),
        )

        mail_sent = _run_count_channel_safely(
            channel_label="mail",
            runner=lambda: _run_mail_inform(
                rows=rows,
                channel_by_target=channel_by_target,
            ),
        )

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
