# =============================================================================
# 모듈 설명: account 도메인 서비스/셀렉터/엔드포인트 테스트를 제공합니다.
# - 주요 대상: 소속 변경, 접근 권한, 외부 동기화, 개요 응답
# - 불변 조건: 테스트는 등록된 URL 네임을 기준으로 수행합니다.
# =============================================================================

"""계정 도메인 서비스/셀렉터/엔드포인트 테스트 모음.

- 주요 대상: 소속 변경, 접근 권한, 외부 동기화, 개요 응답
- 주요 엔드포인트/클래스: AccountEndpointTests 등
- 가정/불변 조건: 테스트는 기본 URL 네임이 등록되어 있음
"""
from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from io import StringIO
from unittest.mock import patch

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from api.account.models import (
    ACCESS_MANAGERS_GROUP_NAME,
    ACCESS_SCOPE_PORTAL,
    MANAGE_ACCESS_PERMISSION,
    AccessAuditLog,
    AccessPolicyRule,
    AccessScope,
    AccessSource,
    Affiliation,
    ExternalAffiliationSnapshot,
    UserAccess,
    UserCurrentAffiliation,
    UserProfile,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)
from api.account.selectors import (
    get_accessible_user_sdwt_prods_for_user,
    get_current_user_sdwt_prod,
    get_next_user_sdwt_prod_change,
    list_active_user_emails_by_user_sdwt_prod,
    list_active_user_knox_ids_by_user_sdwt_prod,
    list_affiliation_options,
    list_line_sdwt_pairs,
    resolve_user_affiliation,
)
from api.account.services import (
    approve_affiliation_change,
    auto_approve_affiliation_from_snapshot,
    create_access_policy_rule,
    decide_access,
    delete_access_policy_rule,
    ensure_self_access,
    ensure_user_profile,
    get_account_overview,
    get_access_payload,
    get_affiliation_change_requests,
    get_affiliation_overview,
    get_portal_access_payload,
    can_manage_access,
    request_affiliation_change,
    request_access,
    request_portal_access,
    submit_affiliation_reconfirm_response,
    sync_external_affiliations,
    update_access_policy_rule,
)


def _affiliation(*, department: str = "Dept", line: str = "Line", user_sdwt_prod: str) -> Affiliation:
    """테스트용 소속 옵션을 중복 없이 준비합니다."""
    option = Affiliation.objects.filter(user_sdwt_prod__iexact=user_sdwt_prod).order_by("id").first()
    if option is not None:
        option.department = department
        option.line = line
        option.save(update_fields=["department", "line"])
        return option
    return Affiliation.objects.create(
        department=department,
        line=line,
        user_sdwt_prod=user_sdwt_prod,
    )


def _set_current_affiliation(
    user,
    *,
    user_sdwt_prod: str,
    department: str = "Dept",
    line: str = "Line",
    requires_reconfirm: bool = False,
    confirmed_at=None,
    source: str = UserCurrentAffiliation.Sources.USER_SELECTED,
) -> UserCurrentAffiliation:
    """테스트 사용자의 현재 앱 소속을 명시적으로 설정합니다."""

    option = _affiliation(department=department, line=line, user_sdwt_prod=user_sdwt_prod)
    row, _created = UserCurrentAffiliation.objects.update_or_create(
        user=user,
        defaults={
            "affiliation": option,
            "source": source,
            "requires_reconfirm": requires_reconfirm,
            "confirmed_at": confirmed_at,
        },
    )
    return row


def _grant_access(
    *,
    user,
    user_sdwt_prod: str,
    role: str,
    department: str = "Dept",
    line: str = "Line",
    granted_by=None,
) -> UserSdwtProdAccess:
    """테스트용 소속 접근 권한을 생성합니다."""

    option = _affiliation(department=department, line=line, user_sdwt_prod=user_sdwt_prod)
    return UserSdwtProdAccess.objects.create(
        user=user,
        affiliation=option,
        role=role,
        granted_by=granted_by,
    )


def _clear_permission_cache(user) -> None:
    """사용자 인스턴스의 Django permission 캐시를 제거합니다."""

    for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, cache_name):
            delattr(user, cache_name)


def _grant_manage_access(user):
    """테스트 사용자에게 접근 권한 관리 capability를 부여합니다."""

    group = Group.objects.get(name=ACCESS_MANAGERS_GROUP_NAME)
    app_label, codename = MANAGE_ACCESS_PERMISSION.split(".", maxsplit=1)
    permission = Permission.objects.get(
        content_type__app_label=app_label,
        codename=codename,
    )
    group.permissions.add(permission)
    user.groups.add(group)
    _clear_permission_cache(user)
    return user


class AccountConfigDefaultUserTests(TestCase):
    """account 앱의 migrate 후 기본 사용자 보장 로직을 검증합니다."""

    def test_ensure_default_superuser_promotes_existing_dev_dummy_user(self) -> None:
        """기존 dev dummy 사용자는 migrate 보정 시 staff 슈퍼유저가 되어야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S-DUMMY-EXISTING",
            password="test-password",
            knox_id="dummy.existing",
            email="old@example.com",
        )

        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DUMMY_ADFS_SABUN": "S-DUMMY-EXISTING",
                "DUMMY_ADFS_LOGINID": "dummy.existing",
                "DUMMY_ADFS_EMAIL": "dummy.existing@example.com",
                "DUMMY_ADFS_NAME": "Dummy Existing",
                "DUMMY_ADFS_DEPT": "Development",
            },
            clear=True,
        ):
            django_apps.get_app_config("account")._ensure_default_superuser()

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "dummy.existing@example.com")
        self.assertEqual(user.username, "Dummy Existing")
        self.assertEqual(user.department, "Development")

    def test_ensure_default_superuser_creates_dev_dummy_superuser(self) -> None:
        """dev dummy 사용자가 없으면 migrate 보정 시 슈퍼유저로 생성해야 합니다."""

        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DUMMY_ADFS_SABUN": "S-DUMMY-NEW",
                "DUMMY_ADFS_LOGINID": "dummy.new",
                "DUMMY_ADFS_EMAIL": "dummy.new@example.com",
                "DUMMY_ADFS_NAME": "Dummy New",
                "DUMMY_ADFS_DEPT": "Development",
                "DJANGO_SUPERUSER_PASSWORD": "test-password",
            },
            clear=True,
        ):
            django_apps.get_app_config("account")._ensure_default_superuser()

        User = get_user_model()
        user = User.objects.get(sabun="S-DUMMY-NEW")
        self.assertEqual(user.knox_id, "dummy.new")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "dummy.new@example.com")
        self.assertTrue(user.check_password("test-password"))

    def test_ensure_default_superuser_does_not_promote_dummy_outside_development(self) -> None:
        """development 환경이 아니면 dummy 사용자를 보정하지 않아야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S-DUMMY-OIDC",
            password="test-password",
            knox_id="dummy.oidc",
            email="old@example.com",
        )

        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "production",
                "DUMMY_ADFS_SABUN": "S-DUMMY-OIDC",
                "DUMMY_ADFS_LOGINID": "dummy.oidc",
                "DUMMY_ADFS_EMAIL": "dummy.oidc@example.com",
            },
            clear=True,
        ):
            django_apps.get_app_config("account")._ensure_default_superuser()

        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.email, "old@example.com")


