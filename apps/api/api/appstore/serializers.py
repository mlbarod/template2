# =============================================================================
# 모듈 설명: AppStore 직렬화/정규화 유틸을 제공합니다.
# - 주요 함수: serialize_app, serialize_comment
# - 불변 조건: 요청/응답은 카멜 케이스 키를 기본으로 합니다.
# =============================================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple


def _user_display_name(user) -> str:
    """사용자 표시 이름(username/이름/email)을 계산합니다.

    인자:
        user: Django 사용자 객체(또는 None).

    반환:
        표시용 사용자 이름 문자열.

    부작용:
        없음. 읽기 전용 계산입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 존재 여부 확인
    # -----------------------------------------------------------------------------
    if not user:
        return ""

    # -----------------------------------------------------------------------------
    # 2) username
    # -----------------------------------------------------------------------------
    username = getattr(user, "username", "") or ""
    if username:
        return username

    # -----------------------------------------------------------------------------
    # 3) 이름(first_name/last_name)
    # -----------------------------------------------------------------------------
    first_name = getattr(user, "first_name", "") or ""
    last_name = getattr(user, "last_name", "") or ""
    full_name = " ".join([part for part in [first_name, last_name] if part]).strip()
    if full_name:
        return full_name

    # -----------------------------------------------------------------------------
    # 4) email
    # -----------------------------------------------------------------------------
    email = getattr(user, "email", "") or ""
    if email:
        return email

    # -----------------------------------------------------------------------------
    # 5) 기본값
    # -----------------------------------------------------------------------------
    return ""


def _user_knoxid(user) -> str:
    """사용자의 knox_id 값을 그대로 반환합니다.

    인자:
        user: Django 사용자 객체(또는 None).

    반환:
        knox id 문자열(없으면 빈 문자열).

    부작용:
        없음. 읽기 전용 계산입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 존재 여부 확인
    # -----------------------------------------------------------------------------
    if not user:
        return ""
    return getattr(user, "knox_id", "") or ""


def serialize_user(user) -> Optional[Dict[str, Any]]:
    """사용자 정보를 API 응답 형태로 직렬화합니다.

    인자:
        user: Django 사용자 객체(또는 None).

    반환:
        사용자 정보 dict 또는 None.

    부작용:
        없음. 읽기 전용 변환입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 유효성 확인
    # -----------------------------------------------------------------------------
    if not user:
        return None
    # -----------------------------------------------------------------------------
    # 2) 응답 payload 구성
    # -----------------------------------------------------------------------------
    return {
        "id": user.pk,
        "name": _user_display_name(user) or "사용자",
        "knoxid": _user_knoxid(user),
    }


def default_contact(user) -> Tuple[str, str]:
    """연락처 기본값(contact_name, contact_knoxid)을 계산합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        (contact_name, contact_knoxid) 튜플.

    부작용:
        없음. 읽기 전용 계산입니다.

    오류:
        없음.
    """

    return (_user_display_name(user) or "사용자").strip(), _user_knoxid(user)


def sanitize_screenshot_urls(value: Any) -> List[str]:
    """스크린샷 URL 목록을 정규화합니다.

    인자:
        value: 원본 스크린샷 URL 입력.

    반환:
        공백 제거가 적용된 URL 목록.

    부작용:
        없음. 읽기 전용 정규화입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 타입 검증
    # -----------------------------------------------------------------------------
    if not isinstance(value, list):
        return []

    # -----------------------------------------------------------------------------
    # 2) 문자열 URL만 추출
    # -----------------------------------------------------------------------------
    cleaned: List[str] = []
    for raw in value:
        if not isinstance(raw, str):
            continue
        url = raw.strip()
        if not url:
            continue
        cleaned.append(url)
    return cleaned


def apply_cover_index(screenshot_urls: List[str], cover_index: Any) -> List[str]:
    """cover_index를 반영해 대표 이미지를 0번으로 이동합니다.

    인자:
        screenshot_urls: 스크린샷 URL 목록(대표 포함).
        cover_index: 대표 이미지 인덱스 입력값.

    반환:
        대표 이미지가 0번에 위치하도록 정렬된 목록.

    부작용:
        없음. 읽기 전용 정렬입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 유효성 확인
    # -----------------------------------------------------------------------------
    if not screenshot_urls:
        return []

    # -----------------------------------------------------------------------------
    # 2) 대표 인덱스 파싱
    # -----------------------------------------------------------------------------
    try:
        index = int(cover_index)
    except (TypeError, ValueError):
        return screenshot_urls

    # -----------------------------------------------------------------------------
    # 3) 범위/무변경 조건 처리
    # -----------------------------------------------------------------------------
    if index < 0 or index >= len(screenshot_urls):
        return screenshot_urls

    if index == 0:
        return screenshot_urls

    # -----------------------------------------------------------------------------
    # 4) 대표 이미지 이동
    # -----------------------------------------------------------------------------
    cover = screenshot_urls[index]
    remaining = [item for i, item in enumerate(screenshot_urls) if i != index]
    return [cover, *remaining]


def can_manage_app(user, app: Any) -> bool:
    """현재 사용자가 앱을 수정/삭제할 수 있는지 검사합니다.

    인자:
        user: 현재 사용자 객체(또는 None).
        app: 대상 AppStoreApp.

    반환:
        수정/삭제 가능 여부.

    부작용:
        없음. 읽기 전용 검사입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 인증/권한 기본 확인
    # -----------------------------------------------------------------------------
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    # -----------------------------------------------------------------------------
    # 2) 소유자 여부 확인
    # -----------------------------------------------------------------------------
    return getattr(user, "pk", None) is not None and app.owner_id == user.pk


