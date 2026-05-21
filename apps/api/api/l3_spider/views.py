# =============================================================================
# 모듈: L3 Spider API 뷰
# 주요 엔드포인트: meta, summary, data
# 주요 가정: 로그인 사용자만 조회할 수 있습니다.
# =============================================================================
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import L3SpiderDataRequestSerializer


def _error_response(error: Exception) -> Response:
    """서비스 오류를 일관된 JSON 응답으로 변환합니다."""

    status_code = getattr(error, "status_code", 400)
    return Response({"error": str(error)}, status=status_code)


class L3SpiderMetaView(APIView):
    """L3 Spider 선택 메타데이터를 반환합니다."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        """사용 가능한 날짜/라인/프로세스/EDS step 목록을 반환합니다."""

        try:
            return Response(services.get_meta())
        except services.L3SpiderServiceError as error:
            return _error_response(error)


class L3SpiderSummaryView(APIView):
    """L3 Spider 요약 데이터를 반환합니다."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        """선택 조건 기준 통계와 이상 목록을 반환합니다."""

        serializer = L3SpiderDataRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(services.get_summary(serializer.validated_data))
        except services.L3SpiderServiceError as error:
            return _error_response(error)


class L3SpiderDataView(APIView):
    """L3 Spider 차트 행 데이터를 반환합니다."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        """선택 조건과 화면 필터 기준 차트 행을 반환합니다."""

        serializer = L3SpiderDataRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(services.get_data(serializer.validated_data))
        except services.L3SpiderServiceError as error:
            return _error_response(error)
