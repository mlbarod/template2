# =============================================================================
# 모듈 설명: AppStore 작성자/관리자 권한 helper를 제공합니다.
# - 주요 함수: can_manage_app, can_manage_comment
# - 불변 조건: staff/superuser 또는 작성자만 수정/삭제할 수 있습니다.
# =============================================================================
from __future__ import annotations

from typing import Any


def is_authenticated_user(user: Any) -> bool:
    """인증된 사용자 객체인지 확인합니다."""

    return bool(user and getattr(user, "is_authenticated", False))


def has_appstore_editor_permission(user: Any) -> bool:
    """AppStore 전체 편집 권한이 있는 관리자 계정인지 확인합니다."""

    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))


def is_app_owner(user: Any, app: Any) -> bool:
    """사용자가 앱 작성자인지 확인합니다."""

    user_id = getattr(user, "pk", None)
    return user_id is not None and getattr(app, "owner_id", None) == user_id


def is_comment_author(user: Any, comment: Any) -> bool:
    """사용자가 댓글 작성자인지 확인합니다."""

    user_id = getattr(user, "pk", None)
    return user_id is not None and getattr(comment, "user_id", None) == user_id


def can_manage_app(user: Any, app: Any) -> bool:
    """현재 사용자가 앱을 수정/삭제할 수 있는지 검사합니다."""

    if not is_authenticated_user(user):
        return False
    return has_appstore_editor_permission(user) or is_app_owner(user, app)


def can_manage_comment(user: Any, comment: Any) -> bool:
    """현재 사용자가 댓글을 수정/삭제할 수 있는지 검사합니다."""

    if not is_authenticated_user(user):
        return False
    return has_appstore_editor_permission(user) or is_comment_author(user, comment)


__all__ = [
    "can_manage_app",
    "can_manage_comment",
    "has_appstore_editor_permission",
    "is_app_owner",
    "is_authenticated_user",
    "is_comment_author",
]
