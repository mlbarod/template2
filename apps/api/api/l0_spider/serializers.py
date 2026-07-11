from __future__ import annotations

from rest_framework import serializers


class HardSpecMetaQuerySerializer(serializers.Serializer):
    """Hard Limit 추천 선택 옵션 요청을 검증합니다."""

    lineId = serializers.CharField(required=False, allow_blank=True)
    stepSeq = serializers.CharField(required=False, allow_blank=True)
    recipeId = serializers.CharField(required=False, allow_blank=True)


class HardSpecQuerySerializer(serializers.Serializer):
    """Hard Limit 추천 결과 요청을 검증합니다."""

    lineId = serializers.CharField(required=True, allow_blank=False)
    stepSeq = serializers.CharField(required=True, allow_blank=False)
    recipeId = serializers.CharField(required=True, allow_blank=False)
    fdcModel = serializers.CharField(required=True, allow_blank=False)
