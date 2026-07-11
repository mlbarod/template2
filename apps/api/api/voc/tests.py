# =============================================================================
# 모듈 설명: voc 엔드포인트 테스트를 제공합니다.
# - 주요 클래스: VocEndpointTests
# - 불변 조건: URL 네임(voc-*)이 등록되어 있어야 합니다.
# =============================================================================

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from api.voc.models import VocPost


def _allow_test_scope_access(test_case: TestCase) -> None:
    """도메인 endpoint 테스트에서 공통 portal/app 권한 경계를 격리합니다."""

    for service_name in ("get_portal_access_payload", "get_access_payload"):
        patcher = patch(
            f"api.account.services.{service_name}",
            return_value={"allowed": True},
        )
        patcher.start()
        test_case.addCleanup(patcher.stop)


class VocEndpointTests(TestCase):
    def setUp(self) -> None:
        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S80000",
            password="test-password",
            knox_id="knox-80000",
            username="정진우",
        )
        self.client.force_login(self.user)

    def test_voc_posts_list_returns_results(self) -> None:
        VocPost.objects.create(title="Hello", content="World", author=self.user, status="접수")
        response = self.client.get(reverse("voc-posts"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["results"][0]["app"], "기타")
        self.assertEqual(response.json()["results"][0]["author"]["name"], "정진우(knox-80000)")

    def test_voc_author_display_uses_only_username_and_knox_id(self) -> None:
        User = get_user_model()
        fallback_user = User.objects.create_user(
            sabun="S80001",
            password="test-password",
            knox_id="knox-80001",
            username="",
            first_name="진우",
            last_name="정",
            email="jinwoo@example.com",
        )
        VocPost.objects.create(title="Fallback", content="Body", author=fallback_user, status="접수")

        response = self.client.get(reverse("voc-posts"))

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        fallback_post = next(post for post in results if post["title"] == "Fallback")
        self.assertEqual(fallback_post["author"]["name"], "knox-80001")

    def test_voc_posts_create_update_delete_and_reply(self) -> None:
        # -----------------------------------------------------------------------------
        # 1) 게시글 생성
        # -----------------------------------------------------------------------------
        create_response = self.client.post(
            reverse("voc-posts"),
            data='{"title":"Title","content":"Body","status":"접수","app":"기타"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        post_id = create_response.json()["post"]["id"]

        # -----------------------------------------------------------------------------
        # 2) 게시글 수정
        # -----------------------------------------------------------------------------
        update_response = self.client.patch(
            reverse("voc-post-detail", kwargs={"post_id": post_id}),
            data='{"status":"진행중","title":"Updated"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["post"]["status"], "진행중")

        # -----------------------------------------------------------------------------
        # 3) 답변 추가
        # -----------------------------------------------------------------------------
        reply_response = self.client.post(
            reverse("voc-post-reply", kwargs={"post_id": post_id}),
            data='{"content":"Reply"}',
            content_type="application/json",
        )
        self.assertEqual(reply_response.status_code, 201)

        # -----------------------------------------------------------------------------
        # 4) 게시글 삭제
        # -----------------------------------------------------------------------------
        delete_response = self.client.delete(reverse("voc-post-detail", kwargs={"post_id": post_id}))
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.json()["success"])

    def test_voc_posts_create_requires_app(self) -> None:
        response = self.client.post(
            reverse("voc-posts"),
            data='{"title":"Title","content":"Body","status":"접수"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_voc_posts_status_counts_order(self) -> None:
        """statusCounts가 상태 정의 순서를 유지하는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) 게시글 생성(순서와 무관하게 섞어서 생성)
        # -------------------------------------------------------------------------
        VocPost.objects.create(title="A", content="A", author=self.user, status="진행중")
        VocPost.objects.create(title="B", content="B", author=self.user, status="접수")
        VocPost.objects.create(title="C", content="C", author=self.user, status="완료")
        VocPost.objects.create(title="D", content="D", author=self.user, status="반려")

        # -------------------------------------------------------------------------
        # 2) 목록 조회
        # -------------------------------------------------------------------------
        response = self.client.get(reverse("voc-posts"))
        self.assertEqual(response.status_code, 200)
        counts = response.json()["statusCounts"]

        # -------------------------------------------------------------------------
        # 3) 상태 키 순서 검증
        # -------------------------------------------------------------------------
        self.assertEqual(list(counts.keys()), ["접수", "진행중", "완료", "반려"])
