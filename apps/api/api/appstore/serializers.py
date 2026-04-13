# =============================================================================
# 모듈 설명: AppStore 직렬화/정규화 유틸을 제공합니다.
# - 주요 함수: serialize_app, serialize_comment
# - 불변 조건: 요청/응답은 카멜 케이스 키를 기본으로 합니다.
# =============================================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from rest_framework import serializers


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


class AppStoreAppCreateSerializer(serializers.Serializer):
    """AppStore 앱 생성 요청을 검증합니다."""

    name = serializers.CharField(
        allow_blank=True,
        trim_whitespace=True,
        error_messages={"required": "name is required"},
    )
    category = serializers.CharField(
        allow_blank=True,
        trim_whitespace=True,
        error_messages={"required": "category is required"},
    )
    description = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    url = serializers.CharField(
        allow_blank=True,
        trim_whitespace=True,
        error_messages={"required": "url is required"},
    )
    manual_url = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    screenshot_urls = serializers.ListField(child=serializers.CharField(), required=False)
    cover_screenshot_index = serializers.IntegerField(required=False, allow_null=True)
    screenshot_url = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    contact_name = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    contact_knoxid = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        """카멜/스네이크 케이스 입력을 내부 필드로 정규화합니다."""

        if not isinstance(data, dict):
            raise serializers.ValidationError("Invalid JSON body")

        def _pick(camel_key: str, snake_key: str) -> Any:
            if camel_key in data:
                return data.get(camel_key)
            if snake_key in data:
                return data.get(snake_key)
            return None

        normalized: Dict[str, Any] = {}
        if "name" in data:
            normalized["name"] = data.get("name") or ""
        if "category" in data:
            normalized["category"] = data.get("category") or ""
        if "description" in data:
            description_value = data.get("description")
            if description_value is not None:
                normalized["description"] = description_value
        if "url" in data:
            normalized["url"] = data.get("url") or ""

        manual_url_value = _pick("manualUrl", "manual_url")
        if manual_url_value is not None:
            normalized["manual_url"] = manual_url_value

        screenshot_urls_value = _pick("screenshotUrls", "screenshot_urls")
        if screenshot_urls_value is not None and not isinstance(screenshot_urls_value, list):
            screenshot_urls_value = []
        if screenshot_urls_value is not None:
            normalized["screenshot_urls"] = screenshot_urls_value

        cover_index_value = _pick("coverScreenshotIndex", "cover_screenshot_index")
        if cover_index_value == "":
            cover_index_value = None
        if cover_index_value is not None:
            normalized["cover_screenshot_index"] = cover_index_value

        screenshot_url_value = _pick("screenshotUrl", "screenshot_url")
        if screenshot_url_value is not None:
            normalized["screenshot_url"] = screenshot_url_value

        contact_name_value = _pick("contactName", "contact_name")
        if contact_name_value is not None:
            normalized["contact_name"] = contact_name_value

        contact_knoxid_value = _pick("contactKnoxid", "contact_knoxid")
        if contact_knoxid_value is not None:
            normalized["contact_knoxid"] = contact_knoxid_value

        return super().to_internal_value(normalized)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """입력 정규화/기본값 보정을 수행합니다."""

        name = (attrs.get("name") or "").strip()
        if not name:
            raise serializers.ValidationError({"name": ["name is required"]})

        category = (attrs.get("category") or "").strip()
        if not category:
            raise serializers.ValidationError({"category": ["category is required"]})

        url = (attrs.get("url") or "").strip()
        if not url:
            raise serializers.ValidationError({"url": ["url is required"]})

        description = (attrs.get("description") or "").strip()
        manual_url = (attrs.get("manual_url") or "").strip() or None
        screenshot_url = (attrs.get("screenshot_url") or "").strip()

        max_category_length = int(self.context.get("max_category_length") or 0)
        max_contact_length = int(self.context.get("max_contact_length") or 0)

        if max_category_length > 0:
            category = category[:max_category_length]

        contact_name = (attrs.get("contact_name") or "").strip()
        contact_knoxid = (attrs.get("contact_knoxid") or "").strip()
        if max_contact_length > 0:
            contact_name = contact_name[:max_contact_length]
            contact_knoxid = contact_knoxid[:max_contact_length]

        if not contact_name or not contact_knoxid:
            user = self.context.get("user")
            if user:
                default_name, default_knoxid = default_contact(user)
                contact_name = contact_name or default_name
                contact_knoxid = contact_knoxid or default_knoxid

        screenshot_urls = sanitize_screenshot_urls(attrs.get("screenshot_urls"))
        screenshot_urls = apply_cover_index(
            screenshot_urls,
            attrs.get("cover_screenshot_index"),
        )

        attrs.update(
            {
                "name": name,
                "category": category,
                "description": description,
                "url": url,
                "manual_url": manual_url,
                "screenshot_urls": screenshot_urls,
                "screenshot_url": screenshot_url,
                "contact_name": contact_name,
                "contact_knoxid": contact_knoxid,
            }
        )
        return attrs


__all__ = [
    "apply_cover_index",
    "AppStoreAppCreateSerializer",
    "can_manage_app",
    "can_manage_comment",
    "default_contact",
    "sanitize_screenshot_urls",
    "serialize_app",
    "serialize_comment",
    "serialize_user",
]
