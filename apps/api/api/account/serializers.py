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

from .models import AccessPolicyRule, AccessRole


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


class AccessDecisionSerializer(serializers.Serializer):
    """사용자 접근 상태 결정 입력 스키마."""

    requestId = serializers.IntegerField()
    decision = serializers.ChoiceField(choices=["approve", "reject", "allow", "deny"])
    role = serializers.ChoiceField(choices=AccessRole.values, required=False, allow_blank=True, allow_null=True)
    rejectionReason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class AccessUserDecisionSerializer(serializers.Serializer):
    """관리자 사용자별 접근 상태 변경 입력 스키마."""

    userId = serializers.IntegerField()
    scope = serializers.CharField(max_length=64, required=False, allow_blank=True)
    action = serializers.ChoiceField(
        choices=["approve", "reject", "grant", "revoke", "reset_to_policy", "change_role", "allow", "deny"]
    )
    role = serializers.ChoiceField(choices=AccessRole.values, required=False, allow_blank=True, allow_null=True)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    rejectionReason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate(self, attrs):
        """권한 변경 action별 필수 입력을 검증합니다."""

        if attrs.get("action") == "change_role" and not attrs.get("role"):
            raise serializers.ValidationError({"role": "change_role에는 role이 필요합니다."})
        return attrs


class AccessPolicyRuleMutationSerializer(serializers.Serializer):
    """관리자 접근 정책 규칙 변경 입력 스키마."""

    scope = serializers.CharField(max_length=64, required=False, allow_blank=True)
    ruleType = serializers.ChoiceField(choices=AccessPolicyRule.RuleTypes.values, required=False)
    value = serializers.CharField(max_length=150, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=AccessRole.values, required=False, allow_blank=True, allow_null=True)
    isActive = serializers.BooleanField(required=False)
