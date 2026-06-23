# =============================================================================
# 모듈 설명: observer 더미 엔드포인트 라우팅을 정의합니다.
# - 주요 경로: lines, sdwts, prc-groups, equipments, logs
# - 불변 조건: 상대 경로만 선언합니다.
# =============================================================================

from __future__ import annotations

from django.urls import path

from .views import (
    ObserverCtttmLogsView,
    ObserverEsopLogsView,
    ObserverEquipmentInfoView,
    ObserverEqpLogsView,
    ObserverEquipmentsView,
    ObserverLinesView,
    ObserverLogsView,
    ObserverPrcGroupView,
    ObserverRacbLogsView,
    ObserverSdwtView,
    ObserverTipLogsView,
    ObserverTkinPreventMatrixView,
    ObserverTkinPreventProcessesView,
    ObserverTkinPreventStepSeqsView,
)

urlpatterns = [
    path("lines", ObserverLinesView.as_view(), name="observer-lines"),
    path("sdwts", ObserverSdwtView.as_view(), name="observer-sdwts"),
    path("prc-groups", ObserverPrcGroupView.as_view(), name="observer-prc-groups"),
    path("equipments", ObserverEquipmentsView.as_view(), name="observer-equipments"),
    path(
        "equipment-info/<str:line_id>/<str:eqp_id>",
        ObserverEquipmentInfoView.as_view(),
        name="observer-equipment-info-line",
    ),
    path(
        "equipment-info/<str:eqp_id>",
        ObserverEquipmentInfoView.as_view(),
        name="observer-equipment-info",
    ),
    path("logs", ObserverLogsView.as_view(), name="observer-logs"),
    path("logs/eqp", ObserverEqpLogsView.as_view(), name="observer-logs-eqp"),
    path("logs/tip", ObserverTipLogsView.as_view(), name="observer-logs-tip"),
    path("logs/ctttm", ObserverCtttmLogsView.as_view(), name="observer-logs-ctttm"),
    path("logs/racb", ObserverRacbLogsView.as_view(), name="observer-logs-racb"),
    path("logs/esop", ObserverEsopLogsView.as_view(), name="observer-logs-esop"),
    path(
        "tkin-prevent/processes",
        ObserverTkinPreventProcessesView.as_view(),
        name="observer-tkin-prevent-processes",
    ),
    path(
        "tkin-prevent/step-seqs",
        ObserverTkinPreventStepSeqsView.as_view(),
        name="observer-tkin-prevent-step-seqs",
    ),
    path(
        "tkin-prevent/matrix",
        ObserverTkinPreventMatrixView.as_view(),
        name="observer-tkin-prevent-matrix",
    ),
]
