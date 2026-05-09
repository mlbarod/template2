# =============================================================================
# 모듈 설명: appstore CRUD/상호작용 APIView를 제공합니다.
# - 주요 대상: AppStoreAppsView, AppStoreAppDetailView, AppStoreCommentsView 등
# - 불변 조건: 비즈니스 로직은 서비스/셀렉터로 위임합니다.
# =============================================================================

"""AppStore 생성/조회/수정/삭제 및 상호작용 엔드포인트 모음입니다.

- GET    /api/v1/appstore/apps                     : 앱 목록 조회
- POST   /api/v1/appstore/apps                     : 앱 등록
- GET    /api/v1/appstore/apps/<id>                : 단일 앱 상세(+댓글)
- GET    /api/v1/appstore/apps/<id>/cover          : 앱 대표 스크린샷(바이너리)
- PATCH  /api/v1/appstore/apps/<id>                : 앱 정보 수정
- DELETE /api/v1/appstore/apps/<id>                : 앱 삭제(작성자/관리자)
- POST   /api/v1/appstore/apps/<id>/like           : 좋아요 토글
- POST   /api/v1/appstore/apps/<id>/view           : 조회수 증가
- GET    /api/v1/appstore/apps/<id>/comments       : 댓글 목록
- POST   /api/v1/appstore/apps/<id>/comments       : 댓글 작성
- PATCH  /api/v1/appstore/apps/<id>/comments/<cid> : 댓글 수정
- DELETE /api/v1/appstore/apps/<id>/comments/<cid> : 댓글 삭제
- POST   /api/v1/appstore/apps/<id>/comments/<cid>/like : 댓글 좋아요 토글

주의:
- 요청/응답 키는 카멜 케이스를 기본으로 하며, 일부 입력은 스네이크 케이스도 허용합니다.
- 길이 제한은 MAX_CATEGORY_LENGTH / MAX_CONTACT_LENGTH 기준입니다.
"""
from __future__ import annotations

import logging
from typing import Any, Sequence

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import extract_first_error_message, parse_json_body

from .selectors import (
    get_app_by_id,
    get_app_detail,
    get_app_list,
    get_comment_by_id,
    get_comments_for_app,
    get_liked_app_ids_for_user,
    get_liked_comment_ids_for_user,
)
from .serializers import (
    AppStoreAppCreateSerializer,
    AppStoreAppUpdateSerializer,
    AppStoreCommentCreateSerializer,
    AppStoreCommentUpdateSerializer,
    serialize_app,
    serialize_comment,
)
from .services import (
    create_app,
    create_comment,
    delete_app,
    delete_comment,
    increment_view_count,
    toggle_comment_like,
    toggle_like,
    update_app,
    update_comment,
)
from .services.permissions import can_manage_app, can_manage_comment
from .services.screenshots import resolve_cover_image

logger = logging.getLogger(__name__)

# =============================================================================
# 상수: 입력 길이 제한
# =============================================================================
MAX_CATEGORY_LENGTH = 100
MAX_CONTACT_LENGTH = 255


