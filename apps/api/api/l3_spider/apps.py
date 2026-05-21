# =============================================================================
# 모듈: L3 Spider 앱 설정
# 주요 클래스: L3SpiderConfig
# 주요 가정: 앱 라벨은 api.l3_spider를 사용합니다.
# =============================================================================
from __future__ import annotations

from django.apps import AppConfig


class L3SpiderConfig(AppConfig):
    """L3 Spider 도메인 앱 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.l3_spider"
