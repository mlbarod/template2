# =============================================================================
# 모듈 설명: Knox 메신저 서비스 파사드를 제공합니다.
# - 주요 대상: Knox 메신저 API 클라이언트 함수/설정
# - 불변 조건: 외부 모듈은 이 파사드를 통해 접근합니다.
# =============================================================================
"""Knox 메신저 서비스 공개 파사드."""
from __future__ import annotations

from .knox_client import (
    KnoxMessengerConfig,
    KnoxMessengerError,
    change_chatroom_title,
    create_chatroom,
    create_request_parameters,
    knox_decrypt,
    knox_encrypt,
    resolve_user_ids_by_single_ids,
    search_user_ids_by_single_ids,
    send_chat_message,
    send_excel_table_message_from_file,
)

__all__ = [
    "KnoxMessengerConfig",
    "KnoxMessengerError",
    "change_chatroom_title",
    "create_chatroom",
    "create_request_parameters",
    "knox_decrypt",
    "knox_encrypt",
    "resolve_user_ids_by_single_ids",
    "search_user_ids_by_single_ids",
    "send_chat_message",
    "send_excel_table_message_from_file",
]