class AccountEndpointTests(TestCase):
    """계정 관련 엔드포인트의 기본 흐름을 검증합니다."""

    def setUp(self) -> None:
        """테스트에 필요한 사용자/권한/소속 데이터를 준비합니다."""
        # -----------------------------------------------------------------------------
        # 1) 기본 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        self.user = User.objects.create_user(sabun="S50000", password="test-password")
        self.user.knox_id = "knox-50000"
        self.user.department = "Dept"
        self.user.save(update_fields=["knox_id", "department"])
        scope, _created = AccessScope.objects.get_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={"name": "Portal", "scope_type": AccessScope.ScopeTypes.PORTAL},
        )
        AccessPolicyRule.objects.update_or_create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Dept",
            defaults={"is_active": True},
        )
        _set_current_affiliation(
            self.user,
            department="Dept",
            line="L1",
            user_sdwt_prod="group-a",
        )

        # -----------------------------------------------------------------------------
        # 2) 매니저/접근 권한 준비
        # -----------------------------------------------------------------------------
        self.manager = User.objects.create_user(
            sabun="S50001",
            password="test-password",
            knox_id="knox-50001",
            department="Dept",
        )
        _set_current_affiliation(self.manager, user_sdwt_prod="group-b")
        _grant_access(user=self.manager, user_sdwt_prod="group-a", role="manager")
        _grant_access(user=self.manager, user_sdwt_prod="group-b", role="manager")

        # -----------------------------------------------------------------------------
        # 3) 슈퍼유저/소속 옵션 준비
        # -----------------------------------------------------------------------------
        self.superuser = User.objects.create_superuser(
            sabun="S50002",
            password="test-password",
            knox_id="knox-50002",
        )

        _affiliation(department="Dept", line="L1", user_sdwt_prod="group-a")
        _affiliation(department="Dept", line="L1", user_sdwt_prod="group-b")

    def test_default_app_access_scopes_are_seeded(self) -> None:
        """포털 내부 앱의 기본 접근 scope와 공통 속성을 검증합니다."""

        expected_scopes = {
            "access-stats": "접속 현황",
            "appstore": "Appstore",
            "assistant": "Assistant",
            "emails": "Emails",
            "l0-spider": "L0 Spider",
            "l1-spider": "L1 Spider",
            "l3-spider": "L3 Spider",
            "line-dashboard": "ESOP Dashboard",
            "observer": "Observer",
            "pm-spider": "PM Spider",
            "teamstaff": "Teamstaff",
            "tttm-spider": "TTTM Spider",
            "voc": "VoE",
        }
        scopes = AccessScope.objects.filter(scope_type=AccessScope.ScopeTypes.APP).order_by("key")

        self.assertEqual({scope.key: scope.name for scope in scopes}, expected_scopes)
        for scope in scopes:
            with self.subTest(scope=scope.key):
                self.assertTrue(scope.is_active)
                self.assertFalse(scope.requestable)
                self.assertEqual(scope.default_role, "viewer")

    def test_new_user_does_not_receive_automatic_app_access(self) -> None:
        """마이그레이션 이후 생성된 신규 사용자는 앱 허용 행을 자동 생성하지 않아야 합니다."""

        User = get_user_model()
        new_user = User.objects.create_user(
            sabun="S-NEW-ACCESS",
            password="test-password",
            department="New Department",
        )

        self.assertFalse(
            UserAccess.objects.filter(
                user=new_user,
                scope__scope_type=AccessScope.ScopeTypes.APP,
            ).exists()
        )
        payload = get_access_payload(user=new_user, scope_key="appstore")
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["source"], AccessSource.PORTAL_ACCESS_REQUIRED)
        self.assertTrue(payload["blockedByPortal"])
        self.assertEqual(payload["underlyingAccess"]["source"], AccessSource.NONE)

    def test_access_permissions_migration_preserves_decisions_and_backfills_existing_users(self) -> None:
        """순방향 권한 migration은 기존 결정을 보존하고 기존 사용자의 누락 앱을 허용해야 합니다."""

        User = get_user_model()
        inactive_user = User.objects.create_user(
            sabun="S-INACTIVE-ACCESS",
            password="test-password",
            is_active=False,
        )
        appstore_scope = AccessScope.objects.get(key="appstore")
        UserAccess.objects.create(
            scope=appstore_scope,
            user=self.user,
            status=UserAccess.Status.DENIED,
            role="viewer",
            reason="기존 수동 차단 유지",
        )
        migration = import_module("api.account.migrations.0002_access_permissions")

        migration._backfill_existing_user_app_access(django_apps)

        app_scope_count = AccessScope.objects.filter(scope_type=AccessScope.ScopeTypes.APP).count()
        self.assertEqual(
            UserAccess.objects.filter(user=self.user, scope__scope_type=AccessScope.ScopeTypes.APP).count(),
            app_scope_count,
        )
        self.assertEqual(
            UserAccess.objects.filter(
                user=inactive_user,
                scope__scope_type=AccessScope.ScopeTypes.APP,
            ).count(),
            app_scope_count,
        )
        preserved = UserAccess.objects.get(user=self.user, scope=appstore_scope)
        self.assertEqual(preserved.status, UserAccess.Status.DENIED)
        self.assertEqual(preserved.reason, "기존 수동 차단 유지")

    def test_app_scope_is_not_self_requestable(self) -> None:
        """앱 권한은 self-service 요청 대신 권한 관리자가 직접 결정해야 합니다."""

        payload, status_code = request_access(user=self.user, scope_key="appstore")

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "not_requestable")
        self.assertFalse(UserAccess.objects.filter(user=self.user, scope__key="appstore").exists())

    def test_access_permissions_migration_moves_existing_managers_to_standard_group(self) -> None:
        """순방향 권한 migration은 기존 관리자와 직접 permission 보유자를 표준 그룹으로 이전해야 합니다."""

        permission = Permission.objects.get(
            content_type__app_label="account",
            codename="manage_access",
        )
        group = Group.objects.get(name=ACCESS_MANAGERS_GROUP_NAME)
        self.manager.groups.remove(group)
        self.manager.user_permissions.add(permission)
        UserProfile.objects.filter(user=self.manager).update(role=UserProfile.Roles.ADMIN)
        _clear_permission_cache(self.manager)
        migration = import_module("api.account.migrations.0002_access_permissions")

        migration._migrate_access_managers(django_apps)

        _clear_permission_cache(self.manager)
        self.assertTrue(self.manager.groups.filter(id=group.id).exists())
        self.assertFalse(self.manager.user_permissions.filter(id=permission.id).exists())
        self.assertTrue(self.manager.has_perm("account.manage_access"))

    def test_spider_scope_migration_preserves_l0_decisions_and_backfills_l1(self) -> None:
        """Spider scope 순방향 migration은 기존 L0 결정을 보존하고 L1 권한을 승계해야 합니다."""

        User = get_user_model()
        inactive_user = User.objects.create_user(
            sabun="S-SPIDER-INACTIVE",
            password="test-password",
            is_active=False,
        )
        legacy_scope = AccessScope.objects.get(key="l0-spider")
        legacy_scope.key = "fdc-trend"
        legacy_scope.name = "FDC Trend"
        legacy_scope.save(update_fields=["key", "name"])
        AccessScope.objects.filter(key="l1-spider").delete()
        denied_access = UserAccess.objects.create(
            scope=legacy_scope,
            user=self.user,
            status=UserAccess.Status.DENIED,
            role="viewer",
            reason="기존 L0 차단 유지",
        )
        migration = import_module("api.account.migrations.0003_spider_access_scopes")

        migration.migrate_spider_access_scopes(django_apps, None)

        migrated_scope = AccessScope.objects.get(key="l0-spider")
        self.assertEqual(migrated_scope.id, legacy_scope.id)
        self.assertEqual(migrated_scope.name, "L0 Spider")
        self.assertFalse(AccessScope.objects.filter(key="fdc-trend").exists())
        denied_access.refresh_from_db()
        self.assertEqual(denied_access.scope_id, migrated_scope.id)
        self.assertEqual(denied_access.status, UserAccess.Status.DENIED)
        self.assertEqual(denied_access.reason, "기존 L0 차단 유지")

        l1_scope = AccessScope.objects.get(key="l1-spider")
        inherited_rows = UserAccess.objects.filter(scope=l1_scope)
        self.assertEqual(
            set(inherited_rows.values_list("user_id", flat=True)),
            set(User.objects.values_list("id", flat=True)),
        )
        self.assertFalse(inherited_rows.exclude(status=UserAccess.Status.ALLOWED, role="viewer").exists())
        self.assertTrue(inherited_rows.filter(user=inactive_user).exists())

        migration.restore_legacy_fdc_scope(django_apps, None)
        restored_scope = AccessScope.objects.get(key="fdc-trend")
        self.assertEqual(restored_scope.id, legacy_scope.id)
        self.assertEqual(restored_scope.name, "FDC Trend")
        self.assertTrue(AccessScope.objects.filter(key="l1-spider").exists())

    def test_access_source_contract_uses_explicit_stable_values(self) -> None:
        """접근 판정 source 값은 API 계약에 사용하는 명시적 목록으로 고정되어야 합니다."""

        self.assertEqual(
            set(AccessSource.values),
            {
                "superuser_bypass",
                "portal_access_required",
                "scope_inactive",
                "explicit_denied",
                "explicit_allowed",
                "explicit_pending",
                "policy_department",
                "none",
                "scope_not_found",
            },
        )

    def test_app_scope_models_reject_non_viewer_roles(self) -> None:
        """앱 scope 관련 모델은 호환 필드에 viewer 외 role을 허용하지 않아야 합니다."""

        scope = AccessScope.objects.get(key="appstore")
        scope.default_role = "manager"
        policy = AccessPolicyRule(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Role Validation Dept",
            role="manager",
        )
        access = UserAccess(
            scope=scope,
            user=self.user,
            status=UserAccess.Status.ALLOWED,
            role="manager",
        )

        with self.assertRaises(ValidationError):
            scope.full_clean()
        with self.assertRaises(ValidationError):
            policy.full_clean()
        with self.assertRaises(ValidationError):
            access.full_clean()

        requestable_scope = AccessScope(
            key="requestable-app",
            name="Requestable App",
            scope_type=AccessScope.ScopeTypes.APP,
            requestable=True,
        )
        with self.assertRaises(ValidationError):
            requestable_scope.full_clean()

    def test_user_access_database_rejects_unknown_status(self) -> None:
        """UserAccess status는 DB에서도 pending/allowed/denied 외 값을 거부해야 합니다."""

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserAccess.objects.create(
                    scope=AccessScope.objects.get(key="appstore"),
                    user=self.user,
                    status="unknown",
                )

    def test_account_admin_blocks_non_superuser_privilege_escalation(self) -> None:
        """일반 staff는 민감 권한 필드와 privileged user를 변경하지 못해야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccountUserAdmin

        User = get_user_model()
        staff_user = self.manager
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        staff_user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="account",
                codename__in=("change_user", "delete_user"),
            )
        )
        _clear_permission_cache(staff_user)
        request = RequestFactory().get("/admin/account/user/")
        request.user = staff_user
        user_admin = AccountUserAdmin(User, AdminSite())

        readonly_fields = set(user_admin.get_readonly_fields(request, self.user))
        self.assertTrue({"is_staff", "is_superuser", "groups", "user_permissions"} <= readonly_fields)
        self.assertTrue(user_admin.has_change_permission(request, self.user))
        self.assertTrue(user_admin.has_delete_permission(request, self.user))

        _grant_manage_access(self.user)

        self.assertFalse(user_admin.has_change_permission(request, self.user))
        self.assertFalse(user_admin.has_delete_permission(request, self.user))
        self.assertFalse(user_admin.has_change_permission(request, self.superuser))

        superuser_request = RequestFactory().get("/admin/account/user/")
        superuser_request.user = self.superuser
        superuser_readonly_fields = set(user_admin.get_readonly_fields(superuser_request, self.user))
        self.assertFalse(
            {"is_staff", "is_superuser", "groups", "user_permissions"}
            & superuser_readonly_fields
        )
        self.assertTrue(user_admin.has_change_permission(superuser_request, self.user))

    def test_group_admin_is_superuser_only_and_protects_access_managers(self) -> None:
        """Django Group 변경은 superuser 전용이며 표준 권한 관리자 그룹은 불변이어야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccountGroupAdmin

        staff_user = self.manager
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        staff_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="auth",
                codename="change_group",
            )
        )
        _clear_permission_cache(staff_user)
        group_admin = AccountGroupAdmin(Group, AdminSite())
        standard_group = Group.objects.get(name=ACCESS_MANAGERS_GROUP_NAME)
        other_group = Group.objects.create(name="Other Operators")
        staff_request = RequestFactory().get("/admin/auth/group/")
        staff_request.user = staff_user
        superuser_request = RequestFactory().get("/admin/auth/group/")
        superuser_request.user = self.superuser

        self.assertFalse(group_admin.has_add_permission(staff_request))
        self.assertFalse(group_admin.has_change_permission(staff_request, other_group))
        self.assertFalse(group_admin.has_delete_permission(staff_request, other_group))
        self.assertTrue(group_admin.has_add_permission(superuser_request))
        self.assertTrue(group_admin.has_change_permission(superuser_request, other_group))
        self.assertFalse(group_admin.has_change_permission(superuser_request, standard_group))
        self.assertFalse(group_admin.has_delete_permission(superuser_request, standard_group))

    def test_access_model_admin_writes_require_superuser(self) -> None:
        """scope, 정책, 사용자 접근 row의 Django Admin 쓰기는 superuser만 가능해야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccessPolicyRuleAdmin, AccessScopeAdmin, UserAccessAdmin

        staff_user = self.manager
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        staff_user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="account",
                codename__in=(
                    "add_accessscope",
                    "change_accessscope",
                    "delete_accessscope",
                    "add_accesspolicyrule",
                    "change_accesspolicyrule",
                    "delete_accesspolicyrule",
                    "add_useraccess",
                    "change_useraccess",
                    "delete_useraccess",
                ),
            )
        )
        _clear_permission_cache(staff_user)
        scope = AccessScope.objects.get(key="appstore")
        policy = AccessPolicyRule.objects.create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Admin Security Dept",
            role="viewer",
        )
        access = UserAccess.objects.create(
            scope=scope,
            user=self.user,
            status=UserAccess.Status.ALLOWED,
            role="viewer",
        )
        site = AdminSite()
        admin_objects = (
            (AccessScopeAdmin(AccessScope, site), scope),
            (AccessPolicyRuleAdmin(AccessPolicyRule, site), policy),
            (UserAccessAdmin(UserAccess, site), access),
        )
        staff_request = RequestFactory().get("/admin/account/")
        staff_request.user = staff_user
        superuser_request = RequestFactory().get("/admin/account/")
        superuser_request.user = self.superuser

        for model_admin, obj in admin_objects:
            with self.subTest(model=obj._meta.label_lower):
                self.assertFalse(model_admin.has_add_permission(staff_request))
                self.assertFalse(model_admin.has_change_permission(staff_request, obj))
                self.assertFalse(model_admin.has_delete_permission(staff_request, obj))
                self.assertTrue(model_admin.has_add_permission(superuser_request))
                self.assertTrue(model_admin.has_change_permission(superuser_request, obj))
                expected_delete = not isinstance(model_admin, AccessScopeAdmin)
                self.assertEqual(model_admin.has_delete_permission(superuser_request, obj), expected_delete)

    def test_account_admin_audits_manage_access_capability_changes(self) -> None:
        """Django Admin의 capability 부여와 회수는 account 감사 로그에 남아야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccountUserAdmin

        class GroupMembershipForm:
            """Admin save_related 호출을 위한 최소 M2M 테스트 폼입니다."""

            def __init__(self, *, instance, group, add: bool):
                self.instance = instance
                self.group = group
                self.add = add
                self.cleaned_data = {}

            def save_m2m(self):
                """테스트 대상 그룹 멤버십을 추가하거나 제거합니다."""

                if self.add:
                    self.instance.groups.add(self.group)
                else:
                    self.instance.groups.remove(self.group)

        User = get_user_model()
        group = Group.objects.get(name=ACCESS_MANAGERS_GROUP_NAME)
        user_admin = AccountUserAdmin(User, AdminSite())

        grant_request = RequestFactory().post("/admin/account/user/")
        grant_request.user = self.superuser
        grant_form = GroupMembershipForm(instance=self.user, group=group, add=True)
        user_admin.save_model(grant_request, self.user, grant_form, True)
        user_admin.save_related(grant_request, grant_form, [], True)

        grant_log = AccessAuditLog.objects.get(
            target_user=self.user,
            action=AccessAuditLog.Actions.ACCESS_MANAGER_GRANT,
        )
        self.assertEqual(grant_log.actor, self.superuser)
        self.assertEqual(grant_log.before, {"canManageAccess": False})
        self.assertEqual(grant_log.after, {"canManageAccess": True})

        revoke_request = RequestFactory().post("/admin/account/user/")
        revoke_request.user = self.superuser
        revoke_form = GroupMembershipForm(instance=self.user, group=group, add=False)
        user_admin.save_model(revoke_request, self.user, revoke_form, True)
        user_admin.save_related(revoke_request, revoke_form, [], True)

        revoke_log = AccessAuditLog.objects.get(
            target_user=self.user,
            action=AccessAuditLog.Actions.ACCESS_MANAGER_REVOKE,
        )
        self.assertEqual(revoke_log.actor, self.superuser)
        self.assertEqual(revoke_log.before, {"canManageAccess": True})
        self.assertEqual(revoke_log.after, {"canManageAccess": False})

    def test_account_overview_and_affiliation_endpoints(self) -> None:
        """개요/소속/옵션 엔드포인트가 정상 응답하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 로그인
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)

        # -----------------------------------------------------------------------------
        # 2) 개요 조회 및 검증
        # -----------------------------------------------------------------------------
        overview = self.client.get(reverse("account-overview"))
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["user"]["userSdwtProd"], "group-a")

        # -----------------------------------------------------------------------------
        # 3) 소속 조회 및 검증
        # -----------------------------------------------------------------------------
        affiliation = self.client.get(reverse("account-affiliation"))
        self.assertEqual(affiliation.status_code, 200)

        # -----------------------------------------------------------------------------
        # 4) 옵션 조회 및 검증
        # -----------------------------------------------------------------------------
        options = self.client.get(reverse("account-line-sdwt-options"))
        self.assertEqual(options.status_code, 200)
        self.assertIn("lines", options.json())

    def test_onboarding_affiliation_post_auto_applies_external_match(self) -> None:
        """신규 사용자가 외부 예측 소속과 같은 값을 선택하면 즉시 적용되는지 확인합니다."""

        User = get_user_model()
        onboarding_user = User.objects.create_user(
            sabun="S50009",
            password="test-password",
            knox_id="knox-50009",
        )
        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50009",
            department="Dept",
            predicted_user_sdwt_prod="GROUP-B",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        self.client.force_login(onboarding_user)
        response = self.client.post(
            reverse("account-affiliation"),
            data='{"department":"Dept","line":"L1","userSdwtProd":"group-b"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "applied")
        self.assertEqual(get_current_user_sdwt_prod(user=onboarding_user), "group-b")
        change = UserSdwtProdChange.objects.get(user=onboarding_user)
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)

    def test_account_user_pool_requires_authentication(self) -> None:
        """사용자 pool 조회는 인증된 사용자에게만 허용되어야 합니다."""

        response = self.client.get(reverse("account-users"))

        self.assertEqual(response.status_code, 401)

    def test_account_user_pool_filters_by_search_and_group(self) -> None:
        """사용자 pool 조회가 검색어와 user_sdwt_prod 필터를 적용하는지 확인합니다."""

        User = get_user_model()
        searched_user = User.objects.create_user(
            sabun="S50003",
            password="test-password",
            knox_id="knox-50003",
            email="searched@example.com",
            username="검색대상",
        )
        _set_current_affiliation(searched_user, user_sdwt_prod="group-a")
        group_user = User.objects.create_user(
            sabun="S50004",
            password="test-password",
            knox_id="knox-50004",
            email="group@example.com",
            username="그룹대상",
        )
        _set_current_affiliation(group_user, user_sdwt_prod="group-b")

        self.client.force_login(self.user)
        search_response = self.client.get(reverse("account-users"), {"search": "검색대상"})
        group_response = self.client.get(reverse("account-users"), {"userSdwtProd": "group-b"})

        self.assertEqual(search_response.status_code, 200)
        search_ids = {row["id"] for row in search_response.json()["results"]}
        self.assertIn(searched_user.id, search_ids)
        self.assertNotIn(group_user.id, search_ids)

        self.assertEqual(group_response.status_code, 200)
        group_ids = {row["id"] for row in group_response.json()["results"]}
        self.assertIn(group_user.id, group_ids)
        self.assertNotIn(searched_user.id, group_ids)

    def test_account_user_pool_filters_by_contact_field(self) -> None:
        """사용자 pool 조회가 요청한 연락처 보유 사용자만 반환하는지 확인합니다."""

        User = get_user_model()
        email_user = User.objects.create_user(
            sabun="S50006",
            password="test-password",
            knox_id="knox-50006",
            email="with-email@example.com",
            username="메일있음",
        )
        _set_current_affiliation(email_user, user_sdwt_prod="group-a")
        no_email_user = User.objects.create_user(
            sabun="S50007",
            password="test-password",
            knox_id="knox-50007",
            username="메일없음",
        )
        _set_current_affiliation(no_email_user, user_sdwt_prod="group-a")

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("account-users"),
            {"userSdwtProd": "group-a", "contactField": "email", "limit": "all"},
        )

        self.assertEqual(response.status_code, 200)
        user_ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(email_user.id, user_ids)
        self.assertNotIn(no_email_user.id, user_ids)

    def test_account_user_pool_can_include_external_snapshot_users(self) -> None:
        """수신인 선택용 사용자 pool이 미가입 외부 스냅샷 사용자를 함께 반환하는지 확인합니다."""

        now = timezone.now()
        ExternalAffiliationSnapshot.objects.create(
            knox_id="external-50008",
            department="ExtDept",
            predicted_user_sdwt_prod="external-group",
            source_updated_at=now,
            last_seen_at=now,
        )

        self.client.force_login(self.user)
        default_response = self.client.get(reverse("account-users"), {"search": "external-50008"})
        include_response = self.client.get(
            reverse("account-users"),
            {
                "search": "external-50008",
                "contactField": "email",
                "includeExternalSnapshots": "true",
            },
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(default_response.json()["results"], [])

        self.assertEqual(include_response.status_code, 200)
        payload = include_response.json()
        self.assertIn("external-group", payload["userSdwtProds"])
        self.assertEqual(len(payload["results"]), 1)
        row = payload["results"][0]
        self.assertEqual(row["recipientType"], "external")
        self.assertEqual(row["recipientKey"], "external:external-50008")
        self.assertIsNone(row["userId"])
        self.assertEqual(row["knoxId"], "external-50008")
        self.assertEqual(row["email"], "external-50008@samsung.com")
        self.assertEqual(row["userSdwtProd"], "external-group")

    def test_account_user_pool_filters_by_department_before_group(self) -> None:
        """사용자 pool 조회가 department 기준 소속 후보와 사용자 결과를 좁히는지 확인합니다."""

        User = get_user_model()
        now = timezone.now()
        target_user = User.objects.create_user(
            sabun="S52001",
            password="test-password",
            knox_id="knox-52001",
            email="target@example.com",
            username="대상사용자",
        )
        _set_current_affiliation(
            target_user,
            department="TargetDept",
            line="L9",
            user_sdwt_prod="target-group",
        )
        same_department_other_group = User.objects.create_user(
            sabun="S52002",
            password="test-password",
            knox_id="knox-52002",
            email="same-dept-other@example.com",
            username="같은부서다른소속",
        )
        _set_current_affiliation(
            same_department_other_group,
            department="TargetDept",
            line="L9",
            user_sdwt_prod="target-other-group",
        )
        other_department_user = User.objects.create_user(
            sabun="S52003",
            password="test-password",
            knox_id="knox-52003",
            email="other-dept-same@example.com",
            username="다른부서사용자",
        )
        _set_current_affiliation(
            other_department_user,
            department="OtherDept",
            line="L9",
            user_sdwt_prod="other-dept-group",
        )
        ExternalAffiliationSnapshot.objects.create(
            knox_id="external-target-dept",
            username="외부대상",
            department="TargetDept",
            predicted_user_sdwt_prod="target-group",
            source_updated_at=now,
            last_seen_at=now,
        )
        ExternalAffiliationSnapshot.objects.create(
            knox_id="external-other-dept",
            username="외부타부서",
            department="OtherDept",
            predicted_user_sdwt_prod="target-group",
            source_updated_at=now,
            last_seen_at=now,
        )

        self.client.force_login(self.user)
        option_response = self.client.get(
            reverse("account-users"),
            {"department": "TargetDept", "includeExternalSnapshots": "true", "limit": 1},
        )
        load_response = self.client.get(
            reverse("account-users"),
            {
                "department": "TargetDept",
                "userSdwtProd": "target-group",
                "contactField": "email",
                "includeExternalSnapshots": "true",
                "limit": "all",
            },
        )

        self.assertEqual(option_response.status_code, 200)
        option_payload = option_response.json()
        self.assertIn("TargetDept", option_payload["departments"])
        self.assertIn("OtherDept", option_payload["departments"])
        self.assertIn("target-group", option_payload["userSdwtProds"])
        self.assertIn("target-other-group", option_payload["userSdwtProds"])
        self.assertNotIn("other-dept-group", option_payload["userSdwtProds"])
        self.assertNotIn("group-a", option_payload["userSdwtProds"])

        self.assertEqual(load_response.status_code, 200)
        rows_by_key = {row["recipientKey"]: row for row in load_response.json()["results"]}
        self.assertIn(f"user:{target_user.id}", rows_by_key)
        self.assertIn("external:external-target-dept", rows_by_key)
        self.assertNotIn(f"user:{same_department_other_group.id}", rows_by_key)
        self.assertNotIn(f"user:{other_department_user.id}", rows_by_key)
        self.assertNotIn("external:external-other-dept", rows_by_key)
        self.assertEqual(rows_by_key[f"user:{target_user.id}"]["department"], "TargetDept")
        self.assertEqual(rows_by_key[f"user:{target_user.id}"]["userSdwtProd"], "target-group")
        self.assertEqual(rows_by_key["external:external-target-dept"]["recipientType"], "external")
        self.assertEqual(rows_by_key["external:external-target-dept"]["department"], "TargetDept")
        self.assertEqual(rows_by_key["external:external-target-dept"]["userSdwtProd"], "target-group")

    def test_account_user_pool_rejects_unknown_contact_field(self) -> None:
        """지원하지 않는 연락처 필드는 명시적으로 거부해야 합니다."""

        self.client.force_login(self.user)
        response = self.client.get(reverse("account-users"), {"contactField": "phone"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "contactField must be email or knox_id")

    def test_account_user_pool_returns_all_group_users_when_requested(self) -> None:
        """소속 단위 전체 불러오기는 기본 500명 제한 없이 해당 소속 사용자를 반환해야 합니다."""

        User = get_user_model()
        for index in range(505):
            user = User.objects.create_user(
                sabun=f"S51{index:03d}",
                knox_id=f"knox-51{index:03d}",
                email=f"bulk-{index}@example.com",
                username=f"Bulk {index}",
            )
            _set_current_affiliation(user, user_sdwt_prod="bulk-group-all")

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("account-users"),
            {"userSdwtProd": "bulk-group-all", "limit": "all"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 505)

    def test_portal_access_allows_configured_department(self) -> None:
        """허용 부서 사용자는 별도 승인 없이 포털 접근이 허용되어야 합니다."""

        scope, _created = AccessScope.objects.get_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={"name": "Portal", "scope_type": AccessScope.ScopeTypes.PORTAL},
        )
        AccessPolicyRule.objects.update_or_create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="메모리Etch기술팀(글로벌 제조&인프라총괄)",
            defaults={"is_active": True},
        )
        self.user.department = "메모리Etch기술팀(글로벌 제조&인프라총괄)"
        self.user.save(update_fields=["department"])

        payload = get_portal_access_payload(user=self.user)

        self.assertTrue(payload["allowed"])
        self.assertEqual(payload["reason"], "department_allowed")
        self.assertTrue(payload["departmentAllowed"])

    def test_portal_access_rejected_row_blocks_allowed_department(self) -> None:
        """허용 부서 사용자도 거절 상태 행이 있으면 수동 차단되어야 합니다."""

        scope, _created = AccessScope.objects.get_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={"name": "Portal", "scope_type": AccessScope.ScopeTypes.PORTAL},
        )
        AccessPolicyRule.objects.update_or_create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="메모리Etch기술팀(글로벌 제조&인프라총괄)",
            defaults={"is_active": True},
        )
        self.user.department = "메모리Etch기술팀(글로벌 제조&인프라총괄)"
        self.user.save(update_fields=["department"])
        UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.DENIED,
            reason="수동 차단",
        )

        payload = get_portal_access_payload(user=self.user)

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["reason"], "denied")
        self.assertEqual(payload["rejectionReason"], "수동 차단")

        self.client.force_login(self.user)
        onboarding_response = self.client.get(reverse("account-affiliation"))
        self.assertEqual(onboarding_response.status_code, 200)

        response = self.client.get(reverse("account-overview"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "portal_access_required")

        request_list_response = self.client.get(reverse("account-affiliation-requests"))
        self.assertEqual(request_list_response.status_code, 403)
        self.assertEqual(request_list_response.json()["error"], "portal_access_required")

        request_payload, request_status = request_portal_access(user=self.user)
        self.assertEqual(request_status, 200)
        self.assertEqual(request_payload["status"], "pending")
        self.assertFalse(request_payload["portalAccess"]["allowed"])
        self.assertEqual(request_payload["portalAccess"]["reason"], "pending")

        approval = UserAccess.objects.get(user=self.user, scope=scope)
        self.assertEqual(approval.status, UserAccess.Status.PENDING)

        response_after_rerequest = self.client.get(reverse("account-overview"))
        self.assertEqual(response_after_rerequest.status_code, 403)
        self.assertEqual(response_after_rerequest.json()["portalAccess"]["reason"], "pending")

    def test_portal_access_request_and_admin_approval_flow(self) -> None:
        """비허용 부서 사용자가 요청 후 account admin 승인으로 접근 가능한지 확인합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        admin_user = self.manager
        _grant_manage_access(admin_user)

        request_payload, request_status = request_portal_access(user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.assertEqual(request_status, 200)
        self.assertEqual(request_payload["status"], "pending")
        self.assertFalse(request_payload["portalAccess"]["allowed"])
        self.assertEqual(approval.department, "OtherDept")

        self.client.force_login(admin_user)
        list_response = self.client.get(reverse("account-portal-access-approvals"))
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["results"][0]["id"], approval.id)

        approve_response = self.client.post(
            reverse("account-portal-access-approvals"),
            data='{"requestId": %d, "decision": "approve"}' % approval.id,
            content_type="application/json",
        )
        self.assertEqual(approve_response.status_code, 200)

        payload = get_portal_access_payload(user=self.user)
        self.assertTrue(payload["allowed"])
        self.assertEqual(payload["reason"], "allowed")

    def test_portal_access_admin_approval_applies_role(self) -> None:
        """포털 접근 승인 API가 요청 role을 사용자 접근 행에 반영하는지 확인합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        admin_user = self.manager
        _grant_manage_access(admin_user)
        request_portal_access(user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-portal-access-approvals"),
            data='{"requestId": %d, "decision": "approve", "role": "manager"}' % approval.id,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.ALLOWED)
        self.assertEqual(approval.role, "manager")
        self.assertEqual(response.json()["approval"]["role"], "manager")

    def test_portal_access_admin_approval_rejects_invalid_role(self) -> None:
        """포털 접근 승인 API는 정의되지 않은 role 입력을 거절해야 합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        admin_user = self.manager
        _grant_manage_access(admin_user)
        request_portal_access(user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-portal-access-approvals"),
            data='{"requestId": %d, "decision": "approve", "role": "owner"}' % approval.id,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)

    def test_portal_access_admin_approval_requires_explicit_decision(self) -> None:
        """포털 접근 승인 API는 decision 누락을 묵시 승인으로 처리하지 않아야 합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        admin_user = self.manager
        _grant_manage_access(admin_user)
        request_portal_access(user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-portal-access-approvals"),
            data='{"requestId": %d}' % approval.id,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)

    def test_portal_access_admin_approval_rejects_non_portal_scope_request(self) -> None:
        """포털 접근 승인 API는 portal scope 요청만 결정해야 합니다."""

        non_portal_scope = AccessScope.objects.create(
            key="app-alpha",
            name="App Alpha",
            scope_type=AccessScope.ScopeTypes.APP,
            requestable=False,
        )
        approval = UserAccess.objects.create(
            user=self.user,
            scope=non_portal_scope,
            department=self.user.department,
            status=UserAccess.Status.PENDING,
        )
        admin_user = self.manager
        _grant_manage_access(admin_user)

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-portal-access-approvals"),
            data='{"requestId": %d, "decision": "approve"}' % approval.id,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)

    def test_portal_access_request_uses_current_affiliation_department_fallback(self) -> None:
        """접근 요청 row의 부서는 현재 소속 부서 fallback과 일치해야 합니다."""

        self.user.department = ""
        self.user.save(update_fields=["department"])
        _set_current_affiliation(
            self.user,
            department="FallbackDept",
            line="L9",
            user_sdwt_prod="group-fallback",
        )
        self.user = get_user_model().objects.get(id=self.user.id)

        payload, status_code = request_portal_access(user=self.user)

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "pending")
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)
        self.assertEqual(approval.department, "FallbackDept")

    def test_portal_access_rerequest_updates_requested_at(self) -> None:
        """거절 사용자가 재요청하면 pending 전환 시 요청 시각을 갱신해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.DENIED,
            reason="사유 확인 필요",
            decided_by=self.manager,
            decided_at=timezone.now() - timedelta(days=1),
        )
        old_requested_at = timezone.now() - timedelta(days=2)
        UserAccess.objects.filter(id=approval.id).update(requested_at=old_requested_at)
        before_request = timezone.now()

        payload, status_code = request_portal_access(user=self.user)

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "pending")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertIsNone(approval.reason)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)
        self.assertGreaterEqual(approval.requested_at, before_request)

    def test_portal_access_rerequest_resets_role_to_scope_default(self) -> None:
        """거절 사용자가 재요청하면 이전 고권한 role을 기본 role로 초기화해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        scope.default_role = "viewer"
        scope.save(update_fields=["default_role"])
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.DENIED,
            role="manager",
            reason="권한 회수",
            decided_by=self.manager,
            decided_at=timezone.now(),
        )

        payload, status_code = request_portal_access(user=self.user)

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "pending")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertEqual(approval.role, "viewer")

    def test_portal_access_request_records_initial_and_rerequest_audit_snapshots(self) -> None:
        """최초 요청과 거절 후 재요청은 각각 당시 상태 snapshot을 감사 로그에 남겨야 합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])

        request_portal_access(user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)
        first_log = AccessAuditLog.objects.get(
            action=AccessAuditLog.Actions.REQUEST,
            target_user=self.user,
        )
        self.assertEqual(first_log.before, {})
        self.assertEqual(first_log.after["status"], UserAccess.Status.PENDING)

        approval.status = UserAccess.Status.DENIED
        approval.reason = "추가 확인"
        approval.decided_by = self.manager
        approval.decided_at = timezone.now()
        approval.save(update_fields=["status", "reason", "decided_by", "decided_at", "updated_at"])

        request_portal_access(user=self.user)
        logs = list(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.REQUEST,
                target_user=self.user,
            ).order_by("id")
        )
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[1].before["status"], UserAccess.Status.DENIED)
        self.assertEqual(logs[1].before["rejectionReason"], "추가 확인")
        self.assertEqual(logs[1].after["status"], UserAccess.Status.PENDING)
        self.assertIsNone(logs[1].after["rejectionReason"])

    def test_portal_access_request_rolls_back_when_audit_creation_fails(self) -> None:
        """접근 요청 감사 로그 생성 실패 시 pending 행도 남지 않아야 합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])

        with patch(
            "api.account.services.access_control._create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                request_portal_access(user=self.user)

        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).exists()
        )

    def test_decide_access_rolls_back_when_audit_creation_fails(self) -> None:
        """승인 감사 로그 생성 실패 시 pending 상태를 유지해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        _grant_manage_access(self.manager)
        self.manager.refresh_from_db()
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.PENDING,
        )

        with patch(
            "api.account.services.access_control._create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                decide_access(
                    actor=self.manager,
                    access_id=approval.id,
                    decision="approve",
                    reason=None,
                )

        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)

    def test_decide_access_rejects_stale_already_decided_request(self) -> None:
        """이미 결정된 요청을 다시 승인하거나 거절하지 않아야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        _grant_manage_access(self.manager)
        self.manager.refresh_from_db()
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.ALLOWED,
            decided_by=self.manager,
            decided_at=timezone.now(),
        )

        payload, status_code = decide_access(
            actor=self.manager,
            access_id=approval.id,
            decision="reject",
            reason="늦게 도착한 요청",
        )

        self.assertEqual(status_code, 409)
        self.assertEqual(payload["error"], "invalid_status_transition")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.ALLOWED)
        self.assertFalse(
            AccessAuditLog.objects.filter(target_user=self.user, action=AccessAuditLog.Actions.REJECT).exists()
        )

    def test_decide_access_rejects_invalid_service_role(self) -> None:
        """서비스 직접 호출에서도 정의되지 않은 role은 조용히 viewer로 바꾸지 않아야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        _grant_manage_access(self.manager)
        self.manager.refresh_from_db()
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.PENDING,
        )

        payload, status_code = decide_access(
            actor=self.manager,
            access_id=approval.id,
            decision="approve",
            reason=None,
            role="owner",
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "invalid_role")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)

    def test_decide_access_rejects_invalid_service_decision(self) -> None:
        """서비스 직접 호출에서도 정의되지 않은 decision은 승인으로 처리하지 않아야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        _grant_manage_access(self.manager)
        self.manager.refresh_from_db()
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.PENDING,
        )

        payload, status_code = decide_access(
            actor=self.manager,
            access_id=approval.id,
            decision="aprove",
            reason=None,
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "invalid_decision")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)

    def test_inactive_portal_scope_cannot_be_requested(self) -> None:
        """비활성 portal scope는 화면에서 승인 요청 가능 상태로 노출하지 않아야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        scope.is_active = False
        scope.save(update_fields=["is_active"])

        payload = get_portal_access_payload(user=self.user)

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["reason"], "scope_inactive")
        self.assertFalse(payload["canRequest"])

    def test_superuser_is_allowed_when_portal_scope_is_missing(self) -> None:
        """portal scope 설정이 누락되어도 superuser 비상 접근은 허용해야 합니다."""

        AccessScope.objects.filter(key=ACCESS_SCOPE_PORTAL).delete()
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])

        payload = get_portal_access_payload(user=self.user)

        self.assertTrue(payload["allowed"])
        self.assertEqual(payload["reason"], "superuser_bypass")
        self.assertEqual(payload["source"], "superuser_bypass")
        self.assertEqual(payload["role"], "admin")

    def test_portal_access_staff_without_capability_cannot_approve(self) -> None:
        """is_staff만 있는 사용자는 포털 접근 승인 관리자가 아니어야 합니다."""

        staff_user = self.manager
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        UserProfile.objects.filter(user=staff_user).update(role=UserProfile.Roles.VIEWER)

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        request_portal_access(user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.client.force_login(staff_user)
        response = self.client.post(
            reverse("account-portal-access-approvals"),
            data='{"requestId": %d, "decision": "approve"}' % approval.id,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)

    def test_access_management_lists_policy_allowed_user_and_revoke_blocks(self) -> None:
        """권한 관리 목록은 정책 허용 사용자를 표시하고 명시 회수로 차단할 수 있어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.user.department = "Dept"
        self.user.save(update_fields=["department"])

        self.client.force_login(admin_user)
        list_response = self.client.get(reverse("account-access-users"), {"search": self.user.knox_id})
        self.assertEqual(list_response.status_code, 200)
        row = list_response.json()["results"][0]
        self.assertEqual(row["user"]["id"], self.user.id)
        self.assertTrue(row["access"]["allowed"])
        self.assertEqual(row["access"]["source"], "policy_department")
        self.assertIsNone(row["access"]["explicitStatus"])

        revoke_response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"action": "revoke", "reason": "운영 회수"}',
            content_type="application/json",
        )
        self.assertEqual(revoke_response.status_code, 200)
        self.assertEqual(revoke_response.json()["row"]["access"]["source"], "explicit_denied")

        payload = get_portal_access_payload(user=self.user)
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["reason"], "denied")
        self.assertEqual(UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).status, UserAccess.Status.DENIED)
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.REVOKE,
                target_user=self.user,
                actor=admin_user,
            ).exists()
        )

    def test_access_management_change_role_requires_explicit_role(self) -> None:
        """change_role action은 정책 허용 사용자에게도 명시적인 role이 필요합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"action": "change_role"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json())
        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).exists()
        )

    def test_access_management_approve_requires_pending_request(self) -> None:
        """운영 승인 action은 pending 요청이 없으면 직접 부여로 동작하지 않아야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"action": "approve", "role": "viewer"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "invalid_status_transition")
        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).exists()
        )

    def test_access_management_fast_filters_only_exclude_superuser_bypass(self) -> None:
        """명시 상태 필터는 capability 사용자를 포함하고 superuser만 제외해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        admin_user = self.manager
        _grant_manage_access(admin_user)
        User = get_user_model()
        capability_user = User.objects.create_user(
            sabun="S51000",
            password="test-password",
            knox_id="knox-51000",
            department="Dept",
        )
        _grant_manage_access(capability_user)
        UserAccess.objects.create(
            user=capability_user,
            scope=scope,
            status=UserAccess.Status.PENDING,
        )
        UserAccess.objects.create(
            user=self.user,
            scope=scope,
            status=UserAccess.Status.PENDING,
        )
        UserAccess.objects.create(
            user=self.superuser,
            scope=scope,
            status=UserAccess.Status.DENIED,
        )

        self.client.force_login(admin_user)
        pending_response = self.client.get(reverse("account-access-users"), {"status": "pending"})
        denied_source_response = self.client.get(
            reverse("account-access-users"),
            {"source": "explicit_denied"},
        )
        bypass_source_response = self.client.get(
            reverse("account-access-users"),
            {"source": "superuser_bypass"},
        )
        legacy_bypass_source_response = self.client.get(
            reverse("account-access-users"),
            {"source": "admin"},
        )

        pending_ids = {row["user"]["id"] for row in pending_response.json()["results"]}
        denied_ids = {row["user"]["id"] for row in denied_source_response.json()["results"]}
        bypass_ids = {row["user"]["id"] for row in bypass_source_response.json()["results"]}
        legacy_bypass_ids = {
            row["user"]["id"] for row in legacy_bypass_source_response.json()["results"]
        }
        self.assertIn(self.user.id, pending_ids)
        self.assertIn(capability_user.id, pending_ids)
        self.assertNotIn(self.superuser.id, denied_ids)
        self.assertIn(self.superuser.id, bypass_ids)
        self.assertNotIn(self.user.id, bypass_ids)
        self.assertNotIn(capability_user.id, bypass_ids)
        self.assertEqual(legacy_bypass_ids, bypass_ids)

    def test_profile_admin_without_capability_cannot_manage_or_bypass_access(self) -> None:
        """프로필 admin 역할만으로는 권한 관리나 접근 제한 우회가 허용되지 않아야 합니다."""

        UserProfile.objects.filter(user=self.manager).update(role=UserProfile.Roles.ADMIN)
        UserAccess.objects.create(
            user=self.manager,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            status=UserAccess.Status.DENIED,
        )
        self.manager.refresh_from_db()

        payload = get_portal_access_payload(user=self.manager)

        self.assertFalse(can_manage_access(user=self.manager))
        self.assertFalse(payload["allowed"])
        self.assertFalse(payload["canManage"])
        self.assertEqual(payload["source"], "explicit_denied")

    def test_portal_admin_role_without_capability_cannot_manage_access(self) -> None:
        """Portal admin 역할은 별도 manage_access capability를 부여하지 않아야 합니다."""

        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            status=UserAccess.Status.ALLOWED,
            role="admin",
        )

        payload = get_portal_access_payload(user=self.user)

        self.assertTrue(payload["allowed"])
        self.assertEqual(payload["role"], "admin")
        self.assertFalse(payload["canManage"])
        self.assertFalse(can_manage_access(user=self.user))

        self.client.force_login(self.user)
        response = self.client.get(reverse("account-access-users"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "forbidden")

    def test_manage_access_capability_does_not_bypass_explicit_denial(self) -> None:
        """권한 관리 capability 보유자도 자신의 명시적 차단을 우회하지 못해야 합니다."""

        _grant_manage_access(self.manager)
        UserAccess.objects.create(
            user=self.manager,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            status=UserAccess.Status.DENIED,
        )

        payload = get_portal_access_payload(user=self.manager)

        self.assertTrue(can_manage_access(user=self.manager))
        self.assertTrue(payload["canManage"])
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["source"], "explicit_denied")

        self.client.force_login(self.manager)
        response = self.client.get(reverse("account-access-users"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "portal_access_required")
        self.assertTrue(response.json()["portalAccess"]["canManage"])

    def test_pending_access_remains_denied_when_department_policy_matches(self) -> None:
        """승인 대기 상태는 부서 자동 허용 규칙보다 우선해 접근을 차단해야 합니다."""

        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            status=UserAccess.Status.PENDING,
        )

        payload = get_portal_access_payload(user=self.user)

        self.assertTrue(payload["policyMatched"])
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["effectiveStatus"], "pending")
        self.assertEqual(payload["source"], "explicit_pending")

    def test_access_admin_mutations_require_json_content_type(self) -> None:
        """브라우저 form Content-Type으로 권한과 정책을 변경할 수 없어야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        admin_user = self.manager
        _grant_manage_access(admin_user)
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            status=UserAccess.Status.PENDING,
        )
        rule = AccessPolicyRule.objects.get(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Dept",
        )
        self.client.force_login(admin_user)

        approval_response = self.client.post(
            reverse("account-portal-access-approvals"),
            data='{"requestId": %d, "decision": "approve"}' % approval.id,
            content_type="text/plain",
        )
        user_response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"action": "grant"}',
            content_type="application/x-www-form-urlencoded",
        )
        create_response = self.client.post(
            reverse("account-access-policy-rules"),
            data='{"ruleType": "department", "value": "FormDept"}',
            content_type="text/plain",
        )
        patch_response = self.client.patch(
            reverse("account-access-policy-rule-detail", kwargs={"rule_id": rule.id}),
            data='{"role": "manager"}',
            content_type="text/plain",
        )

        self.assertEqual(approval_response.status_code, 415)
        self.assertEqual(user_response.status_code, 415)
        self.assertEqual(create_response.status_code, 415)
        self.assertEqual(patch_response.status_code, 415)
        approval.refresh_from_db()
        rule.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertEqual(rule.role, "viewer")
        self.assertFalse(AccessPolicyRule.objects.filter(value="FormDept").exists())

    def test_access_management_users_paginates_default_list(self) -> None:
        """권한 관리 기본 사용자 목록은 페이지 크기만큼만 응답해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        User = get_user_model()
        for index in range(25):
            User.objects.create_user(
                sabun=f"S51{index:03d}",
                password="test-password",
                knox_id=f"knox-51{index:03d}",
                department="Dept",
            )

        self.client.force_login(admin_user)
        response = self.client.get(reverse("account-access-users"), {"page_size": "5"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 5)
        self.assertEqual(payload["pagination"]["pageSize"], 5)
        self.assertEqual(payload["pagination"]["total"], payload["summary"]["total"])
        self.assertEqual(payload["summary"]["pageTotal"], 5)

    def test_access_matrix_returns_portal_role_and_app_boolean_contracts(self) -> None:
        """통합 권한 매트릭스는 Portal 역할과 앱 boolean 판정을 함께 반환해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        appstore_scope = AccessScope.objects.get(key="appstore")
        line_dashboard_scope = AccessScope.objects.get(key="line-dashboard")
        UserAccess.objects.create(
            user=self.user,
            scope=appstore_scope,
            department="Dept",
            status=UserAccess.Status.ALLOWED,
            role="member",
        )
        AccessPolicyRule.objects.create(
            scope=line_dashboard_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Dept",
            role="viewer",
        )

        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("account-access-matrix"),
            {"search": self.user.knox_id, "page_size": 5},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["scopes"]), 14)
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["scopes"][0]["key"], ACCESS_SCOPE_PORTAL)
        self.assertEqual(payload["scopes"][0]["scopeType"], AccessScope.ScopeTypes.PORTAL)
        self.assertEqual(payload["scopes"][0]["defaultRole"], "viewer")
        self.assertNotIn("defaultRole", payload["scopes"][1])
        row = payload["results"][0]
        self.assertEqual(row["user"]["id"], self.user.id)
        self.assertEqual(row["accesses"][ACCESS_SCOPE_PORTAL]["source"], "policy_department")
        self.assertEqual(row["accesses"][ACCESS_SCOPE_PORTAL]["role"], "viewer")
        self.assertEqual(row["accesses"][ACCESS_SCOPE_PORTAL]["policy"]["role"], "viewer")
        self.assertEqual(row["accesses"]["appstore"]["source"], "explicit_allowed")
        self.assertNotIn("role", row["accesses"]["appstore"])
        self.assertNotIn("role", row["accesses"]["appstore"]["policy"])
        self.assertEqual(row["accesses"]["line-dashboard"]["source"], "policy_department")
        self.assertTrue(row["accesses"]["line-dashboard"]["allowed"])
        self.assertNotIn("role", row["accesses"]["line-dashboard"])
        self.assertEqual(row["accesses"]["observer"]["effectiveStatus"], "not_requested")

    def test_access_matrix_blocks_apps_when_portal_access_is_denied(self) -> None:
        """Portal 차단 사용자의 앱 명시 허용은 보존하되 최종 접근은 차단해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        appstore_scope = AccessScope.objects.get(key="appstore")
        UserAccess.objects.create(
            user=self.user,
            scope=portal_scope,
            department="Dept",
            status=UserAccess.Status.DENIED,
            role="viewer",
            reason="Portal 운영 차단",
        )
        UserAccess.objects.create(
            user=self.user,
            scope=appstore_scope,
            department="Dept",
            status=UserAccess.Status.ALLOWED,
            role="viewer",
        )

        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("account-access-matrix"),
            {"search": self.user.knox_id, "page_size": 5},
        )

        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        portal_access = row["accesses"][ACCESS_SCOPE_PORTAL]
        app_access = row["accesses"]["appstore"]
        self.assertFalse(portal_access["allowed"])
        self.assertFalse(app_access["allowed"])
        self.assertTrue(app_access["blockedByPortal"])
        self.assertEqual(app_access["source"], AccessSource.PORTAL_ACCESS_REQUIRED)
        self.assertEqual(app_access["explicitStatus"], UserAccess.Status.ALLOWED)
        self.assertEqual(app_access["underlyingAccess"]["source"], AccessSource.EXPLICIT_ALLOWED)
        self.assertTrue(app_access["underlyingAccess"]["allowed"])

    def test_access_users_filters_portal_blocked_apps_by_final_source(self) -> None:
        """앱 권한 목록 필터는 Portal 우선 차단 source를 최종 판정으로 사용해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            status=UserAccess.Status.DENIED,
            role="viewer",
        )
        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key="appstore"),
            status=UserAccess.Status.ALLOWED,
            role="viewer",
        )

        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("account-access-users"),
            {
                "scope": "appstore",
                "status": "denied",
                "source": AccessSource.PORTAL_ACCESS_REQUIRED,
            },
        )

        self.assertEqual(response.status_code, 200)
        rows_by_user_id = {row["user"]["id"]: row for row in response.json()["results"]}
        self.assertIn(self.user.id, rows_by_user_id)
        self.assertTrue(rows_by_user_id[self.user.id]["access"]["blockedByPortal"])

    def test_app_access_matrix_requires_access_admin(self) -> None:
        """일반 사용자는 앱 권한 매트릭스를 조회할 수 없어야 합니다."""

        self.client.force_login(self.user)

        response = self.client.get(reverse("account-access-matrix"))

        self.assertEqual(response.status_code, 403)

    def test_app_access_matrix_decision_updates_selected_app_scope(self) -> None:
        """매트릭스의 수동 권한 변경은 선택한 앱 scope에만 저장되어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"scope": "appstore", "action": "grant"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        app_access = UserAccess.objects.get(user=self.user, scope__key="appstore")
        self.assertEqual(app_access.status, UserAccess.Status.ALLOWED)
        self.assertEqual(app_access.role, "viewer")
        self.assertNotIn("role", response.json()["row"]["access"])
        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).exists()
        )

    def test_app_access_decision_rejects_role_input_and_change_role(self) -> None:
        """앱 scope는 role 입력과 change_role action을 허용하지 않아야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)
        endpoint = reverse("account-access-user-decision", kwargs={"user_id": self.user.id})

        role_response = self.client.post(
            endpoint,
            data='{"scope": "appstore", "action": "grant", "role": "manager"}',
            content_type="application/json",
        )
        change_role_response = self.client.post(
            endpoint,
            data='{"scope": "appstore", "action": "change_role", "role": "viewer"}',
            content_type="application/json",
        )

        self.assertEqual(role_response.status_code, 400)
        self.assertEqual(role_response.json()["error"], "app_role_not_supported")
        self.assertEqual(change_role_response.status_code, 400)
        self.assertEqual(change_role_response.json()["error"], "app_role_not_supported")
        self.assertFalse(UserAccess.objects.filter(user=self.user, scope__key="appstore").exists())

    def test_app_access_policy_rejects_role_and_omits_role_from_response(self) -> None:
        """앱 자동 정책도 role 없이 allowed 정책으로만 관리되어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)
        endpoint = reverse("account-access-policy-rules")

        role_response = self.client.post(
            endpoint,
            data='{"scope":"appstore","ruleType":"department","value":"Role Dept","role":"manager"}',
            content_type="application/json",
        )
        create_response = self.client.post(
            endpoint,
            data='{"scope":"appstore","ruleType":"department","value":"Allowed Dept"}',
            content_type="application/json",
        )

        self.assertEqual(role_response.status_code, 400)
        self.assertEqual(role_response.json()["error"], "app_role_not_supported")
        self.assertEqual(create_response.status_code, 201)
        self.assertNotIn("role", create_response.json()["policyRule"])
        rule = AccessPolicyRule.objects.get(scope__key="appstore", value="Allowed Dept")
        self.assertEqual(rule.role, "viewer")

    def test_access_management_users_combined_status_source_filter_requires_both(self) -> None:
        """권한 관리 복합 필터는 status와 source를 모두 만족하는 사용자만 반환해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        User = get_user_model()
        pending_user = User.objects.create_user(
            sabun="S52000",
            password="test-password",
            knox_id="knox-52000",
            department="OtherDept",
        )
        UserAccess.objects.create(
            user=pending_user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            department="OtherDept",
            status=UserAccess.Status.PENDING,
        )

        self.client.force_login(admin_user)
        impossible_response = self.client.get(
            reverse("account-access-users"),
            {"status": "pending", "source": "policy_department"},
        )
        self.assertEqual(impossible_response.status_code, 200)
        self.assertEqual(impossible_response.json()["results"], [])

        policy_allowed_response = self.client.get(
            reverse("account-access-users"),
            {"status": "allowed", "source": "policy_department"},
        )
        self.assertEqual(policy_allowed_response.status_code, 200)
        self.assertIn(self.user.id, {row["user"]["id"] for row in policy_allowed_response.json()["results"]})
        self.assertNotIn(pending_user.id, {row["user"]["id"] for row in policy_allowed_response.json()["results"]})

    def test_access_management_users_inactive_scope_uses_effective_status_filter(self) -> None:
        """비활성 scope에서는 명시 상태 fast filter보다 최종 inactive 판정을 우선해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        scope = AccessScope.objects.get(key="appstore")
        UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.DENIED,
            reason="운영 차단",
        )
        scope.is_active = False
        scope.save(update_fields=["is_active"])

        self.client.force_login(admin_user)
        denied_response = self.client.get(
            reverse("account-access-users"),
            {"scope": scope.key, "status": "denied"},
        )
        explicit_denied_response = self.client.get(
            reverse("account-access-users"),
            {"scope": scope.key, "source": "explicit_denied"},
        )
        inactive_response = self.client.get(
            reverse("account-access-users"),
            {"scope": scope.key, "status": "inactive"},
        )

        self.assertEqual(denied_response.status_code, 200)
        self.assertEqual(explicit_denied_response.status_code, 200)
        self.assertEqual(inactive_response.status_code, 200)
        self.assertNotIn(self.user.id, {row["user"]["id"] for row in denied_response.json()["results"]})
        self.assertNotIn(self.user.id, {row["user"]["id"] for row in explicit_denied_response.json()["results"]})
        self.assertIn(self.user.id, {row["user"]["id"] for row in inactive_response.json()["results"]})

    def test_access_management_reset_to_policy_restores_policy_allowed(self) -> None:
        """명시 차단을 정책 기준으로 복귀하면 부서 정책 허용이 다시 적용되어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        self.user.department = "Dept"
        self.user.save(update_fields=["department"])
        UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department="Dept",
            status=UserAccess.Status.DENIED,
            reason="임시 차단",
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"action": "reset_to_policy"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["row"]["access"]["source"], "policy_department")
        self.assertFalse(UserAccess.objects.filter(user=self.user, scope=scope).exists())
        self.assertTrue(get_portal_access_payload(user=self.user)["allowed"])
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.RESET_TO_POLICY,
                target_user=self.user,
                actor=admin_user,
            ).exists()
        )

    def test_access_policy_rule_management_crud_and_audit_log(self) -> None:
        """관리자는 기본 허용 정책 규칙을 생성, 수정, 삭제하고 감사 로그를 남길 수 있어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        create_response = self.client.post(
            reverse("account-access-policy-rules"),
            data='{"ruleType": "department", "value": "NewDept", "role": "member", "isActive": true}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        rule_id = create_response.json()["policyRule"]["id"]
        self.assertEqual(create_response.json()["policyRule"]["role"], "member")

        patch_response = self.client.patch(
            reverse("account-access-policy-rule-detail", kwargs={"rule_id": rule_id}),
            data='{"isActive": false, "role": "viewer"}',
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertFalse(patch_response.json()["policyRule"]["isActive"])

        list_response = self.client.get(reverse("account-access-policy-rules"))
        self.assertEqual(list_response.status_code, 200)
        self.assertIn(rule_id, {row["id"] for row in list_response.json()["results"]})

        delete_response = self.client.delete(
            reverse("account-access-policy-rule-detail", kwargs={"rule_id": rule_id})
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(AccessPolicyRule.objects.filter(id=rule_id).exists())
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.POLICY_CREATE,
                actor=admin_user,
            ).exists()
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.POLICY_UPDATE,
                actor=admin_user,
            ).exists()
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.POLICY_DELETE,
                actor=admin_user,
            ).exists()
        )
        audit_response = self.client.get(
            reverse("account-access-audit-logs"),
            {"action": AccessAuditLog.Actions.POLICY_DELETE},
        )
        self.assertEqual(audit_response.status_code, 200)
        self.assertEqual(audit_response.json()["results"][0]["policyRule"]["value"], "NewDept")

    def test_access_policy_rule_api_rejects_non_department_types(self) -> None:
        """정책 API는 부서 이외의 적용 기준을 거부해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        for rule_type in ("profile_role", "user_sdwt_prod_role", "authenticated"):
            with self.subTest(rule_type=rule_type):
                response = self.client.post(
                    reverse("account-access-policy-rules"),
                    data={"ruleType": rule_type, "value": "invalid", "role": "viewer"},
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("ruleType", response.json())

        self.assertFalse(AccessPolicyRule.objects.filter(value="invalid").exists())

    def test_access_policy_mutations_roll_back_when_audit_creation_fails(self) -> None:
        """정책 생성, 수정, 삭제는 감사 로그 실패 시 모두 원래 상태로 복구되어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        admin_user.refresh_from_db()

        with patch(
            "api.account.services.access_control._create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                create_access_policy_rule(
                    actor=admin_user,
                    scope_key=ACCESS_SCOPE_PORTAL,
                    rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
                    value="RollbackCreateDept",
                    role="viewer",
                    is_active=True,
                )
        self.assertFalse(AccessPolicyRule.objects.filter(value="RollbackCreateDept").exists())

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        rule = AccessPolicyRule.objects.create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="RollbackMutationDept",
            role="viewer",
        )
        with patch(
            "api.account.services.access_control._create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                update_access_policy_rule(
                    actor=admin_user,
                    rule_id=rule.id,
                    scope_key=None,
                    rule_type=None,
                    value=None,
                    role="manager",
                    is_active=None,
                )
        rule.refresh_from_db()
        self.assertEqual(rule.role, "viewer")

        with patch(
            "api.account.services.access_control._create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                delete_access_policy_rule(actor=admin_user, rule_id=rule.id)
        self.assertTrue(AccessPolicyRule.objects.filter(id=rule.id).exists())

    def test_access_audit_api_prefers_event_policy_snapshot(self) -> None:
        """과거 정책 감사 응답은 이후 수정된 live 정책 값이 아니라 당시 snapshot을 반환해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)
        create_response = self.client.post(
            reverse("account-access-policy-rules"),
            data='{"ruleType": "department", "value": "SnapshotBefore", "role": "viewer"}',
            content_type="application/json",
        )
        rule_id = create_response.json()["policyRule"]["id"]
        patch_response = self.client.patch(
            reverse("account-access-policy-rule-detail", kwargs={"rule_id": rule_id}),
            data='{"value": "SnapshotAfter", "role": "manager"}',
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)

        audit_response = self.client.get(
            reverse("account-access-audit-logs"),
            {"action": AccessAuditLog.Actions.POLICY_CREATE},
        )
        matching_log = next(
            row for row in audit_response.json()["results"] if row["policyRule"]["id"] == rule_id
        )
        self.assertEqual(matching_log["policyRule"]["value"], "SnapshotBefore")
        self.assertEqual(matching_log["policyRule"]["role"], "viewer")

    def test_access_admin_direct_policy_and_user_access_changes_are_audited(self) -> None:
        """superuser의 Django Admin 직접 변경도 접근 권한 감사 로그에 기록되어야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccessPolicyRuleAdmin, UserAccessAdmin

        admin_user = self.superuser
        request = RequestFactory().post("/admin/")
        request.user = admin_user
        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)

        policy_admin = AccessPolicyRuleAdmin(AccessPolicyRule, AdminSite())
        rule = AccessPolicyRule(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="AdminDept",
            role="member",
        )
        policy_admin.save_model(request, rule, form=None, change=False)

        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.POLICY_CREATE,
                actor=admin_user,
                policy_rule=rule,
            ).exists()
        )

        user_access = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.PENDING,
            role="viewer",
        )
        user_access.status = UserAccess.Status.ALLOWED
        user_access.role = "member"
        user_access.decided_by = admin_user

        user_access_admin = UserAccessAdmin(UserAccess, AdminSite())
        user_access_admin.save_model(request, user_access, form=None, change=True)

        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.GRANT,
                actor=admin_user,
                target_user=self.user,
                after__status=UserAccess.Status.ALLOWED,
            ).exists()
        )

    def test_access_scope_admin_protects_system_scopes_and_audits_custom_scope_changes(self) -> None:
        """Admin은 시스템 scope 식별자와 삭제를 막고 사용자 정의 scope 변경을 기록해야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccessScopeAdmin

        request = RequestFactory().post("/admin/")
        request.user = self.superuser
        scope_admin = AccessScopeAdmin(AccessScope, AdminSite())
        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)

        self.assertIn("key", scope_admin.get_readonly_fields(request, portal_scope))
        self.assertIn("scope_type", scope_admin.get_readonly_fields(request, portal_scope))
        self.assertFalse(scope_admin.has_delete_permission(request, portal_scope))
        portal_scope.key = "renamed-portal"
        with self.assertRaises(ValidationError):
            scope_admin.save_model(request, portal_scope, form=None, change=True)
        portal_scope.refresh_from_db()
        self.assertEqual(portal_scope.key, ACCESS_SCOPE_PORTAL)
        with self.assertRaises(PermissionDenied):
            scope_admin.delete_model(request, portal_scope)

        appstore_scope = AccessScope.objects.get(key="appstore")
        self.assertIn("key", scope_admin.get_readonly_fields(request, appstore_scope))
        self.assertIn("scope_type", scope_admin.get_readonly_fields(request, appstore_scope))
        self.assertFalse(scope_admin.has_delete_permission(request, appstore_scope))
        appstore_scope.scope_type = AccessScope.ScopeTypes.FEATURE
        with self.assertRaises(ValidationError):
            scope_admin.save_model(request, appstore_scope, form=None, change=True)
        appstore_scope.refresh_from_db()
        self.assertEqual(appstore_scope.scope_type, AccessScope.ScopeTypes.APP)
        with self.assertRaises(PermissionDenied):
            scope_admin.delete_model(request, appstore_scope)

        app_scope = AccessScope(
            key="audited-app",
            name="Audited App",
            scope_type=AccessScope.ScopeTypes.APP,
            requestable=False,
        )
        scope_admin.save_model(request, app_scope, form=None, change=False)
        app_scope.name = "Audited App Updated"
        scope_admin.save_model(request, app_scope, form=None, change=True)
        app_scope_id = app_scope.id
        scope_admin.delete_model(request, app_scope)

        self.assertFalse(AccessScope.objects.filter(id=app_scope_id).exists())
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.SCOPE_CREATE,
                before={},
                after__key="audited-app",
            ).exists()
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.SCOPE_UPDATE,
                before__name="Audited App",
                after__name="Audited App Updated",
            ).exists()
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.SCOPE_DELETE,
                before__key="audited-app",
            ).exists()
        )

    def test_access_audit_log_admin_is_fully_read_only(self) -> None:
        """Django Admin에서 감사 로그를 추가, 수정, 삭제할 수 없어야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccessAuditLogAdmin

        request = RequestFactory().get("/admin/")
        request.user = self.superuser
        audit_admin = AccessAuditLogAdmin(AccessAuditLog, AdminSite())

        self.assertFalse(audit_admin.has_add_permission(request))
        self.assertFalse(audit_admin.has_change_permission(request))
        self.assertFalse(audit_admin.has_delete_permission(request))
        self.assertEqual(
            set(audit_admin.readonly_fields),
            {
                "id",
                "scope",
                "actor",
                "target_user",
                "policy_rule",
                "action",
                "before",
                "after",
                "reason",
                "created_at",
            },
        )

    def test_access_audit_log_endpoint_requires_access_admin(self) -> None:
        """감사 로그는 권한 관리자에게 전체 scope를 기본 제공하고 scope 필터를 지원해야 합니다."""

        self.client.force_login(self.user)
        forbidden_response = self.client.get(reverse("account-access-audit-logs"))
        self.assertEqual(forbidden_response.status_code, 403)

        admin_user = self.manager
        _grant_manage_access(admin_user)
        AccessAuditLog.objects.create(
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            actor=admin_user,
            target_user=self.user,
            action=AccessAuditLog.Actions.GRANT,
            after={"status": "allowed"},
        )
        AccessAuditLog.objects.create(
            scope=AccessScope.objects.get(key="appstore"),
            actor=admin_user,
            target_user=self.user,
            action=AccessAuditLog.Actions.REVOKE,
            after={"status": "denied"},
        )
        AccessAuditLog.objects.create(
            scope=None,
            actor=self.superuser,
            target_user=admin_user,
            action=AccessAuditLog.Actions.ACCESS_MANAGER_GRANT,
            after={"canManageAccess": True},
        )

        self.client.force_login(admin_user)
        response = self.client.get(reverse("account-access-audit-logs"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pagination"]["total"], 3)
        self.assertEqual(
            {row["action"] for row in response.json()["results"]},
            {
                AccessAuditLog.Actions.GRANT,
                AccessAuditLog.Actions.REVOKE,
                AccessAuditLog.Actions.ACCESS_MANAGER_GRANT,
            },
        )

        portal_response = self.client.get(
            reverse("account-access-audit-logs"),
            {"scope": ACCESS_SCOPE_PORTAL},
        )
        self.assertEqual(portal_response.status_code, 200)
        self.assertEqual(portal_response.json()["pagination"]["total"], 1)
        self.assertEqual(portal_response.json()["results"][0]["action"], AccessAuditLog.Actions.GRANT)

    def test_access_policy_rule_only_accepts_department_type(self) -> None:
        """모델 검증과 DB 제약은 부서 이외의 정책 유형을 차단해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        self.assertEqual(AccessPolicyRule.RuleTypes.values, ["department"])

        with self.assertRaises(ValidationError):
            AccessPolicyRule(
                scope=scope,
                rule_type="profile_role",
                value="viewer",
            ).full_clean()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccessPolicyRule.objects.create(
                    scope=scope,
                    rule_type="authenticated",
                    value="*",
                )

    def test_access_policy_rule_requires_department_value(self) -> None:
        """부서 정책에는 비교할 부서명이 필요합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        rule = AccessPolicyRule(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="",
        )

        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_access_policy_rule_normalizes_value_and_rejects_semantic_duplicates(self) -> None:
        """정책 값은 공백을 제거하고 대소문자가 다른 의미상 중복도 차단해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        normalized_rule = AccessPolicyRule(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="  New Department  ",
        )
        normalized_rule.full_clean()
        self.assertEqual(normalized_rule.value, "New Department")

        AccessPolicyRule.objects.create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Case Department",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccessPolicyRule.objects.create(
                    scope=scope,
                    rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
                    value=" case department ",
                )

    def test_access_permission_integrity_command_reports_group_misconfiguration(self) -> None:
        """운영 점검 명령은 정상 상태를 통과시키고 관리자 그룹 오류를 실패로 보고해야 합니다."""

        output = StringIO()
        call_command("check_access_permission_integrity", stdout=output)
        self.assertIn("무결성 점검을 통과", output.getvalue())

        app_label, codename = MANAGE_ACCESS_PERMISSION.split(".", maxsplit=1)
        permission = Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )
        Group.objects.get(name=ACCESS_MANAGERS_GROUP_NAME).permissions.remove(permission)

        with self.assertRaises(CommandError):
            call_command("check_access_permission_integrity", stdout=StringIO(), stderr=StringIO())

    def test_grant_initial_access_command_grants_portal_and_active_apps(self) -> None:
        """초기 권한 부여 명령은 활성 사용자에게 Portal과 활성 앱 권한을 생성해야 합니다."""

        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        app_scope_ids = set(
            AccessScope.objects.filter(
                scope_type=AccessScope.ScopeTypes.APP,
                is_active=True,
            ).values_list("id", flat=True)
        )
        target_scope_ids = {portal_scope.id, *app_scope_ids}

        output = StringIO()
        call_command("grant_initial_access", stdout=output)

        rows = UserAccess.objects.filter(user=self.user, scope_id__in=target_scope_ids)
        self.assertEqual(set(rows.values_list("scope_id", flat=True)), target_scope_ids)
        self.assertFalse(rows.exclude(status=UserAccess.Status.ALLOWED, role="viewer").exists())
        self.assertEqual(
            AccessAuditLog.objects.filter(
                target_user=self.user,
                scope_id__in=target_scope_ids,
                action=AccessAuditLog.Actions.GRANT,
                reason="초기 배포 전체 권한 부여",
            ).count(),
            len(target_scope_ids),
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.USER_ACCESS_UPDATE,
                after__marker="grant_initial_access",
                reason="초기 배포 전체 권한 부여 완료",
            ).exists()
        )
        self.assertIn("초기 접근 권한 부여를 완료", output.getvalue())

    def test_grant_initial_access_command_dry_run_does_not_write(self) -> None:
        """dry-run은 권한 row와 감사 로그를 생성하지 않아야 합니다."""

        before_access_count = UserAccess.objects.count()
        before_audit_count = AccessAuditLog.objects.count()
        output = StringIO()

        call_command("grant_initial_access", dry_run=True, stdout=output)

        self.assertEqual(UserAccess.objects.count(), before_access_count)
        self.assertEqual(AccessAuditLog.objects.count(), before_audit_count)
        self.assertIn("dryRun=True", output.getvalue())

    def test_grant_initial_access_command_preserves_existing_decisions_by_default(self) -> None:
        """초기 권한 부여 명령은 기본 실행에서 기존 결정을 덮어쓰지 않아야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        access = UserAccess.objects.create(
            scope=scope,
            user=self.user,
            status=UserAccess.Status.DENIED,
            role="viewer",
            reason="운영 전 수동 차단",
        )

        call_command("grant_initial_access", stdout=StringIO())

        access.refresh_from_db()
        self.assertEqual(access.status, UserAccess.Status.DENIED)
        self.assertEqual(access.reason, "운영 전 수동 차단")

    def test_grant_initial_access_command_can_overwrite_existing_decisions(self) -> None:
        """명시 옵션이 있으면 기존 pending/denied 상태도 allowed로 변경해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        access = UserAccess.objects.create(
            scope=scope,
            user=self.user,
            status=UserAccess.Status.DENIED,
            role="viewer",
            reason="운영 전 수동 차단",
        )

        call_command("grant_initial_access", overwrite_existing=True, stdout=StringIO())

        access.refresh_from_db()
        self.assertEqual(access.status, UserAccess.Status.ALLOWED)
        self.assertIsNone(access.reason)

    def test_grant_initial_access_command_skips_after_completion_marker(self) -> None:
        """초기 권한 부여 명령은 완료 marker가 있으면 다시 실행하지 않아야 합니다."""

        call_command("grant_initial_access", stdout=StringIO())

        User = get_user_model()
        later_user = User.objects.create_user(
            sabun=f"S{timezone.now().strftime('%H%M%S%f')}",
            password="test-password",
        )
        output = StringIO()
        call_command("grant_initial_access", stdout=output)

        self.assertIn("이미 완료되어 건너뜁니다", output.getvalue())
        self.assertFalse(UserAccess.objects.filter(user=later_user).exists())

    def test_grant_initial_access_command_force_ignores_completion_marker(self) -> None:
        """force 옵션은 완료 marker가 있어도 명시적으로 다시 실행해야 합니다."""

        call_command("grant_initial_access", stdout=StringIO())

        User = get_user_model()
        later_user = User.objects.create_user(
            sabun=f"S{timezone.now().strftime('%H%M%S%f')}",
            password="test-password",
        )
        output = StringIO()
        call_command("grant_initial_access", force=True, stdout=output)

        self.assertIn("초기 접근 권한 부여를 완료", output.getvalue())
        self.assertTrue(UserAccess.objects.filter(user=later_user).exists())

    def test_auth_me_does_not_create_access_row_for_current_affiliation(self) -> None:
        """auth_me 호출이 현재 소속 접근 권한 행을 백필하지 않는지 확인합니다."""
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=self.user,
                affiliation__user_sdwt_prod__iexact="group-a",
            ).exists()
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=self.user,
                affiliation__user_sdwt_prod__iexact="group-a",
            ).exists()
        )

    def test_account_affiliation_request_and_approval_flow(self) -> None:
        """소속 변경 요청과 승인 플로우가 정상 동작하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 소속 변경 요청 생성
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)

        create_response = self.client.post(
            reverse("account-affiliation"),
            data='{"department":"Dept","line":"L1","user_sdwt_prod":"group-b"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 202)
        change_id = create_response.json()["changeId"]

        # -----------------------------------------------------------------------------
        # 2) 요청 목록 조회
        # -----------------------------------------------------------------------------
        self.client.force_login(self.manager)
        list_response = self.client.get(reverse("account-affiliation-requests"))
        self.assertEqual(list_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 승인 요청
        # -----------------------------------------------------------------------------
        approve_response = self.client.post(
            reverse("account-affiliation-approve"),
            data='{"changeId": %d, "decision": "approve"}' % change_id,
            content_type="application/json",
        )
        self.assertEqual(approve_response.status_code, 200)

    def test_account_affiliation_post_ignores_effective_from_input(self) -> None:
        """사용자 소속 변경 API는 클라이언트 기준 시각 입력을 받지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 과거 기준 시각을 포함해 소속 변경 요청
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)
        requested_effective_from = timezone.now() - timedelta(days=30)
        before = timezone.now()

        create_response = self.client.post(
            reverse("account-affiliation"),
            data=(
                '{"department":"Dept","line":"L1","user_sdwt_prod":"group-b",'
                '"effectiveFrom":"%s"}' % requested_effective_from.isoformat()
            ),
            content_type="application/json",
        )
        after = timezone.now()

        # -----------------------------------------------------------------------------
        # 2) 저장된 기준 시각은 요청 처리 시각인지 확인
        # -----------------------------------------------------------------------------
        self.assertEqual(create_response.status_code, 202)
        change = UserSdwtProdChange.objects.get(id=create_response.json()["changeId"])
        self.assertGreaterEqual(change.effective_from, before)
        self.assertLessEqual(change.effective_from, after)

    def test_account_affiliation_rejection_reason_is_exposed(self) -> None:
        """거절 사유가 히스토리에 노출되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 소속 변경 요청 생성
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)

        create_response = self.client.post(
            reverse("account-affiliation"),
            data='{"department":"Dept","line":"L1","user_sdwt_prod":"group-b"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 202)
        change_id = create_response.json()["changeId"]

        # -----------------------------------------------------------------------------
        # 2) 관리자 거절 처리(거절 사유 포함)
        # -----------------------------------------------------------------------------
        self.client.force_login(self.manager)
        reject_response = self.client.post(
            reverse("account-affiliation-approve"),
            data='{"changeId": %d, "decision": "reject", "rejectionReason": "사유 확인 필요"}'
            % change_id,
            content_type="application/json",
        )
        self.assertEqual(reject_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 요청자 히스토리 확인
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)
        overview_response = self.client.get(reverse("account-overview"))
        self.assertEqual(overview_response.status_code, 200)
        history = overview_response.json()["affiliationHistory"]
        self.assertTrue(history)
        self.assertEqual(history[0]["status"], "REJECTED")
        self.assertEqual(history[0]["rejectionReason"], "사유 확인 필요")

    def test_account_affiliation_rejects_non_string_user_sdwt_prod(self) -> None:
        """user_sdwt_prod 타입 오류는 400을 반환해야 합니다."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("account-affiliation"),
            data='{"department":"Dept","line":"L1","user_sdwt_prod":123}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "user_sdwt_prod is required")

    def test_account_affiliation_reconfirm(self) -> None:
        """소속 재확인 플로우가 정상 응답하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 외부 예측/재확인 데이터 준비
        # -----------------------------------------------------------------------------
        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50000",
            predicted_user_sdwt_prod="group-b",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )
        current_affiliation = UserCurrentAffiliation.objects.get(user=self.user)
        current_affiliation.requires_reconfirm = True
        current_affiliation.save(update_fields=["requires_reconfirm"])

        # -----------------------------------------------------------------------------
        # 2) 상태 조회
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)

        status_response = self.client.get(reverse("account-affiliation-reconfirm"))
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.json()["requiresReconfirm"])

        # -----------------------------------------------------------------------------
        # 3) 재확인 응답 전송
        # -----------------------------------------------------------------------------
        confirm_response = self.client.post(
            reverse("account-affiliation-reconfirm"),
            data='{"accepted": true, "user_sdwt_prod": "group-b"}',
            content_type="application/json",
        )
        self.assertEqual(confirm_response.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=self.user), "group-b")
        self.assertFalse(UserCurrentAffiliation.objects.get(user=self.user).requires_reconfirm)

    def test_account_affiliation_reconfirm_requires_flag(self) -> None:
        """재확인 플래그가 없으면 409를 반환하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 외부 예측 데이터 준비
        # -----------------------------------------------------------------------------
        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50000",
            predicted_user_sdwt_prod="group-b",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        # -----------------------------------------------------------------------------
        # 2) 재확인 응답 전송
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)
        confirm_response = self.client.post(
            reverse("account-affiliation-reconfirm"),
            data='{"accepted": true, "user_sdwt_prod": "group-b"}',
            content_type="application/json",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(confirm_response.status_code, 409)
        self.assertEqual(confirm_response.json().get("error"), "reconfirm not required")

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    def test_account_external_sync_and_grants(self) -> None:
        """외부 동기화/권한 부여 흐름을 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 외부 소속 동기화 호출
        # -----------------------------------------------------------------------------
        sync_response = self.client.post(
            reverse("account-external-affiliation-sync"),
            data='{"records":[{"knox_id":"knox-50000","department":"Dept","user_sdwt_prod":"group-a"}]}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(sync_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 2) 매니저 권한 부여 및 조회
        # -----------------------------------------------------------------------------
        self.client.force_login(self.manager)
        grant_response = self.client.post(
            reverse("account-access-grant"),
            data='{"user_sdwt_prod":"group-a","userId":%d,"action":"grant","role":"member"}' % self.user.id,
            content_type="application/json",
        )
        self.assertEqual(grant_response.status_code, 200)

        manageable = self.client.get(reverse("account-access-manageable"))
        self.assertEqual(manageable.status_code, 200)

    def test_viewer_grant_for_current_affiliation_upgrades_to_member(self) -> None:
        """현재 소속에 viewer 권한을 부여하면 member로 승급되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 대상 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        target = User.objects.create_user(
            sabun="S50003",
            password="test-password",
            knox_id="knox-50003",
        )
        _set_current_affiliation(target, user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 2) viewer 부여 요청
        # -----------------------------------------------------------------------------
        self.client.force_login(self.manager)
        grant_response = self.client.post(
            reverse("account-access-grant"),
            data='{"user_sdwt_prod":"group-a","userId":%d,"action":"grant","role":"viewer"}'
            % target.id,
            content_type="application/json",
        )
        self.assertEqual(grant_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        access = UserSdwtProdAccess.objects.get(
            user=target,
            affiliation__user_sdwt_prod__iexact="group-a",
        )
        self.assertEqual(access.role, "member")

    def test_revoke_current_affiliation_is_blocked(self) -> None:
        """현재 소속에 대한 권한 회수는 거부되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 대상 사용자/권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        target = User.objects.create_user(
            sabun="S50004",
            password="test-password",
            knox_id="knox-50004",
        )
        _set_current_affiliation(target, user_sdwt_prod="group-a")
        _grant_access(user=target, user_sdwt_prod="group-a", role="member")

        # -----------------------------------------------------------------------------
        # 2) 회수 요청
        # -----------------------------------------------------------------------------
        self.client.force_login(self.manager)
        revoke_response = self.client.post(
            reverse("account-access-grant"),
            data='{"user_sdwt_prod":"group-a","userId":%d,"action":"revoke"}' % target.id,
            content_type="application/json",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(revoke_response.status_code, 400)
        self.assertEqual(
            revoke_response.json().get("error"),
            "Cannot revoke access for the user's current affiliation",
        )

    def test_account_affiliation_members_uses_account_domain(self) -> None:
        """소속 멤버 조회가 emails 정보 없이 account 소속/권한 기준으로 동작해야 합니다."""

        User = get_user_model()
        member = User.objects.create_user(
            sabun="S50008",
            password="test-password",
            knox_id="knox-50008",
            username="소속멤버",
        )
        _set_current_affiliation(member, user_sdwt_prod="group-a")

        viewer = User.objects.create_user(
            sabun="S50009",
            password="test-password",
            knox_id="knox-50009",
            username="권한멤버",
        )
        _grant_access(user=viewer, user_sdwt_prod="group-a", role="viewer")

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("account-affiliation-members"),
            {"user_sdwt_prod": "group-a"},
        )

        self.assertEqual(response.status_code, 200)
        rows = response.json()["members"]
        user_ids = {row["userId"] for row in rows}
        self.assertIn(member.id, user_ids)
        self.assertIn(viewer.id, user_ids)
        self.assertNotIn("emailCount", rows[0])


class AffiliationSelectorTests(TestCase):
    """소속 셀렉터 로직을 검증합니다."""

    def test_list_affiliation_options_orders_rows(self) -> None:
        """소속 옵션이 정렬된 순서로 반환되는지 확인합니다."""
        _affiliation(department="DeptB", line="L2", user_sdwt_prod="S3")
        _affiliation(department="DeptA", line="L2", user_sdwt_prod="S2")
        _affiliation(department="DeptA", line="L1", user_sdwt_prod="S1")

        rows = list_affiliation_options()
        self.assertEqual(
            rows,
            [
                {"department": "DeptA", "line": "L1", "user_sdwt_prod": "S1"},
                {"department": "DeptA", "line": "L2", "user_sdwt_prod": "S2"},
                {"department": "DeptB", "line": "L2", "user_sdwt_prod": "S3"},
            ],
        )

    def test_list_line_sdwt_pairs_filters_and_orders(self) -> None:
        """station_master에 존재하는 라인-소속 쌍만 정렬 반환되는지 확인합니다."""
        Affiliation.objects.bulk_create(
            [
                Affiliation(department="DeptA", line="L1", user_sdwt_prod="S1"),
                Affiliation(department="DeptB", line="L1", user_sdwt_prod="S2"),
                Affiliation(department="DeptA", line="L2", user_sdwt_prod="S0"),
                Affiliation(department="DeptA", line="L3", user_sdwt_prod=""),
            ],
            ignore_conflicts=True,
        )

        with patch(
            "api.account.selectors.station_master_selectors.list_distinct_sdwt_prod_lookup_values",
            return_value={"S1", "S2"},
        ):
            rows = list_line_sdwt_pairs()

        self.assertEqual(
            rows,
            [
                {"line_id": "L1", "user_sdwt_prod": "S1"},
                {"line_id": "L1", "user_sdwt_prod": "S2"},
            ],
        )

    def test_list_line_sdwt_pairs_returns_empty_without_station_match(self) -> None:
        """station_master 매칭 값이 없으면 선택지를 반환하지 않습니다."""
        _affiliation(department="DeptA", line="L1", user_sdwt_prod="S1")

        with patch(
            "api.account.selectors.station_master_selectors.list_distinct_sdwt_prod_lookup_values",
            return_value=set(),
        ):
            rows = list_line_sdwt_pairs()

        self.assertEqual(rows, [])


class AccessibleUserSdwtProdTests(TestCase):
    """사용자 접근 가능한 user_sdwt_prod 계산을 검증합니다."""

    def test_pending_change_not_included_when_no_current_affiliation(self) -> None:
        """현재 소속이 없고 승인 대기 상태라도 접근 목록은 비어 있어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S42000",
            password="test-password",
            knox_id="knox-42000",
        )

        UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod=None,
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        accessible = get_accessible_user_sdwt_prods_for_user(user)
        self.assertEqual(accessible, set())

    def test_pending_change_ignored_when_current_affiliation_exists(self) -> None:
        """현재 소속이 있으면 대기 변경이 제외되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S42001",
            password="test-password",
            knox_id="knox-42001",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-old")

        UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        accessible = get_accessible_user_sdwt_prods_for_user(user)
        self.assertIn("group-old", accessible)
        self.assertNotIn("group-new", accessible)


class AffiliationChangeApprovalTests(TestCase):
    """소속 변경 승인 로직을 검증합니다."""

    def test_member_can_approve_and_preserves_effective_from(self) -> None:
        """대상 소속 멤버 승인 시 적용 시각을 유지하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/승인자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10000",
            password="test-password",
            knox_id="knox-10000",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")

        member = User.objects.create_user(
            sabun="S20000",
            password="test-password",
            knox_id="knox-20000",
        )
        _set_current_affiliation(member, user_sdwt_prod="group-new")
        _grant_access(user=member, user_sdwt_prod="group-new", role="member")

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        past = timezone.now() - timedelta(days=7)
        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=past,
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 승인 처리 실행
        # -----------------------------------------------------------------------------
        _payload, status_code = approve_affiliation_change(approver=member, change_id=change.id)

        # -----------------------------------------------------------------------------
        # 4) 승인 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        change.refresh_from_db()
        requester.refresh_from_db()

        self.assertEqual(get_current_user_sdwt_prod(user=requester), "group-new")
        self.assertTrue(change.approved)
        self.assertTrue(change.applied)
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)
        self.assertEqual(change.approved_by_id, member.id)
        self.assertIsNotNone(change.approved_at)
        self.assertEqual(change.effective_from, past)

    def test_non_member_cannot_approve(self) -> None:
        """대상 소속 멤버가 아니면 승인할 수 없음을 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 요청자/비관리자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10001",
            password="test-password",
            knox_id="knox-10001",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")

        other = User.objects.create_user(
            sabun="S30000",
            password="test-password",
            knox_id="knox-30000",
        )
        _set_current_affiliation(other, user_sdwt_prod="group-other")

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now() - timedelta(days=1),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 승인 시도 및 결과 검증
        # -----------------------------------------------------------------------------
        _payload, status_code = approve_affiliation_change(approver=other, change_id=change.id)
        self.assertEqual(status_code, 403)
        requester.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=requester), "group-old")


