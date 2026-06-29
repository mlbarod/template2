# =============================================================================
# 모듈 설명: 활동 로그 조회 APIView를 제공합니다.
# - 주요 클래스: ActivityLogView, AppAccessEventView, AppAccessStatsView, ManualAppAccessStatsView
# - 불변 조건: 권한 확인 후 view는 HTTP 처리만 수행합니다.
# =============================================================================

"""액티비티 로그 조회 엔드포인트를 제공합니다."""
from __future__ import annotations

from typing import Any

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import parse_json_body

from .serializers import normalize_app_access_payload, normalize_manual_app_access_paste_payload
from .services import (
    build_manual_app_access_preview,
    commit_manual_app_access_stats,
    get_app_access_stats_payload,
    get_recent_activity_payload,
    record_app_access,
)

# 조회 건수 관련 상수(한 곳에서 관리)
DEFAULT_LIMIT: int = 50
MAX_LIMIT: int = 200
MIN_LIMIT: int = 1
VIEW_ACTIVITY_LOG_PERMISSIONS = ("activity.view_activitylog", "api.view_activitylog")


def _parse_activity_log_limit(raw_limit: str | None) -> int:
    """limit 쿼리 값을 기존 규칙대로 기본값/허용 범위 안으로 정규화합니다."""

    try:
        limit = int(raw_limit) if raw_limit is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        # 비정상 값은 기존 API 동작처럼 오류 대신 기본값으로 처리합니다.
        limit = DEFAULT_LIMIT

    return max(MIN_LIMIT, min(limit, MAX_LIMIT))


def _can_view_activity_logs(user: Any) -> bool:
    """현재 사용자가 ActivityLog 조회 권한을 하나라도 보유했는지 확인합니다."""

    return any(user.has_perm(permission) for permission in VIEW_ACTIVITY_LOG_PERMISSIONS)


class ActivityLogView(APIView):
    """최근 액티비티 로그 조회.

    - 인증 필요
    - 권한 코드: "activity.view_activitylog" 또는 "api.view_activitylog"
    - GET 파라미터:
        - limit (int, optional): 반환 개수. 기본 50, 최소 1, 최대 200.
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """최근 로그를 최대 limit개까지 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: {"results": [...]} 형태의 응답

        부작용:
        - 없음(읽기 전용)

        오류:
        - 401: 인증 실패
        - 403: 권한 없음

        예시 요청:
        - 예시 요청: GET /api/v1/activity/logs?limit=50

        응답 필드:
        - 필드: id, user, role, action, path, method, status, metadata, timestamp

        snake/camel 호환:
        - 해당 없음(쿼리 파라미터 limit만 사용)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증/권한 체크
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        if not _can_view_activity_logs(request.user):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 2) limit 파라미터 파싱/정규화
        # -----------------------------------------------------------------------------
        limit = _parse_activity_log_limit(request.GET.get("limit"))

        # -----------------------------------------------------------------------------
        # 3) payload 생성
        # -----------------------------------------------------------------------------
        payload = get_recent_activity_payload(limit=limit)

        # -----------------------------------------------------------------------------
        # 4) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse({"results": payload})


@method_decorator(csrf_exempt, name="dispatch")
class AppAccessEventView(APIView):
    """앱 화면 진입 이벤트 기록 API입니다."""

    permission_classes: list[type] = []

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자의 앱 접속 이벤트를 기록합니다.

        입력:
        - 요청: appId, appName, path를 담은 JSON body

        반환:
        - JsonResponse: 생성된 이벤트 id

        부작용:
        - ActivityLog 테이블에 APP_ACCESS 이벤트를 생성합니다.

        오류:
        - 401: 인증 실패
        - 400: JSON/필수값 오류
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        payload = parse_json_body(request)
        normalized, error = normalize_app_access_payload(payload)
        if error or normalized is None:
            return JsonResponse({"error": error or "Invalid payload"}, status=400)

        entry = record_app_access(
            user=request.user,
            app_id=normalized["app_id"],
            app_name=normalized["app_name"],
            path=normalized["path"],
        )
        return JsonResponse({"id": entry.pk}, status=201)


