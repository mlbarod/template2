# =============================================================================
# 모듈: Drone SOP 메신저 전송(Knox API)
# 주요 기능: 공통 Knox 메신저 서비스로 메시지 전송
# 주요 가정: chatroom_id는 채팅룸 ID(정수)입니다.
# =============================================================================
"""Drone SOP Knox 메신저 전송 유틸리티."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from api.messenger import services as messenger_services

from .messenger_sender import build_drone_sop_messenger_card
from ..shared.utils import _parse_int

_DEFAULT_MSG_TYPE = 0
_DEFAULT_TTL = 7200


@dataclass(frozen=True)
class DroneMessengerConfig:
    """Drone SOP 메신저 전송 설정입니다."""

    msg_type: int
    ttl: int
    knox_config: messenger_services.KnoxMessengerConfig

    @classmethod
    def from_settings(cls) -> "DroneMessengerConfig":
        """settings/env에서 메시지 타입/TTL과 Knox 설정을 로드합니다."""

        msg_type_raw = (
            getattr(settings, "DRONE_MESSENGER_MSG_TYPE", None)
            or os.getenv("DRONE_MESSENGER_MSG_TYPE")
        )
        ttl_raw = (
            getattr(settings, "DRONE_MESSENGER_TTL", None)
            or os.getenv("DRONE_MESSENGER_TTL")
        )

        msg_type = _parse_int(msg_type_raw, _DEFAULT_MSG_TYPE)
        ttl = _parse_int(ttl_raw, _DEFAULT_TTL)
        if ttl <= 0:
            ttl = _DEFAULT_TTL

        return cls(
            msg_type=msg_type,
            ttl=ttl,
            knox_config=messenger_services.KnoxMessengerConfig.from_settings(),
        )

    def is_ready(self) -> bool:
        """Knox 설정 준비 여부를 반환합니다."""

        return self.knox_config.is_ready()


def _resolve_chat_message(card_payload: dict[str, Any], msg_type: int) -> Any:
    """msg_type과 무관하게 문자열 chatMsg 값을 반환합니다."""

    return json.dumps(card_payload, ensure_ascii=False)


def send_drone_sop_messenger_message(
    *,
    row: dict[str, Any],
    chatroom_id: int,
    messenger_template_key: str,
    config: DroneMessengerConfig,
) -> None:
    """Drone SOP 메신저 메시지를 전송합니다.

    인자:
        row: Drone SOP 행 dict.
        chatroom_id: 채팅룸 ID(정수).
        messenger_template_key: 메신저 템플릿 키.
        config: Drone 메신저 설정.

    반환:
        없음.

    부작용:
        외부 Knox 메신저 API 호출이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 설정/입력 검증
    # -------------------------------------------------------------------------
    if not config.is_ready():
        raise ValueError("KNOX_MESSENGER_API_BASE_URL/AUTHORIZATION/SYSTEM_ID 미설정")
    if not isinstance(chatroom_id, int) or chatroom_id <= 0:
        raise ValueError("chatroom_id는 양의 정수여야 합니다")
    if not isinstance(messenger_template_key, str) or not messenger_template_key.strip():
        raise ValueError("messenger_template_key is required")

    # -------------------------------------------------------------------------
    # 2) 메시지 payload 구성
    # -------------------------------------------------------------------------
    card_payload = build_drone_sop_messenger_card(template_key=messenger_template_key, row=row)
    chat_msg = _resolve_chat_message(card_payload, config.msg_type)

    # -------------------------------------------------------------------------
    # 3) Knox 메신저 전송
    # -------------------------------------------------------------------------
    messenger_services.send_chat_message(
        chatroom_id=chatroom_id,
        msg_type=config.msg_type,
        chat_msg=chat_msg,
        ttl=config.ttl,
        config=config.knox_config,
    )


__all__ = ["DroneMessengerConfig", "send_drone_sop_messenger_message"]
