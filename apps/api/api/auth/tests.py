# =============================================================================
# 모듈 설명: 인증(Auth) 기능 테스트를 제공합니다.
# - 주요 대상: /auth/me, /auth/login, /auth/logout, /auth/config, 프론트 리다이렉트
# - 불변 조건: URL 네임은 auth-* 네임스페이스로 등록되어 있어야 합니다.
# =============================================================================

"""인증(Auth) 기능 관련 테스트 모음.

- 주요 대상: /auth/me, /auth/login, /auth/logout, /auth/config, 프론트 리다이렉트
- 주요 엔드포인트/클래스: AuthMeTests, AuthEndpointTests
- 가정/불변 조건: URL 네임은 auth-* 네임스페이스로 등록됨
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.urls import reverse

import api.account.services as account_services
from api.auth.services.oidc import _extract_user_info_from_claims, _upsert_user_from_claims


def _set_current_affiliation(user, *, user_sdwt_prod: str) -> None:
    """테스트 사용자의 현재 앱 소속을 설정합니다."""

    knox_id = getattr(user, "knox_id", None)
    if not knox_id:
        user.knox_id = f"KNOX-{user.sabun}"
        user.save(update_fields=["knox_id"])
        knox_id = user.knox_id

    option = account_services.ensure_affiliation_option(
        department="Dept",
        line="Line",
        user_sdwt_prod=user_sdwt_prod,
    )
    account_services.sync_external_affiliations(
        records=[
            {
                "knox_id": knox_id,
                "department": "Dept",
                "user_sdwt_prod": user_sdwt_prod,
                "source_updated_at": timezone.now(),
            }
        ]
    )
    payload, status_code = account_services.request_affiliation_change(
        user=user,
        option=option,
        to_user_sdwt_prod=user_sdwt_prod,
        effective_from=timezone.now(),
        timezone_name="Asia/Seoul",
    )
    if status_code != 200:
        raise AssertionError(payload)


class AuthMeTests(TestCase):
    """auth_me 응답의 인증/필드 구성을 검증합니다."""

    def test_auth_me_requires_login(self) -> None:
        """미인증 요청은 401을 반환해야 합니다."""
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "unauthorized"})

    def test_auth_me_returns_username_and_knox_id(self) -> None:
        """인증된 사용자의 username/knox_id/avatarid가 응답에 포함되어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(sabun="S12345", password="test-password")
        user.knox_id = "KNOX-12345"
        user.avatarid = "U-12345"
        user.username = "홍길동"
        user.first_name = "John"
        user.last_name = "Doe"
        user.email = "hong@example.com"
        user.department = "Engineering"
        user.save(
            update_fields=[
                "knox_id",
                "avatarid",
                "username",
                "first_name",
                "last_name",
                "email",
                "department",
            ]
        )

        self.client.force_login(user)

        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["usr_id"], "KNOX-12345")
        self.assertEqual(payload["avatarid"], "U-12345")
        self.assertEqual(payload["username"], "홍길동")
        self.assertNotIn("name", payload)
        self.assertEqual(payload["email"], "hong@example.com")
        self.assertEqual(payload["department"], "Engineering")
        self.assertFalse(payload["has_pending_affiliation"])

    def test_auth_me_includes_pending_user_sdwt_prod(self) -> None:
        """pending_user_sdwt_prod 값이 있을 때 응답에 포함되어야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/대기 변경 요청 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S12346", password="test-password")
        user.knox_id = "KNOX-12346"
        user.save(update_fields=["knox_id"])
        option = account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-pending",
        )
        approver = User.objects.create_user(sabun="S22346", password="test-password")
        _set_current_affiliation(approver, user_sdwt_prod="group-pending")
        account_services.ensure_self_access(approver, role="manager")
        payload, status_code = account_services.request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-pending",
            effective_from=timezone.now(),
            timezone_name="Asia/Seoul",
        )
        self.assertEqual(status_code, 202)
        self.assertIn("changeId", payload)

        # -----------------------------------------------------------------------------
        # 2) 로그인 및 API 호출
        # -----------------------------------------------------------------------------
        self.client.force_login(user)

        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        # -----------------------------------------------------------------------------
        # 3) 응답 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(payload["pending_user_sdwt_prod"], "group-pending")
        self.assertTrue(payload["has_pending_affiliation"])

    def test_auth_me_includes_pending_with_current_affiliation(self) -> None:
        """현재 소속이 있어도 pending_user_sdwt_prod 값이 포함되어야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/대기 변경 요청 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S12347", password="test-password")
        _set_current_affiliation(user, user_sdwt_prod="group-current")

        option = account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-next",
        )
        approver = User.objects.create_user(sabun="S22347", password="test-password")
        _set_current_affiliation(approver, user_sdwt_prod="group-next")
        account_services.ensure_self_access(approver, role="manager")
        payload, status_code = account_services.request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-next",
            effective_from=timezone.now(),
            timezone_name="Asia/Seoul",
        )
        self.assertEqual(status_code, 202)
        self.assertIn("changeId", payload)

        # -----------------------------------------------------------------------------
        # 2) 로그인 및 API 호출
        # -----------------------------------------------------------------------------
        self.client.force_login(user)

        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        # -----------------------------------------------------------------------------
        # 3) 응답 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(payload["pending_user_sdwt_prod"], "group-next")
        self.assertTrue(payload["has_pending_affiliation"])


