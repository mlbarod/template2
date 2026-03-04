# =============================================================================
# 모듈 설명: 라인 B용 Knox Excel Table(msgType=7) 템플릿 전송을 제공합니다.
# - 주요 대상: TEMPLATE_KEY, build_excel_table_html, send_excel_table_message
# - 불변 조건: line_b는 Excel Table 전송만 지원합니다.
# =============================================================================
"""라인 B 메신저 템플릿 정의 모음."""
from __future__ import annotations

import os
import tempfile
from html import escape
from typing import Any

from api.messenger import services as messenger_services

TEMPLATE_KEY = "line_b"


def _normalize_text(value: str | None) -> str:
    """템플릿 텍스트 값을 안전한 기본값으로 정규화합니다."""

    normalized = str(value or "").strip()
    return normalized if normalized else "-"


def _split_ctttm_and_defect_links(actions: list[dict[str, Any]]) -> tuple[list[dict[str, str]], str]:
    """OpenUrl 액션을 CTTTM 링크 목록과 Defect URL로 분리합니다."""

    ctttm_links: list[dict[str, str]] = []
    defect_url = ""
    for action in actions:
        if not isinstance(action, dict):
            continue
        url = str(action.get("url") or "").strip()
        if not url:
            continue
        label = str(action.get("title") or "Link").strip() or "Link"
        if label.strip().lower() == "defect":
            defect_url = url
            continue
        ctttm_links.append({"label": label, "url": url})
    return ctttm_links, defect_url


def build_excel_table_html(*, context: dict[str, str], actions: list[dict[str, Any]]) -> str:
    """라인 B용 Excel Table HTML 문자열을 구성합니다.

    Jira line_b 템플릿과 동일한 테이블/섹션 스타일을 사용합니다.
    """

    main_step = _normalize_text(context.get("main_step"))
    ppid = _normalize_text(context.get("ppid"))
    eqp_cb = _normalize_text(context.get("eqp_cb"))
    lot_id = _normalize_text(context.get("lot_id"))
    knoxid = _normalize_text(context.get("knoxid"))
    user_sdwt_prod = _normalize_text(context.get("user_sdwt_prod"))
    comment = _normalize_text(context.get("comment_raw"))
    ctttm_links, defect_url = _split_ctttm_and_defect_links(actions)

    ctttm_link_html = (
        ", ".join(
            [
                f'<a href="{escape(item["url"], quote=True)}" target="_blank" rel="noopener noreferrer" style="font-size:14px;">{escape(item["label"])}</a>'
                for item in ctttm_links
            ]
        )
        if ctttm_links
        else '<span style="font-size:14px; color:#999;">-</span>'
    )

    defect_link_html = (
        f'<a href="{escape(defect_url, quote=True)}" target="_blank" rel="noopener noreferrer" style="font-size:14px;">{escape(lot_id)}</a>'
        if defect_url
        else '<span style="font-size:14px; color:#999;">-</span>'
    )

    return (
        "<div>"
        '<div style="margin:8px 0;">'
        '<table style="border:1px solid #ccc; border-collapse:collapse; width:auto;">'
        '<caption style="caption-side:bottom; text-align:right; font-size:11px; color:#888; margin:0; padding:0;">'
        f"SOP by : {escape(knoxid)} ({escape(user_sdwt_prod)})"
        "</caption>"
        "<thead><tr>"
        '<th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">Step_seq</th>'
        '<th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">PPID</th>'
        '<th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">EQP_CB</th>'
        '<th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">Lot_id</th>'
        "</tr></thead>"
        "<tbody><tr>"
        f'<td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{escape(main_step)}</td>'
        f'<td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{escape(ppid)}</td>'
        f'<td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{escape(eqp_cb)}</td>'
        f'<td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{escape(lot_id)}</td>'
        "</tr></tbody></table></div>"
        '<div style="margin:4px 0;"><div style="font-size:14px;">'
        "📄 CTTTM URL : "
        f"{ctttm_link_html}"
        "</div></div>"
        '<div style="margin:4px 0;"><div style="font-size:14px; margin-top:12px;">'
        "💿 Defect URL : "
        f"{defect_link_html}"
        "</div></div>"
        + (
            (
                '<div style="margin:4px 0;"><div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">'
                f"🎨 Comment : {escape(comment)}"
                '</div><div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">'
                "💬 답변  :&nbsp; "
                "</div></div>"
            )
            if comment != "-"
            else ""
        )
        + "</div>"
    )


def send_excel_table_message(
    *,
    chatroom_id: int,
    context: dict[str, str],
    actions: list[dict[str, Any]],
    ttl: int,
    config: messenger_services.KnoxMessengerConfig,
) -> None:
    """라인 B 메시지를 Excel Table(msgType=7)로 전송합니다."""

    html = build_excel_table_html(context=context, actions=actions)
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", encoding="utf-8", delete=False) as file:
            file.write(html)
            temp_path = file.name

        messenger_services.send_excel_table_message_from_file(
            chatroom_id=chatroom_id,
            html_path=temp_path,
            ttl=ttl,
            config=config,
            encoding="utf-8",
            debug_print_plain=False,
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


__all__ = ["TEMPLATE_KEY", "build_excel_table_html", "send_excel_table_message"]
