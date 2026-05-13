"""Drone SOP 메신저 채팅방 생성 helper."""

from __future__ import annotations

import logging
from typing import Any

from ... import selectors
from ..channels.user_sdwt_channel import upsert_drone_sop_user_sdwt_channel
from ..messenger.messenger_api import DroneMessengerConfig
from ..shared.policy import REASON_CHANNEL_CONFIG_MISSING, REASON_RECEIVER_NOT_FOUND
from ..shared.utils import _parse_int
from .delivery_preparation import (
    ChannelConfig,
    normalize_string_value as _normalize_string_value,
    normalize_target_lookup_key as _normalize_target_lookup_key,
)

logger = logging.getLogger(__name__)


def normalize_chatroom_id(value: Any) -> int | None:
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


def get_or_create_chatroom_id(
    *,
    row: dict[str, Any],
    config_row: ChannelConfig,
    channel_by_target: dict[str, ChannelConfig],
    messenger_config: DroneMessengerConfig,
    messenger_services_module: Any,
) -> tuple[int | None, str | None]:
    """chatroom_id가 비어 있을 때 채팅방을 생성하고 ID를 저장합니다.

    인자:
        row: Drone SOP 행 dict.
        config_row: target_user_sdwt_prod 기준 채널 설정 dict.
        channel_by_target: target_user_sdwt_prod별 채널 설정 캐시.
        messenger_config: 메신저 설정 객체.
        messenger_services_module: Knox 채팅방 생성 API 모듈.

    반환:
        (생성/조회된 chatroom_id, 실패 사유 코드) 튜플.

    부작용:
        - Knox API로 userID 조회/채팅방 생성 호출이 발생합니다.
        - 생성 성공 시 target channel config의 chatroom_id를 갱신합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 소속/기존 ID 확인
    # -----------------------------------------------------------------------------
    target = _normalize_string_value(row.get("target_user_sdwt_prod"))
    if not target:
        return None, REASON_CHANNEL_CONFIG_MISSING

    existing_chatroom_id = normalize_chatroom_id(config_row.get("chatroom_id"))
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
    resolved_user_ids = messenger_services_module.resolve_user_ids_by_single_ids(
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
    chatroom_id = messenger_services_module.create_chatroom(
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


__all__ = [
    "get_or_create_chatroom_id",
    "normalize_chatroom_id",
]
