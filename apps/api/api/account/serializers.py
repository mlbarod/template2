# =============================================================================
# 모듈 설명: account 도메인 요청/응답 스키마를 정의합니다.
# - 주요 대상: 외부 소속 동기화, 소속 재확인/승인 입력 스키마
# - 불변 조건: 필드명은 클라이언트 계약과 호환되어야 합니다.
# =============================================================================

"""계정 도메인 요청/응답 스키마 정의 모음.

- 주요 대상: 외부 소속 동기화, 소속 재확인/승인 입력 스키마
- 주요 엔드포인트/클래스: ExternalAffiliationSyncSerializer 등
- 가정/불변 조건: 필드명은 클라이언트 계약에 맞춰 유지됨
"""
from __future__ import annotations

from rest_framework import serializers


class ExternalAffiliationRecordSerializer(serializers.Serializer):
    """외부 DB에서 전달되는 사용자 예측 소속 레코드 입력 스키마."""

    knox_id = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    department = serializers.CharField(max_length=128)
    user_sdwt_prod = serializers.CharField(max_length=64)
    source_updated_at = serializers.DateTimeField(required=False, allow_null=True)


class ExternalAffiliationSyncSerializer(serializers.Serializer):
    """외부 예측 소속 동기화 요청 스키마."""

    records = ExternalAffiliationRecordSerializer(many=True)


class AffiliationReconfirmResponseSerializer(serializers.Serializer):
    """소속 재확인 응답 입력 스키마."""

    accepted = serializers.BooleanField()
    department = serializers.CharField(max_length=128, required=False, allow_blank=True)
    line = serializers.CharField(max_length=64, required=False, allow_blank=True)
    user_sdwt_prod = serializers.CharField(max_length=64, required=False, allow_blank=True)


class AffiliationApprovalSerializer(serializers.Serializer):
    """소속 변경 승인/거절 입력 스키마."""

    changeId = serializers.IntegerField()
    decision = serializers.ChoiceField(choices=["approve", "reject"], required=False)
    rejectionReason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
