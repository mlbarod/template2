# =============================================================================
# 모듈 설명: timeline 더미 엔드포인트 라우팅을 정의합니다.
# - 주요 경로: lines, sdwts, prc-groups, equipments, logs
# - 불변 조건: 상대 경로만 선언합니다.
# =============================================================================

from __future__ import annotations

from django.urls import path

from .views import (
    TimelineCtttmLogsView,
    TimelineDroneLogsView,
    TimelineEquipmentInfoView,
    TimelineEqpLogsView,
    TimelineEquipmentsView,
    TimelineLinesView,
    TimelineLogsView,
    TimelinePrcGroupView,
    TimelineRacbLogsView,
    TimelineSdwtView,
    TimelineTipLogsView,
)

urlpatterns = [
    path("lines", TimelineLinesView.as_view(), name="timeline-lines"),
    path("sdwts", TimelineSdwtView.as_view(), name="timeline-sdwts"),
    path("prc-groups", TimelinePrcGroupView.as_view(), name="timeline-prc-groups"),
    path("equipments", TimelineEquipmentsView.as_view(), name="timeline-equipments"),
    path(
        "equipment-info/<str:line_id>/<str:eqp_id>",
        TimelineEquipmentInfoView.as_view(),
        name="timeline-equipment-info-line",
    ),
    path(
        "equipment-info/<str:eqp_id>",
        TimelineEquipmentInfoView.as_view(),
        name="timeline-equipment-info",
    ),
    path("logs", TimelineLogsView.as_view(), name="timeline-logs"),
    path("logs/eqp", TimelineEqpLogsView.as_view(), name="timeline-logs-eqp"),
    path("logs/tip", TimelineTipLogsView.as_view(), name="timeline-logs-tip"),
    path("logs/ctttm", TimelineCtttmLogsView.as_view(), name="timeline-logs-ctttm"),
    path("logs/racb", TimelineRacbLogsView.as_view(), name="timeline-logs-racb"),
    path("logs/drone", TimelineDroneLogsView.as_view(), name="timeline-logs-drone"),
]
