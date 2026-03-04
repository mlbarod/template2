# =============================================================================
# 모듈: Drone SOP 메신저 전송(Knox API)
# 주요 기능: 공통 Knox 메신저 Excel Table(msgType=7) 전송
# 주요 가정: chatroom_id는 채팅룸 ID(정수)입니다.
# =============================================================================
"""Drone SOP Knox 메신저 전송 유틸리티."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from api.messenger import services as messenger_services

from .messenger_sender import build_drone_sop_messenger_template_inputs
from .templates.messenger_template_registry import EXCEL_TABLE_TEMPLATE_SENDERS
from ..shared.utils import _parse_int

_DEFAULT_TTL = 7200


@dataclass(frozen=True)
class DroneMessengerConfig:
    """Drone SOP 메신저 전송 설정입니다."""

    ttl: int
    knox_config: messenger_services.KnoxMessengerConfig

    @classmethod
    def from_settings(cls) -> "DroneMessengerConfig":
        """settings/env에서 TTL과 Knox 설정을 로드합니다."""

        ttl_raw = (
            getattr(settings, "DRONE_MESSENGER_TTL", None)
            or os.getenv("DRONE_MESSENGER_TTL")
        )

        ttl = _parse_int(ttl_raw, _DEFAULT_TTL)
        if ttl <= 0:
            ttl = _DEFAULT_TTL

        return cls(
            ttl=ttl,
            knox_config=messenger_services.KnoxMessengerConfig.from_env(),
        )

    def is_ready(self) -> bool:
        """Knox 설정 준비 여부를 반환합니다."""

        return self.knox_config.is_ready()


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
    # 2) 템플릿별 전송기 선택
    # -------------------------------------------------------------------------
    normalized_template_key = messenger_template_key.strip()
    template_sender = EXCEL_TABLE_TEMPLATE_SENDERS.get(normalized_template_key)
    if not callable(template_sender):
        raise ValueError(f"Unsupported messenger template key: {messenger_template_key!r}")

    # -------------------------------------------------------------------------
    # 3) 템플릿 입력 구성
    # -------------------------------------------------------------------------
    normalized_context, actions = build_drone_sop_messenger_template_inputs(row=row)

    # -------------------------------------------------------------------------
    # 4) Excel Table(msgType=7) 전송
    # -------------------------------------------------------------------------
    template_sender(
        chatroom_id=chatroom_id,
        context=normalized_context,
        actions=actions,
        ttl=config.ttl,
        config=config.knox_config,
    )


__all__ = ["DroneMessengerConfig", "send_drone_sop_messenger_message"]
