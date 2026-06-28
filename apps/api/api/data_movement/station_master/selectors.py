"""station_master 읽기 전용 selector입니다."""

from __future__ import annotations

from django.db.models import QuerySet

from api.data_movement.station_master.models import StationMaster, StationMasterLoadJob


def list_recent_load_jobs(*, limit: int = 20) -> QuerySet[StationMasterLoadJob]:
    """최근 적재 이력을 최신순으로 반환합니다."""

    return StationMasterLoadJob.objects.order_by("-created_at", "-id")[:limit]


def list_distinct_sdwt_prod_lookup_values() -> set[str]:
    """station_master에 등록된 sdwt_prod_lookup 값 집합을 반환합니다."""

    values = (
        StationMaster.objects.exclude(sdwt_prod_lookup__isnull=True)
        .exclude(sdwt_prod_lookup__exact="")
        .values_list("sdwt_prod_lookup", flat=True)
    )
    return {
        value.strip().upper()
        for value in values
        if isinstance(value, str) and value.strip()
    }
