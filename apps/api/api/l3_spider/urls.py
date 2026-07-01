# =============================================================================
# 모듈: L3 Spider 라우팅
# 주요 경로: meta, summary, data
# 주요 가정: 전역 prefix는 api.urls에서만 선언합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import (
    L3SpiderDataView,
    L3SpiderExclusionFilterDetailView,
    L3SpiderExclusionFilterListCreateView,
    L3SpiderFilterCandidatesView,
    L3SpiderMailRuleDetailView,
    L3SpiderMailRuleListCreateView,
    L3SpiderMailRulePermissionView,
    L3SpiderMailRuleTestSendView,
    L3SpiderMailTriggerView,
    L3SpiderMetaView,
    L3SpiderStatsView,
    L3SpiderStructureView,
    L3SpiderSummaryView,
)

urlpatterns = [
    path("meta", L3SpiderMetaView.as_view(), name="l3-spider-meta"),
    path("structure", L3SpiderStructureView.as_view(), name="l3-spider-structure"),
    path("stats", L3SpiderStatsView.as_view(), name="l3-spider-stats"),
    path("summary", L3SpiderSummaryView.as_view(), name="l3-spider-summary"),
    path("data", L3SpiderDataView.as_view(), name="l3-spider-data"),
    path("filter-candidates", L3SpiderFilterCandidatesView.as_view(), name="l3-spider-filter-candidates"),
    path("exclusion-filters", L3SpiderExclusionFilterListCreateView.as_view(), name="l3-spider-exclusion-filters"),
    path("exclusion-filters/<int:pk>", L3SpiderExclusionFilterDetailView.as_view(), name="l3-spider-exclusion-filter-detail"),
    path("mail-rules", L3SpiderMailRuleListCreateView.as_view(), name="l3-spider-mail-rules"),
    path("mail-rules/trigger", L3SpiderMailTriggerView.as_view(), name="l3-spider-mail-rule-trigger"),
    path("mail-rules/<int:pk>/permissions", L3SpiderMailRulePermissionView.as_view(), name="l3-spider-mail-rule-permissions"),
    path("mail-rules/<int:pk>/test-send", L3SpiderMailRuleTestSendView.as_view(), name="l3-spider-mail-rule-test-send"),
    path("mail-rules/<int:pk>", L3SpiderMailRuleDetailView.as_view(), name="l3-spider-mail-rule-detail"),
]
