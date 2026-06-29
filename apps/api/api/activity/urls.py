# =============================================================================
# 모듈 설명: activity 도메인 라우팅을 제공합니다.
# - 주요 경로: logs, app-access, app-access-stats, app-access-manual-*
# - 불변 조건: 상위 URLConf에서 /api/v1/activity/ 프리픽스를 제공합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import (
    ActivityLogView,
    AppAccessEventView,
    AppAccessStatsView,
    ManualAppAccessStatsCommitView,
    ManualAppAccessStatsPreviewView,
)

urlpatterns = [
    path("app-access", AppAccessEventView.as_view(), name="activity-app-access"),
    path(
        "app-access-manual-commit",
        ManualAppAccessStatsCommitView.as_view(),
        name="activity-app-access-manual-commit",
    ),
    path(
        "app-access-manual-preview",
        ManualAppAccessStatsPreviewView.as_view(),
        name="activity-app-access-manual-preview",
    ),
    path("app-access-stats", AppAccessStatsView.as_view(), name="activity-app-access-stats"),
    path("logs", ActivityLogView.as_view(), name="activity-logs"),
]
