# =============================================================================
# 모듈 설명: api 전역 URL 레지스트리를 구성합니다.
# - 주요 대상: urlpatterns
# - 불변 조건: feature별 urls.py만 include하며 비즈니스 로직을 포함하지 않습니다.
# =============================================================================

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("auth/", include("api.auth.callback_urls")),
    path("api/v1/health/", include("api.health.urls")),
    path("api/v1/auth/", include("api.auth.urls")),
    path("api/v1/activity/", include("api.activity.urls")),
    path("api/v1/line-dashboard/", include("api.drone.urls")),
    path("api/v1/l3_spider/", include("api.l3_spider.urls")),
    path("api/v1/assistant/", include("api.assistant.urls")),
    path("api/v1/timeline/", include("api.timeline.urls")),
    path("api/v1/emails/", include("api.emails.urls")),
    path("api/v1/appstore/", include("api.appstore.urls")),
    path("api/v1/account/", include("api.account.urls")),
    path("api/v1/voc/", include("api.voc.urls")),
]
