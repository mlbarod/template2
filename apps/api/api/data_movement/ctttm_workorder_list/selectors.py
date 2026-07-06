"""ctttm_workorder_list 읽기 전용 selector입니다."""

from __future__ import annotations

from django.db.models import QuerySet

from api.data_movement.ctttm_workorder_list.models import CtttmWorkorderList, CtttmWorkorderListLoadJob


def list_recent_load_jobs(*, limit: int = 20) -> QuerySet[CtttmWorkorderListLoadJob]:
    """최근 적재 이력을 최신순으로 반환합니다."""

    return CtttmWorkorderListLoadJob.objects.order_by("-created_at", "-id")[:limit]


def load_workorder_descriptions_by_ids(*, workorder_ids: list[str]) -> dict[str, str]:
    """workorder_id별 CTTTM 작업 설명을 반환합니다."""

    normalized_ids = [workorder_id for workorder_id in dict.fromkeys(workorder_ids) if workorder_id]
    if not normalized_ids:
        return {}

    rows = (
        CtttmWorkorderList.objects.filter(workorder_id__in=normalized_ids)
        .exclude(description__isnull=True)
        .exclude(description="")
        .order_by("workorder_id", "-inprg_date", "-id")
        .values("workorder_id", "description")
    )
    descriptions: dict[str, str] = {}
    for row in rows:
        workorder_id = str(row["workorder_id"])
        if workorder_id not in descriptions:
            descriptions[workorder_id] = str(row["description"])
    return descriptions
