# =============================================================================
# 모듈 설명: observer API 엔드포인트를 제공합니다.
# - 주요 클래스: ObserverLinesView, ObserverEquipmentInfoView, ObserverLogsView 등
# - 불변 조건: HTTP 계층은 selectors를 통해서만 조회합니다.
# =============================================================================

"""Observer API 뷰."""
from __future__ import annotations

from datetime import datetime, time, timezone as datetime_timezone

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
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


def _parse_log_limit(request: HttpRequest) -> tuple[int | None, JsonResponse | None]:
    """로그 조회 limit 값을 검증하고, 입력된 경우에만 최대값 안으로 보정합니다."""

    raw_limit = (request.GET.get("limit") or "").strip()
    if not raw_limit:
        return None, None

    try:
        limit = int(raw_limit)
    except ValueError:
        return 0, _missing_query_response("limit must be a positive integer")

    if limit <= 0:
        return 0, _missing_query_response("limit must be a positive integer")
    return min(limit, selectors.MAX_LOG_LIMIT), None


def _to_comparable_datetime(value: datetime) -> datetime:
    """aware/naive datetime 비교가 가능하도록 UTC naive 값으로 통일합니다."""

    if timezone.is_aware(value):
        return value.astimezone(datetime_timezone.utc).replace(tzinfo=None)
    return value


def _parse_log_datetime(
    request: HttpRequest,
    key: str,
    *,
    is_end: bool = False,
) -> tuple[str | None, datetime | None, JsonResponse | None]:
    """로그 조회 시각 파라미터를 ISO 문자열과 비교용 datetime으로 변환합니다."""

    raw_value = (request.GET.get(key) or "").strip()
    if not raw_value:
        return None, None, None

    parsed_date = parse_date(raw_value)
    if parsed_date is not None and len(raw_value) == 10:
        boundary_time = time.max if is_end else time.min
        value = datetime.combine(parsed_date, boundary_time)
        return value.isoformat(), value, None

    parsed_datetime = parse_datetime(raw_value)
    if parsed_datetime is not None:
        comparable = _to_comparable_datetime(parsed_datetime)
        return comparable.isoformat(), comparable, None

    return (
        None,
        None,
        _missing_query_response(f"{key} must be a valid date or datetime"),
    )


def _log_query_options(
    request: HttpRequest,
) -> tuple[dict[str, object], JsonResponse | None]:
    """로그 조회 공통 query option을 파싱합니다."""

    limit, limit_error = _parse_log_limit(request)
    if limit_error:
        return {}, limit_error

    start_at, start_comparable, start_error = _parse_log_datetime(request, "from")
    if start_error:
        return {}, start_error

    end_at, end_comparable, end_error = _parse_log_datetime(request, "to", is_end=True)
    if end_error:
        return {}, end_error

    if start_comparable and end_comparable and start_comparable > end_comparable:
        return {}, _missing_query_response("from must be earlier than or equal to to")

    return {"start_at": start_at, "end_at": end_at, "limit": limit}, None


class ObserverLinesView(APIView):
    """라인 목록을 반환합니다."""

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
        - 예시 요청: GET /api/v1/observer/lines

        snake/camel 호환:
        - 해당 없음(쿼리/바디 없음)
        """
        return JsonResponse(selectors.list_lines(), safe=False)


class ObserverSdwtView(APIView):
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
        - 예시 요청: GET /api/v1/observer/sdwts?lineId=LINE-A

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


class ObserverPrcGroupView(APIView):
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
        - 예시 요청: GET /api/v1/observer/prc-groups?lineId=LINE-A&sdwtId=SD-10

        snake/camel 호환:
        - lineId/sdwtId만 지원(snake_case 미지원)
        """
        line_id = _query_id(request, "lineId")
        sdwt_id = _query_id(request, "sdwtId")

        if not line_id or not sdwt_id:
            return _missing_query_response("lineId and sdwtId are required")

        return JsonResponse(
            selectors.list_prc_groups(line_id=line_id, sdwt_id=sdwt_id),
            safe=False,
        )


class ObserverEquipmentsView(APIView):
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
        - 예시 요청: GET /api/v1/observer/equipments?lineId=LINE-A
        - 예시 요청: GET /api/v1/observer/equipments?lineId=LINE-A&sdwtId=SD-10
        - 예시 요청: GET /api/v1/observer/equipments?lineId=LINE-A&sdwtId=SD-10&prcGroup=ETCH

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


def _required_tkin_scope(
    request: HttpRequest,
) -> tuple[dict[str, str], JsonResponse | None]:
    """m_tkin_prevent scope query 값을 검증합니다."""

    line_id = _query_id(request, "lineId")
    sdwt_id = _query_id(request, "sdwtId")
    prc_group = _query_id(request, "prcGroup")

    if not line_id or not sdwt_id or not prc_group:
        return {}, _missing_query_response("lineId, sdwtId and prcGroup are required")

    return {"line_id": line_id, "sdwt_id": sdwt_id, "prc_group": prc_group}, None


