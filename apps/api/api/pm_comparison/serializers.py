# =============================================================================
# 모듈: PM SPIDER 요청 직렬화
# 주요 클래스: PmComparisonRequestSerializer
# 주요 가정: 외부 API 계약은 camelCase를 사용합니다.
# =============================================================================
from __future__ import annotations

import re
from typing import Any

from rest_framework import serializers

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")
_SAFE_DATETIME_SEGMENT = re.compile(r"^[A-Za-z0-9_.: -]+$")


def _is_safe_segment(value: str) -> bool:
    """파일 경로 partition 값으로 사용할 수 있는 문자열인지 확인합니다."""

    return bool(_SAFE_SEGMENT.match(value)) and ".." not in value


def _is_safe_datetime_segment(value: str) -> bool:
    """공백/콜론을 포함한 날짜 partition 값이 안전한지 확인합니다."""

    return bool(_SAFE_DATETIME_SEGMENT.match(value)) and ".." not in value and "/" not in value and "\\" not in value


class PmComparisonRequestSerializer(serializers.Serializer):
    """PM SPIDER 조회 요청을 검증합니다."""

    lineId = serializers.CharField()
    eqpId = serializers.CharField()
    pmTimestamp = serializers.CharField()
    beforeHours = serializers.FloatField(min_value=0.1, max_value=720, default=24)
    afterHours = serializers.FloatField(min_value=0.1, max_value=720, default=24)
    chamberId = serializers.CharField(required=False, allow_blank=True, default="")
    fdcBin = serializers.CharField(required=False, allow_blank=True, default="")
    type = serializers.CharField(required=False, allow_blank=True, default="")
    ppid = serializers.CharField(required=False, allow_blank=True, default="")
    recipeId = serializers.CharField(required=False, allow_blank=True, default="")
    traceParamNames = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    dtValues = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    traceDataSource = serializers.CharField(required=False, allow_blank=True, default="trace")
    oesDataSource = serializers.CharField(required=False, allow_blank=True, default="oes")
    selectedStep = serializers.CharField(required=False, allow_blank=True, default="")
    selectedWavelength = serializers.CharField(required=False, allow_blank=True, default="")
    includeDetails = serializers.BooleanField(required=False, default=True)
    includeTraceDetails = serializers.BooleanField(required=False, default=True)
    includeOesDetails = serializers.BooleanField(required=False, default=True)
    includeOesHeatmap = serializers.BooleanField(required=False, default=True)
    includeOesSpectrum = serializers.BooleanField(required=False, default=True)
    refPmDates = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
    )
    limit = serializers.IntegerField(min_value=50, max_value=5000, default=1200)
    maxPoints = serializers.IntegerField(min_value=100, max_value=20000, default=2400)
    xStart = serializers.FloatField(required=False)
    xEnd = serializers.FloatField(required=False)
    heatmapXBins = serializers.IntegerField(min_value=20, max_value=1600, default=1200)
    heatmapYBins = serializers.IntegerField(min_value=10, max_value=240, default=100)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """파일 경로에 반영되는 값을 traversal 없이 안전하게 제한합니다."""

        path_values = [
            attrs.get("lineId"),
            attrs.get("eqpId"),
            attrs.get("chamberId"),
            attrs.get("type"),
            attrs.get("fdcBin"),
            attrs.get("ppid"),
            attrs.get("recipeId"),
            attrs.get("traceDataSource"),
            attrs.get("oesDataSource"),
            attrs.get("selectedStep"),
            attrs.get("selectedWavelength"),
            *attrs.get("traceParamNames", []),
        ]
        for value in path_values:
            if value and not _is_safe_segment(str(value)):
                raise serializers.ValidationError(
                    {"detail": f"유효하지 않은 선택값입니다: {value!r}"}
                )
        for value in [*attrs.get("dtValues", []), *attrs.get("refPmDates", [])]:
            if value and not _is_safe_datetime_segment(str(value)):
                raise serializers.ValidationError(
                    {"detail": f"유효하지 않은 선택값입니다: {value!r}"}
                )
        return attrs
