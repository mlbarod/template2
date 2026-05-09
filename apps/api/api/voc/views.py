# =============================================================================
# 모듈 설명: voc 게시판 CRUD APIView를 제공합니다.
# - 주요 클래스: VocPostsView, VocPostDetailView, VocReplyView
# - 불변 조건: 서비스 검증 결과와 기존 JSON 응답 형식을 유지합니다.
# =============================================================================

"""VOC(Q&A) 게시판 CRUD 뷰.

- GET    /api/v1/voc/posts                          : 게시글 목록 조회
- POST   /api/v1/voc/posts                          : 새 게시글 생성
- PATCH  /api/v1/voc/posts/<id>                     : 제목/내용/상태 수정
- DELETE /api/v1/voc/posts/<id>                     : 게시글 삭제(작성자+관리자)
- POST   /api/v1/voc/posts/<id>/replies             : 답변 추가
"""
from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)
from api.common.services import parse_json_body

from .selectors import (
    get_post_detail,
    get_post_list,
    get_status_counts,
)
from .serializers import serialize_post, serialize_reply
from .services import add_reply, can_manage_post, create_post, delete_post, update_post
from .services.posts import (
    VocInputError,
    build_create_post_data,
    build_reply_content,
    build_update_post_data,
    validate_status_filter,
)

logger = logging.getLogger(__name__)


def _json_error(message: str, *, status: int) -> JsonResponse:
    """기존 오류 응답 형식으로 JSON 오류를 반환합니다."""

    return JsonResponse({"error": message}, status=status)


def _parse_payload(request: HttpRequest) -> tuple[dict[str, Any] | None, JsonResponse | None]:
    """JSON 요청 바디를 파싱하고 오류 응답을 함께 반환합니다."""

    payload = parse_json_body(request)
    if payload is None:
        return None, _json_error("Invalid JSON body", status=400)
    return payload, None


def _validation_error_response(error: VocInputError) -> JsonResponse:
    """입력 검증 예외를 기존 400 응답으로 변환합니다."""

    return _json_error(str(error), status=400)


def _get_mutable_post_or_none(*, post_id: int) -> Any | None:
    """수정/삭제 대상 게시글을 조회하고 조회 예외는 기존처럼 없음으로 처리합니다."""

    try:
        return get_post_detail(post_id=post_id)
    except Exception:
        return None


def _post_list_response(posts: list[dict[str, Any]]) -> JsonResponse:
    """게시글 목록 응답 payload를 조립합니다."""

    return JsonResponse(
        {
            "results": posts,
            "total": len(posts),
            "statusCounts": get_status_counts(),
        }
    )


def _post_with_counts_response(post: Any, *, status: int = 200) -> JsonResponse:
    """게시글 단건과 statusCounts를 기존 형식으로 반환합니다."""

    return JsonResponse(
        {"post": serialize_post(post), "statusCounts": get_status_counts()},
        status=status,
    )


