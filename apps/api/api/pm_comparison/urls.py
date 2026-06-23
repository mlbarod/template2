# =============================================================================
# 모듈: PM SPIDER 라우팅
# 주요 경로: meta, compare
# 주요 가정: 전역 prefix는 api.urls에서만 선언합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import PmComparisonCompareView, PmComparisonMetaView

urlpatterns = [
    path("meta", PmComparisonMetaView.as_view(), name="pm-spider-meta"),
    path("compare", PmComparisonCompareView.as_view(), name="pm-spider-compare"),
]
