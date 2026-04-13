# =============================================================================
# 모듈: 어시스턴트 요청 직렬화/검증
# 주요 클래스: AssistantChatRequestSerializer
# =============================================================================
"""어시스턴트 요청 입력 검증을 담당합니다."""
from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers


class AssistantChatRequestSerializer(serializers.Serializer):
    """어시스턴트 채팅 요청을 검증합니다."""

    prompt = serializers.CharField(
        allow_blank=True,
        trim_whitespace=True,
        error_messages={"required": "prompt is required"},
    )
    room_id = serializers.JSONField(required=False)
    permission_groups = serializers.JSONField(required=False)
    rag_index_name = serializers.JSONField(required=False)
    history = serializers.JSONField(required=False)

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        """카멜/스네이크 케이스 입력을 내부 필드로 정규화합니다."""

        if not isinstance(data, dict):
            raise serializers.ValidationError("Invalid JSON body")

        normalized: Dict[str, Any] = {}

        if "prompt" in data:
            prompt_value = data.get("prompt")
            if prompt_value is None or not isinstance(prompt_value, str):
                raise serializers.ValidationError({"prompt": ["prompt is required"]})
            normalized["prompt"] = prompt_value

        if "roomId" in data:
            room_id_value = data.get("roomId")
            if room_id_value is not None:
                normalized["room_id"] = room_id_value
        elif "room_id" in data:
            room_id_value = data.get("room_id")
            if room_id_value is not None:
                normalized["room_id"] = room_id_value

        if "permissionGroups" in data:
            permission_groups_value = data.get("permissionGroups")
            if permission_groups_value is not None:
                normalized["permission_groups"] = permission_groups_value
        elif "permission_groups" in data:
            permission_groups_value = data.get("permission_groups")
            if permission_groups_value is not None:
                normalized["permission_groups"] = permission_groups_value

        if "ragIndexName" in data:
            rag_index_value = data.get("ragIndexName")
            if rag_index_value is not None:
                normalized["rag_index_name"] = rag_index_value
        elif "rag_index_name" in data:
            rag_index_value = data.get("rag_index_name")
            if rag_index_value is not None:
                normalized["rag_index_name"] = rag_index_value

        if "history" in data:
            history_value = data.get("history")
            if history_value is not None:
                normalized["history"] = history_value

        return super().to_internal_value(normalized)

    def validate_prompt(self, value: object) -> str:
        """prompt가 공백/빈 문자열이 아닌지 확인합니다."""

        if not isinstance(value, str):
            raise serializers.ValidationError("prompt is required")
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("prompt is required")
        return cleaned


__all__ = ["AssistantChatRequestSerializer"]