class ObserverTkinPreventProcessesView(APIView):
    """m_tkin_prevent process_id 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """m_tkin_prevent process_id 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: process_id option 목록

        부작용:
        - 없음

        오류:
        - 400: lineId, sdwtId, prcGroup 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/tkin-prevent/processes?lineId=L1&sdwtId=S1&prcGroup=P1

        snake/camel 호환:
        - lineId/sdwtId/prcGroup만 지원(snake_case 미지원)
        """
        scope, error_response = _required_tkin_scope(request)
        if error_response:
            return error_response

        return JsonResponse(
            selectors.list_tkin_prevent_processes(**scope),
            safe=False,
        )


class ObserverTkinPreventStepSeqsView(APIView):
    """m_tkin_prevent step_seq 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """m_tkin_prevent step_seq 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: step_seq option 목록

        부작용:
        - 없음

        오류:
        - 400: lineId, sdwtId, prcGroup, processId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/tkin-prevent/step-seqs?lineId=L1&sdwtId=S1&prcGroup=P1&processId=P100

        snake/camel 호환:
        - lineId/sdwtId/prcGroup/processId만 지원(snake_case 미지원)
        """
        scope, error_response = _required_tkin_scope(request)
        if error_response:
            return error_response

        process_id = _query_id(request, "processId")
        if not process_id:
            return _missing_query_response("processId is required")

        return JsonResponse(
            selectors.list_tkin_prevent_step_seqs(
                **scope,
                process_id=process_id,
            ),
            safe=False,
        )


class ObserverTkinPreventMatrixView(APIView):
    """m_tkin_prevent matrix 데이터를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """m_tkin_prevent matrix 데이터를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: columns/rows matrix 데이터

        부작용:
        - 없음

        오류:
        - 400: lineId, sdwtId, prcGroup, processId, stepSeq 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/tkin-prevent/matrix?lineId=L1&sdwtId=S1&prcGroup=P1&processId=P100&stepSeq=10

        snake/camel 호환:
        - lineId/sdwtId/prcGroup/processId/stepSeq만 지원(snake_case 미지원)
        """
        scope, error_response = _required_tkin_scope(request)
        if error_response:
            return error_response

        process_id = _query_id(request, "processId")
        step_seq = _query_id(request, "stepSeq")
        if not process_id or not step_seq:
            return _missing_query_response("processId and stepSeq are required")

        return JsonResponse(
            selectors.get_tkin_prevent_matrix(
                **scope,
                process_id=process_id,
                step_seq=step_seq,
            ),
        )


class ObserverEquipmentInfoView(APIView):
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
        - 예시 요청: GET /api/v1/observer/equipment-info/EQP-ALPHA
        - 예시 요청: GET /api/v1/observer/equipment-info/LINE-A/EQP-ALPHA

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


class _ObserverLogsByTypeView(APIView):
    """log_key에 해당하는 로그 배열을 반환하는 베이스 뷰입니다."""

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
        - 예시 요청: GET /api/v1/observer/logs/eqp?eqpId=EQP-ALPHA

        snake/camel 호환:
        - eqpId만 지원(snake_case 미지원)
        """
        eqp_id, error_response = _required_query_id(request, "eqpId", "eqpId is required")
        if error_response:
            return error_response

        log_options, option_error = _log_query_options(request)
        if option_error:
            return option_error

        return JsonResponse(
            selectors.get_logs_by_type(
                eqp_id=eqp_id,
                log_key=self.log_key,
                **log_options,
            ),
            safe=False,
        )


class ObserverLogsView(_ObserverLogsByTypeView):
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
        - 예시 요청: GET /api/v1/observer/logs?eqpId=EQP-ALPHA

        snake/camel 호환:
        - eqpId만 지원(snake_case 미지원)
        """
        eqp_id, error_response = _required_query_id(request, "eqpId", "eqpId is required")
        if error_response:
            return error_response

        log_options, option_error = _log_query_options(request)
        if option_error:
            return option_error

        return JsonResponse(
            selectors.get_merged_logs(
                eqp_id=eqp_id,
                **log_options,
            ),
            safe=False,
        )


class ObserverEqpLogsView(_ObserverLogsByTypeView):
    """설비(EQP) 타입 로그만 반환합니다."""

    log_key = "eqp"


class ObserverTipLogsView(_ObserverLogsByTypeView):
    """TIP 타입 로그만 반환합니다."""

    log_key = "tip"


class ObserverCtttmLogsView(_ObserverLogsByTypeView):
    """CTTTM 타입 로그만 반환합니다."""

    log_key = "ctttm"


class ObserverRacbLogsView(_ObserverLogsByTypeView):
    """RACB 타입 로그만 반환합니다."""

    log_key = "racb"


class ObserverEsopLogsView(_ObserverLogsByTypeView):
    """ESOP 타입 로그만 반환합니다."""

    log_key = "esop"


__all__ = [
    "ObserverCtttmLogsView",
    "ObserverEsopLogsView",
    "ObserverEquipmentInfoView",
    "ObserverEqpLogsView",
    "ObserverEquipmentsView",
    "ObserverLinesView",
    "ObserverLogsView",
    "ObserverPrcGroupView",
    "ObserverRacbLogsView",
    "ObserverSdwtView",
    "ObserverTipLogsView",
    "ObserverTkinPreventMatrixView",
    "ObserverTkinPreventProcessesView",
    "ObserverTkinPreventStepSeqsView",
]
