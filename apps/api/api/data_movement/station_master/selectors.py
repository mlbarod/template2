"""station_master 읽기 전용 selector입니다."""

from __future__ import annotations

from collections.abc import Iterable

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


def map_station_lookup_to_sdwt_prod_lookup(*, station_lookup_values: Iterable[str]) -> dict[str, str]:
    """station_lookup 값별 sdwt_prod_lookup 매핑을 반환합니다.

    입력:
    - station_lookup_values: 조회할 station_lookup 값 목록.

    반환:
    - dict[str, str]: 대문자 station_lookup → 원본 sdwt_prod_lookup 매핑.

    부작용:
    - 없음. 읽기 전용 조회입니다.
    """

    lookup_keys = {
        value.strip().upper()
        for value in station_lookup_values
        if isinstance(value, str) and value.strip()
    }
    if not lookup_keys:
        return {}

    rows = (
        StationMaster.objects.filter(station_lookup__in=lookup_keys)
        .exclude(sdwt_prod_lookup=None)
        .values_list("station_lookup", "sdwt_prod_lookup")
    )
    return {
        station_lookup.strip().upper(): sdwt_prod_lookup
        for station_lookup, sdwt_prod_lookup in rows
        if isinstance(station_lookup, str) and station_lookup.strip() and sdwt_prod_lookup
    }
