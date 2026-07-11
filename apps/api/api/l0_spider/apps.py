from __future__ import annotations

from django.apps import AppConfig


class L0SpiderConfig(AppConfig):
    """L0 Spider 도메인 앱 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.l0_spider"
