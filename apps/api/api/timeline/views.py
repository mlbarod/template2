# =============================================================================
# 모듈 설명: timeline 더미 엔드포인트를 제공합니다.
# - 주요 클래스: TimelineLinesView, TimelineEquipmentInfoView, TimelineLogsView 등
# - 불변 조건: 더미 데이터만 반환하며 외부 호출은 없습니다.
# =============================================================================

"""타임라인 더미 뷰."""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

from . import selectors


def _query_id(request: HttpRequest, key: str) -> str:
    """query string ID 값을 동일한 규칙으로 정규화합니다."""

    return selectors.normalize_id(request.GET.get(key))


def _missing_query_response(message: str) -> JsonResponse:
    """필수 query 누락 응답을 생성합니다."""

    return JsonResponse({"error": message}, status=400)


def _required_query_id(
    request: HttpRequest,
    key: str,
    message: str,
) -> tuple[str, JsonResponse | None]:
    """필수 query ID를 정규화하고 누락 응답을 함께 반환합니다."""

    value = _query_id(request, key)
    if not value:
        return "", _missing_query_response(message)
    return value, None


class TimelineLinesView(APIView):
    """더미 라인 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 라인 목록 배열

        부작용:
        - 없음

        오류:
        - 없음

        예시 요청:
        - 예시 요청: GET /api/v1/timeline/lines

        snake/camel 호환:
        - 해당 없음(쿼리/바디 없음)
        """
        return JsonResponse(selectors.list_lines(), safe=False)


class TimelineSdwtView(APIView):
    """라인 기준 SDWT 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인 기준 SDWT 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: SDWT 목록 배열

        부작용:
        - 없음

        오류:
        - 400: lineId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/timeline/sdwts?lineId=LINE-A

        snake/camel 호환:
        - lineId만 지원(snake_case 미지원)
        """
        line_id, error_response = _required_query_id(
            request,
            "lineId",
            "lineId is required",
        )
        if error_response:
            return error_response

        return JsonResponse(selectors.list_sdwt_for_line(line_id=line_id), safe=False)


class TimelinePrcGroupView(APIView):
    """라인/SDWT 조합 기준 PRC 그룹 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인/SDWT 기준 PRC 그룹 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: PRC 그룹 목록 배열

        부작용:
        - 없음

        오류:
        - 400: lineId 또는 sdwtId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/timeline/prc-groups?lineId=LINE-A&sdwtId=SD-10

        snake/camel 호환:
        - lineId/sdwtId만 지원(snake_case 미지원)
        """
        line_id = _query_id(request, "lineId")
        sdwt_id = _query_id(request, "sdwtId")

        if not line_id or not sdwt_id:
            return _missing_query_response("lineId and sdwtId are required")

        return JsonResponse(selectors.list_prc_groups(line_id=line_id, sdwt_id=sdwt_id), safe=False)


class TimelineEquipmentsView(APIView):
    """라인/SDWT/PRC 그룹 조합 기준 설비 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인/SDWT/PRC 그룹 기준 설비 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 설비 목록 배열

        부작용:
        - 없음

        오류:
        - 400: lineId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/timeline/equipments?lineId=LINE-A
        - 예시 요청: GET /api/v1/timeline/equipments?lineId=LINE-A&sdwtId=SD-10
        - 예시 요청: GET /api/v1/timeline/equipments?lineId=LINE-A&sdwtId=SD-10&prcGroup=ETCH

        snake/camel 호환:
        - lineId/sdwtId/prcGroup만 지원(snake_case 미지원)
        """
        line_id, error_response = _required_query_id(
            request,
            "lineId",
            "lineId is required",
        )
        if error_response:
            return error_response
        sdwt_id = _query_id(request, "sdwtId")
        prc_group = _query_id(request, "prcGroup")

        return JsonResponse(
            selectors.list_equipments(
                line_id=line_id,
                sdwt_id=sdwt_id,
                prc_group=prc_group,
            ),
            safe=False,
        )


