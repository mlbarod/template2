# =============================================================================
# 모듈: L3 Spider 요청 직렬화
# 주요 클래스: L3SpiderDataRequestSerializer
# 주요 가정: 외부 API 계약은 camelCase를 사용합니다.
# =============================================================================
from __future__ import annotations

import re
from typing import Any

from rest_framework import serializers

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


def _is_safe_segment(value: str) -> bool:
    """경로 구성 요소로 사용할 수 있는 안전한 문자열인지 확인합니다."""

    return bool(_SAFE_SEGMENT.match(value)) and ".." not in value


class L3SpiderDataRequestSerializer(serializers.Serializer):
    """L3 Spider 데이터 조회 요청을 검증합니다."""

    dates = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    lineIds = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    processIds = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    edsSteps = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    selectedEqcs = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    selectedStepBins = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    selectedPpidBins = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    selectedSteps = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    checkedPpids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    checkedBins = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """파일 경로에 직접 반영되는 선택값을 검증합니다."""

        path_values = [
            *attrs.get("dates", []),
            *attrs.get("lineIds", []),
            *attrs.get("processIds", []),
            *attrs.get("edsSteps", []),
        ]
        for value in path_values:
            if not _is_safe_segment(value):
                raise serializers.ValidationError(
                    {"detail": f"유효하지 않은 선택값입니다: {value!r}"}
                )
        return attrs
