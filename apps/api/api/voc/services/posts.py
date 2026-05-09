# =============================================================================
# 모듈 설명: voc 게시글/답변 생성 및 수정 서비스를 제공합니다.
# - 주요 함수: create_post, update_post, delete_post, add_reply, can_manage_post
# - 불변 조건: 읽기 쿼리는 selectors를 통해 조회합니다.
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Tuple

from django.db import transaction

from ..models import VocPost, VocReply
from ..selectors import (
    get_default_post_status,
    get_post_detail,
    get_reply_by_id,
    get_valid_post_apps,
    get_valid_post_statuses,
    is_admin_user,
)

MAX_TITLE_LENGTH = VocPost._meta.get_field("title").max_length or 255
MAX_APP_LENGTH = VocPost._meta.get_field("app").max_length or 80


class VocInputError(ValueError):
    """VOC 입력 검증 실패 메시지를 담는 예외입니다."""


def validate_status_filter(*, status: str | None) -> str | None:
    """목록 조회 status 필터 값을 검증해 반환합니다."""

    if status and status not in get_valid_post_statuses():
        raise VocInputError("Invalid status value")
    return status or None


def _clean_required_text(*, payload: dict[str, Any], field: str, required_message: str) -> str:
    """필수 문자열 필드를 기존 규칙대로 정리하고 검증합니다."""

    value = str(payload.get(field) or "").strip()
    if not value:
        raise VocInputError(required_message)
    return value


def _validate_title(*, title: str) -> str:
    """게시글 제목 길이를 검증합니다."""

    if len(title) > MAX_TITLE_LENGTH:
        raise VocInputError("title is too long")
    return title


def _validate_content(*, content: str) -> str:
    """게시글 본문 존재 여부를 검증합니다."""

    if not content:
        raise VocInputError("content is required")
    return content


def _validate_status(*, status: Any) -> str:
    """게시글 상태 값을 검증합니다."""

    if status not in get_valid_post_statuses():
        raise VocInputError("Invalid status value")
    return status


def _validate_app(*, app: str) -> str:
    """앱 카테고리 값을 검증합니다."""

    if len(app) > MAX_APP_LENGTH:
        raise VocInputError("app is too long")
    if app not in get_valid_post_apps():
        raise VocInputError("Invalid app value")
    return app


def build_create_post_data(*, payload: dict[str, Any]) -> dict[str, Any]:
    """게시글 생성 입력을 검증하고 서비스 호출용 데이터로 변환합니다."""

    title = _validate_title(
        title=_clean_required_text(
            payload=payload,
            field="title",
            required_message="title is required",
        )
    )
    content = _validate_content(
        content=_clean_required_text(
            payload=payload,
            field="content",
            required_message="content is required",
        )
    )
    status = _validate_status(status=payload.get("status") or get_default_post_status())
    app = _validate_app(
        app=_clean_required_text(
            payload=payload,
            field="app",
            required_message="app is required",
        )
    )
    return {"title": title, "content": content, "status": status, "app": app}


def build_update_post_data(*, payload: dict[str, Any]) -> Dict[str, Any]:
    """게시글 수정 입력을 검증하고 변경 필드만 반환합니다."""

    updates: Dict[str, Any] = {}
    if "title" in payload:
        title = _clean_required_text(
            payload=payload,
            field="title",
            required_message="title is required",
        )
        updates["title"] = _validate_title(title=title)

    if "content" in payload:
        content = _clean_required_text(
            payload=payload,
            field="content",
            required_message="content is required",
        )
        updates["content"] = _validate_content(content=content)

    if "status" in payload:
        updates["status"] = _validate_status(status=payload.get("status"))

    if "app" in payload:
        app = _clean_required_text(
            payload=payload,
            field="app",
            required_message="app is required",
        )
        updates["app"] = _validate_app(app=app)

    if not updates:
        raise VocInputError("No changes provided")
    return updates


def build_reply_content(*, payload: dict[str, Any]) -> str:
    """답변 작성 입력에서 content를 검증해 반환합니다."""

    return _clean_required_text(
        payload=payload,
        field="content",
        required_message="content is required",
    )


def create_post(*, author: Any, title: str, content: str, status: str, app: str) -> VocPost:
    """VOC 게시글을 생성하고 관계(prefetch)까지 포함해 반환합니다.

    입력:
    - author: 작성자 사용자 객체
    - title: 게시글 제목
    - content: 게시글 내용
    - status: 게시글 상태
    - app: 앱 카테고리

    반환:
    - VocPost: 관계가 로딩된 게시글

    부작용:
    - VocPost 레코드 생성

    오류:
    - 없음
    """

    with transaction.atomic():
        post = VocPost.objects.create(
            title=title,
            content=content,
            status=status,
            app=app,
            author=author,
        )
    return get_post_detail(post_id=post.pk) or post


def update_post(*, post: VocPost, updates: Dict[str, Any]) -> VocPost:
    """VOC 게시글을 수정하고 관계(prefetch)까지 포함해 반환합니다.

    입력:
    - post: 대상 VocPost
    - updates: 업데이트 필드/값 맵(title/content/status/app)

    반환:
    - VocPost: 관계가 로딩된 게시글

    부작용:
    - VocPost 레코드 갱신

    오류:
    - 없음
    """

    with transaction.atomic():
        for field, value in updates.items():
            setattr(post, field, value)
        post.save(update_fields=list(updates.keys()) + ["updated_at"])
    return get_post_detail(post_id=post.pk) or post


def delete_post(*, post: VocPost) -> None:
    """VOC 게시글을 삭제합니다.

    입력:
    - post: 대상 VocPost

    반환:
    - 없음

    부작용:
    - VocPost 레코드 삭제

    오류:
    - 없음
    """

    with transaction.atomic():
        post.delete()


def add_reply(*, post: VocPost, author: Any, content: str) -> Tuple[VocReply, VocPost]:
    """게시글에 답변을 추가하고 (reply, refreshed_post)를 반환합니다.

    입력:
    - post: 대상 VocPost
    - author: 작성자 사용자 객체
    - content: 답변 내용

    반환:
    - Tuple[VocReply, VocPost]: (답변, 갱신된 게시글)

    부작용:
    - VocReply 레코드 생성

    오류:
    - 없음
    """

    with transaction.atomic():
        reply = VocReply.objects.create(post=post, author=author, content=content)
    loaded_reply = get_reply_by_id(reply_id=reply.pk) or reply
    refreshed_post = get_post_detail(post_id=post.pk) or post
    return loaded_reply, refreshed_post


def can_manage_post(*, user: Any, post: VocPost) -> bool:
    """게시글 수정/삭제 가능 여부(관리자 또는 작성자)를 판별합니다.

    입력:
    - user: 사용자 객체
    - post: 대상 VocPost

    반환:
    - bool: 수정/삭제 가능 여부

    부작용:
    - 없음

    오류:
    - 없음
    """

    return bool(
        is_admin_user(user=user) or (user and getattr(user, "pk", None) == post.author_id)
    )
