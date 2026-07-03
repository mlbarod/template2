# =============================================================================
# 모듈: L3 Spider 요청 직렬화
# 주요 클래스: L3SpiderDataRequestSerializer
# 주요 가정: 외부 API 계약은 camelCase를 사용합니다.
# =============================================================================
from __future__ import annotations

from datetime import time as datetime_time
import re
from typing import Any

from rest_framework import serializers

from .models import L3SpiderMailRule, L3SpiderMailRulePermission

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")
_MAX_MAIL_RECEIVERS = 20
_MAX_MAIL_RULE_PERMISSIONS = 30


def _is_safe_segment(value: str) -> bool:
    """경로 구성 요소로 사용할 수 있는 안전한 문자열인지 확인합니다."""

    return bool(_SAFE_SEGMENT.match(value)) and ".." not in value


class L3SpiderDataRequestSerializer(serializers.Serializer):
    """L3 Spider 데이터 조회 요청을 검증합니다."""

    dates = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    lineIds = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    processIds = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    edsSteps = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    # line_name(조직 라벨 또는 미분류 폴백 line_id). 경로가 아니라 행 필터용이므로 path 검증 제외.
    lineNames = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )
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


class L3SpiderExclusionFilterSerializer(serializers.Serializer):
    """제외 필터 생성/수정 요청을 검증합니다."""

    line_id = serializers.CharField(max_length=200, default="*")
    process_id = serializers.CharField(max_length=200, default="*")
    eds_step = serializers.CharField(max_length=200, default="*")
    step_seq = serializers.CharField(max_length=200, default="*")
    ppid = serializers.CharField(max_length=200, default="*")
    eqpch = serializers.CharField(max_length=200, default="*")
    bin_name = serializers.CharField(max_length=200, default="*")
    date_from = serializers.DateField(required=False, allow_null=True, default=None)
    date_to = serializers.DateField(required=False, allow_null=True, default=None)
    is_active = serializers.BooleanField(default=True)
    memo = serializers.CharField(allow_blank=True, default="", max_length=2000)


class L3SpiderMailRuleSerializer(serializers.Serializer):
    """메일 알림 규칙 생성/수정 요청을 검증합니다."""

    name = serializers.CharField(max_length=100, default="L3 Spider 알림")
    line_id = serializers.CharField(max_length=200, default="*")
    process_id = serializers.CharField(max_length=200, default="*")
    eds_step = serializers.CharField(max_length=200, default="*")
    step_seq = serializers.CharField(max_length=200, default="*")
    ppid = serializers.CharField(max_length=200, default="*")
    eqpch = serializers.CharField(max_length=200, default="*")
    bin_name = serializers.CharField(max_length=200, default="*")
    date_to = serializers.DateField(required=False, allow_null=True, default=None)
    severity_mode = serializers.ChoiceField(
        choices=L3SpiderMailRule.SeverityModes.choices,
        default=L3SpiderMailRule.SeverityModes.HIGH_RISK,
    )
    receiver_emails = serializers.ListField(
        child=serializers.EmailField(max_length=254),
        allow_empty=True,
        required=False,
        default=list,
    )
    schedule_type = serializers.ChoiceField(
        choices=L3SpiderMailRule.ScheduleTypes.choices,
        default=L3SpiderMailRule.ScheduleTypes.DAILY,
    )
    send_time = serializers.TimeField(
        input_formats=["%H:%M", "%H:%M:%S"],
        format="%H:%M",
        default=datetime_time(9, 0),
    )
    timezone = serializers.CharField(max_length=64, default="Asia/Seoul")
    is_active = serializers.BooleanField(default=True)
    memo = serializers.CharField(allow_blank=True, default="", max_length=2000)

    def validate_receiver_emails(self, value: list[str]) -> list[str]:
        """수신자 목록을 정규화하고 중복과 최대 개수를 검증합니다."""

        normalized: list[str] = []
        seen: set[str] = set()
        for email in value:
            cleaned = str(email).strip().lower()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            normalized.append(cleaned)

        if len(normalized) > _MAX_MAIL_RECEIVERS:
            raise serializers.ValidationError(
                f"수신자는 최대 {_MAX_MAIL_RECEIVERS}명까지 설정할 수 있습니다."
            )
        return normalized

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """메일 알림 규칙의 필수 조합과 날짜 범위를 검증합니다."""

        receiver_emails = attrs.get("receiver_emails")
        if not self.partial and not receiver_emails:
            raise serializers.ValidationError({"receiver_emails": "수신자가 필요합니다."})
        if "receiver_emails" in attrs and not receiver_emails:
            raise serializers.ValidationError({"receiver_emails": "수신자가 필요합니다."})

        timezone_value = str(attrs.get("timezone") or "").strip()
        if timezone_value and timezone_value != "Asia/Seoul":
            raise serializers.ValidationError({"timezone": "현재는 Asia/Seoul만 지원합니다."})
        if "timezone" in attrs:
            attrs["timezone"] = timezone_value or "Asia/Seoul"
        return attrs


class L3SpiderMailTriggerSerializer(serializers.Serializer):
    """메일 알림 trigger 요청을 검증합니다."""

    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)


class L3SpiderMailRulePermissionEntrySerializer(serializers.Serializer):
    """메일 rule 공유 권한 단일 항목을 검증합니다."""

    user = serializers.CharField(max_length=254)
    access_level = serializers.ChoiceField(
        choices=L3SpiderMailRulePermission.AccessLevels.choices,
        default=L3SpiderMailRulePermission.AccessLevels.READ,
    )


class L3SpiderMailRulePermissionUpdateSerializer(serializers.Serializer):
    """메일 rule 공유 권한 전체 교체 요청을 검증합니다."""

    permissions = serializers.ListField(
        child=L3SpiderMailRulePermissionEntrySerializer(),
        allow_empty=True,
        max_length=_MAX_MAIL_RULE_PERMISSIONS,
    )

    def validate_permissions(self, value: list[dict[str, str]]) -> list[dict[str, str]]:
        """권한 대상 식별자의 빈 값과 중복을 검증합니다."""

        seen: set[str] = set()
        normalized: list[dict[str, str]] = []
        for item in value:
            identifier = str(item.get("user") or "").strip()
            if not identifier:
                raise serializers.ValidationError("사용자 식별자가 필요합니다.")
            lookup_key = identifier.casefold()
            if lookup_key in seen:
                raise serializers.ValidationError("같은 사용자를 중복 입력할 수 없습니다.")
            seen.add(lookup_key)
            normalized.append({
                "user": identifier,
                "access_level": item.get("access_level") or L3SpiderMailRulePermission.AccessLevels.READ,
            })
        return normalized


class L3SpiderFilterCandidatesSerializer(serializers.Serializer):
    """PPID 선택 기준 EQPCH/Bin 후보 조회 요청을 검증합니다."""

    dates = serializers.ListField(child=serializers.CharField(), min_length=1)
    lineIds = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    processIds = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    edsStep = serializers.CharField()
    stepSeq = serializers.CharField()
    ppid = serializers.CharField()
    lineNames = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        default=list,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """파일 경로에 직접 반영되는 값을 검증합니다."""

        path_values = [
            *attrs.get("dates", []),
            *attrs.get("lineIds", []),
            *attrs.get("processIds", []),
            attrs.get("edsStep", ""),
            attrs.get("stepSeq", ""),
            attrs.get("ppid", ""),
        ]
        for value in path_values:
            if not _is_safe_segment(value):
                raise serializers.ValidationError(
                    {"detail": f"유효하지 않은 선택값입니다: {value!r}"}
                )
        return attrs