class AffiliationChangeSelectorTests(TestCase):
    """소속 변경 셀렉터 동작을 검증합니다."""

    def test_resolve_user_affiliation_ignores_unapproved_change(self) -> None:
        """미승인 변경은 현재 소속 계산에 반영되지 않아야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S40000",
            password="test-password",
            knox_id="knox-40000",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now() - timedelta(days=1),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
        )

        affiliation = resolve_user_affiliation(user, timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-a")

    def test_get_next_user_sdwt_prod_change_ignores_unapproved_change(self) -> None:
        """다음 변경 조회에서 미승인 변경은 제외되어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S40001",
            password="test-password",
            knox_id="knox-40001",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        now = timezone.now()
        UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-b",
            effective_from=now + timedelta(days=1),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
        )

        approved_change = UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-c",
            effective_from=now + timedelta(days=2),
            status=UserSdwtProdChange.Status.APPROVED,
            applied=True,
            approved=True,
        )

        next_change = get_next_user_sdwt_prod_change(user=user, effective_from=now)
        self.assertIsNotNone(next_change)
        self.assertEqual(next_change.id, approved_change.id)


class AffiliationChangeRequestListTests(TestCase):
    """소속 변경 요청 목록 조회를 검증합니다."""

    def test_manager_only_sees_manageable_groups(self) -> None:
        """관리자는 관리 가능한 그룹만 조회해야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 관리자/요청자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        manager = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            knox_id="knox-90000",
        )
        _grant_access(user=manager, user_sdwt_prod="group-a", role="manager")

        requester_a = User.objects.create_user(
            sabun="S90001",
            password="test-password",
            knox_id="knox-90001",
        )
        requester_b = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            knox_id="knox-90002",
        )

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change_a = UserSdwtProdChange.objects.create(
            user=requester_a,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester_a,
        )
        UserSdwtProdChange.objects.create(
            user=requester_b,
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester_b,
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출
        # -----------------------------------------------------------------------------
        payload, status_code = get_affiliation_change_requests(
            user=manager,
            status="pending",
            search=None,
            user_sdwt_prod=None,
            page=1,
            page_size=20,
        )

        # -----------------------------------------------------------------------------
        # 4) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        ids = [entry["id"] for entry in payload["results"]]
        self.assertIn(change_a.id, ids)
        self.assertEqual(len(ids), 1)
        self.assertEqual(payload["results"][0]["role"], "manager")

    def test_manager_filters_manageable_groups_case_insensitively(self) -> None:
        """관리 그룹 필터가 user_sdwt_prod 대소문자를 구분하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 관리자/요청자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        manager = User.objects.create_user(
            sabun="S90010",
            password="test-password",
            knox_id="knox-90010",
        )
        _grant_access(user=manager, user_sdwt_prod="GROUP-A", role="manager")

        requester = User.objects.create_user(
            sabun="S90011",
            password="test-password",
            knox_id="knox-90011",
        )

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=requester,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 결과 검증
        # -----------------------------------------------------------------------------
        payload, status_code = get_affiliation_change_requests(
            user=manager,
            status="pending",
            search=None,
            user_sdwt_prod="group-a",
            page=1,
            page_size=20,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual([entry["id"] for entry in payload["results"]], [change.id])

    def test_search_filters_by_sabun(self) -> None:
        """검색 조건이 사번 필터에 적용되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 관리자/요청자 및 권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        manager = User.objects.create_user(
            sabun="S91000",
            password="test-password",
            knox_id="knox-91000",
        )
        _grant_access(user=manager, user_sdwt_prod="group-c", role="manager")

        requester = User.objects.create_user(
            sabun="S91001",
            password="test-password",
            knox_id="knox-91001",
        )

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=requester,
            to_user_sdwt_prod="group-c",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출
        # -----------------------------------------------------------------------------
        payload, status_code = get_affiliation_change_requests(
            user=manager,
            status="pending",
            search="S91001",
            user_sdwt_prod=None,
            page=1,
            page_size=20,
        )

        # -----------------------------------------------------------------------------
        # 4) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["results"][0]["id"], change.id)
        self.assertEqual(payload["results"][0]["user"]["sabun"], "S91001")
        self.assertEqual(payload["results"][0]["role"], "manager")

    def test_non_manager_is_forbidden(self) -> None:
        """비관리자는 요청 목록 조회가 거부되어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S92000",
            password="test-password",
            knox_id="knox-92000",
        )

        payload, status_code = get_affiliation_change_requests(
            user=user,
            status="pending",
            search=None,
            user_sdwt_prod=None,
            page=1,
            page_size=20,
        )

        self.assertEqual(status_code, 403)
        self.assertEqual(payload["error"], "forbidden")

    def test_non_manager_can_view_own_group_requests(self) -> None:
        """비관리자는 자신의 그룹 요청만 조회 가능해야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 요청자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S93000",
            password="test-password",
            knox_id="knox-93000",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-own")
        _grant_access(user=requester, user_sdwt_prod="group-own", role="member")

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=requester,
            to_user_sdwt_prod="group-own",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출
        # -----------------------------------------------------------------------------
        payload, status_code = get_affiliation_change_requests(
            user=requester,
            status="pending",
            search=None,
            user_sdwt_prod="group-own",
            page=1,
            page_size=20,
        )

        # -----------------------------------------------------------------------------
        # 4) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["results"][0]["id"], change.id)
        self.assertEqual(payload["results"][0]["role"], "member")


class AffiliationChangeRequestEffectiveFromTests(TestCase):
    """소속 변경 요청 서비스 로직을 검증합니다."""

    def test_request_affiliation_change_respects_effective_from_for_all(self) -> None:
        """요청 시각이 관리자/일반 사용자 모두에 적용되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50000",
            password="test-password",
            knox_id="knox-50000",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-old")
        approver = User.objects.create_user(
            sabun="S50010",
            password="test-password",
            knox_id="knox-50010",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-new")
        _grant_access(user=approver, user_sdwt_prod="group-new", role="member")

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-new")
        requested_effective_from = timezone.now() - timedelta(days=30)

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=requested_effective_from,
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)
        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.effective_from, requested_effective_from)
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)


