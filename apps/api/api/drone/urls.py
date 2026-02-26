# =============================================================================
# 모듈: 드론 라우팅
# 주요 경로: /early-inform, /history, /line-ids, /sop/* 트리거
# 주요 가정: 상세 로직은 views에서 처리합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import (
    DroneEarlyInformView,
    DroneSopInformPrecheckView,
    DroneSopInformTriggerView,
    DroneJiraKeyView,
    DroneSopInstantInformView,
    DroneSopJiraPrecheckView,
    DroneSopJiraTriggerView,
    DroneSopPop3IngestTriggerView,
    JiraUserSdwtProdListView,
    LineHistoryView,
    LineIdListView,
)

urlpatterns = [
    path("early-inform", DroneEarlyInformView.as_view(), name="drone-early-inform"),
    path("jira-keys", DroneJiraKeyView.as_view(), name="line-dashboard-jira-keys"),
    path(
        "jira-user-sdwt-prods",
        JiraUserSdwtProdListView.as_view(),
        name="line-dashboard-jira-user-sdwt-prods",
    ),
    path("history", LineHistoryView.as_view(), name="line-dashboard-history"),
    path("line-ids", LineIdListView.as_view(), name="line-dashboard-line-ids"),
    path(
        "sop/<int:sop_id>/instant-inform",
        DroneSopInstantInformView.as_view(),
        name="drone-sop-instant-inform",
    ),
    path(
        "sop/ingest/pop3/trigger",
        DroneSopPop3IngestTriggerView.as_view(),
        name="drone-sop-pop3-ingest-trigger",
    ),
    path(
        "sop/jira/precheck",
        DroneSopJiraPrecheckView.as_view(),
        name="drone-sop-jira-precheck",
    ),
    path(
        "sop/jira/trigger",
        DroneSopJiraTriggerView.as_view(),
        name="drone-sop-jira-trigger",
    ),
    path(
        "sop/inform/precheck",
        DroneSopInformPrecheckView.as_view(),
        name="drone-sop-inform-precheck",
    ),
    path(
        "sop/inform/trigger",
        DroneSopInformTriggerView.as_view(),
        name="drone-sop-inform-trigger",
    ),
]