class AuthEndpointTests(TestCase):
    """인증 엔드포인트의 기본 동작을 검증합니다."""

    @override_settings(OIDC_PROVIDER_CONFIGURED=False)
    def test_auth_login_returns_bad_request_when_not_configured(self) -> None:
        """OIDC 설정이 비활성화되면 login이 400을 반환해야 합니다."""
        response = self.client.get(reverse("auth-login"))
        self.assertEqual(response.status_code, 400)

    def test_auth_logout_returns_logout_url(self) -> None:
        """POST logout은 logoutUrl을 포함한 JSON을 반환해야 합니다."""
        response = self.client.post(reverse("auth-logout"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("logoutUrl", response.json())

    def test_auth_config_returns_fields(self) -> None:
        """auth_config 응답에 기본 필드가 포함되어야 합니다."""
        response = self.client.get(reverse("auth-config"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("clientId", payload)
        self.assertIn("loginUrl", payload)

    @override_settings(FRONTEND_BASE_URL="http://frontend.local")
    def test_frontend_redirect_uses_base_url(self) -> None:
        """프론트 리다이렉트는 설정된 베이스 URL을 사용해야 합니다."""
        response = self.client.get(reverse("frontend-redirect"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("http://frontend.local"))


class AuthOidcClaimMappingTests(TestCase):
    """OIDC 클레임 매핑 로직을 검증합니다."""

    def test_extract_user_info_maps_avatarid(self) -> None:
        """userid 클레임이 avatarid 필드로 매핑되어야 합니다."""
        claims = {
            "loginid": "KNOX-123",
            "sabun": "S12345",
            "username": "홍길동",
            "mail": "hong@example.com",
            "userid": "U-12345",
        }

        info = _extract_user_info_from_claims(claims)

        self.assertEqual(info.get("avatarid"), "U-12345")


class AuthOidcClaimExtractionTests(TestCase):
    """OIDC 클레임 파싱 로직을 검증합니다."""

    def test_extract_user_info_maps_loginid_to_knox_id(self) -> None:
        """loginid가 knox_id로 매핑되는지 확인합니다."""
        claims = {
            "loginid": "knox-user",
            "sabun": "12345",
            "username": "홍길동",
            "deptname": "Engineering",
            "mail": "user@example.com",
        }

        info = _extract_user_info_from_claims(claims)
        self.assertEqual(info["knox_id"], "knox-user")
        self.assertEqual(info["sabun"], "12345")
        self.assertEqual(info["department"], "Engineering")
        self.assertEqual(info["email"], "user@example.com")

    def test_extract_user_info_sets_korean_and_english_names(self) -> None:
        """한글/영문 이름 필드가 기대대로 채워지는지 확인합니다."""
        claims = {
            "loginid": "knox-user",
            "sabun": "12345",
            "username": "홍길동",
            "givenname": "John",
            "surname": "Doe",
        }

        info = _extract_user_info_from_claims(claims)
        self.assertEqual(info["first_name"], "길동")
        self.assertEqual(info["last_name"], "홍")
        self.assertEqual(info["givenname"], "John")
        self.assertEqual(info["surname"], "Doe")


class AuthOidcUserUpsertTests(TestCase):
    """OIDC 사용자 생성/갱신 로직을 검증합니다."""

    def test_upsert_user_from_claims_creates_user(self) -> None:
        """신규 사용자일 때 생성 및 필드 저장이 수행되어야 합니다."""
        info = {
            "sabun": "S99990",
            "knox_id": "KNOX-99990",
            "username": "홍길동",
            "email": "hong@example.com",
        }

        user, created = _upsert_user_from_claims(
            info=info,
            sabun="S99990",
            knox_id="KNOX-99990",
        )

        self.assertTrue(created)
        user.refresh_from_db()
        self.assertEqual(user.sabun, "S99990")
        self.assertEqual(user.knox_id, "KNOX-99990")
        self.assertEqual(user.email, "hong@example.com")

    def test_upsert_user_from_claims_saves_sso_department(self) -> None:
        """SSO department 값은 account_user.department에 저장되어야 합니다."""
        info = {
            "sabun": "S99992",
            "knox_id": "KNOX-99992",
            "department": "Engineering",
        }

        user, created = _upsert_user_from_claims(
            info=info,
            sabun="S99992",
            knox_id="KNOX-99992",
        )

        self.assertTrue(created)
        user.refresh_from_db()
        self.assertEqual(user.department, "Engineering")

    def test_upsert_user_from_claims_updates_existing_user(self) -> None:
        """기존 사용자의 변경 필드가 갱신되어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(sabun="S99991", password="test-password")
        user.knox_id = "KNOX-OLD"
        user.email = "old@example.com"
        user.save(update_fields=["knox_id", "email"])

        info = {
            "sabun": "S99991",
            "knox_id": "KNOX-NEW",
            "email": "new@example.com",
        }

        updated_user, created = _upsert_user_from_claims(
            info=info,
            sabun="S99991",
            knox_id="KNOX-NEW",
        )

        self.assertFalse(created)
        updated_user.refresh_from_db()
        self.assertEqual(updated_user.knox_id, "KNOX-NEW")
        self.assertEqual(updated_user.email, "new@example.com")