class AccountOverviewTests(TestCase):
    """계정 개요 응답을 검증합니다."""

    def test_account_overview_includes_profile_history_and_groups(self) -> None:
        """프로필/소속 이력/관리 그룹 정보 포함을 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/프로필/권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            knox_id="knox-90000",
        )
        user.username = "Tester"
        user.knox_id = "KNOX-90000"
        _set_current_affiliation(user, user_sdwt_prod="group-a")
        user.save(update_fields=["username", "knox_id"])

        profile, _created = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.Roles.MANAGER
        profile.save(update_fields=["role"])
        _grant_access(user=user, user_sdwt_prod="group-b", role="manager")

        # -----------------------------------------------------------------------------
        # 2) 변경 이력 준비
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-a",
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.APPROVED,
            applied=True,
            approved=True,
            created_by=user,
            approved_by=user,
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 결과 검증
        # -----------------------------------------------------------------------------
        payload = get_account_overview(user=user, timezone_name="Asia/Seoul")

        self.assertEqual(payload["user"]["role"], UserProfile.Roles.MANAGER)
        self.assertTrue(payload["affiliationHistory"])
        self.assertEqual(payload["affiliationHistory"][0]["id"], change.id)
        self.assertIn("manageableGroups", payload)
        self.assertNotIn("mailboxAccess", payload)

    def test_account_overview_collapses_accessible_groups_case_insensitively(self) -> None:
        """개요 응답의 접근 가능 그룹이 대소문자 비구분으로 중복 제거되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/접근 권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S90010",
            password="test-password",
            knox_id="knox-90010",
        )
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")
        _grant_access(user=user, user_sdwt_prod="group-a", role="member")
        _grant_access(user=user, user_sdwt_prod="group-b", role="manager")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        payload = get_account_overview(user=user, timezone_name="Asia/Seoul")

        accessible_rows = payload["affiliation"]["accessibleUserSdwtProds"]
        normalized_groups = {row["userSdwtProd"].casefold() for row in accessible_rows}

        self.assertEqual(len(accessible_rows), 2)
        self.assertEqual(normalized_groups, {"group-a", "group-b"})

        group_a_row = next(
            row for row in accessible_rows if isinstance(row["userSdwtProd"], str) and row["userSdwtProd"].casefold() == "group-a"
        )
        self.assertEqual(group_a_row["source"], "self")

    def test_request_affiliation_change_defaults_to_request_time(self) -> None:
        """effective_from이 없으면 요청 시각이 사용되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50001",
            password="test-password",
            is_staff=True,
            knox_id="knox-50001",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-old")
        approver = User.objects.create_user(
            sabun="S50011",
            password="test-password",
            knox_id="knox-50011",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-new")
        _grant_access(user=approver, user_sdwt_prod="group-new", role="member")

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-new")

        before = timezone.now()
        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=None,
            timezone_name="Asia/Seoul",
        )
        after = timezone.now()

        self.assertEqual(status_code, 202)
        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertGreaterEqual(change.effective_from, before)
        self.assertLessEqual(change.effective_from, after)
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)


class AffiliationOverviewTests(TestCase):
    """소속 개요 응답을 검증합니다."""

    def test_get_affiliation_overview_does_not_create_access_row(self) -> None:
        """개요 조회가 접근 권한 행을 생성하지 않는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S60000",
            password="test-password",
            knox_id="knox-60000",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        self.assertEqual(UserSdwtProdAccess.objects.count(), 0)
        payload = get_affiliation_overview(user=user, timezone_name="Asia/Seoul")
        self.assertEqual(UserSdwtProdAccess.objects.count(), 0)

        self.assertEqual(payload["currentUserSdwtProd"], "group-a")
        self.assertEqual(payload["accessibleUserSdwtProds"][0]["userSdwtProd"], "group-a")

    def test_get_affiliation_overview_includes_external_snapshot(self) -> None:
        """외부 소속 스냅샷 값이 개요 응답에 포함되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S60001",
            password="test-password",
            knox_id="knox-60001",
        )

        now = timezone.now()
        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-60001",
            department="Dept-External",
            predicted_user_sdwt_prod="group-external",
            source_updated_at=now,
            last_seen_at=now,
        )

        payload = get_affiliation_overview(user=user, timezone_name="Asia/Seoul")

        self.assertEqual(payload["snapshotUserSdwtProd"], "group-external")
        self.assertEqual(payload["snapshotDepartment"], "Dept-External")

    def test_get_affiliation_overview_uses_sso_department_without_snapshot(self) -> None:
        """외부 스냅샷이 없으면 SSO department를 개요 응답에 사용합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S60002",
            password="test-password",
            knox_id="knox-60002",
        )
        user.department = "Dept-SSO"
        user.save(update_fields=["department"])

        payload = get_affiliation_overview(user=user, timezone_name="Asia/Seoul")

        self.assertEqual(payload["currentDepartment"], "Dept-SSO")
        self.assertIsNone(payload["snapshotUserSdwtProd"])
        self.assertEqual(payload["snapshotDepartment"], "Dept-SSO")


