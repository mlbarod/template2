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

import base64
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.urls import reverse

import api.account.services as account_services
from api.account.models import (
    ACCESS_SCOPE_PORTAL,
    AccessPolicyRule,
    AccessScope,
    UserAccess,
    UserCurrentAffiliation,
    UserSdwtProdAccess,
)
from api.auth.services.oidc import _extract_user_info_from_claims, _upsert_user_from_claims
from api.common.permissions import (
    is_portal_access_protected_path,
    resolve_api_route_access_policy,
    resolve_app_access_scope_for_path,
)


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


def _basic_auth_header(*, sabun: str, password: str) -> str:
    """테스트용 HTTP Basic Authorization 헤더 값을 생성합니다."""

    encoded = base64.b64encode(f"{sabun}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


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
        self.assertIn("portal_access", payload)
        self.assertIn("app_access", payload)
        self.assertEqual(len(payload["app_access"]), 12)
        self.assertFalse(payload["app_access"]["appstore"]["allowed"])
        self.assertFalse(payload["portal_access"]["allowed"])
        self.assertEqual(payload["portal_access"]["department"], "Engineering")

        scope, _created = AccessScope.objects.get_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={"name": "Portal", "scope_type": AccessScope.ScopeTypes.PORTAL},
        )
        AccessPolicyRule.objects.create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Engineering",
            is_active=True,
        )
        response = self.client.get(reverse("auth-me"))
        self.assertTrue(response.json()["portal_access"]["allowed"])

        appstore_scope = AccessScope.objects.get(key="appstore")
        UserAccess.objects.create(
            scope=appstore_scope,
            user=user,
            status=UserAccess.Status.ALLOWED,
            role="viewer",
        )
        response = self.client.get(reverse("auth-me"))
        appstore_access = response.json()["app_access"]["appstore"]
        self.assertTrue(appstore_access["allowed"])
        self.assertNotIn("role", appstore_access)
        self.assertNotIn("role", appstore_access["policy"])

    def test_auth_me_department_matches_user_department_for_access_policy(self) -> None:
        """현재 앱 소속 department가 달라도 auth 응답 department는 사용자 기준이어야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(sabun="S32345", password="test-password")
        user.knox_id = "KNOX-32345"
        user.department = "Engineering"
        user.email = "engineer@example.com"
        user.save(update_fields=["knox_id", "department", "email"])
        _set_current_affiliation(user, user_sdwt_prod="GROUP-X")

        self.client.force_login(user)
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["department"], "Engineering")
        self.assertEqual(payload["portal_access"]["department"], "Engineering")
        self.assertEqual(payload["user_sdwt_prod"], "GROUP-X")

    def test_auth_me_department_falls_back_to_current_affiliation(self) -> None:
        """사용자 부서가 공백이면 현재 앱 소속 부서를 auth 응답과 권한 판정에 사용해야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(sabun="S42345", password="test-password")
        user.knox_id = "KNOX-42345"
        user.department = "   "
        user.save(update_fields=["knox_id", "department"])
        _set_current_affiliation(user, user_sdwt_prod="GROUP-FALLBACK")

        self.client.force_login(user)
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["department"], "Dept")
        self.assertEqual(payload["portal_access"]["department"], "Dept")
        self.assertEqual(payload["user_sdwt_prod"], "GROUP-FALLBACK")

    def test_auth_me_does_not_auto_assign_dev_affiliation_without_flag(self) -> None:
        """dev 자동 소속 플래그가 없으면 소속 없는 사용자를 변경하지 않아야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(sabun="S52345", password="test-password")
        user.knox_id = "KNOX-52345"
        user.save(update_fields=["knox_id"])

        self.client.force_login(user)
        with patch.dict(
            "os.environ",
            {"ENVIRONMENT": "development"},
            clear=True,
        ):
            response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload["user_sdwt_prod"])
        self.assertFalse(UserCurrentAffiliation.objects.filter(user=user).exists())

    def test_auth_me_auto_assigns_dev_affiliation_when_enabled(self) -> None:
        """외부망 dev 자동 소속 플래그가 켜지면 기본 소속을 보장해야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(sabun="S52346", password="test-password")
        user.knox_id = "KNOX-52346"
        user.department = "Engineering"
        user.save(update_fields=["knox_id", "department"])

        self.client.force_login(user)
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DEV_AUTO_AFFILIATION_ALLOWED": "1",
                "DEV_AUTO_AFFILIATION_PREFIX": "TDEV",
            },
            clear=True,
        ):
            response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["department"], "Engineering")
        self.assertEqual(payload["line"], "TDEV-L1")
        self.assertEqual(payload["user_sdwt_prod"], "TDEV_ALPHA")

        current = UserCurrentAffiliation.objects.get(user=user)
        self.assertEqual(current.source, UserCurrentAffiliation.Sources.ADMIN_ASSIGNED)
        self.assertEqual(current.affiliation.user_sdwt_prod, "TDEV_ALPHA")
        self.assertTrue(
            UserSdwtProdAccess.objects.filter(
                user=user,
                affiliation=current.affiliation,
                role=UserSdwtProdAccess.Roles.MEMBER,
            ).exists()
        )

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


