# =============================================================================
# 모듈 설명: 활동 로그 조회 셀렉터를 제공합니다.
# - 주요 함수: get_recent_activity_logs, get_app_access_* 계열 조회 함수
# - 불변 조건: 읽기 전용 QuerySet/집계만 반환합니다.
# =============================================================================
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.db.models import Count, Max, Q, QuerySet, Sum
from django.db.models.functions import TruncDate

from .models import ActivityLog, ExternalAppAccessDailyStat

APP_ACCESS_ACTION = "APP_ACCESS"
KST = ZoneInfo("Asia/Seoul")


def get_recent_activity_logs(*, limit: int) -> QuerySet[ActivityLog]:
    """최근 활동 로그를 최신순으로 조회합니다.

    입력:
    - limit: 반환할 최대 건수

    반환:
    - QuerySet[ActivityLog]: 최신순 ActivityLog QuerySet(사용자/프로필 포함)

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    safe_limit = max(1, limit)
    return ActivityLog.objects.select_related("user", "user__profile").order_by("-created_at")[:safe_limit]


def get_app_access_logs(
    *,
    start_at: datetime,
    end_at: datetime,
    app_id: str | None = None,
) -> QuerySet[ActivityLog]:
    """앱 접속 이벤트 로그를 기간/앱 기준으로 조회합니다.

    입력:
    - start_at: UTC 기준 조회 시작 시각(포함)
    - end_at: UTC 기준 조회 종료 시각(미포함)
    - app_id: 특정 앱 id 필터(선택)

    반환:
    - QuerySet[ActivityLog]: APP_ACCESS 이벤트 QuerySet

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    queryset = ActivityLog.objects.select_related("user").filter(
        action=APP_ACCESS_ACTION,
        created_at__gte=start_at,
        created_at__lt=end_at,
    )
    if app_id:
        queryset = queryset.filter(metadata__app_id=app_id)
    return queryset


def summarize_app_access_by_app(
    *,
    start_at: datetime,
    end_at: datetime,
    app_id: str | None = None,
) -> list[dict[str, object]]:
    """앱별 접속 이벤트를 집계합니다.

    입력:
    - start_at/end_at: UTC 기준 조회 범위
    - app_id: 특정 앱 id 필터(선택)

    반환:
    - list[dict[str, object]]: 앱별 집계 row

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    queryset = get_app_access_logs(start_at=start_at, end_at=end_at, app_id=app_id)
    return list(
        queryset.values("metadata__app_id", "metadata__app_name")
        .annotate(
            access_count=Count("id"),
            unique_user_count=Count(
                "user__knox_id",
                filter=Q(user__knox_id__isnull=False) & ~Q(user__knox_id=""),
                distinct=True,
            ),
            last_accessed_at=Max("created_at"),
        )
        .order_by("-access_count", "metadata__app_name", "metadata__app_id")
    )


def summarize_app_access_totals(
    *,
    start_at: datetime,
    end_at: datetime,
    app_id: str | None = None,
) -> dict[str, int]:
    """앱 접속 이벤트 전체 합계를 집계합니다.

    입력:
    - start_at/end_at: UTC 기준 조회 범위
    - app_id: 특정 앱 id 필터(선택)

    반환:
    - dict[str, int]: 전체 접속수와 고유 knox_id 수

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    queryset = get_app_access_logs(start_at=start_at, end_at=end_at, app_id=app_id)
    totals = queryset.aggregate(
        access_count=Count("id"),
        unique_user_count=Count(
            "user__knox_id",
            filter=Q(user__knox_id__isnull=False) & ~Q(user__knox_id=""),
            distinct=True,
        ),
    )
    return {
        "access_count": int(totals.get("access_count") or 0),
        "unique_user_count": int(totals.get("unique_user_count") or 0),
    }


