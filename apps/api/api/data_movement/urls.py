"""data_movement API 라우팅입니다."""

from __future__ import annotations

from django.urls import path

from api.data_movement.views import DataMovementCtProcessCommentSummaryTriggerView, DataMovementLoadTriggerView

urlpatterns = [
    path(
        "ct_process_comment/summarize/",
        DataMovementCtProcessCommentSummaryTriggerView.as_view(),
        name="data-movement-ct-process-comment-summarize",
    ),
    path("<str:table_name>/load/", DataMovementLoadTriggerView.as_view(), name="data-movement-load"),
]
