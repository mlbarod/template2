# =============================================================================
# 모듈 설명: H1용 Knox Excel Table(msgType=7) 템플릿 전송을 제공합니다.
# - 주요 대상: TEMPLATE_KEY, build_excel_table_html, send_excel_table_message
# - 불변 조건: H1은 Excel Table 전송만 지원합니다.
#
# 변경사항(요청 반영):
# - common 템플릿과 동일하게 하단 정보를 표 형태(info_table_html)로 구성
# - layer 정보만 추가 행으로 노출
# =============================================================================
"""H1 메신저 템플릿 정의 모음."""
from __future__ import annotations

import os
import tempfile
from html import escape
from typing import Any

from api.messenger import services as messenger_services

from ...jira.templates.jira_template_h1 import find_layer

TEMPLATE_KEY = "H1"


def _normalize_text(value: Any) -> str:
    """템플릿 텍스트 값을 안전한 기본값으로 정규화합니다."""
    normalized = str(value or "").strip()
    return normalized if normalized else "-"


def _normalize_comment(value: Any) -> str:
    """Comment의 과도한 빈공간(연속 빈 줄/줄끝 공백)을 줄입니다."""
    s = str(value or "")
    lines = [line.rstrip() for line in s.splitlines()]
    s = "\n".join(lines).strip()
    while "\n\n\n" in s:
        s = s.replace("\n\n\n", "\n\n")
    return s if s else "-"


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

        label_raw = str(action.get("title") or "Link").strip() or "Link"
        label_key = label_raw.strip().lower().replace(" ", "").replace("_", "")

        if label_key in {"defect", "defecturl"}:
            defect_url = url
            continue

        ctttm_links.append({"label": label_raw, "url": url})

    return ctttm_links, defect_url


def build_excel_table_html(*, context: dict[str, Any], actions: list[dict[str, Any]]) -> str:
    """H1용 Excel Table HTML 문자열을 구성합니다.

    common 템플릿과 동일한 표 구조를 사용하고, layer 행만 추가합니다.
    """

    main_step = _normalize_text(context.get("main_step"))
    ppid = _normalize_text(context.get("ppid"))
    layer = find_layer(ppid)
    eqp_cb = _normalize_text(context.get("eqp_cb"))
    lot_id = _normalize_text(context.get("lot_id"))
    knoxid = _normalize_text(context.get("knoxid"))
    user_sdwt_prod = _normalize_text(context.get("user_sdwt_prod"))
    comment = _normalize_comment(context.get("comment_raw"))

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

    # 메인 테이블: 행높이 유지(padding-top/bottom=4px), 좌우만 타이트(2px)
    th_style = (
        "border:1px solid #ccc; width:25%; background-color:#F2F2F2; "
        "text-align:center; padding:4px 2px; font-size:12px; white-space:nowrap;"
    )
    td_style = (
        "border:1px solid #ccc; text-align:center; "
        "padding:4px 2px; font-size:14px; white-space:nowrap;"
    )

    # 하단 영역: common과 동일한 border 없는 정보 테이블
    info_table_style = (
        "border-collapse:collapse; width:100%; min-width:400px; table-layout:fixed; "
        "margin:4px 0 0 0;"
    )
    info_td_style = "border:none; padding:2px 0; font-size:14px; white-space:normal;"
    info_label_style = "font-weight:normal;"

    comment_row = (
        f"<tr><td style=\"{info_td_style}\"><span style=\"{info_label_style}\">🎨 Comment : </span>"
        f"<span style=\"white-space:pre-wrap;\">{escape(comment)}</span></td></tr>"
        if comment != "-"
        else ""
    )

    info_table_html = (
        f'<table style="{info_table_style}">'
        f"<tbody>"
        f'<tr><td style="{info_td_style}"><span style="{info_label_style}">🧩 Layer : </span>{escape(layer)}</td></tr>'
        f'<tr><td style="{info_td_style}"><span style="{info_label_style}">📄 CTTTM URL : </span>{ctttm_link_html}</td></tr>'
        f'<tr><td style="{info_td_style}"><span style="{info_label_style}">💿 Defect URL : </span>{defect_link_html}</td></tr>'
        f"{comment_row}"
        f"</tbody></table>"
    )

    return (
        "<div>"
        '<div style="margin:8px 0;">'
        '<table style="border:1px solid #ccc; border-collapse:collapse; width:100%; min-width:400px; table-layout:fixed;">'
        '<caption style="caption-side:bottom; text-align:right; font-size:11px; color:#888; margin:0; padding:0;">'
        f"SOP by : {escape(knoxid)} ({escape(user_sdwt_prod)})"
        "</caption>"
        "<thead><tr>"
        f'<th style="{th_style}">Step_seq</th>'
        f'<th style="{th_style}">PPID</th>'
        f'<th style="{th_style}">EQP_CB</th>'
        f'<th style="{th_style}">Lot_id</th>'
        "</tr></thead>"
        "<tbody><tr>"
        f'<td style="{td_style}">{escape(main_step)}</td>'
        f'<td style="{td_style}">{escape(ppid)}</td>'
        f'<td style="{td_style}">{escape(eqp_cb)}</td>'
        f'<td style="{td_style}">{escape(lot_id)}</td>'
        "</tr></tbody></table></div>"
        f"{info_table_html}"
        "</div>"
    )


def send_excel_table_message(
    *,
    chatroom_id: int,
    context: dict[str, Any],
    actions: list[dict[str, Any]],
    ttl: int,
    config: messenger_services.KnoxMessengerConfig,
) -> None:
    """H1 메시지를 Excel Table(msgType=7)로 전송합니다."""

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