def summarize_app_access_by_date(
    *,
    start_at: datetime,
    end_at: datetime,
    app_id: str | None = None,
) -> list[dict[str, object]]:
    """앱 접속 이벤트를 KST 날짜와 앱 기준으로 집계합니다.

    입력:
    - start_at/end_at: UTC 기준 조회 범위
    - app_id: 특정 앱 id 필터(선택)

    반환:
    - list[dict[str, object]]: 날짜/앱별 집계 row

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    queryset = get_app_access_logs(start_at=start_at, end_at=end_at, app_id=app_id)
    return list(
        queryset.annotate(local_date=TruncDate("created_at", tzinfo=KST))
        .values("local_date", "metadata__app_id", "metadata__app_name")
        .annotate(access_count=Count("id"))
        .order_by("local_date", "metadata__app_name", "metadata__app_id")
    )


def get_external_app_access_daily_stats(
    *,
    start_date: date,
    end_date: date,
    app_id: str | None = None,
) -> QuerySet[ExternalAppAccessDailyStat]:
    """외부 앱 일별 접속 집계 rows를 기간/앱 기준으로 조회합니다.

    입력:
    - start_date/end_date: KST 기준 조회 날짜 범위(포함)
    - app_id: 특정 앱 id 필터(선택)

    반환:
    - QuerySet[ExternalAppAccessDailyStat]: 외부 앱 일별 집계 QuerySet

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    queryset = ExternalAppAccessDailyStat.objects.filter(
        stat_date__gte=start_date,
        stat_date__lte=end_date,
    )
    if app_id:
        queryset = queryset.filter(app_id=app_id)
    return queryset


def summarize_external_app_access_by_app(
    *,
    start_date: date,
    end_date: date,
    app_id: str | None = None,
) -> list[dict[str, object]]:
    """외부 앱 접속 집계를 앱 기준으로 합산합니다.

    입력:
    - start_date/end_date: KST 기준 조회 날짜 범위(포함)
    - app_id: 특정 앱 id 필터(선택)

    반환:
    - list[dict[str, object]]: 앱별 외부 집계 row

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    queryset = get_external_app_access_daily_stats(start_date=start_date, end_date=end_date, app_id=app_id)
    return list(
        queryset.values("app_id", "app_name", "source_type", "source_name")
        .annotate(
            access_count=Sum("access_count"),
            unique_user_count=Sum("unique_user_count"),
            last_stat_date=Max("stat_date"),
        )
        .order_by("-access_count", "app_name", "app_id")
    )


def summarize_external_app_access_totals(
    *,
    start_date: date,
    end_date: date,
    app_id: str | None = None,
) -> dict[str, int]:
    """외부 앱 접속 집계 전체 합계를 반환합니다.

    입력:
    - start_date/end_date: KST 기준 조회 날짜 범위(포함)
    - app_id: 특정 앱 id 필터(선택)

    반환:
    - dict[str, int]: 전체 접속수와 외부 고유 사용자 수 합계

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    queryset = get_external_app_access_daily_stats(start_date=start_date, end_date=end_date, app_id=app_id)
    totals = queryset.aggregate(
        access_count=Sum("access_count"),
        unique_user_count=Sum("unique_user_count"),
    )
    return {
        "access_count": int(totals.get("access_count") or 0),
        "unique_user_count": int(totals.get("unique_user_count") or 0),
    }


def summarize_external_app_access_by_date(
    *,
    start_date: date,
    end_date: date,
    app_id: str | None = None,
) -> list[dict[str, object]]:
    """외부 앱 접속 집계를 날짜와 앱 기준으로 합산합니다.

    입력:
    - start_date/end_date: KST 기준 조회 날짜 범위(포함)
    - app_id: 특정 앱 id 필터(선택)

    반환:
    - list[dict[str, object]]: 날짜/앱별 외부 집계 row

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    queryset = get_external_app_access_daily_stats(start_date=start_date, end_date=end_date, app_id=app_id)
    return list(
        queryset.values("stat_date", "app_id", "app_name", "source_type", "source_name")
        .annotate(access_count=Sum("access_count"))
        .order_by("stat_date", "app_name", "app_id")
    )