class AppAccessStatsView(APIView):
    """슈퍼유저 전용 앱 접속 통계 조회 API입니다."""

    permission_classes: list[type] = []

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """KST 기준 날짜 범위의 앱별 접속 통계를 반환합니다.

        입력:
        - from: YYYY-MM-DD(선택)
        - to: YYYY-MM-DD(선택)
        - appId: 특정 앱 id(선택)
        - period: day/week/month(선택)

        반환:
        - JsonResponse: summary/apps/series payload

        부작용:
        - 없음(읽기 전용)

        오류:
        - 401: 인증 실패
        - 403: 슈퍼유저 아님
        - 400: 날짜 범위 오류
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        if not request.user.is_superuser:
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            payload = get_app_access_stats_payload(
                from_value=request.GET.get("from"),
                to_value=request.GET.get("to"),
                app_id=request.GET.get("appId") or request.GET.get("app_id"),
                period_value=request.GET.get("period") or request.GET.get("granularity"),
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        return JsonResponse(payload)


class ManualAppAccessStatsPreviewView(APIView):
    """슈퍼유저 전용 외부 앱 접속현황 붙여넣기 미리보기 API입니다."""

    permission_classes: list[type] = []

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """붙여넣기 원문을 검증하고 반영 전 미리보기를 반환합니다.

        입력:
        - pastedText: 스프레드시트에서 복사한 TSV/CSV 원문
        - sourceName: 입력 출처 이름(선택)

        반환:
        - JsonResponse: summary/errors/rows preview payload

        부작용:
        - 없음(검증 전용)

        오류:
        - 401: 인증 실패
        - 403: 슈퍼유저 아님
        - 400: JSON/필수값 오류
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        if not request.user.is_superuser:
            return JsonResponse({"error": "Forbidden"}, status=403)

        normalized, error = normalize_manual_app_access_paste_payload(parse_json_body(request))
        if error or normalized is None:
            return JsonResponse({"error": error or "Invalid payload"}, status=400)

        payload = build_manual_app_access_preview(
            pasted_text=normalized["pasted_text"],
            source_name=normalized["source_name"],
        )
        return JsonResponse(payload)


class ManualAppAccessStatsCommitView(APIView):
    """슈퍼유저 전용 외부 앱 접속현황 수동 반영 API입니다."""

    permission_classes: list[type] = []

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """검증된 붙여넣기 데이터를 외부 앱 일별 접속현황으로 반영합니다.

        입력:
        - pastedText: 스프레드시트에서 복사한 TSV/CSV 원문
        - sourceName: 입력 출처 이름(선택)

        반환:
        - JsonResponse: commit 요약과 preview payload

        부작용:
        - ExternalAppAccessDailyStat rows를 생성하거나 갱신합니다.

        오류:
        - 401: 인증 실패
        - 403: 슈퍼유저 아님
        - 400: JSON/필수값/행 검증 오류
        """

        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        if not request.user.is_superuser:
            return JsonResponse({"error": "Forbidden"}, status=403)

        normalized, error = normalize_manual_app_access_paste_payload(parse_json_body(request))
        if error or normalized is None:
            return JsonResponse({"error": error or "Invalid payload"}, status=400)

        try:
            payload = commit_manual_app_access_stats(
                pasted_text=normalized["pasted_text"],
                source_name=normalized["source_name"],
                user=request.user,
            )
        except ValueError as exc:
            return JsonResponse(
                {
                    "error": str(exc),
                    "preview": getattr(exc, "preview", None),
                },
                status=400,
            )

        return JsonResponse(payload, status=201)


__all__ = [
    "ActivityLogView",
    "AppAccessEventView",
    "AppAccessStatsView",
    "ManualAppAccessStatsCommitView",
    "ManualAppAccessStatsPreviewView",
]
