from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import HardSpecMetaQuerySerializer, HardSpecQuerySerializer


def _error_response(error: Exception) -> Response:
    """서비스 오류를 일관된 JSON 응답으로 변환합니다."""

    status_code = getattr(error, "status_code", 400)
    return Response({"error": str(error)}, status=status_code)


class HardSpecMetaView(APIView):
    """FDC Hard Limit 추천 선택 옵션을 반환합니다."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        """예시: GET /api/v1/l0_spider/hard-spec/meta?lineId=PFBP"""

        serializer = HardSpecMetaQuerySerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(services.get_hard_spec_meta(serializer.validated_data))
        except services.L0SpiderServiceError as error:
            return _error_response(error)


class HardSpecRecommendationsView(APIView):
    """FDC Hard Limit 추천 결과를 반환합니다."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        """예시: GET /api/v1/l0_spider/hard-spec/recommendations?lineId=PFBP&stepSeq=C%25123&recipeId=RCP&fdcModel=MODEL"""

        serializer = HardSpecQuerySerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(services.get_hard_spec_recommendations(serializer.validated_data))
        except services.L0SpiderServiceError as error:
            return _error_response(error)
