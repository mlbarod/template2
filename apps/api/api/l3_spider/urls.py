# =============================================================================
# 모듈: L3 Spider 라우팅
# 주요 경로: meta, summary, data
# 주요 가정: 전역 prefix는 api.urls에서만 선언합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import L3SpiderDataView, L3SpiderMetaView, L3SpiderSummaryView

urlpatterns = [
    path("meta", L3SpiderMetaView.as_view(), name="l3-spider-meta"),
    path("summary", L3SpiderSummaryView.as_view(), name="l3-spider-summary"),
    path("data", L3SpiderDataView.as_view(), name="l3-spider-data"),
]