@method_decorator(csrf_exempt, name="dispatch")
class VocPostsView(APIView):
    """목록 조회 및 신규 작성."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """게시글 목록을 조회합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 게시글 목록 및 statusCounts

        부작용:
        - 없음(읽기 전용)

        오류:
        - 400: status 값이 유효하지 않을 때

        예시 요청:
        - 예시 요청: GET /api/v1/voc/posts
        - 예시 요청: GET /api/v1/voc/posts?status=접수

        snake/camel 호환:
        - status 키 동일
        """
        try:
            status_filter = validate_status_filter(status=request.GET.get("status"))
        except VocInputError as error:
            return _validation_error_response(error)

        queryset = get_post_list(status=status_filter)
        posts = [serialize_post(post) for post in queryset]
        return _post_list_response(posts)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """게시글을 생성합니다.

        입력:
        - 요청: Django HttpRequest(JSON 바디: title, content, status, app)
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 생성된 게시글 및 statusCounts

        부작용:
        - VocPost 레코드 생성
        - 활동 로그 기록(activity_logging)

        오류:
        - 401: 인증 필요
        - 400: JSON 파싱 실패/필수 필드 누락/상태 값 오류/제목·앱 길이 초과/앱 값 오류
        - 500: 생성 실패

        예시 요청:
        - 예시 요청: POST /api/v1/voc/posts
          예시 바디: {"title":"제목","content":"내용","status":"접수","app":"기타"}

        snake/camel 호환:
        - title/content/status/app 키 동일
        """
        if not request.user.is_authenticated:
            return _json_error("Authentication required", status=401)

        payload, error_response = _parse_payload(request)
        if error_response:
            return error_response
        try:
            post_data = build_create_post_data(payload=payload or {})
        except VocInputError as error:
            return _validation_error_response(error)

        try:
            post = create_post(author=request.user, **post_data)

            set_activity_summary(request, "Create VOC post")
            set_activity_new_state(request, serialize_post(post))
            merge_activity_metadata(request, resource="voc_post", entryId=post.pk)

            return _post_with_counts_response(post, status=201)
        except Exception:  # 방어적 로깅: pragma: no cover
            logger.exception("Failed to create VOC post")
            return _json_error("Failed to create post", status=500)


@method_decorator(csrf_exempt, name="dispatch")
class VocPostDetailView(APIView):
    """단일 게시글 수정/삭제."""

    def patch(self, request: HttpRequest, post_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """게시글을 수정합니다.

        입력:
        - 요청: Django HttpRequest(JSON 바디: title/content/status/app 선택)
        - post_id: 게시글 ID
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 수정된 게시글 및 statusCounts

        부작용:
        - VocPost 레코드 갱신
        - 활동 로그 기록(activity_logging)

        오류:
        - 401: 인증 필요
        - 400: JSON 파싱 실패/입력 오류/앱 값 오류/변경 없음
        - 403: 권한 없음
        - 404: 게시글 없음
        - 500: 수정 실패

        예시 요청:
        - 예시 요청: PATCH /api/v1/voc/posts/1
          예시 바디: {"title":"수정","status":"진행중","app":"기타"}

        snake/camel 호환:
        - title/content/status/app 키 동일
        """
        if not request.user.is_authenticated:
            return _json_error("Authentication required", status=401)

        payload, error_response = _parse_payload(request)
        if error_response:
            return error_response

        post = _get_mutable_post_or_none(post_id=post_id)
        if not post:
            return _json_error("Post not found", status=404)

        if not can_manage_post(user=request.user, post=post):
            return _json_error("Forbidden", status=403)
        try:
            updates = build_update_post_data(payload=payload or {})
        except VocInputError as error:
            return _validation_error_response(error)

        try:
            before = serialize_post(post)
            post = update_post(post=post, updates=updates)

            set_activity_summary(request, "Update VOC post")
            set_activity_previous_state(request, before)
            set_activity_new_state(request, serialize_post(post))
            merge_activity_metadata(request, resource="voc_post", entryId=post.pk)

            return _post_with_counts_response(post)
        except Exception:  # 방어적 로깅: pragma: no cover
            logger.exception("Failed to update VOC post")
            return _json_error("Failed to update post", status=500)

    def delete(self, request: HttpRequest, post_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """게시글을 삭제합니다.

        입력:
        - 요청: Django HttpRequest
        - post_id: 게시글 ID
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 삭제 성공 여부 및 statusCounts

        부작용:
        - VocPost 레코드 삭제
        - 활동 로그 기록(activity_logging)

        오류:
        - 401: 인증 필요
        - 403: 권한 없음
        - 404: 게시글 없음
        - 500: 삭제 실패

        예시 요청:
        - 예시 요청: DELETE /api/v1/voc/posts/1

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        if not request.user.is_authenticated:
            return _json_error("Authentication required", status=401)

        post = _get_mutable_post_or_none(post_id=post_id)
        if not post:
            return _json_error("Post not found", status=404)

        if not can_manage_post(user=request.user, post=post):
            return _json_error("Forbidden", status=403)

        try:
            before = serialize_post(post)
            delete_post(post=post)

            set_activity_summary(request, "Delete VOC post")
            set_activity_previous_state(request, before)
            merge_activity_metadata(request, resource="voc_post", entryId=post_id)

            return JsonResponse({"success": True, "statusCounts": get_status_counts()})
        except Exception:  # 방어적 로깅: pragma: no cover
            logger.exception("Failed to delete VOC post")
            return _json_error("Failed to delete post", status=500)


@method_decorator(csrf_exempt, name="dispatch")
class VocReplyView(APIView):
    """답변 추가."""

    def post(self, request: HttpRequest, post_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """게시글에 답변을 추가합니다.

        입력:
        - 요청: Django HttpRequest(JSON 바디: content)
        - post_id: 게시글 ID
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 생성된 답변 및 갱신된 게시글

        부작용:
        - VocReply 레코드 생성
        - 활동 로그 기록(activity_logging)

        오류:
        - 401: 인증 필요
        - 400: JSON 파싱 실패/내용 누락
        - 404: 게시글 없음
        - 500: 답변 추가 실패

        예시 요청:
        - 예시 요청: POST /api/v1/voc/posts/1/replies
          예시 바디: {"content":"답변 내용"}

        snake/camel 호환:
        - content 키 동일
        """
        if not request.user.is_authenticated:
            return _json_error("Authentication required", status=401)

        payload, error_response = _parse_payload(request)
        if error_response:
            return error_response

        try:
            content = build_reply_content(payload=payload or {})
        except VocInputError as error:
            return _validation_error_response(error)

        post = get_post_detail(post_id=post_id)
        if not post:
            return _json_error("Post not found", status=404)

        try:
            reply, refreshed_post = add_reply(post=post, author=request.user, content=content)

            set_activity_summary(request, "Add VOC reply")
            set_activity_new_state(request, serialize_reply(reply))
            merge_activity_metadata(request, resource="voc_reply", entryId=reply.pk, postId=post_id)

            return JsonResponse(
                {"reply": serialize_reply(reply), "post": serialize_post(refreshed_post)}, status=201
            )
        except Exception:  # 방어적 로깅: pragma: no cover
            logger.exception("Failed to add VOC reply")
            return _json_error("Failed to add reply", status=500)


__all__ = ["VocPostsView", "VocPostDetailView", "VocReplyView"]
