# =============================================================================
# 모듈 설명: Drone SOP 메신저 Excel Table 템플릿 전송기를 등록합니다.
# - 주요 대상: EXCEL_TABLE_TEMPLATE_SENDERS
# - 불변 조건: 템플릿 키는 사전에 정의된 문자열이어야 함
# =============================================================================
"""Drone SOP 메신저 템플릿 레지스트리 모음."""
from __future__ import annotations

from .messenger_template_line_a import (
    TEMPLATE_KEY as LINE_A_KEY,
    send_excel_table_message as send_line_a_excel_table_message,
)
from .messenger_template_line_b import (
    TEMPLATE_KEY as LINE_B_KEY,
    send_excel_table_message as send_line_b_excel_table_message,
)

EXCEL_TABLE_TEMPLATE_SENDERS = {
    LINE_A_KEY: send_line_a_excel_table_message,
    LINE_B_KEY: send_line_b_excel_table_message,
}

__all__ = ["EXCEL_TABLE_TEMPLATE_SENDERS"]