class AffiliationChangeRequestTests(TestCase):
    """소속 변경 요청을 검증합니다."""

    def test_request_affiliation_change_creates_pending_when_approver_exists(self) -> None:
        """승인자가 있으면 첫 소속 변경 요청은 승인 대기 상태로 생성되어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50001",
            password="test-password",
            knox_id="knox-50001",
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-new")
        approver = User.objects.create_user(
            sabun="S50012",
            password="test-password",
            knox_id="knox-50012",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-new")
        _grant_access(user=approver, user_sdwt_prod="group-new", role="member")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now() - timedelta(days=30),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)

        user.refresh_from_db()
        self.assertIsNone(get_current_user_sdwt_prod(user=user))

        change = UserSdwtProdChange.objects.get(user=user, to_user_sdwt_prod="group-new")
        self.assertFalse(change.approved)
        self.assertFalse(change.applied)
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)

    def test_request_affiliation_change_rejects_same_as_current(self) -> None:
        """현재 소속과 동일한 값으로 요청하면 거절되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50010",
            password="test-password",
            knox_id="knox-50010",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-a")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "already current affiliation")
        self.assertFalse(UserSdwtProdChange.objects.filter(user=user).exists())

    def test_request_affiliation_change_rejects_same_as_current_case_insensitively(self) -> None:
        """현재 소속과 대소문자만 다른 값으로 요청해도 거절되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50013",
            password="test-password",
            knox_id="knox-50013",
        )
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-a")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "already current affiliation")
        self.assertFalse(UserSdwtProdChange.objects.filter(user=user).exists())

    def test_request_affiliation_change_creates_pending_when_no_approver_and_no_prediction(self) -> None:
        """승인자가 없어도 예측 소속이 없으면 승인 대기가 생성되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50020",
            password="test-password",
            knox_id="knox-50020",
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-auto")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-auto",
            effective_from=timezone.now() - timedelta(days=30),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(payload["status"], "pending")

        user.refresh_from_db()
        self.assertIsNone(get_current_user_sdwt_prod(user=user))

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)
        self.assertFalse(change.approved)
        self.assertFalse(change.applied)

    def test_request_affiliation_change_auto_applies_when_predicted_match(self) -> None:
        """예측 소속과 일치하면 승인자 유무와 관계없이 자동 승인되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50021",
            password="test-password",
            knox_id="knox-50021",
        )

        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50021",
            predicted_user_sdwt_prod="group-auto",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-auto")

        approver = User.objects.create_user(
            sabun="S50022",
            password="test-password",
            knox_id="knox-50022",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-auto")
        _grant_access(user=approver, user_sdwt_prod="group-auto", role="member")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-auto",
            effective_from=timezone.now() - timedelta(days=30),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "applied")

        user.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=user), "group-auto")

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)
        access = UserSdwtProdAccess.objects.get(
            user=user,
            affiliation__user_sdwt_prod__iexact="group-auto",
        )
        self.assertEqual(access.role, "member")

    def test_request_affiliation_change_auto_applies_when_predicted_match_case_insensitively(self) -> None:
        """예측 소속과 대소문자만 다른 요청도 자동 승인되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50023",
            password="test-password",
            knox_id="knox-50023",
        )

        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50023",
            predicted_user_sdwt_prod="GROUP-AUTO",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-auto")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-auto",
            effective_from=timezone.now() - timedelta(days=30),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "applied")

        user.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=user), "group-auto")

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)

    def test_request_affiliation_change_supersedes_pending_and_skips_auto_apply(self) -> None:
        """기존 pending이 있으면 대체하고 자동 승인을 건너뛰는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50002",
            password="test-password",
            knox_id="knox-50002",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-old")

        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50002",
            predicted_user_sdwt_prod="group-new",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        pending = UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-pending",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-new")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(payload["status"], "pending")

        pending.refresh_from_db()
        self.assertEqual(pending.status, UserSdwtProdChange.Status.SUPERSEDED)
        self.assertEqual(pending.rejection_reason, "취소(대체됨)")

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)
        self.assertFalse(change.approved)
        self.assertFalse(change.applied)

        user.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=user), "group-old")

    def test_member_can_approve_affiliation_change(self) -> None:
        """소속 멤버도 승인할 수 있는지 확인합니다."""
        User = get_user_model()
        approver = User.objects.create_user(
            sabun="S50003",
            password="test-password",
            knox_id="knox-50003",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-a")
        _grant_access(user=approver, user_sdwt_prod="group-a", role="member")

        requester = User.objects.create_user(
            sabun="S50004",
            password="test-password",
            knox_id="knox-50004",
        )

        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod=None,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        payload, status_code = approve_affiliation_change(approver=approver, change_id=change.id)
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "approved")

        change.refresh_from_db()
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)
        requester.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=requester), "group-a")


class ExternalAffiliationSyncTests(TestCase):
    """외부 소속 동기화/재확인 흐름을 검증합니다."""

    def test_sync_external_affiliations_stores_username_from_record(self) -> None:
        """외부 동기화 입력의 username을 스냅샷에 저장하는지 확인합니다."""

        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-username-1",
                    "username": "홍길동",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-username-1")
        self.assertEqual(result["created"], 1)
        self.assertEqual(snapshot.username, "홍길동")

    def test_sync_external_affiliations_does_not_use_account_user_username_when_record_missing(self) -> None:
        """입력 username이 없으면 account_user.username을 대신 저장하지 않습니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S70100",
            password="test-password",
            username="계정사용자",
            knox_id="loginid-ext-username-2",
        )

        sync_external_affiliations(
            records=[
                {
                    "knox_id": user.knox_id,
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-username-2")
        self.assertIsNone(snapshot.username)

    def test_sync_external_affiliations_keeps_username_when_record_omits_username(self) -> None:
        """기존 username은 입력 필드가 아예 없을 때 보존합니다."""

        updated_at = timezone.now()
        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-username-3",
            username="기존이름",
            department="Dept",
            predicted_user_sdwt_prod="group-a",
            source_updated_at=updated_at,
            last_seen_at=updated_at,
        )

        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-username-3",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": updated_at,
                }
            ]
        )

        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-username-3")
        self.assertEqual(result["unchanged"], 1)
        self.assertEqual(snapshot.username, "기존이름")

    def test_sync_external_affiliations_flags_user_on_change(self) -> None:
        """예측 소속 변경 시 재확인 플래그가 켜지는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70001", password="test-password")
        user.knox_id = "loginid-ext-1"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 2) 초기 동기화(변경 없음)
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-1",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": timezone.now(),
                }
            ]
        )
        user.refresh_from_db()
        self.assertFalse(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)

        # -----------------------------------------------------------------------------
        # 3) 변경 동기화 및 결과 검증
        # -----------------------------------------------------------------------------
        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-1",
                    "department": "Dept",
                    "user_sdwt_prod": "group-b",
                    "source_updated_at": timezone.now(),
                }
            ]
        )
        user.refresh_from_db()

        self.assertEqual(result["updated"], 1)
        self.assertTrue(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)

    def test_sync_external_affiliations_ignores_case_only_predicted_change(self) -> None:
        """예측 소속이 대소문자만 다르면 변경으로 보지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/스냅샷 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70009", password="test-password")
        user.knox_id = "loginid-ext-9"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        updated_at = timezone.now()
        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-9",
            department="Dept",
            predicted_user_sdwt_prod="GROUP-A",
            source_updated_at=updated_at,
            last_seen_at=updated_at,
        )

        # -----------------------------------------------------------------------------
        # 2) 동일 소속(대소문자만 다름) 동기화 호출
        # -----------------------------------------------------------------------------
        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-9",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": updated_at,
                }
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        user.refresh_from_db()
        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-9")

        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["unchanged"], 1)
        self.assertFalse(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)
        self.assertEqual(snapshot.predicted_user_sdwt_prod, "GROUP-A")

    def test_sync_external_affiliations_ignores_when_pending_exists(self) -> None:
        """대기 변경이 있으면 재확인 플래그를 켜지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/스냅샷/대기 요청 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70008", password="test-password")
        user.knox_id = "loginid-ext-8"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-8",
            predicted_user_sdwt_prod="group-a",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-a",
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        # -----------------------------------------------------------------------------
        # 2) 예측 변경 동기화 호출
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-8",
                    "department": "Dept",
                    "user_sdwt_prod": "group-b",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        user.refresh_from_db()
        self.assertFalse(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)

    def test_sync_external_affiliations_dedupes_knox_ids(self) -> None:
        """동일 knox_id가 중복되면 최신 값만 반영되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/스냅샷 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70003", password="test-password")
        user.knox_id = "loginid-ext-3"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-3",
            predicted_user_sdwt_prod="group-a",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        # -----------------------------------------------------------------------------
        # 2) 중복 knox_id 동기화 호출
        # -----------------------------------------------------------------------------
        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-3",
                    "department": "Dept",
                    "user_sdwt_prod": "group-b",
                    "source_updated_at": timezone.now(),
                },
                {
                    "knox_id": "loginid-ext-3",
                    "department": "Dept",
                    "user_sdwt_prod": "group-c",
                    "source_updated_at": timezone.now(),
                },
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(result["updated"], 1)
        user.refresh_from_db()
        self.assertTrue(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)
        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-3")
        self.assertEqual(snapshot.predicted_user_sdwt_prod, "group-c")

    def test_sync_external_affiliations_keeps_affiliation_options_app_managed(self) -> None:
        """외부 동기화가 앱 소속 옵션을 자동 생성하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사전 조건 확인
        # -----------------------------------------------------------------------------
        self.assertFalse(Affiliation.objects.filter(user_sdwt_prod="group-new").exists())

        # -----------------------------------------------------------------------------
        # 2) 외부 동기화 호출
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-9",
                    "department": "Dept",
                    "user_sdwt_prod": "group-new",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        option = Affiliation.objects.filter(user_sdwt_prod="group-new").first()
        self.assertIsNone(option)

    def test_sync_external_affiliations_reuses_affiliation_option_case_insensitively(self) -> None:
        """기존 소속 옵션이 대소문자만 다르면 중복 생성하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 기존 소속 옵션 준비
        # -----------------------------------------------------------------------------
        _affiliation(department="Dept", line="", user_sdwt_prod="GROUP-NEW")

        # -----------------------------------------------------------------------------
        # 2) 외부 동기화 호출
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-13",
                    "department": "Dept",
                    "user_sdwt_prod": "group-new",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(Affiliation.objects.filter(user_sdwt_prod__iexact="group-new").count(), 1)
        option = Affiliation.objects.get(user_sdwt_prod__iexact="group-new")
        self.assertEqual(option.user_sdwt_prod, "GROUP-NEW")

    def test_sync_external_affiliations_does_not_create_majority_affiliation(self) -> None:
        """외부 스냅샷 department 다수결로 앱 소속 옵션을 만들지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사전 조건 확인
        # -----------------------------------------------------------------------------
        self.assertFalse(Affiliation.objects.filter(user_sdwt_prod="group-major").exists())

        # -----------------------------------------------------------------------------
        # 2) 외부 동기화 호출(DeptA 2회, DeptB 1회)
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-10",
                    "department": "DeptA",
                    "user_sdwt_prod": "group-major",
                    "source_updated_at": timezone.now(),
                },
                {
                    "knox_id": "loginid-ext-11",
                    "department": "DeptA",
                    "user_sdwt_prod": "group-major",
                    "source_updated_at": timezone.now(),
                },
                {
                    "knox_id": "loginid-ext-12",
                    "department": "DeptB",
                    "user_sdwt_prod": "group-major",
                    "source_updated_at": timezone.now(),
                },
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        option = Affiliation.objects.filter(user_sdwt_prod="group-major").first()
        self.assertIsNone(option)

    def test_reconfirm_response_auto_approves(self) -> None:
        """재확인 응답이 자동 승인으로 적용되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/소속 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70002", password="test-password")
        user.knox_id = "loginid-ext-2"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(
            user,
            user_sdwt_prod="group-old",
            requires_reconfirm=True,
        )

        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-old")
        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 2) 외부 동기화 및 재확인 요청
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-2",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        payload, status_code = submit_affiliation_reconfirm_response(
            user=user,
            accepted=True,
            user_sdwt_prod="group-a",
            timezone_name="Asia/Seoul",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "applied")

        user.refresh_from_db()
        values = UserCurrentAffiliation.objects.get(user=user)
        self.assertEqual(values.affiliation.user_sdwt_prod, "group-a")
        self.assertFalse(values.requires_reconfirm)

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)

    def test_reconfirm_response_creates_pending_on_mismatch(self) -> None:
        """재확인 응답이 예측값과 불일치하면 승인 대기를 생성하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/소속/스냅샷 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70006", password="test-password")
        user.knox_id = "loginid-ext-6"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(
            user,
            user_sdwt_prod="group-a",
            requires_reconfirm=True,
        )

        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-a")
        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-b")
        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-6",
            predicted_user_sdwt_prod="group-a",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        # -----------------------------------------------------------------------------
        # 2) 재확인 응답(불일치) 제출
        # -----------------------------------------------------------------------------
        payload, status_code = submit_affiliation_reconfirm_response(
            user=user,
            accepted=True,
            user_sdwt_prod="group-b",
            timezone_name="Asia/Seoul",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 202)
        self.assertEqual(payload["status"], "pending")

        user.refresh_from_db()
        self.assertFalse(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)

    def test_reconfirm_response_keeps_current_affiliation(self) -> None:
        """재확인에서 기존 소속 유지를 선택하면 플래그만 해제되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70004", password="test-password")
        user.knox_id = "loginid-ext-4"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(
            user,
            user_sdwt_prod="group-x",
            requires_reconfirm=True,
        )

        # -----------------------------------------------------------------------------
        # 2) 재확인 유지 응답
        # -----------------------------------------------------------------------------
        payload, status_code = submit_affiliation_reconfirm_response(
            user=user,
            accepted=False,
            user_sdwt_prod=None,
            timezone_name="Asia/Seoul",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "kept")

        user.refresh_from_db()
        values = UserCurrentAffiliation.objects.get(user=user)
        self.assertEqual(values.affiliation.user_sdwt_prod, "group-x")
        self.assertFalse(values.requires_reconfirm)

    def test_reconfirm_response_keeps_current_affiliation_case_insensitively(self) -> None:
        """재확인에서 현재 소속과 대소문자만 다른 선택을 해도 유지 처리되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70010", password="test-password")
        user.knox_id = "loginid-ext-10"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(
            user,
            user_sdwt_prod="GROUP-X",
            requires_reconfirm=True,
        )

        # -----------------------------------------------------------------------------
        # 2) 재확인 응답
        # -----------------------------------------------------------------------------
        payload, status_code = submit_affiliation_reconfirm_response(
            user=user,
            accepted=True,
            user_sdwt_prod="group-x",
            timezone_name="Asia/Seoul",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "kept")

        user.refresh_from_db()
        values = UserCurrentAffiliation.objects.get(user=user)
        self.assertEqual(values.affiliation.user_sdwt_prod, "GROUP-X")
        self.assertFalse(values.requires_reconfirm)

    def test_auto_approve_affiliation_from_snapshot(self) -> None:
        """외부 스냅샷 기반 자동 승인이 적용되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 소속/스냅샷 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-auto")
        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-auto-1",
            predicted_user_sdwt_prod="group-auto",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        # -----------------------------------------------------------------------------
        # 2) 사용자 생성 및 자동 승인 호출
        # -----------------------------------------------------------------------------
        user = User.objects.create_user(sabun="S70005", password="test-password")
        user.knox_id = "loginid-auto-1"
        user.save(update_fields=["knox_id"])

        result = auto_approve_affiliation_from_snapshot(user=user, timezone_name="Asia/Seoul")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertIsNotNone(result)
        payload, status_code = result or ({}, 0)
        self.assertEqual(status_code, 200)
        self.assertEqual(payload.get("status"), "applied")

        user.refresh_from_db()
        values = UserCurrentAffiliation.objects.get(user=user)
        self.assertEqual(values.affiliation.user_sdwt_prod, "group-auto")
        self.assertFalse(values.requires_reconfirm)


