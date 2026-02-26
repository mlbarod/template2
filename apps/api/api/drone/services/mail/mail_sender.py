# =============================================================================
# 모듈: Drone SOP 메일 발송
# 주요 기능: 메일 템플릿 렌더링 및 Knox 메일 API 호출
# 주요 가정: 발신자는 DRONE_MAIL_SENDER 설정으로 주입됩니다.
# =============================================================================
"""Drone SOP 메일 발송 유틸리티."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Sequence

from django.conf import settings
from django.template import Context, Engine

from api.emails import services as email_services

from ..shared.inform_context import build_inform_context
from ..shared.utils import _truncate_text
from ..jira.templates.jira_template_registry import SUMMARY_BUILDERS
from .templates.mail_template_registry import MAIL_TEMPLATE_SOURCES


_TEMPLATE_ENGINE = Engine(autoescape=True)
_TEMPLATE_CACHE: dict[str, str] = {}


@dataclass(frozen=True)
class DroneMailConfig:
    """메일 발송 설정."""

    sender_email: str

    @classmethod
    def from_settings(cls) -> "DroneMailConfig":
        """settings/env에서 메일 발신자 설정을 로드합니다."""

        sender = (
            getattr(settings, "DRONE_MAIL_SENDER", "")
            or os.getenv("DRONE_MAIL_SENDER")
            or ""
        ).strip()
        return cls(sender_email=sender)


def _load_mail_template_source(template_key: str) -> str:
    """메일 템플릿 소스를 로드합니다."""

    if template_key in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[template_key]
    source = MAIL_TEMPLATE_SOURCES.get(template_key)
    if not source:
        raise ValueError(f"Unsupported mail template key: {template_key!r}")
    _TEMPLATE_CACHE[template_key] = source
    return source


def _render_mail_body(*, template_key: str, row: dict[str, Any]) -> str:
    """메일 본문 HTML을 렌더링합니다."""

    source = _load_mail_template_source(template_key)
    context = Context(build_inform_context(row))
    return _TEMPLATE_ENGINE.from_string(source).render(context)


def _build_mail_subject(*, template_key: str, row: dict[str, Any]) -> str:
    """메일 제목을 생성합니다."""

    summary_builder = SUMMARY_BUILDERS.get(template_key)
    if not callable(summary_builder):
        raise ValueError(f"Unsupported mail summary key: {template_key!r}")
    summary = summary_builder(row)
    if not isinstance(summary, str):
        summary = str(summary)
    return _truncate_text(summary.strip(), 255)


def send_drone_sop_mail(
    *,
    row: dict[str, Any],
    template_key: str,
    receiver_emails: Sequence[str],
    config: DroneMailConfig,
) -> dict[str, Any]:
    """Drone SOP 메일을 발송합니다.

    인자:
        row: Drone SOP 행 dict.
        template_key: 메일 템플릿 키.
        receiver_emails: 수신자 이메일 목록.
        config: 메일 설정.

    반환:
        메일 API 응답 dict.

    부작용:
        외부 메일 API 호출이 발생합니다.
    """

    if not config.sender_email:
        raise ValueError("DRONE_MAIL_SENDER 미설정")
    subject = _build_mail_subject(template_key=template_key, row=row)
    body_html = _render_mail_body(template_key=template_key, row=row)
    return email_services.send_knox_mail_api(
        sender_email=config.sender_email,
        receiver_emails=receiver_emails,
        subject=subject,
        html_content=body_html,
    )


__all__ = ["DroneMailConfig", "send_drone_sop_mail"]
