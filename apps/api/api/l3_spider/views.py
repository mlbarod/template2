# =============================================================================
# 모듈: L3 Spider API 뷰
# 주요 엔드포인트: meta, summary, data
# 주요 가정: 로그인 사용자만 조회할 수 있습니다.
# =============================================================================
from __future__ import annotations

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from api.common.services import ensure_airflow_token, parse_json_body_or_error_when_present

try:
    import orjson

    def _fast_response(data, status: int = 200):
        from django.http import HttpResponse
        return HttpResponse(
            orjson.dumps(data),
            content_type="application/json; charset=utf-8",
            status=status,
        )
except ImportError:
    from rest_framework.response import Response as _DRFResponse

    def _fast_response(data, status: int = 200):
        return _DRFResponse(data, status=status)

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import (
    L3SpiderDataRequestSerializer,
    L3SpiderExclusionFilterSerializer,
    L3SpiderFilterCandidatesSerializer,
    L3SpiderMailRulePermissionUpdateSerializer,
    L3SpiderMailRuleSerializer,
    L3SpiderMailTriggerSerializer,
)


def _error_response(error: Exception) -> Response:
    status_code = getattr(error, "status_code", 400)
    return Response({"error": str(error)}, status=status_code)


class L3SpiderMetaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        try:
            return Response(services.get_meta(user=request.user))
        except services.L3SpiderServiceError as error:
            return _error_response(error)


class L3SpiderUnmappedLineRulesView(APIView):
    """개발자 옵션에서 미매핑 line name 규칙을 조회합니다."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        try:
            return Response(services.get_unmapped_line_name_rules())
        except Exception as error:
            return _error_response(error)


class L3SpiderStructureView(APIView):
    """파일명 스캔만으로 edsStepSeqs·edsStepPpids를 즉시 반환합니다."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        serializer = L3SpiderDataRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                services.get_structure(serializer.validated_data, user=request.user)
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)


class L3SpiderStatsView(APIView):
    """slim parquet 읽기로 stats + PPID별 last_tkin_time을 반환합니다."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        serializer = L3SpiderDataRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return _fast_response(
                services.get_stats(serializer.validated_data, user=request.user)
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)


class L3SpiderSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        serializer = L3SpiderDataRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                services.get_summary(serializer.validated_data, user=request.user)
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)


class L3SpiderDailySummaryView(APIView):
    """선택한 날짜 전체의 이상감지 요약(헤드라인/매트릭스/TopEDS/드릴다운)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = L3SpiderDataRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return _fast_response(
                services.get_daily_summary(serializer.validated_data, user=request.user)
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)


class L3SpiderDataView(APIView):
    """차트 행 데이터: orjson + 컬럼 포맷으로 빠르게 반환합니다."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = L3SpiderDataRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return _fast_response(
                services.get_data(serializer.validated_data, user=request.user)
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)


class L3SpiderExclusionFilterListCreateView(APIView):
    """제외 필터 목록 조회 및 생성."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        return Response(services.list_exclusion_filters(user=request.user))

    def post(self, request, *args, **kwargs) -> Response:
        serializer = L3SpiderExclusionFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.create_exclusion_filter(serializer.validated_data, user=request.user)
        return Response(data, status=201)


class L3SpiderExclusionFilterDetailView(APIView):
    """제외 필터 단건 수정/삭제."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int, *args, **kwargs) -> Response:
        serializer = L3SpiderExclusionFilterSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                services.update_exclusion_filter(
                    pk,
                    serializer.validated_data,
                    user=request.user,
                )
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)

    def delete(self, request, pk: int, *args, **kwargs) -> Response:
        try:
            services.delete_exclusion_filter(pk, user=request.user)
        except services.L3SpiderServiceError as error:
            return _error_response(error)
        return Response(status=204)


class L3SpiderMailRuleListCreateView(APIView):
    """메일 알림 rule 목록 조회 및 생성."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        try:
            return Response(services.list_mail_rules(user=request.user))
        except services.L3SpiderServiceError as error:
            return _error_response(error)

    def post(self, request, *args, **kwargs) -> Response:
        serializer = L3SpiderMailRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            data = services.create_mail_rule(serializer.validated_data, user=request.user)
        except services.L3SpiderServiceError as error:
            return _error_response(error)
        return Response(data, status=201)


class L3SpiderMailRuleDetailView(APIView):
    """메일 알림 rule 단건 수정/삭제."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int, *args, **kwargs) -> Response:
        serializer = L3SpiderMailRuleSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                services.update_mail_rule(
                    pk,
                    serializer.validated_data,
                    user=request.user,
                )
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)

    def delete(self, request, pk: int, *args, **kwargs) -> Response:
        try:
            services.delete_mail_rule(pk, user=request.user)
        except services.L3SpiderServiceError as error:
            return _error_response(error)
        return Response(status=204)


class L3SpiderMailRulePermissionView(APIView):
    """메일 알림 rule 공유 권한 조회/교체."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int, *args, **kwargs) -> Response:
        try:
            return Response(
                {"permissions": services.list_mail_rule_permissions(pk, user=request.user)}
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)

    def put(self, request, pk: int, *args, **kwargs) -> Response:
        serializer = L3SpiderMailRulePermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                services.replace_mail_rule_permissions(
                    pk,
                    serializer.validated_data["permissions"],
                    user=request.user,
                )
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)

    def patch(self, request, pk: int, *args, **kwargs) -> Response:
        return self.put(request, pk, *args, **kwargs)


class L3SpiderMailRuleTestSendView(APIView):
    """메일 알림 rule을 단발성으로 테스트 발송."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int, *args, **kwargs) -> Response:
        try:
            return Response(services.send_mail_rule_test(pk, user=request.user))
        except services.L3SpiderServiceError as error:
            return _error_response(error)


@method_decorator(csrf_exempt, name="dispatch")
class L3SpiderMailTriggerView(APIView):
    """Airflow에서 due 메일 rule 처리를 호출하는 endpoint."""

    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs) -> JsonResponse:
        auth_response = ensure_airflow_token(request, require_bearer=True)
        if auth_response is not None:
            return auth_response

        payload, payload_error = parse_json_body_or_error_when_present(request)
        if payload_error is not None:
            return payload_error

        serializer = L3SpiderMailTriggerSerializer(data=payload or {})
        serializer.is_valid(raise_exception=True)
        try:
            result = services.trigger_due_mail_rules(
                limit=serializer.validated_data["limit"],
            )
        except services.L3SpiderServiceError as error:
            return JsonResponse({"error": str(error)}, status=error.status_code)
        return JsonResponse(result)


class L3SpiderFilterCandidatesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        serializer = L3SpiderFilterCandidatesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                services.get_filter_candidates(
                    serializer.validated_data,
                    user=request.user,
                )
            )
        except services.L3SpiderServiceError as error:
            return _error_response(error)


class L3SpiderTrendView(APIView):
    """날짜별·라인별 이상감지 건수 트렌드 조회 (GET)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        try:
            return Response(services.get_trend(user=request.user))
        except Exception as exc:
            return _error_response(exc)
