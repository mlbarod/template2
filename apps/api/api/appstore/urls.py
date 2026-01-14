# =============================================================================
# 모듈 설명: appstore 도메인 라우팅을 제공합니다.
# - 주요 경로: apps, apps/<id>, cover, comments, like/view
# - 불변 조건: 상위 URLConf에서 /api/v1/appstore/ 프리픽스를 제공합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import (
    AppStoreAppCoverView,
    AppStoreAppDetailView,
    AppStoreAppsView,
    AppStoreCommentDetailView,
    AppStoreCommentLikeToggleView,
    AppStoreCommentsView,
    AppStoreLikeToggleView,
    AppStoreViewIncrementView,
)

urlpatterns = [
    path("apps", AppStoreAppsView.as_view(), name="appstore-apps"),
    path("apps/<int:app_id>", AppStoreAppDetailView.as_view(), name="appstore-app-detail"),
    path("apps/<int:app_id>/cover", AppStoreAppCoverView.as_view(), name="appstore-app-cover"),
    path(
        "apps/<int:app_id>/like",
        AppStoreLikeToggleView.as_view(),
        name="appstore-app-like",
    ),
    path(
        "apps/<int:app_id>/view",
        AppStoreViewIncrementView.as_view(),
        name="appstore-app-view",
    ),
    path(
        "apps/<int:app_id>/comments",
        AppStoreCommentsView.as_view(),
        name="appstore-app-comments",
    ),
    path(
        "apps/<int:app_id>/comments/<int:comment_id>",
        AppStoreCommentDetailView.as_view(),
        name="appstore-app-comment-detail",
    ),
    path(
        "apps/<int:app_id>/comments/<int:comment_id>/like",
        AppStoreCommentLikeToggleView.as_view(),
        name="appstore-app-comment-like",
    ),
]