def _load_app(app_id: int) -> Any | None:
    """앱 id로 AppStoreApp을 조회합니다.

    인자:
        app_id: 앱 PK.

    반환:
        AppStoreApp 인스턴스 또는 None.

    부작용:
        없음. 읽기 전용 조회입니다.

    오류:
        없음(미존재 시 None 반환).
    """

    return get_app_by_id(app_id=app_id)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppsView(APIView):
    """앱 목록 조회 및 신규 등록."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """앱 목록을 조회합니다.

        입력:
          - 요청: Django HttpRequest
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: GET /api/v1/appstore/apps

        반환:
          - results: 앱 목록
          - total: 총 개수

        부작용:
          없음. 읽기 전용 조회입니다.

        오류:
          - 없음

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 목록/좋아요 정보 조회
        # -----------------------------------------------------------------------------
        queryset = get_app_list()
        liked_ids: Sequence[int] = []
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        if user:
            liked_ids = get_liked_app_ids_for_user(user=user)

        # -----------------------------------------------------------------------------
        # 2) 응답 직렬화
        # -----------------------------------------------------------------------------
        apps = []
        for app in queryset:
            # 목록에서는 base64 데이터를 직접 내려보내지 않도록 커버 URL을 치환합니다.
            cover_src = ""
            if getattr(app, "screenshot_url", ""):
                cover_src = app.screenshot_url
            elif getattr(app, "screenshot_base64", ""):
                cover_src = request.build_absolute_uri(
                    reverse("appstore-app-cover", kwargs={"app_id": app.pk})
                )
            apps.append(serialize_app(app, user, liked_ids, cover_src=cover_src))

        # -----------------------------------------------------------------------------
        # 3) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse({"results": apps, "total": len(apps)})

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """앱을 신규 등록합니다.

        입력:
          - 요청: Django HttpRequest
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps
            {
              예시 "name": "New App",
              예시 "category": "Tools",
              예시 "description": "desc",
              예시 "url": "https://example.com",
              예시 "manualUrl": "https://example.com/manual",
              예시 "screenshotUrls": ["https://example.com/cover.png"],
              예시 "coverScreenshotIndex": 0,
              예시 "screenshotUrl": "",
              예시 "contactName": "홍길동",
              예시 "contactKnoxid": "hong"
            }

        snake/camel 호환:
          - screenshotUrls / screenshot_urls (키 매핑)
          - coverScreenshotIndex / cover_screenshot_index (키 매핑)
          - screenshotUrl / screenshot_url (키 매핑)
          - manualUrl / manual_url (키 매핑)

        반환:
          - app: 생성된 앱 상세 payload

        부작용:
          AppStoreApp 레코드를 생성합니다.

        오류:
          - 401: 인증 실패
          - 400: 필수 필드 누락/JSON 파싱 실패
          - 500: 내부 오류
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 입력 검증/정규화
        # -----------------------------------------------------------------------------
        serializer = AppStoreAppCreateSerializer(
            data=payload,
            context={
                "user": request.user,
                "max_category_length": MAX_CATEGORY_LENGTH,
                "max_contact_length": MAX_CONTACT_LENGTH,
            },
        )
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        validated = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 4) 생성 및 응답
        # -----------------------------------------------------------------------------
        try:
            app = create_app(
                owner=request.user,
                name=validated["name"],
                category=validated["category"],
                description=validated["description"],
                url=validated["url"],
                manual_url=validated["manual_url"],
                screenshot_urls=validated["screenshot_urls"],
                screenshot_url=validated["screenshot_url"],
                contact_name=validated["contact_name"],
                contact_knoxid=validated["contact_knoxid"],
            )
            liked_ids = get_liked_app_ids_for_user(user=request.user)
            return JsonResponse(
                {"app": serialize_app(app, request.user, liked_ids, include_screenshots=True)},
                status=201,
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to create appstore app")
            return JsonResponse({"error": "Failed to create app"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppCoverView(APIView):
    """앱 대표 스크린샷 바이너리를 제공합니다."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> HttpResponse:
        """앱 대표 스크린샷을 반환합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: GET /api/v1/appstore/apps/123/cover

        반환:
          - 이미지 바이너리(Content-Type: image/*)

        부작용:
          없음. 읽기 전용 조회입니다.

        오류:
          - 404: 앱 또는 스크린샷 없음
          - 400: 스크린샷 디코딩 실패

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 앱 조회
        # -----------------------------------------------------------------------------
        app = get_app_by_id(app_id=app_id)
        if not app:
            return HttpResponse(status=404)

        # -----------------------------------------------------------------------------
        # 2) 커버 이미지 해석 및 HTTP 응답 매핑
        # -----------------------------------------------------------------------------
        cover = resolve_cover_image(app)
        if cover.is_redirect:
            return HttpResponseRedirect(cover.redirect_url)
        if cover.has_binary:
            return HttpResponse(cover.binary, content_type=cover.content_type)
        if cover.status_code == 400:
            logger.error("Failed to decode appstore screenshot for app %s", app_id)
        return HttpResponse(status=cover.status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppDetailView(APIView):
    """앱 단건 조회/수정/삭제."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱 상세 정보를 조회합니다(댓글/스크린샷 포함).

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: GET /api/v1/appstore/apps/123

        반환:
          - app: 앱 상세 payload

        부작용:
          없음. 읽기 전용 조회입니다.

        오류:
          - 404: 앱 없음

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 앱 조회
        # -----------------------------------------------------------------------------
        app = get_app_detail(app_id=app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)
        # -----------------------------------------------------------------------------
        # 2) 좋아요/댓글 좋아요 목록 조회
        # -----------------------------------------------------------------------------
        liked_ids: Sequence[int] = []
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        liked_comment_ids: set[int] = set()
        if user:
            liked_ids = get_liked_app_ids_for_user(user=user)
            liked_comment_ids = set(get_liked_comment_ids_for_user(user=user, app_id=app.pk))

        # -----------------------------------------------------------------------------
        # 3) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse(
            {
                "app": serialize_app(
                    app,
                    user,
                    liked_ids,
                    include_comments=True,
                    include_screenshots=True,
                    liked_comment_ids=liked_comment_ids,
                )
            }
        )

    def patch(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱 정보를 부분 수정합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: PATCH /api/v1/appstore/apps/123
            예시 바디: {"description": "updated"}

        snake/camel 호환:
          - screenshotUrls / screenshot_urls (키 매핑)
          - coverScreenshotIndex / cover_screenshot_index (키 매핑)
          - screenshotUrl / screenshot_url (키 매핑)
          - manualUrl / manual_url (키 매핑)

        반환:
          - app: 업데이트된 앱 payload

        부작용:
          AppStoreApp 레코드를 업데이트합니다.

        오류:
          - 401: 인증 실패
          - 403: 권한 없음
          - 404: 앱 없음
          - 400: 입력 오류/변경 사항 없음
          - 500: 내부 오류
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱 조회 및 권한 확인
        # -----------------------------------------------------------------------------
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        if not can_manage_app(request.user, app):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) JSON 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # -----------------------------------------------------------------------------
        # 4) 입력 검증/업데이트 필드 구성
        # -----------------------------------------------------------------------------
        serializer = AppStoreAppUpdateSerializer(
            data=payload,
            context={
                "max_category_length": MAX_CATEGORY_LENGTH,
                "max_contact_length": MAX_CONTACT_LENGTH,
            },
        )
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        updates = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 5) 업데이트 수행
        # -----------------------------------------------------------------------------
        try:
            app = update_app(app=app, updates=updates)
            liked_ids = get_liked_app_ids_for_user(user=request.user)
            return JsonResponse({"app": serialize_app(app, request.user, liked_ids, include_screenshots=True)})
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to update appstore app")
            return JsonResponse({"error": "Failed to update app"}, status=500)

    def delete(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱을 삭제합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: DELETE /api/v1/appstore/apps/123

        반환:
          - 예시 응답: success: true

        부작용:
          AppStoreApp 레코드를 삭제합니다.

        오류:
          - 401: 인증 실패
          - 403: 권한 없음
          - 404: 앱 없음
          - 500: 내부 오류

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱 조회 및 권한 확인
        # -----------------------------------------------------------------------------
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        if not can_manage_app(request.user, app):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) 삭제 수행
        # -----------------------------------------------------------------------------
        try:
            delete_app(app=app)
            return JsonResponse({"success": True})
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to delete appstore app")
            return JsonResponse({"error": "Failed to delete app"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreLikeToggleView(APIView):
    """좋아요 토글."""

    def post(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱 좋아요를 토글합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps/123/like

        반환:
          - liked: 좋아요 여부
          - likeCount: 최신 좋아요 수
          - appId: 앱 id

        부작용:
          AppStoreLike 생성/삭제 및 like_count 갱신이 발생합니다.

        오류:
          - 401: 인증 실패
          - 404: 앱 없음
          - 500: 내부 오류

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱 조회
        # -----------------------------------------------------------------------------
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 3) 좋아요 토글
        # -----------------------------------------------------------------------------
        try:
            liked, like_count = toggle_like(app=app, user=request.user)
            return JsonResponse(
                {"liked": liked, "likeCount": like_count, "appId": app.pk},
                status=200,
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to toggle like for appstore app %s", app_id)
            return JsonResponse({"error": "Failed to toggle like"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreViewIncrementView(APIView):
    """조회수 증가."""

    def post(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱 조회수를 증가시킵니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps/123/view

        반환:
          - viewCount: 최신 조회수
          - appId: 앱 id

        부작용:
          AppStoreApp.view_count를 갱신합니다.

        오류:
          - 404: 앱 없음

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 앱 조회
        # -----------------------------------------------------------------------------
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 2) 조회수 증가
        # -----------------------------------------------------------------------------
        view_count = increment_view_count(app=app)
        return JsonResponse({"viewCount": view_count, "appId": app.pk})


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentsView(APIView):
    """댓글 목록 조회/작성."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """댓글 목록을 조회합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: GET /api/v1/appstore/apps/123/comments

        반환:
          - comments: 댓글 목록
          - total: 총 개수

        부작용:
          없음. 읽기 전용 조회입니다.

        오류:
          - 404: 앱 없음

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 앱 조회
        # -----------------------------------------------------------------------------
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 2) 댓글/좋아요 목록 조회
        # -----------------------------------------------------------------------------
        comments = get_comments_for_app(app_id=app.pk)
        liked_comment_ids: set[int] = set()
        if request.user.is_authenticated:
            liked_comment_ids = set(get_liked_comment_ids_for_user(user=request.user, app_id=app.pk))
        payload = [serialize_comment(comment, request.user, liked_comment_ids) for comment in comments]
        # -----------------------------------------------------------------------------
        # 3) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse({"comments": payload, "total": len(payload)})

    def post(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """댓글을 작성합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps/123/comments
            예시 바디: {"content": "댓글입니다", "parentCommentId": 10}

        snake/camel 호환:
          - parentCommentId / parent_comment_id (키 매핑)

        반환:
          - comment: 생성된 댓글 payload

        부작용:
          AppStoreComment 레코드를 생성합니다.

        오류:
          - 401: 인증 실패
          - 404: 앱/부모 댓글 없음
          - 400: 입력 오류/JSON 파싱 실패
          - 500: 내부 오류
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱 조회
        # -----------------------------------------------------------------------------
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 3) JSON 파싱 및 입력 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = AppStoreCommentCreateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        validated = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 4) 부모 댓글 확인(대댓글)
        # -----------------------------------------------------------------------------
        parent_comment: Any | None = None
        parent_id = validated.get("parent_comment_id")
        if parent_id is not None:
            parent_comment = get_comment_by_id(app_id=app.pk, comment_id=parent_id)
            if not parent_comment:
                return JsonResponse({"error": "Parent comment not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 5) 댓글 생성
        # -----------------------------------------------------------------------------
        try:
            comment = create_comment(
                app=app,
                user=request.user,
                content=validated["content"],
                parent_comment=parent_comment,
            )
            return JsonResponse(
                {"comment": serialize_comment(comment, request.user, set())},
                status=201,
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to create appstore comment")
            return JsonResponse({"error": "Failed to create comment"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentDetailView(APIView):
    """댓글 수정/삭제."""

    def patch(
        self, request: HttpRequest, app_id: int, comment_id: int, *args: object, **kwargs: object
    ) -> JsonResponse:
        """댓글 내용을 수정합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - comment_id: 댓글 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: PATCH /api/v1/appstore/apps/123/comments/456
            예시 바디: {"content": "수정 내용"}

        반환:
          - comment: 수정된 댓글 payload

        부작용:
          AppStoreComment 레코드를 업데이트합니다.

        오류:
          - 401: 인증 실패
          - 403: 권한 없음
          - 404: 앱/댓글 없음
          - 400: 입력 오류/JSON 파싱 실패
          - 500: 내부 오류

        snake/camel 호환:
          - 해당 없음(요청 바디 키는 content만 사용)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱/댓글 조회 및 권한 확인
        # -----------------------------------------------------------------------------
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comment = get_comment_by_id(app_id=app.pk, comment_id=comment_id)
        if not comment:
            return JsonResponse({"error": "Comment not found"}, status=404)

        if not can_manage_comment(request.user, comment):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) JSON 파싱 및 입력 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = AppStoreCommentUpdateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        validated = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 4) 댓글 업데이트
        # -----------------------------------------------------------------------------
        try:
            comment = update_comment(comment=comment, content=validated["content"])
            liked_comment_ids: set[int] = set()
            if request.user.is_authenticated:
                liked_comment_ids = set(get_liked_comment_ids_for_user(user=request.user, app_id=app.pk))
            return JsonResponse({"comment": serialize_comment(comment, request.user, liked_comment_ids)})
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to update appstore comment %s", comment_id)
            return JsonResponse({"error": "Failed to update comment"}, status=500)

    def delete(
        self, request: HttpRequest, app_id: int, comment_id: int, *args: object, **kwargs: object
    ) -> JsonResponse:
        """댓글을 삭제합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - comment_id: 댓글 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: DELETE /api/v1/appstore/apps/123/comments/456

        반환:
          - 예시 응답: success: true

        부작용:
          AppStoreComment 레코드를 삭제합니다.

        오류:
          - 401: 인증 실패
          - 403: 권한 없음
          - 404: 앱/댓글 없음
          - 500: 내부 오류

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱/댓글 조회 및 권한 확인
        # -----------------------------------------------------------------------------
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comment = get_comment_by_id(app_id=app.pk, comment_id=comment_id)
        if not comment:
            return JsonResponse({"error": "Comment not found"}, status=404)

        if not can_manage_comment(request.user, comment):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) 삭제 수행
        # -----------------------------------------------------------------------------
        try:
            delete_comment(comment=comment)
            return JsonResponse({"success": True})
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to delete appstore comment %s", comment_id)
            return JsonResponse({"error": "Failed to delete comment"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentLikeToggleView(APIView):
    """댓글 좋아요 토글."""

    def post(
        self, request: HttpRequest, app_id: int, comment_id: int, *args: object, **kwargs: object
    ) -> JsonResponse:
        """댓글 좋아요를 토글합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - comment_id: 댓글 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps/123/comments/456/like

        반환:
          - liked: 좋아요 여부
          - likeCount: 최신 좋아요 수
          - appId / commentId (식별자 키)

        부작용:
          AppStoreCommentLike 생성/삭제 및 like_count 갱신이 발생합니다.

        오류:
          - 401: 인증 실패
          - 404: 앱/댓글 없음
          - 500: 내부 오류

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱/댓글 조회
        # -----------------------------------------------------------------------------
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comment = get_comment_by_id(app_id=app.pk, comment_id=comment_id)
        if not comment:
            return JsonResponse({"error": "Comment not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 3) 좋아요 토글
        # -----------------------------------------------------------------------------
        try:
            liked, like_count = toggle_comment_like(comment=comment, user=request.user)
            return JsonResponse(
                {
                    "appId": app.pk,
                    "commentId": comment.pk,
                    "liked": liked,
                    "likeCount": like_count,
                },
                status=200,
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to toggle comment like for app %s comment %s", app_id, comment_id)
            return JsonResponse({"error": "Failed to toggle comment like"}, status=500)


__all__ = [
    "AppStoreAppsView",
    "AppStoreAppDetailView",
    "AppStoreLikeToggleView",
    "AppStoreViewIncrementView",
    "AppStoreCommentsView",
    "AppStoreCommentDetailView",
    "AppStoreCommentLikeToggleView",
]