class PortalAccessEnforcementTests(TestCase):
    """middleware와 DRF 인증 방식별 포털 접근 강제를 검증합니다."""

    PASSWORD = "portal-test-password"

    def _create_user(self, *, sabun: str, department: str):
        """포털 접근 회귀 테스트용 사용자를 생성합니다."""

        User = get_user_model()
        return User.objects.create_user(
            sabun=sabun,
            password=self.PASSWORD,
            knox_id=f"KNOX-{sabun}",
            department=department,
        )

    def _basic_credentials(self, *, user) -> dict[str, str]:
        """Django test client에 전달할 Basic 인증 헤더를 반환합니다."""

        return {
            "HTTP_AUTHORIZATION": _basic_auth_header(
                sabun=user.sabun,
                password=self.PASSWORD,
            )
        }

    def _allow_department(self, *, department: str) -> None:
        """테스트 부서에 portal 접근 정책을 부여합니다."""

        scope, _created = AccessScope.objects.get_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={"name": "Portal", "scope_type": AccessScope.ScopeTypes.PORTAL},
        )
        AccessPolicyRule.objects.update_or_create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value=department,
            defaults={"is_active": True},
        )

    def test_anonymous_default_drf_view_requires_portal_authentication(self) -> None:
        """기본 permission을 쓰는 보호 GET은 익명 요청을 허용하지 않아야 합니다."""

        response = self.client.get(reverse("observer-lines"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "unauthorized"})

    def test_blocked_basic_user_cannot_access_default_protected_view(self) -> None:
        """미승인 Basic 사용자는 기본 보호 API를 우회할 수 없어야 합니다."""

        user = self._create_user(sabun="BASIC-BLOCKED", department="Blocked Department")

        response = self.client.get(
            reverse("account-overview"),
            **self._basic_credentials(user=user),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "portal_access_required")
        self.assertFalse(response.json()["portalAccess"]["allowed"])

    def test_allowed_basic_user_can_access_default_protected_view(self) -> None:
        """정책 승인된 Basic 사용자는 기본 보호 API를 사용할 수 있어야 합니다."""

        department = "Allowed Basic Department"
        user = self._create_user(sabun="BASIC-ALLOWED", department=department)
        self._allow_department(department=department)

        response = self.client.get(
            reverse("account-overview"),
            **self._basic_credentials(user=user),
        )

        self.assertEqual(response.status_code, 200)

    def test_app_api_requires_selected_app_scope_after_portal_access(self) -> None:
        """포털 승인만으로 앱 전용 API를 사용할 수 없어야 합니다."""

        department = "App Scope Department"
        user = self._create_user(sabun="APP-SCOPE-BLOCKED", department=department)
        self._allow_department(department=department)

        response = self.client.get(
            reverse("appstore-apps"),
            **self._basic_credentials(user=user),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "app_access_required")
        self.assertEqual(response.json()["scope"], "appstore")

    def test_app_api_allows_selected_app_scope(self) -> None:
        """포털과 앱 권한이 모두 허용된 사용자는 앱 API를 사용할 수 있어야 합니다."""

        department = "App Scope Allowed Department"
        user = self._create_user(sabun="APP-SCOPE-ALLOWED", department=department)
        self._allow_department(department=department)
        UserAccess.objects.create(
            scope=AccessScope.objects.get(key="appstore"),
            user=user,
            status=UserAccess.Status.ALLOWED,
            role="viewer",
        )

        response = self.client.get(
            reverse("appstore-apps"),
            **self._basic_credentials(user=user),
        )

        self.assertEqual(response.status_code, 200)

    def test_global_app_access_event_does_not_require_access_stats_scope(self) -> None:
        """전역 앱 접속 기록은 access-stats 조회 권한 없이도 저장할 수 있어야 합니다."""

        department = "Activity Event Department"
        user = self._create_user(sabun="ACTIVITY-EVENT", department=department)
        self._allow_department(department=department)

        response = self.client.post(
            reverse("activity-app-access"),
            data='{"appId":"home","appName":"Portal Home","path":"/"}',
            content_type="application/json",
            **self._basic_credentials(user=user),
        )

        self.assertEqual(response.status_code, 201)

    def test_app_api_path_mapping_covers_internal_app_endpoints(self) -> None:
        """내부 앱 API 경로가 올바른 app scope로 매핑되어야 합니다."""

        cases = {
            "/api/v1/appstore/apps": "appstore",
            "/api/v1/line-dashboard/summary": "line-dashboard",
            "/api/v1/l3_spider/meta": "l3-spider",
            "/api/v1/pm_spider/meta": "pm-spider",
            "/api/v1/assistant/chat": "assistant",
            "/api/v1/observer/lines": "observer",
            "/api/v1/emails/inbox/": "emails",
            "/api/v1/fdc-trend/hard-spec/meta": "fdc-trend",
            "/api/v1/voc/posts": "voc",
            "/api/v1/activity/app-access-stats": "access-stats",
        }
        for path, expected_scope in cases.items():
            with self.subTest(path=path):
                self.assertEqual(resolve_app_access_scope_for_path(path), expected_scope)

        self.assertIsNone(resolve_app_access_scope_for_path("/api/v1/activity/app-access"))

    def test_api_route_registry_drives_runtime_access_policy(self) -> None:
        """루트 registry와 하위 override가 런타임 권한 판정의 단일 기준이어야 합니다."""

        cases = {
            "/api/v1/auth/me": "public",
            "/api/v1/data-movement/m_tkin_prevent/load": "token",
            "/api/v1/account/overview": "portal",
            "/api/v1/appstore/apps": "app:appstore",
            "/api/v1/activity/app-access": "portal",
            "/api/v1/activity/app-access-stats": "app:access-stats",
        }
        for path, expected_policy in cases.items():
            with self.subTest(path=path):
                self.assertEqual(resolve_api_route_access_policy(path), expected_policy)

        self.assertIsNone(resolve_api_route_access_policy("/api/v1/unknown/items"))
        self.assertFalse(is_portal_access_protected_path("/api/v1/data-movement/jobs"))
        self.assertTrue(is_portal_access_protected_path("/api/v1/appstore/apps"))
        self.assertTrue(is_portal_access_protected_path("/api/v1/unknown/items"))

    def test_basic_user_without_knox_id_cannot_bypass_middleware_requirement(self) -> None:
        """Basic 인증도 보호 경로에서 비어 있는 knox_id를 허용하지 않아야 합니다."""

        department = "Basic Missing Knox Department"
        User = get_user_model()
        user = User.objects.create_user(
            sabun="BASIC-NO-KNOX",
            password=self.PASSWORD,
            department=department,
        )
        self._allow_department(department=department)

        response = self.client.get(
            reverse("account-overview"),
            **self._basic_credentials(user=user),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "knox_id is required"})

    def test_blocked_basic_user_cannot_bypass_explicit_is_authenticated_view(self) -> None:
        """명시적 IsAuthenticated view도 미승인 Basic 사용자를 차단해야 합니다."""

        user = self._create_user(sabun="BASIC-EXPLICIT", department="Blocked Department")

        response = self.client.get(
            reverse("fdc-trend-hard-spec-meta"),
            **self._basic_credentials(user=user),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "portal_access_required")

    def test_blocked_basic_user_can_query_portal_access_exception(self) -> None:
        """미승인 Basic 사용자는 예외 경로에서 자신의 포털 상태를 조회할 수 있어야 합니다."""

        user = self._create_user(sabun="BASIC-STATUS", department="Blocked Department")

        response = self.client.get(
            reverse("account-portal-access"),
            **self._basic_credentials(user=user),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["portalAccess"]["allowed"])


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