def can_manage_comment(user, comment: Any) -> bool:
    """현재 사용자가 댓글을 수정/삭제할 수 있는지 검사합니다.

    인자:
        user: 현재 사용자 객체(또는 None).
        comment: 대상 AppStoreComment.

    반환:
        수정/삭제 가능 여부.

    부작용:
        없음. 읽기 전용 검사입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 인증/권한 기본 확인
    # -----------------------------------------------------------------------------
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    # -----------------------------------------------------------------------------
    # 2) 작성자 여부 확인
    # -----------------------------------------------------------------------------
    return getattr(user, "pk", None) is not None and comment.user_id == user.pk


def serialize_comment(comment: Any, current_user, liked_comment_ids: set[int]) -> Dict[str, Any]:
    """댓글을 API 응답 형태로 직렬화합니다.

    인자:
        comment: AppStoreComment 인스턴스.
        current_user: 현재 사용자 객체(또는 None).
        liked_comment_ids: 현재 사용자가 좋아요한 댓글 id 집합.

    반환:
        댓글 API 응답 dict.

    부작용:
        없음. 읽기 전용 변환입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 좋아요 여부 계산
    # -----------------------------------------------------------------------------
    author = getattr(comment, "user", None)
    liked = False
    if current_user and getattr(current_user, "is_authenticated", False):
        liked = comment.pk in liked_comment_ids
    # -----------------------------------------------------------------------------
    # 2) 응답 payload 구성
    # -----------------------------------------------------------------------------
    return {
        "id": comment.pk,
        "appId": comment.app_id,
        "parentCommentId": getattr(comment, "parent_id", None),
        "content": comment.content,
        "createdAt": comment.created_at.isoformat(),
        "updatedAt": comment.updated_at.isoformat(),
        "author": serialize_user(author),
        "likeCount": int(getattr(comment, "like_count", 0) or 0),
        "liked": liked,
        "canEdit": can_manage_comment(current_user, comment),
        "canDelete": can_manage_comment(current_user, comment),
    }


def serialize_app(
    app: Any,
    current_user,
    liked_app_ids: Sequence[int],
    *,
    include_comments: bool = False,
    include_screenshots: bool = False,
    cover_src: str | None = None,
    liked_comment_ids: set[int] | None = None,
) -> Dict[str, Any]:
    """앱을 API 응답 형태로 직렬화합니다(선호 시 댓글 포함).

    인자:
        app: AppStoreApp 인스턴스.
        current_user: 현재 사용자 객체(또는 None).
        liked_app_ids: 현재 사용자가 좋아요한 앱 id 목록.
        include_comments: 댓글 포함 여부.
        include_screenshots: 스크린샷 목록 포함 여부.
        cover_src: 대표 스크린샷 URL/소스(없으면 앱 기본값 사용).
        liked_comment_ids: 현재 사용자가 좋아요한 댓글 id 집합.

    반환:
        앱 상세/목록 API 응답 dict.

    부작용:
        없음. 읽기 전용 변환입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 좋아요 여부/기본 값 계산
    # -----------------------------------------------------------------------------
    liked = False
    if current_user and getattr(current_user, "is_authenticated", False):
        liked = app.id in liked_app_ids

    liked_comment_ids = liked_comment_ids or set()

    # -----------------------------------------------------------------------------
    # 2) 댓글 포함 처리
    # -----------------------------------------------------------------------------
    comments: Optional[List[Dict[str, Any]]] = None
    if include_comments:
        related = getattr(app, "comments", None)
        if related is not None:
            comments = [serialize_comment(comment, current_user, liked_comment_ids) for comment in related.all()]
        else:
            comments = []

    # -----------------------------------------------------------------------------
    # 3) 기본 payload 구성
    # -----------------------------------------------------------------------------
    owner_payload = serialize_user(getattr(app, "owner", None))
    comment_count = getattr(app, "comment_count", 0) or 0

    cover_value = cover_src if cover_src is not None else getattr(app, "screenshot_src", "")
    payload: Dict[str, Any] = {
        "id": app.pk,
        "name": app.name,
        "category": app.category,
        "description": app.description,
        "url": app.url,
        "manualUrl": getattr(app, "manual_url", "") or "",
        "screenshotUrl": cover_value,
        "contactName": app.contact_name,
        "contactKnoxid": app.contact_knoxid,
        "viewCount": app.view_count,
        "likeCount": app.like_count,
        "commentCount": int(comment_count),
        "createdAt": app.created_at.isoformat(),
        "updatedAt": app.updated_at.isoformat(),
        "owner": owner_payload,
        "liked": liked,
        "canEdit": can_manage_app(current_user, app),
        "canDelete": can_manage_app(current_user, app),
        **({"comments": comments} if comments is not None else {}),
    }

    # -----------------------------------------------------------------------------
    # 4) 스크린샷 목록 포함 처리
    # -----------------------------------------------------------------------------
    if include_screenshots:
        screenshot_srcs = []
        screenshot_srcs_raw = getattr(app, "screenshot_srcs", None)
        if callable(screenshot_srcs_raw):
            screenshot_srcs = screenshot_srcs_raw()
        if not isinstance(screenshot_srcs, list):
            screenshot_srcs = []
        payload["screenshotUrls"] = screenshot_srcs
        payload["coverScreenshotIndex"] = 0

    # -----------------------------------------------------------------------------
    # 5) 결과 반환
    # -----------------------------------------------------------------------------
    return payload


__all__ = [
    "apply_cover_index",
    "can_manage_app",
    "can_manage_comment",
    "default_contact",
    "sanitize_screenshot_urls",
    "serialize_app",
    "serialize_comment",
    "serialize_user",
]
