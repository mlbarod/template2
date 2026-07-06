"""ct_process_comment 읽기 전용 selector입니다."""

from __future__ import annotations

from django.db.models import QuerySet

from api.data_movement.ct_process_comment.models import CtProcessComment, CtProcessCommentLoadJob


def list_recent_load_jobs(*, limit: int = 20) -> QuerySet[CtProcessCommentLoadJob]:
    """최근 적재 이력을 최신순으로 반환합니다."""

    return CtProcessCommentLoadJob.objects.order_by("-created_at", "-id")[:limit]


def list_pending_summary_comments(
    *,
    limit: int,
    workorder_id: str | None = None,
) -> QuerySet[CtProcessComment]:
    """OpenWebUI 요약 대상 comment row를 최근 업데이트 순으로 반환합니다."""

    queryset = CtProcessComment.objects.filter(update_flag="Y").order_by("-updated_at", "-id")
    if workorder_id:
        queryset = queryset.filter(workorder_id=workorder_id)
    return queryset[:limit]
