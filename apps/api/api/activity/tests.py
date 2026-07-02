# =============================================================================
# 모듈 설명: activity 엔드포인트 테스트를 제공합니다.
# - 주요 대상: ActivityLogView(인증/권한/응답 검증)
# - 불변 조건: URL 네임(activity-logs)이 등록되어 있어야 합니다.
# =============================================================================
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase, override_settings
from django.urls import reverse

from api.activity.models import ActivityLog, ExternalAppAccessDailyStat


@override_settings(EXTERNAL_APP_USAGE_API_URLS="[]")
class ActivityLogEndpointTests(TestCase):
    """Activity 로그 조회 엔드포인트 테스트 모음."""

    def setUp(self) -> None:
        """테스트에 사용할 기본 사용자 계정을 생성합니다."""
        # -----------------------------------------------------------------------------
        # 1) 기본 사용자 생성
        # -----------------------------------------------------------------------------
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S70000",
            password="test-password",
            knox_id="knox-70000",
        )
        self.other_user = User.objects.create_user(
            sabun="S70001",
            password="test-password",
            knox_id="knox-70001",
        )
        self.superuser = User.objects.create_superuser(
            sabun="S70002",
            password="test-password",
            knox_id="knox-70002",
        )

    def test_activity_logs_requires_auth(self) -> None:
        """미인증 요청은 401을 반환하는지 확인합니다."""
        response = self.client.get(reverse("activity-logs"))
        self.assertEqual(response.status_code, 401)

    def test_activity_logs_requires_permission(self) -> None:
        """권한이 없을 때 403을 반환하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 로그인 후 접근 시도
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)

        response = self.client.get(reverse("activity-logs"))
        self.assertEqual(response.status_code, 403)

    def test_activity_logs_returns_recent_entries(self) -> None:
        """정상 요청 시 최근 로그 목록이 반환되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) ActivityLog 생성
        # -----------------------------------------------------------------------------
        ActivityLog.objects.create(
            user=self.user,
            action="UPDATE",
            path="/api/v1/demo",
            method="PATCH",
            status_code=200,
            metadata={"note": "ok"},
        )

        # -----------------------------------------------------------------------------
        # 2) 권한 부여 및 요청 수행
        # -----------------------------------------------------------------------------
        permission = Permission.objects.get(
            content_type__app_label="activity",
            codename="view_activitylog",
        )
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

        # -----------------------------------------------------------------------------
        # 3) 응답 검증
        # -----------------------------------------------------------------------------
        response = self.client.get(reverse("activity-logs"), {"limit": "5"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["action"], "UPDATE")

    def test_activity_logs_handles_missing_profile(self) -> None:
        """프로필이 없는 사용자도 오류 없이 응답되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 프로필 제거(있다면)
        # -----------------------------------------------------------------------------
        try:
            self.user.profile.delete()
        except ObjectDoesNotExist:
            pass
        self.user.refresh_from_db()

        # -----------------------------------------------------------------------------
        # 2) ActivityLog 생성
        # -----------------------------------------------------------------------------
        ActivityLog.objects.create(
            user=self.user,
            action="VIEW",
            path="/api/v1/activity/logs",
            method="GET",
            status_code=200,
            metadata={"note": "ok"},
        )

        # -----------------------------------------------------------------------------
        # 3) 권한 부여 및 요청 수행
        # -----------------------------------------------------------------------------
        permission = Permission.objects.get(
            content_type__app_label="activity",
            codename="view_activitylog",
        )
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

        response = self.client.get(reverse("activity-logs"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertIsNone(payload["results"][0]["role"])

    def test_app_access_event_requires_auth(self) -> None:
        """앱 접속 이벤트 기록은 인증을 요구합니다."""
        response = self.client.post(
            reverse("activity-app-access"),
            data=json.dumps({"appId": "appstore", "appName": "Appstore"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_app_access_event_records_activity_log(self) -> None:
        """앱 접속 이벤트 기록 API가 APP_ACCESS 로그를 생성하는지 확인합니다."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("activity-app-access"),
            data=json.dumps({"appId": "appstore", "appName": "Appstore", "path": "/appstore"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        entry = ActivityLog.objects.get(pk=response.json()["id"])
        self.assertEqual(entry.action, "APP_ACCESS")
        self.assertEqual(entry.metadata["app_id"], "appstore")
        self.assertEqual(entry.metadata["knox_id"], "knox-70000")

    def test_app_access_stats_requires_superuser(self) -> None:
        """앱 접속 통계 조회는 슈퍼유저만 허용합니다."""
        self.client.force_login(self.user)

        response = self.client.get(reverse("activity-app-access-stats"))

        self.assertEqual(response.status_code, 403)

    def test_app_access_stats_aggregates_by_kst_and_knox_id(self) -> None:
        """KST 날짜 기준과 knox_id distinct 기준으로 앱 접속 통계를 집계합니다."""
        ActivityLog.objects.create(
            user=self.user,
            action="APP_ACCESS",
            path="/appstore",
            method="EVENT",
            status_code=200,
            metadata={"app_id": "appstore", "app_name": "Appstore", "event_type": "app_access"},
            created_at=datetime(2026, 6, 16, 15, 30, tzinfo=UTC),
        )
        ActivityLog.objects.create(
            user=self.user,
            action="APP_ACCESS",
            path="/appstore",
            method="EVENT",
            status_code=200,
            metadata={"app_id": "appstore", "app_name": "Appstore", "event_type": "app_access"},
            created_at=datetime(2026, 6, 17, 1, 0, tzinfo=UTC),
        )
        ActivityLog.objects.create(
            user=self.other_user,
            action="APP_ACCESS",
            path="/emails/inbox",
            method="EVENT",
            status_code=200,
            metadata={"app_id": "emails", "app_name": "Emails", "event_type": "app_access"},
            created_at=datetime(2026, 6, 17, 2, 0, tzinfo=UTC),
        )
        ActivityLog.objects.create(
            user=self.other_user,
            action="GET",
            path="/api/v1/appstore/apps",
            method="GET",
            status_code=200,
            metadata={"app_id": "appstore", "app_name": "Appstore"},
            created_at=datetime(2026, 6, 17, 3, 0, tzinfo=UTC),
        )
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("activity-app-access-stats"),
            {"from": "2026-06-17", "to": "2026-06-17"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["timezone"], "Asia/Seoul")
        self.assertEqual(payload["period"], "day")
        self.assertEqual(payload["summary"]["totalAccessCount"], 3)
        self.assertEqual(payload["summary"]["uniqueUserCount"], 2)
        self.assertEqual(payload["summary"]["activeAppCount"], 2)
        self.assertEqual(payload["apps"][0]["appId"], "appstore")
        self.assertEqual(payload["apps"][0]["accessCount"], 2)
        self.assertEqual(payload["apps"][0]["uniqueUserCount"], 1)
        self.assertEqual(payload["series"][0]["date"], "2026-06-17")

    def test_app_access_stats_rejects_invalid_period(self) -> None:
        """앱 접속 통계 조회가 허용되지 않은 집계 단위를 거부하는지 확인합니다."""
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("activity-app-access-stats"),
            {"from": "2026-06-17", "to": "2026-06-17", "period": "quarter"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("period", response.json()["error"])

    def test_app_access_stats_groups_series_by_week(self) -> None:
        """주별 보기에서 내부/외부 접속 추이가 KST 월요일 기준으로 묶이는지 확인합니다."""
        ActivityLog.objects.create(
            user=self.user,
            action="APP_ACCESS",
            path="/appstore",
            method="EVENT",
            status_code=200,
            metadata={"app_id": "appstore", "app_name": "Appstore", "event_type": "app_access"},
            created_at=datetime(2026, 6, 16, 15, 30, tzinfo=UTC),
        )
        ActivityLog.objects.create(
            user=self.other_user,
            action="APP_ACCESS",
            path="/appstore",
            method="EVENT",
            status_code=200,
            metadata={"app_id": "appstore", "app_name": "Appstore", "event_type": "app_access"},
            created_at=datetime(2026, 6, 18, 1, 0, tzinfo=UTC),
        )
        ExternalAppAccessDailyStat.objects.create(
            app_id="external-foo",
            app_name="외부 Foo",
            stat_date="2026-06-19",
            access_count=7,
            unique_user_count=3,
            source_type="manual",
            source_name="manual",
            created_by=self.superuser,
            updated_by=self.superuser,
        )
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("activity-app-access-stats"),
            {"from": "2026-06-17", "to": "2026-06-21", "period": "week"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["period"], "week")
        appstore_series = next(row for row in payload["series"] if row["appId"] == "appstore")
        external_series = next(row for row in payload["series"] if row["appId"] == "external-foo")
        self.assertEqual(appstore_series["date"], "2026-06-15")
        self.assertEqual(appstore_series["accessCount"], 2)
        self.assertEqual(external_series["date"], "2026-06-15")
        self.assertEqual(external_series["accessCount"], 7)

    def test_app_access_stats_groups_series_by_month(self) -> None:
        """월별 보기에서 접속 추이가 월 시작일 기준으로 묶이는지 확인합니다."""
        ActivityLog.objects.create(
            user=self.user,
            action="APP_ACCESS",
            path="/emails",
            method="EVENT",
            status_code=200,
            metadata={"app_id": "emails", "app_name": "Emails", "event_type": "app_access"},
            created_at=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
        )
        ExternalAppAccessDailyStat.objects.create(
            app_id="external-foo",
            app_name="외부 Foo",
            stat_date="2026-06-29",
            access_count=11,
            unique_user_count=5,
            source_type="manual",
            source_name="manual",
            created_by=self.superuser,
            updated_by=self.superuser,
        )
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("activity-app-access-stats"),
            {"from": "2026-06-01", "to": "2026-06-30", "period": "month"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["period"], "month")
        self.assertTrue(all(row["date"] == "2026-06-01" for row in payload["series"]))

    def test_manual_app_access_preview_validates_spreadsheet_paste(self) -> None:
        """외부 앱 접속현황 붙여넣기 미리보기가 행 단위 오류를 반환하는지 확인합니다."""
        self.client.force_login(self.superuser)
        pasted_text = "\t".join(["date", "appName", "accessCount", "uniqueUserCount"]) + "\n"
        pasted_text += "\t".join(["2026-06-17", "external foo", "10", "3"]) + "\n"
        pasted_text += "\t".join(["2026-06-17", "external bar", "2", "5"])

        response = self.client.post(
            reverse("activity-app-access-manual-preview"),
            data=json.dumps({"pastedText": pasted_text}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["totalRows"], 2)
        self.assertEqual(payload["summary"]["validRows"], 1)
        self.assertEqual(payload["summary"]["errorRows"], 1)
        self.assertEqual(payload["rows"][0]["values"]["appId"], "EXTERNAL FOO")
        self.assertEqual(payload["rows"][0]["values"]["appName"], "EXTERNAL FOO")
        self.assertTrue(payload["rows"][1]["errors"])

    def test_manual_app_access_preview_accepts_csv_template_paste(self) -> None:
        """외부 앱 접속현황 CSV 템플릿 붙여넣기가 미리보기 유효 행으로 처리되는지 확인합니다."""
        self.client.force_login(self.superuser)
        pasted_text = (
            "date,appName,accessCount,uniqueUserCount,memo\n"
            "2026-06-17,external csv,9,4,CSV 템플릿"
        )

        response = self.client.post(
            reverse("activity-app-access-manual-preview"),
            data=json.dumps({"pastedText": pasted_text}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["totalRows"], 1)
        self.assertEqual(payload["summary"]["validRows"], 1)
        self.assertEqual(payload["summary"]["errorRows"], 0)
        self.assertEqual(payload["rows"][0]["values"]["appId"], "EXTERNAL CSV")
        self.assertEqual(payload["rows"][0]["values"]["appName"], "EXTERNAL CSV")
        self.assertEqual(payload["rows"][0]["values"]["memo"], "CSV 템플릿")

    def test_manual_app_access_commit_requires_superuser(self) -> None:
        """외부 앱 접속현황 수동 반영은 슈퍼유저만 허용합니다."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("activity-app-access-manual-commit"),
            data=json.dumps({"pastedText": "date\tappName\taccessCount\tuniqueUserCount\n2026-06-17\text\t1\t1"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_manual_app_access_commit_upserts_daily_stats(self) -> None:
        """외부 앱 접속현황 수동 반영이 앱/날짜/출처 기준으로 upsert되는지 확인합니다."""
        self.client.force_login(self.superuser)
        first_text = (
            "date\tappName\taccessCount\tuniqueUserCount\tmemo\n"
            "2026-06-17\texternal foo\t10\t3\t초기 입력"
        )
        second_text = (
            "date\tappName\taccessCount\tuniqueUserCount\tmemo\n"
            "2026-06-17\t EXTERNAL FOO \t12\t4\t수정 입력"
        )

        first_response = self.client.post(
            reverse("activity-app-access-manual-commit"),
            data=json.dumps({"pastedText": first_text}),
            content_type="application/json",
        )
        second_response = self.client.post(
            reverse("activity-app-access-manual-commit"),
            data=json.dumps({"pastedText": second_text}),
            content_type="application/json",
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(ExternalAppAccessDailyStat.objects.count(), 1)
        stat = ExternalAppAccessDailyStat.objects.get(app_id="EXTERNAL FOO")
        self.assertEqual(stat.app_name, "EXTERNAL FOO")
        self.assertEqual(stat.access_count, 12)
        self.assertEqual(stat.unique_user_count, 4)
        self.assertEqual(stat.memo, "수정 입력")
        self.assertEqual(second_response.json()["commit"]["updatedRows"], 1)

    def test_app_access_stats_includes_manual_external_stats(self) -> None:
        """기존 앱 접속 통계 API가 외부 수동 집계를 합산하는지 확인합니다."""
        ExternalAppAccessDailyStat.objects.create(
            app_id="external-foo",
            app_name="외부 Foo",
            stat_date="2026-06-17",
            access_count=10,
            unique_user_count=3,
            source_type="manual",
            source_name="manual",
            created_by=self.superuser,
            updated_by=self.superuser,
        )
        ActivityLog.objects.create(
            user=self.user,
            action="APP_ACCESS",
            path="/appstore",
            method="EVENT",
            status_code=200,
            metadata={"app_id": "appstore", "app_name": "Appstore", "event_type": "app_access"},
            created_at=datetime(2026, 6, 17, 1, 0, tzinfo=UTC),
        )
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("activity-app-access-stats"),
            {"from": "2026-06-17", "to": "2026-06-17"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["totalAccessCount"], 11)
        self.assertEqual(payload["summary"]["uniqueUserCount"], 4)
        external_row = next(app for app in payload["apps"] if app["appId"] == "external-foo")
        self.assertEqual(external_row["sourceType"], "manual")
        self.assertEqual(external_row["accessCount"], 10)

    @override_settings(
        EXTERNAL_APP_USAGE_API_URLS=(
            '[{"sourceName":"m-etch-dx","url":"https://usage.example.test/get/usage"},'
            '{"sourceName":"other-system","url":"https://other.example.test/get/usage"}]'
        ),
        EXTERNAL_APP_USAGE_API_TIMEOUT_SECONDS=3,
    )
    @patch("api.activity.services.activity_logs.requests.get")
    def test_app_access_stats_includes_external_usage_api_source_rows(self, mock_get) -> None:
        """외부 사용량 API source row가 기존 앱 접속 통계에 합산되는지 확인합니다."""

        class FakeResponse:
            """테스트용 외부 사용량 API 응답입니다."""

            def __init__(self, rows: list[dict[str, object]]) -> None:
                """응답 row를 저장합니다."""

                self.rows = rows

            def raise_for_status(self) -> None:
                """HTTP 오류가 없다고 처리합니다."""

            def json(self) -> list[dict[str, object]]:
                """외부 사용량 API row 목록을 반환합니다."""

                return self.rows

        mock_get.side_effect = [
            FakeResponse(
                [
                    {"date": "2026-01-01", "accessCount": 5556, "appName": "AIO"},
                    {"date": "2026-01-02", "accessCount": 5536, "appName": " aio "},
                    {"date": "2026-02-01", "accessCount": 9999, "appName": "AIO"},
                ]
            ),
            FakeResponse(
                [
                    {"date": "2026-01-03", "accessCount": 100, "appName": "AIO"},
                    {"date": "2026-01-03", "accessCount": 200, "appName": "OTHER"},
                ]
            ),
        ]
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("activity-app-access-stats"),
            {"from": "2026-01-01", "to": "2026-01-31", "appId": "aio"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["totalAccessCount"], 11192)
        self.assertEqual(payload["summary"]["uniqueUserCount"], 0)
        self.assertEqual(payload["externalUsage"]["rowCount"], 3)
        self.assertEqual(len(payload["externalUsage"]["sources"]), 2)
        self.assertEqual(payload["externalUsage"]["sources"][0]["sourceName"], "m-etch-dx")
        self.assertEqual(payload["externalUsage"]["sources"][0]["rowCount"], 2)
        self.assertEqual(payload["externalUsage"]["sources"][1]["sourceName"], "other-system")
        self.assertEqual(payload["externalUsage"]["sources"][1]["rowCount"], 1)
        app_row = next(app for app in payload["apps"] if app["appId"] == "AIO")
        self.assertEqual(app_row["appName"], "AIO")
        self.assertEqual(app_row["sourceType"], "external_api")
        self.assertEqual(app_row["sourceName"], "mixed")
        self.assertEqual(app_row["accessCount"], 11192)
        self.assertEqual(app_row["uniqueUserCount"], 0)
        self.assertEqual(len(payload["series"]), 3)
        mock_get.assert_any_call("https://usage.example.test/get/usage", timeout=3)
        mock_get.assert_any_call("https://other.example.test/get/usage", timeout=3)

    @override_settings(
        EXTERNAL_APP_USAGE_API_URLS='[{"sourceName":"m-etch-dx","url":"https://usage.example.test/get/usage"}]'
    )
    @patch("api.activity.services.activity_logs.requests.get")
    def test_app_access_stats_keeps_existing_stats_when_external_usage_api_fails(self, mock_get) -> None:
        """외부 사용량 API 실패 시 기존 통계 응답을 유지하는지 확인합니다."""
        mock_get.side_effect = requests.RequestException("network down")
        ActivityLog.objects.create(
            user=self.user,
            action="APP_ACCESS",
            path="/appstore",
            method="EVENT",
            status_code=200,
            metadata={"app_id": "appstore", "app_name": "Appstore", "event_type": "app_access"},
            created_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        )
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("activity-app-access-stats"),
            {"from": "2026-01-01", "to": "2026-01-01"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["totalAccessCount"], 1)
        self.assertEqual(payload["apps"][0]["appId"], "appstore")
        self.assertTrue(payload["externalUsage"]["error"])
        self.assertEqual(payload["externalUsage"]["rowCount"], 0)

    @override_settings(
        EXTERNAL_APP_USAGE_API_URLS=(
            '[{"sourceName":"m-etch-dx","url":"https://usage.example.test/get/usage"},'
            '{"sourceName":"other-system","url":"https://other.example.test/get/usage"}]'
        )
    )
    @patch("api.activity.services.activity_logs.requests.get")
    def test_app_access_stats_excludes_all_external_api_rows_when_one_source_fails(self, mock_get) -> None:
        """외부 사용량 API source 중 하나라도 실패하면 외부 API 통계를 모두 제외하는지 확인합니다."""

        class FakeResponse:
            """테스트용 외부 사용량 API 응답입니다."""

            def raise_for_status(self) -> None:
                """HTTP 오류가 없다고 처리합니다."""

            def json(self) -> list[dict[str, object]]:
                """외부 사용량 API row 목록을 반환합니다."""

                return [{"date": "2026-01-01", "accessCount": 100, "appName": "AIO"}]

        ActivityLog.objects.create(
            user=self.user,
            action="APP_ACCESS",
            path="/appstore",
            method="EVENT",
            status_code=200,
            metadata={"app_id": "appstore", "app_name": "Appstore", "event_type": "app_access"},
            created_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        )
        mock_get.side_effect = [FakeResponse(), requests.RequestException("network down")]
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("activity-app-access-stats"),
            {"from": "2026-01-01", "to": "2026-01-01"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["totalAccessCount"], 1)
        self.assertEqual(payload["externalUsage"]["rowCount"], 0)
        self.assertEqual(payload["externalUsage"]["sources"][0]["rowCount"], 1)
        self.assertTrue(payload["externalUsage"]["sources"][1]["error"])
        self.assertFalse(any(app["appId"] == "AIO" for app in payload["apps"]))
