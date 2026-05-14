# =============================================================================
# 모듈: 드론 라우팅
# 주요 경로: /early-inform, /history, /line-ids, /sop/* 트리거
# 주요 가정: 상세 로직은 views에서 처리합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import (
    DroneEarlyInformView,
    DroneJiraKeyView,
    DroneMyNotificationRecipientTargetView,
    DroneNotificationRecipientPermissionView,
    DroneNotificationRecipientView,
    DroneNotificationTargetMappingView,
    DroneNotificationTargetView,
    DroneSopInstantInformView,
    DroneSopPop3IngestTriggerView,
    DroneSopPipelinePrecheckView,
    DroneSopPipelineTriggerView,
    DroneSopRetryChannelView,
    DroneTablesView,
    DroneTableUpdateView,
    JiraUserSdwtProdListView,
    LineHistoryView,
    LineIdListView,
)

urlpatterns = [
    path("early-inform", DroneEarlyInformView.as_view(), name="drone-early-inform"),
    path("tables", DroneTablesView.as_view(), name="drone-tables"),
    path("tables/update", DroneTableUpdateView.as_view(), name="drone-tables-update"),
    path("jira-keys", DroneJiraKeyView.as_view(), name="line-dashboard-jira-keys"),
    path(
        "notification-targets",
        DroneNotificationTargetView.as_view(),
        name="line-dashboard-notification-targets",
    ),
    path(
        "notification-target-mappings",
        DroneNotificationTargetMappingView.as_view(),
        name="line-dashboard-notification-target-mappings",
    ),
    path(
        "jira-user-sdwt-prods",
        JiraUserSdwtProdListView.as_view(),
        name="line-dashboard-jira-user-sdwt-prods",
    ),
    path(
        "notification-recipients",
        DroneNotificationRecipientView.as_view(),
        name="line-dashboard-notification-recipients",
    ),
    path(
        "notification-recipient-permissions",
        DroneNotificationRecipientPermissionView.as_view(),
        name="line-dashboard-notification-recipient-permissions",
    ),
    path(
        "my-notification-recipient-targets",
        DroneMyNotificationRecipientTargetView.as_view(),
        name="line-dashboard-my-notification-recipient-targets",
    ),
    path("history", LineHistoryView.as_view(), name="line-dashboard-history"),
    path("line-ids", LineIdListView.as_view(), name="line-dashboard-line-ids"),
    path(
        "sop/<int:sop_id>/instant-inform",
        DroneSopInstantInformView.as_view(),
        name="drone-sop-instant-inform",
    ),
    path(
        "sop/<int:sop_id>/retry-channel",
        DroneSopRetryChannelView.as_view(),
        name="drone-sop-retry-channel",
    ),
    path(
        "sop/ingest/pop3/trigger",
        DroneSopPop3IngestTriggerView.as_view(),
        name="drone-sop-pop3-ingest-trigger",
    ),
    path("sop/precheck", DroneSopPipelinePrecheckView.as_view(), name="drone-sop-pipeline-precheck"),
    path("sop/trigger", DroneSopPipelineTriggerView.as_view(), name="drone-sop-pipeline-trigger"),
]
