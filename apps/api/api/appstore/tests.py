# =============================================================================
# 모듈 설명: AppStore 서비스/엔드포인트 테스트를 제공합니다.
# - 주요 대상: 스크린샷 처리, 댓글/좋아요, 생성/조회/수정/삭제 흐름
# - 불변 조건: URL 네임(appstore-*)이 등록되어 있어야 합니다.
# =============================================================================
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from api.appstore.serializers import default_contact
from api.appstore.services import create_app, create_comment, update_app


class AppstoreScreenshotTests(TestCase):
    """appstore 스크린샷 저장/응답 동작을 검증합니다."""

    def test_create_app_stores_data_url_as_base64(self) -> None:
        """data URL이 base64 필드로 저장되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/입력 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S12345",
            password="test-password",
            knox_id="knox-12345",
        )
        screenshot_url = "data:image/png;base64,AAA="

        # -----------------------------------------------------------------------------
        # 2) 앱 생성
        # -----------------------------------------------------------------------------
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 3) 저장 결과 검증
        # -----------------------------------------------------------------------------
        app.refresh_from_db()
        self.assertEqual(app.screenshot_url, "")
        self.assertEqual(app.screenshot_base64, "AAA=")
        self.assertEqual(app.screenshot_mime_type, "image/png")
        self.assertEqual(app.screenshot_gallery, [])

    def test_create_app_keeps_external_screenshot_url(self) -> None:
        """외부 URL이 screenshot_url로 유지되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/입력 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S88888",
            password="test-password",
            knox_id="knox-88888",
        )
        screenshot_url = "https://example.com/screenshot.png"

        # -----------------------------------------------------------------------------
        # 2) 앱 생성
        # -----------------------------------------------------------------------------
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 3) 저장 결과 검증
        # -----------------------------------------------------------------------------
        app.refresh_from_db()
        self.assertEqual(app.screenshot_url, screenshot_url)
        self.assertEqual(app.screenshot_base64, "")
        self.assertEqual(app.screenshot_mime_type, "")
        self.assertEqual(app.screenshot_gallery, [])

    def test_create_app_stores_gallery_items(self) -> None:
        """갤러리 스크린샷이 올바르게 저장되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/입력 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S77777",
            password="test-password",
            knox_id="knox-77777",
        )

        cover = "data:image/png;base64,COVER="
        extra_url = "https://example.com/extra.png"
        extra_data = "data:image/png;base64,EXTRA="

        # -----------------------------------------------------------------------------
        # 2) 앱 생성
        # -----------------------------------------------------------------------------
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_urls=[cover, extra_url, extra_data],
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 3) 저장 결과 검증
        # -----------------------------------------------------------------------------
        app.refresh_from_db()
        self.assertEqual(app.screenshot_url, "")
        self.assertEqual(app.screenshot_base64, "COVER=")
        self.assertEqual(app.screenshot_mime_type, "image/png")
        self.assertEqual(
            app.screenshot_gallery,
            [
                {"url": extra_url, "base64": "", "mime_type": ""},
                {"url": "", "base64": "EXTRA=", "mime_type": "image/png"},
            ],
        )

    def test_update_app_allows_clearing_screenshot(self) -> None:
        """스크린샷 초기화(빈 값)가 허용되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/기존 앱 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S99999",
            password="test-password",
            knox_id="knox-99999",
        )
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url="data:image/png;base64,BBB=",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 2) 스크린샷 초기화 업데이트
        # -----------------------------------------------------------------------------
        updated = update_app(app=app, updates={"screenshot_url": ""})

        # -----------------------------------------------------------------------------
        # 3) 저장 결과 검증
        # -----------------------------------------------------------------------------
        updated.refresh_from_db()
        self.assertEqual(updated.screenshot_url, "")
        self.assertEqual(updated.screenshot_base64, "")
        self.assertEqual(updated.screenshot_mime_type, "")
        self.assertEqual(updated.screenshot_gallery, [])

    def test_detail_payload_includes_screenshot_url(self) -> None:
        """상세 응답에 screenshotUrl/Urls와 manualUrl이 포함되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/앱 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S54321",
            password="test-password",
            knox_id="knox-54321",
        )
        screenshot_url = "data:image/png;base64,CCC="
        manual_url = "https://example.com/manual"
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            manual_url=manual_url,
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 2) 상세 조회 요청
        # -----------------------------------------------------------------------------
        response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": app.pk}))
        self.assertEqual(response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 응답 페이로드 검증
        # -----------------------------------------------------------------------------
        payload = response.json()
        self.assertEqual(payload["app"]["screenshotUrl"], screenshot_url)
        self.assertEqual(payload["app"]["screenshotUrls"], [screenshot_url])
        self.assertEqual(payload["app"]["coverScreenshotIndex"], 0)
        self.assertEqual(payload["app"]["manualUrl"], manual_url)

    def test_list_payload_uses_cover_endpoint_for_base64(self) -> None:
        """목록 응답은 base64 커버를 엔드포인트 URL로 제공합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/앱 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S22222",
            password="test-password",
            knox_id="knox-22222",
        )
        screenshot_url = "data:image/png;base64,QUJD"
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 2) 목록 조회
        # -----------------------------------------------------------------------------
        response = self.client.get(reverse("appstore-apps"))
        self.assertEqual(response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 응답 페이로드 검증
        # -----------------------------------------------------------------------------
        payload = response.json()
        results = payload.get("results", [])
        self.assertEqual(len(results), 1)
        cover_path = reverse("appstore-app-cover", kwargs={"app_id": app.pk})
        cover_url = results[0].get("screenshotUrl", "")
        self.assertTrue(isinstance(cover_url, str))
        self.assertTrue(cover_url.endswith(cover_path))
        self.assertNotIn("data:image", cover_url)

    def test_cover_endpoint_returns_decoded_image(self) -> None:
        """커버 엔드포인트가 base64 스크린샷을 바이너리로 반환합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/앱 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S33333",
            password="test-password",
            knox_id="knox-33333",
        )
        screenshot_url = "data:image/png;base64,QUJD"
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 2) 커버 조회
        # -----------------------------------------------------------------------------
        response = self.client.get(reverse("appstore-app-cover", kwargs={"app_id": app.pk}))

        # -----------------------------------------------------------------------------
        # 3) 응답 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content, b"ABC")


class AppstoreContactDefaultTests(TestCase):
    """appstore 연락처 기본값 계산을 검증합니다."""

    def test_default_contact_uses_full_name_when_username_missing(self) -> None:
        """username이 없을 때 이름(first/last)을 사용해야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S11111",
            password="test-password",
            knox_id="knox-11111",
        )
        user.first_name = "John"
        user.last_name = "Doe"
        user.save(update_fields=["first_name", "last_name"])

        # -----------------------------------------------------------------------------
        # 2) 기본값 계산
        # -----------------------------------------------------------------------------
        contact_name, contact_knoxid = default_contact(user)

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(contact_name, "John Doe")
        self.assertEqual(contact_knoxid, "knox-11111")

    def test_default_contact_uses_email_when_name_missing(self) -> None:
        """username/이름이 없으면 email을 사용해야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S11112",
            password="test-password",
            knox_id="knox-11112",
        )
        user.email = "user@example.com"
        user.save(update_fields=["email"])

        # -----------------------------------------------------------------------------
        # 2) 기본값 계산
        # -----------------------------------------------------------------------------
        contact_name, contact_knoxid = default_contact(user)

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(contact_name, "user@example.com")
        self.assertEqual(contact_knoxid, "knox-11112")


class AppstoreCommentReplyLikeTests(TestCase):
    """appstore 댓글 대댓글/좋아요 동작을 검증합니다."""

    def setUp(self) -> None:
        """댓글/좋아요 테스트용 사용자와 앱을 준비합니다."""
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S22222",
            password="test-password",
            knox_id="knox-22222",
        )
        self.client.force_login(self.user)
        self.app = create_app(
            owner=self.user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

    def test_create_reply_comment_sets_parent_comment_id(self) -> None:
        """대댓글 생성 시 parentCommentId가 설정되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 부모 댓글 생성
        # -----------------------------------------------------------------------------
        parent = create_comment(app=self.app, user=self.user, content="부모 댓글")
        url = reverse("appstore-app-comments", kwargs={"app_id": self.app.pk})

        # -----------------------------------------------------------------------------
        # 2) 대댓글 생성 요청
        # -----------------------------------------------------------------------------
        response = self.client.post(
            url,
            data='{"content":"대댓글","parentCommentId":%d}' % parent.pk,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

        # -----------------------------------------------------------------------------
        # 3) 응답 페이로드 검증
        # -----------------------------------------------------------------------------
        payload = response.json()
        self.assertEqual(payload["comment"]["parentCommentId"], parent.pk)

        # -----------------------------------------------------------------------------
        # 4) 상세 조회에서 댓글 포함 여부 확인
        # -----------------------------------------------------------------------------
        detail_response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        comment_ids = {comment["id"] for comment in detail_payload["app"]["comments"]}
        self.assertIn(parent.pk, comment_ids)
        self.assertIn(payload["comment"]["id"], comment_ids)

    def test_toggle_comment_like_updates_like_count_and_liked(self) -> None:
        """댓글 좋아요 토글이 상태/카운트를 갱신하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 댓글 생성 및 좋아요 URL 준비
        # -----------------------------------------------------------------------------
        comment = create_comment(app=self.app, user=self.user, content="좋아요 테스트")
        like_url = reverse(
            "appstore-app-comment-like",
            kwargs={"app_id": self.app.pk, "comment_id": comment.pk},
        )

        # -----------------------------------------------------------------------------
        # 2) 첫 번째 토글 결과 검증
        # -----------------------------------------------------------------------------
        first = self.client.post(like_url)
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()
        self.assertTrue(first_payload["liked"])
        self.assertEqual(first_payload["likeCount"], 1)

        # -----------------------------------------------------------------------------
        # 3) 상세 조회에서 반영 여부 확인
        # -----------------------------------------------------------------------------
        detail_response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        liked_comment = next(
            item for item in detail_payload["app"]["comments"] if item["id"] == comment.pk
        )
        self.assertTrue(liked_comment["liked"])
        self.assertEqual(liked_comment["likeCount"], 1)

        # -----------------------------------------------------------------------------
        # 4) 두 번째 토글 결과 검증
        # -----------------------------------------------------------------------------
        second = self.client.post(like_url)
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()
        self.assertFalse(second_payload["liked"])
        self.assertEqual(second_payload["likeCount"], 0)


class AppstoreEndpointTests(TestCase):
    """AppStore 엔드포인트 기본 흐름 테스트."""

    def setUp(self) -> None:
        """엔드포인트 테스트용 사용자와 기본 앱을 생성합니다."""
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S33333",
            password="test-password",
            email="s33333@example.com",
            knox_id="knox-33333",
        )
        self.client.force_login(self.user)
        self.app = create_app(
            owner=self.user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

    def test_appstore_apps_list_and_create(self) -> None:
        """앱 목록 조회 및 생성 API가 정상 동작하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 목록 조회
        # -----------------------------------------------------------------------------
        list_response = self.client.get(reverse("appstore-apps"))
        self.assertEqual(list_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 2) 앱 생성
        # -----------------------------------------------------------------------------
        create_response = self.client.post(
            reverse("appstore-apps"),
            data=(
                '{"name":"New App","category":"Tools","description":"desc","url":"https://new.app",'
                '"contactName":"User","contactKnoxid":"user1"}'
            ),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)

    def test_appstore_create_returns_string_error_for_serializer_validation_failure(self) -> None:
        """앱 생성 검증 실패 시 문자열 error 계약을 유지하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 필수 name 누락 요청
        # -----------------------------------------------------------------------------
        response = self.client.post(
            reverse("appstore-apps"),
            data='{"name":"   ","category":"Tools","url":"https://new.app"}',
            content_type="application/json",
        )

        # -----------------------------------------------------------------------------
        # 2) 문자열 error 응답 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"], "name is required")

    def test_appstore_detail_update_delete_and_view_like(self) -> None:
        """상세 조회/수정/삭제 및 좋아요/조회수 API를 검증합니다."""
        # -----------------------------------------------------------------------------
        # 1) 상세 조회
        # -----------------------------------------------------------------------------
        detail = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail.status_code, 200)

        # -----------------------------------------------------------------------------
        # 2) 상세 수정
        # -----------------------------------------------------------------------------
        update_response = self.client.patch(
            reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}),
            data='{"description":"updated"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 좋아요/조회수 증가
        # -----------------------------------------------------------------------------
        like_response = self.client.post(reverse("appstore-app-like", kwargs={"app_id": self.app.pk}))
        self.assertEqual(like_response.status_code, 200)

        view_response = self.client.post(reverse("appstore-app-view", kwargs={"app_id": self.app.pk}))
        self.assertEqual(view_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 4) 삭제
        # -----------------------------------------------------------------------------
        delete_response = self.client.delete(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(delete_response.status_code, 200)

    def test_appstore_comments_endpoints(self) -> None:
        """댓글 목록/생성/수정/삭제/좋아요 API를 검증합니다."""
        # -----------------------------------------------------------------------------
        # 1) 댓글 목록 조회
        # -----------------------------------------------------------------------------
        list_response = self.client.get(reverse("appstore-app-comments", kwargs={"app_id": self.app.pk}))
        self.assertEqual(list_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 2) 댓글 생성
        # -----------------------------------------------------------------------------
        create_response = self.client.post(
            reverse("appstore-app-comments", kwargs={"app_id": self.app.pk}),
            data='{"content":"comment"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        comment_id = create_response.json()["comment"]["id"]

        # -----------------------------------------------------------------------------
        # 3) 댓글 수정
        # -----------------------------------------------------------------------------
        update_response = self.client.patch(
            reverse(
                "appstore-app-comment-detail",
                kwargs={"app_id": self.app.pk, "comment_id": comment_id},
            ),
            data='{"content":"updated"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 4) 댓글 좋아요
        # -----------------------------------------------------------------------------
        like_response = self.client.post(
            reverse(
                "appstore-app-comment-like",
                kwargs={"app_id": self.app.pk, "comment_id": comment_id},
            )
        )
        self.assertEqual(like_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 5) 댓글 삭제
        # -----------------------------------------------------------------------------
        delete_response = self.client.delete(
            reverse(
                "appstore-app-comment-detail",
                kwargs={"app_id": self.app.pk, "comment_id": comment_id},
            )
        )
        self.assertEqual(delete_response.status_code, 200)
