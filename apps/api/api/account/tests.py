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

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from api.account.models import (
    Affiliation,
    ExternalAffiliationSnapshot,
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
    ensure_self_access,
    ensure_user_profile,
    get_account_overview,
    get_affiliation_change_requests,
    get_affiliation_overview,
    request_affiliation_change,
    submit_affiliation_reconfirm_response,
    sync_external_affiliations,
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
        self.user.save(update_fields=["knox_id"])
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
        """라인-소속 쌍이 필터링되고 정렬되는지 확인합니다."""
        Affiliation.objects.bulk_create(
            [
                Affiliation(department="DeptA", line="L1", user_sdwt_prod="S1"),
                Affiliation(department="DeptB", line="L1", user_sdwt_prod="S2"),
                Affiliation(department="DeptA", line="L2", user_sdwt_prod="S0"),
                Affiliation(department="DeptA", line="L3", user_sdwt_prod=""),
            ],
            ignore_conflicts=True,
        )

        rows = list_line_sdwt_pairs()
        self.assertEqual(
            rows,
            [
                {"line_id": "L1", "user_sdwt_prod": "S1"},
                {"line_id": "L1", "user_sdwt_prod": "S2"},
                {"line_id": "L2", "user_sdwt_prod": "S0"},
            ],
        )


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
            department="Dept",
            line="Line",
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
            department="Dept",
            line="Line",
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
            department=None,
            line=None,
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
            department="Dept",
            line="Line",
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
