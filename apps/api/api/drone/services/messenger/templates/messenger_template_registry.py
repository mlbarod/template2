# =============================================================================
# 모듈 설명: Drone SOP 메신저 Excel Table 템플릿 전송기를 등록합니다.
# - 주요 대상: EXCEL_TABLE_TEMPLATE_SENDERS
# - 불변 조건: 템플릿 키는 사전에 정의된 문자열이어야 함
# =============================================================================
"""Drone SOP 메신저 템플릿 레지스트리 모음."""
from __future__ import annotations

from .messenger_template_common import (
    TEMPLATE_KEY as COMMON_KEY,
    send_excel_table_message as send_common_excel_table_message,
)
from .messenger_template_h1 import (
    TEMPLATE_KEY as H1_KEY,
    send_excel_table_message as send_h1_excel_table_message,
)

EXCEL_TABLE_TEMPLATE_SENDERS = {
    COMMON_KEY: send_common_excel_table_message,
    H1_KEY: send_h1_excel_table_message,
}

__all__ = ["EXCEL_TABLE_TEMPLATE_SENDERS"]
