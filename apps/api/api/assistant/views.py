# =============================================================================
# 모듈: 어시스턴트 API 뷰
# 주요 엔드포인트: AssistantRagIndexListView.get, AssistantChatView.post
# 주요 가정: parse_json_body는 실패 시 None을 반환합니다.
# =============================================================================
"""어시스턴트 채팅/인덱스 조회 엔드포인트 모음입니다."""
from __future__ import annotations

import logging
from typing import Dict, List

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import extract_first_error_message, parse_json_body

from .serializers import AssistantChatRequestSerializer
from .services import (
    AssistantConfigError,
    AssistantRequestError,
    append_user_prompt,
    assistant_chat_service,
    build_rag_index_list_payload,
    conversation_memory,
    normalize_history,
    normalize_room_id,
    normalize_segments,
    normalize_sources,
    resolve_permission_groups,
    resolve_rag_index_names,
    validate_user_identity,
)

logger = logging.getLogger(__name__)


def _normalize_sources(raw_sources: object) -> List[Dict[str, str]]:
    """테스트에서 사용하는 normalize_sources 래퍼입니다.

    인자:
        raw_sources: 원본 출처 목록.

    반환:
        정규화된 출처 목록.

    부작용:
        없음. 순수 래퍼입니다.
    """

    return normalize_sources(raw_sources)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantRagIndexListView(APIView):
    """현재 사용자가 선택 가능한 RAG 인덱스/권한 그룹 정보를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """접근 가능한 RAG 인덱스/권한 그룹 정보를 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/assistant/rag-indexes

        반환:
            200: {
                예시 "ragIndexes": [...],
                예시 "defaultRagIndex": "...",
                예시 "emailRagIndex": "...",
                예시 "permissionGroups": [...],
                예시 "currentUserSdwtProd": "...",
                예시 "ragPublicGroup": "..."
            }

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            401: 비인증
            403: 권한 없음

        snake_case/camelCase 호환:
            입력 파라미터는 없으며, 응답 키는 camelCase로 반환합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 접근 가능한 인덱스/권한 그룹 조회
        # -----------------------------------------------------------------------------
        try:
            return JsonResponse(build_rag_index_list_payload(user=user))
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantChatView(APIView):
    """프론트엔드 어시스턴트 위젯에서 사용하는 채팅 엔드포인트."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """어시스턴트 채팅 요청을 처리하고 답변을 반환합니다.

        요청 예시:
            예시 요청: POST /api/v1/assistant/chat
            {
              예시 "prompt": "장비 점검 절차 알려줘",
              예시 "roomId": "room-1",
              예시 "permissionGroups": ["group-a"],
              예시 "ragIndexName": ["index-a"],
              예시 "history": [{"role": "user", "content": "이전 질문"}]
            }

        반환:
            200: {
              예시 "reply": "...",
              예시 "contexts": [...],
              예시 "sources": [...],
              예시 "segments": [...],
              예시 "meta": {"isDummy": false, "llmConfigured": true, "ragConfigured": true},
              예시 "echo": {"prompt": "...", "historyCount": 3, "username": "u", "roomId": "room-1"}
            }

        부작용:
            대화 이력이 캐시에 저장됩니다.

        오류:
            400: JSON/prompt/입력 형식 오류
            401: 비인증
            403: 권한 없음
            502: 업스트림 요청 실패 또는 응답 공백
            503: 어시스턴트 설정 누락

        snake_case/camelCase 호환:
            permissionGroups ↔ permission_groups, ragIndexName ↔ rag_index_name, roomId ↔ room_id를 모두 지원합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 요청 본문 파싱 및 기본 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = AssistantChatRequestSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        validated_payload = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 2) 인증 및 사용자 식별자 검증
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)

        try:
            user_key, user_header_id = validate_user_identity(request.user)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        # -----------------------------------------------------------------------------
        # 3) room_id/권한 그룹/인덱스 파싱
        # -----------------------------------------------------------------------------
        room_id = normalize_room_id(validated_payload.get("room_id"))
        prompt_clean = validated_payload["prompt"]
        try:
            permission_groups = resolve_permission_groups(validated_payload, request.user)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        try:
            rag_index_names = resolve_rag_index_names(validated_payload)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        # -----------------------------------------------------------------------------
        # 4) 히스토리 정규화 및 캐시 병합
        # -----------------------------------------------------------------------------
        incoming_history = normalize_history(
            validated_payload.get("history"),
            limit=conversation_memory.max_messages,
        )
        stored_history = conversation_memory.load(user_key, room_id)
        base_history = stored_history if stored_history else incoming_history

        history_with_prompt = append_user_prompt(
            base_history,
            prompt_clean,
            limit=conversation_memory.max_messages,
        )
        conversation_memory.save(user_key, room_id, history_with_prompt)

        # -----------------------------------------------------------------------------
        # 5) 어시스턴트 호출 및 응답 정규화
        # -----------------------------------------------------------------------------
        reply = ""
        contexts_used: List[str] = []
        sources_used: List[Dict[str, str]] = []
        segments_used: List[Dict[str, object]] = []
        is_dummy = False
        try:
            chat_result = assistant_chat_service.generate_reply(
                prompt_clean,
                user_header_id=user_header_id,
                rag_index_names=rag_index_names,
                permission_groups=permission_groups,
            )
            reply = chat_result.reply.strip() if isinstance(chat_result.reply, str) else ""
            contexts_used = chat_result.contexts
            sources_used = normalize_sources(getattr(chat_result, "sources", []))
            segments_used = normalize_segments(getattr(chat_result, "segments", []))
            is_dummy = getattr(chat_result, "is_dummy", False)
        except AssistantConfigError as exc:
            logger.error(
                "Assistant service configuration is missing required values.",
                extra={
                    "username": user_key,
                    "roomId": room_id,
                    "llmConfigured": bool(assistant_chat_service.config.llm_url),
                    "ragConfigured": bool(assistant_chat_service.config.rag_url),
                },
                exc_info=exc,
            )
            return JsonResponse(
                {"error": "어시스턴트 API 설정이 누락되었습니다. 관리자에게 문의해주세요."},
                status=503,
            )
        except AssistantRequestError as exc:
            logger.exception(
                "Assistant upstream request failed",
                extra={"username": user_key, "roomId": room_id},
            )
            return JsonResponse({"error": str(exc)}, status=502)

        # -----------------------------------------------------------------------------
        # 6) 응답 검증 및 히스토리 업데이트
        # -----------------------------------------------------------------------------
        if not reply:
            logger.error(
                "Assistant reply is empty despite successful upstream call.",
                extra={"username": user_key, "roomId": room_id, "contextCount": len(contexts_used)},
            )
            return JsonResponse({"error": "어시스턴트 응답이 비어 있습니다. 관리자에게 문의해주세요."}, status=502)

        assistant_history_payload = (
            [{"role": "assistant", "content": segment["reply"]} for segment in segments_used]
            if segments_used
            else [{"role": "assistant", "content": reply}]
        )
        updated_history = conversation_memory.append(user_key, room_id, assistant_history_payload)

        logger.debug(
            "Assistant chat request received",
            extra={
                "historyCount": len(updated_history),
                "username": user_key,
                "roomId": room_id,
                "llmConfigured": bool(assistant_chat_service.config.llm_url) or is_dummy,
                "ragConfigured": bool(assistant_chat_service.config.rag_url) or is_dummy or bool(contexts_used),
                "contextCount": len(contexts_used),
                "sourceCount": len(sources_used),
                "isDummy": is_dummy,
            },
        )

        return JsonResponse(
            {
                "reply": reply,
                "contexts": contexts_used,
                "sources": sources_used,
                "segments": segments_used,
                "meta": {
                    "isDummy": is_dummy,
                    "llmConfigured": bool(assistant_chat_service.config.llm_url) or is_dummy,
                    "ragConfigured": bool(assistant_chat_service.config.rag_url) or is_dummy or bool(contexts_used),
                },
                "echo": {
                    "prompt": prompt_clean,
                    "historyCount": len(updated_history),
                    "username": user_key,
                    "roomId": room_id,
                },
            }
        )