class AccountProfileAccessServiceTests(TestCase):
    """프로필/접근 권한 서비스 로직을 검증합니다."""

    def test_ensure_user_profile_creates_and_reuses(self) -> None:
        """ensure_user_profile이 프로필을 생성하고 재사용하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S80001", password="test-password")

        # -----------------------------------------------------------------------------
        # 2) 프로필 생성 및 재호출
        # -----------------------------------------------------------------------------
        profile = ensure_user_profile(user)
        profile_again = ensure_user_profile(user)

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertIsNotNone(profile)
        self.assertEqual(profile.id, profile_again.id)
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_ensure_self_access_normalizes_user_sdwt_prod(self) -> None:
        """ensure_self_access가 user_sdwt_prod 공백을 정규화하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S80002", password="test-password")
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 2) 접근 권한 보장
        # -----------------------------------------------------------------------------
        access = ensure_self_access(user, role="member")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertIsNotNone(access)
        self.assertEqual(access.user_sdwt_prod, "group-a")
        self.assertEqual(
            UserSdwtProdAccess.objects.filter(
                user=user,
                affiliation__user_sdwt_prod__iexact="group-a",
            ).count(),
            1,
        )

    def test_ensure_self_access_reuses_existing_row_case_insensitively(self) -> None:
        """기존 접근 권한 행이 대소문자만 다르면 재사용하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/기존 접근 권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S80003", password="test-password")
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")

        existing = _grant_access(
            user=user,
            user_sdwt_prod="group-a",
            role="viewer",
        )

        # -----------------------------------------------------------------------------
        # 2) 접근 권한 보장
        # -----------------------------------------------------------------------------
        access = ensure_self_access(user, role="member")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertIsNotNone(access)
        self.assertEqual(access.id, existing.id)
        self.assertEqual(access.role, "member")
        self.assertEqual(
            UserSdwtProdAccess.objects.filter(
                user=user,
                affiliation__user_sdwt_prod__iexact="group-a",
            ).count(),
            1,
        )


class AccountSelectorEmailTests(TestCase):
    """계정 이메일 셀렉터 동작을 검증합니다."""

    def test_list_active_user_emails_deduplicates_and_filters_invalid_values(self) -> None:
        """활성 사용자 이메일 목록이 중복 제거/공백 제거되어 반환되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user_a = User.objects.create_user(sabun="S82001", password="test-password")
        user_a.email = "dup@example.com"
        user_a.save(update_fields=["email"])
        _set_current_affiliation(user_a, user_sdwt_prod="group-a")

        user_b = User.objects.create_user(sabun="S82002", password="test-password")
        user_b.email = " dup@example.com "
        user_b.save(update_fields=["email"])
        _set_current_affiliation(user_b, user_sdwt_prod="group-a")

        user_c = User.objects.create_user(sabun="S82003", password="test-password")
        user_c.email = "other@example.com"
        user_c.save(update_fields=["email"])
        _set_current_affiliation(user_c, user_sdwt_prod="group-a")

        user_inactive = User.objects.create_user(sabun="S82004", password="test-password")
        user_inactive.email = "inactive@example.com"
        user_inactive.is_active = False
        user_inactive.save(update_fields=["email", "is_active"])
        _set_current_affiliation(user_inactive, user_sdwt_prod="group-a")

        user_blank = User.objects.create_user(sabun="S82005", password="test-password")
        user_blank.email = "   "
        user_blank.save(update_fields=["email"])
        _set_current_affiliation(user_blank, user_sdwt_prod="group-a")

        user_other_group = User.objects.create_user(sabun="S82006", password="test-password")
        user_other_group.email = "group-b@example.com"
        user_other_group.save(update_fields=["email"])
        _set_current_affiliation(user_other_group, user_sdwt_prod="group-b")

        # -----------------------------------------------------------------------------
        # 2) 셀렉터 호출
        # -----------------------------------------------------------------------------
        emails = list_active_user_emails_by_user_sdwt_prod(user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(emails, ["dup@example.com", "other@example.com"])

    def test_list_active_user_emails_matches_user_sdwt_prod_case_insensitively(self) -> None:
        """활성 사용자 이메일 조회가 user_sdwt_prod 대소문자를 구분하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user = User.objects.create_user(sabun="S82007", password="test-password")
        user.email = "case@example.com"
        user.save(update_fields=["email"])
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")

        # -----------------------------------------------------------------------------
        # 2) 셀렉터 호출 및 결과 검증
        # -----------------------------------------------------------------------------
        emails = list_active_user_emails_by_user_sdwt_prod(user_sdwt_prod="group-a")
        self.assertEqual(emails, ["case@example.com"])

    def test_list_active_user_knox_ids_deduplicates_and_filters_invalid_values(self) -> None:
        """활성 사용자 knox_id 목록이 중복 제거/공백 제거되어 반환되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user_a = User.objects.create_user(sabun="S82011", password="test-password")
        user_a.knox_id = "knox-dup"
        user_a.save(update_fields=["knox_id"])
        _set_current_affiliation(user_a, user_sdwt_prod="group-a")

        user_b = User.objects.create_user(sabun="S82012", password="test-password")
        user_b.knox_id = " knox-dup "
        user_b.save(update_fields=["knox_id"])
        _set_current_affiliation(user_b, user_sdwt_prod="group-a")

        user_c = User.objects.create_user(sabun="S82013", password="test-password")
        user_c.knox_id = "knox-other"
        user_c.save(update_fields=["knox_id"])
        _set_current_affiliation(user_c, user_sdwt_prod="group-a")

        user_inactive = User.objects.create_user(sabun="S82014", password="test-password")
        user_inactive.knox_id = "knox-inactive"
        user_inactive.is_active = False
        user_inactive.save(update_fields=["knox_id", "is_active"])
        _set_current_affiliation(user_inactive, user_sdwt_prod="group-a")

        user_blank = User.objects.create_user(sabun="S82015", password="test-password")
        user_blank.knox_id = "   "
        user_blank.save(update_fields=["knox_id"])
        _set_current_affiliation(user_blank, user_sdwt_prod="group-a")

        user_other_group = User.objects.create_user(sabun="S82016", password="test-password")
        user_other_group.knox_id = "knox-group-b"
        user_other_group.save(update_fields=["knox_id"])
        _set_current_affiliation(user_other_group, user_sdwt_prod="group-b")

        # -----------------------------------------------------------------------------
        # 2) 셀렉터 호출
        # -----------------------------------------------------------------------------
        knox_ids = list_active_user_knox_ids_by_user_sdwt_prod(user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(knox_ids, ["knox-dup", "knox-other"])

    def test_list_active_user_knox_ids_matches_user_sdwt_prod_case_insensitively(self) -> None:
        """활성 사용자 knox_id 조회가 user_sdwt_prod 대소문자를 구분하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user = User.objects.create_user(sabun="S82017", password="test-password")
        user.knox_id = "knox-case"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")

        # -----------------------------------------------------------------------------
        # 2) 셀렉터 호출 및 결과 검증
        # -----------------------------------------------------------------------------
        knox_ids = list_active_user_knox_ids_by_user_sdwt_prod(user_sdwt_prod="group-a")
        self.assertEqual(knox_ids, ["knox-case"])