class TimelineEquipmentInfoView(APIView):
    """eqpId 기준 설비 메타데이터를 반환합니다(선택적으로 line 범위 제한)."""

    def get(
        self,
        request: HttpRequest,
        line_id: str | None = None,
        eqp_id: str | None = None,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """eqpId 기준 설비 메타데이터를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - line_id: 라인 ID(선택, 경로 파라미터)
        - eqp_id: 설비 ID(경로 파라미터)
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 설비 메타데이터

        부작용:
        - 없음

        오류:
        - 400: eqpId 누락
        - 404: 설비 미존재 또는 라인 범위 불일치

        예시 요청:
        - 예시 요청: GET /api/v1/timeline/equipment-info/EQP-ALPHA
        - 예시 요청: GET /api/v1/timeline/equipment-info/LINE-A/EQP-ALPHA

        snake/camel 호환:
        - 해당 없음(경로 파라미터만 사용)
        """
        # -----------------------------------------------------------------------------
        # 1) eqpId 유효성 확인
        # -----------------------------------------------------------------------------
        eqp_key = selectors.normalize_id(eqp_id)
        if not eqp_key:
            return _missing_query_response("eqpId is required")

        # -----------------------------------------------------------------------------
        # 2) 설비 메타데이터 조회
        # -----------------------------------------------------------------------------
        info = selectors.get_equipment_info(eqp_id=eqp_key)
        if not info:
            return JsonResponse({"error": "Equipment not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 3) 라인 범위 제한 확인
        # -----------------------------------------------------------------------------
        if line_id and selectors.normalize_id(line_id) != selectors.normalize_id(info["lineId"]):
            return JsonResponse({"error": "Equipment not found for line"}, status=404)

        # -----------------------------------------------------------------------------
        # 4) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse(info)


class _TimelineLogsByTypeView(APIView):
    """log_key에 해당하는 더미 로그 배열을 반환하는 베이스 뷰입니다."""

    log_key: str = ""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """설비 로그 중 지정된 타입 로그를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 타입별 로그 배열

        부작용:
        - 없음

        오류:
        - 400: eqpId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/timeline/logs/eqp?eqpId=EQP-ALPHA

        snake/camel 호환:
        - eqpId만 지원(snake_case 미지원)
        """
        eqp_id, error_response = _required_query_id(request, "eqpId", "eqpId is required")
        if error_response:
            return error_response

        return JsonResponse(selectors.get_logs_by_type(eqp_id=eqp_id, log_key=self.log_key), safe=False)


class TimelineLogsView(_TimelineLogsByTypeView):
    """설비의 전체 로그를 타입별로 합쳐 반환합니다."""

    log_key = ""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """설비의 전체 로그를 합쳐 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 통합 로그 배열

        부작용:
        - 없음

        오류:
        - 400: eqpId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/timeline/logs?eqpId=EQP-ALPHA

        snake/camel 호환:
        - eqpId만 지원(snake_case 미지원)
        """
        eqp_id, error_response = _required_query_id(request, "eqpId", "eqpId is required")
        if error_response:
            return error_response

        return JsonResponse(selectors.get_merged_logs(eqp_id=eqp_id), safe=False)


class TimelineEqpLogsView(_TimelineLogsByTypeView):
    """설비(EQP) 타입 로그만 반환합니다."""

    log_key = "eqp"


class TimelineTipLogsView(_TimelineLogsByTypeView):
    """TIP 타입 로그만 반환합니다."""

    log_key = "tip"


class TimelineCtttmLogsView(_TimelineLogsByTypeView):
    """CTTTM 타입 로그만 반환합니다."""

    log_key = "ctttm"


class TimelineRacbLogsView(_TimelineLogsByTypeView):
    """RACB 타입 로그만 반환합니다."""

    log_key = "racb"


class TimelineJiraLogsView(_TimelineLogsByTypeView):
    """Jira 타입 로그만 반환합니다."""

    log_key = "jira"


__all__ = [
    "TimelineCtttmLogsView",
    "TimelineEquipmentInfoView",
    "TimelineEqpLogsView",
    "TimelineEquipmentsView",
    "TimelineJiraLogsView",
    "TimelineLinesView",
    "TimelineLogsView",
    "TimelinePrcGroupView",
    "TimelineRacbLogsView",
    "TimelineSdwtView",
    "TimelineTipLogsView",
]
