# =============================================================================
# 모듈: 드론 기능 테스트
# 주요 대상: POP3 파싱/업서트, Jira 생성, API 엔드포인트
# 주요 가정: 외부 호출은 mock으로 대체합니다.
# =============================================================================
from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

import api.account.services as account_services
from api.drone import selectors, services
from api.drone.models import DroneEarlyInform, DroneSOP, DroneSopJiraUserTemplate

_PREVIOUS_LOGGING_DISABLE: int | None = None


def setUpModule() -> None:
    """테스트 실행 중 로그 출력을 최소화합니다."""

    global _PREVIOUS_LOGGING_DISABLE
    _PREVIOUS_LOGGING_DISABLE = logging.root.manager.disable
    logging.disable(logging.CRITICAL)


def tearDownModule() -> None:
    """테스트 종료 후 로깅 설정을 복구합니다."""

    if _PREVIOUS_LOGGING_DISABLE is not None:
        logging.disable(_PREVIOUS_LOGGING_DISABLE)


class DroneSopPop3ParsingTests(TestCase):
    """POP3 HTML 파싱 로직을 검증합니다."""

    def test_build_drone_sop_row_parses_html_data_tag(self) -> None:
        """data 태그에서 필드를 추출하는지 확인합니다."""
        html = """
        <html><body>
          <data>
            <line_id>L1</line_id>
            <sdwt_prod>SDWT</sdwt_prod>
            <sample_type>NORMAL</sample_type>
            <sample_group>G1</sample_group>
            <eqp_id>EQP1</eqp_id>
            <chamber_ids>1,2</chamber_ids>
            <lot_id>LOT.1</lot_id>
            <proc_id>P</proc_id>
            <ppid>PP</ppid>
            <main_step>MS</main_step>
            <metro_current_step>ST003</metro_current_step>
            <metro_steps>ST001,ST002,ST003</metro_steps>
            <metro_end_step>ST010</metro_end_step>
            <status>IN_PROGRESS</status>
            <knoxid>knox</knoxid>
            <user_sdwt_prod>dummy-prod</user_sdwt_prod>
            <comment>hello@$SETUP_EQP</comment>
            <defect_url>"https://example.com"</defect_url>
          </data>
        </body></html>
        """

        early_inform_map = {("dummy-prod", "MS"): "ST002"}
        row = services._build_drone_sop_row(html=html, early_inform_map=early_inform_map)
        assert row is not None

        self.assertEqual(row["line_id"], "L1")
        self.assertEqual(row["chamber_ids"], "12")
        self.assertEqual(row["knox_id"], "knox")
        self.assertEqual(row["needtosend"], 1)
        self.assertEqual(row["status"], "COMPLETE")
        self.assertEqual(row["defect_url"], "https://example.com")
        self.assertEqual(row["custom_end_step"], "ST002")

    def test_build_drone_sop_row_applies_needtosend_override_rule(self) -> None:
        """needtosend 룰 오버라이드가 적용되는지 확인합니다."""
        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <user_sdwt_prod>prod-1</user_sdwt_prod>
          <comment>hello@$abc</comment>
        </data>
        """
        rules = [services.NeedToSendRule(pattern="prod-*", comment_last_at="$abc", ignore_sample_type=False)]
        row = services._build_drone_sop_row(html=html, early_inform_map={}, needtosend_rules=rules)
        assert row is not None
        self.assertEqual(row["needtosend"], 1)

    def test_build_drone_sop_row_needtosend_zero_for_engr_production(self) -> None:
        """ENGR_PRODUCTION 샘플 타입의 needtosend가 0인지 확인합니다."""
        html = """
        <data>
          <sample_type>ENGR_PRODUCTION</sample_type>
          <comment>hello@$SETUP_EQP</comment>
        </data>
        """
        row = services._build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 0)


class DroneSopUpsertTests(TestCase):
    """UPSERT 동작을 검증합니다."""

    def test_upsert_does_not_update_comment_or_needtosend_on_conflict(self) -> None:
        """충돌 시 comment/needtosend가 덮어쓰이지 않는지 확인합니다."""
        existing = DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            comment="old",
            needtosend=0,
            status="IN_PROGRESS",
            metro_current_step="ST001",
        )

        services._upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "chamber_ids": "1",
                    "lot_id": "LOT.1",
                    "main_step": "MS",
                    "comment": "new",
                    "needtosend": 1,
                    "status": "COMPLETE",
                    "metro_current_step": "ST002",
                }
            ]
        )

        refreshed = DroneSOP.objects.get(id=existing.id)
        self.assertEqual(refreshed.comment, "old")
        self.assertEqual(refreshed.needtosend, 0)
        self.assertEqual(refreshed.status, "COMPLETE")
        self.assertEqual(refreshed.metro_current_step, "ST002")


class DroneSopJiraCandidateTests(TestCase):
    """Jira 후보 조회 로직을 검증합니다."""

    def test_list_drone_sop_jira_candidates_filters_rows(self) -> None:
        """send_jira/needtosend/status/instant_inform 조건이 반영되는지 확인합니다."""
        DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
        )
        DroneSOP.objects.create(
            line_id="L2",
            eqp_id="EQP2",
            chamber_ids="1",
            lot_id="LOT.2",
            main_step="MS",
            status="IN_PROGRESS",
            needtosend=1,
            send_jira=0,
        )
        DroneSOP.objects.create(
            line_id="L3",
            eqp_id="EQP3",
            chamber_ids="1",
            lot_id="LOT.3",
            main_step="MS",
            status="IN_PROGRESS",
            needtosend=0,
            instant_inform=1,
            send_jira=0,
        )

        rows = selectors.list_drone_sop_jira_candidates()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["line_id"] for row in rows}, {"L1", "L3"})

    def test_has_drone_sop_jira_candidates_returns_true_when_exists(self) -> None:
        """Jira 후보가 있으면 True를 반환하는지 확인합니다."""
        DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
        )

        self.assertTrue(selectors.has_drone_sop_jira_candidates())

    def test_has_drone_sop_jira_candidates_returns_false_when_empty(self) -> None:
        """Jira 후보가 없으면 False를 반환하는지 확인합니다."""
        self.assertFalse(selectors.has_drone_sop_jira_candidates())


class DroneSopJiraUpdateTests(TestCase):
    """Jira 상태 업데이트 로직을 검증합니다."""

    def test_update_drone_sop_jira_status_sets_send_jira_and_key(self) -> None:
        """send_jira/jira_key/inform_step이 갱신되는지 확인합니다."""
        row = DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST003",
        )

        updated = services._update_drone_sop_jira_status(
            done_ids=[int(row.id)],
            rows=[{"id": int(row.id), "metro_current_step": "ST003"}],
            key_by_id={int(row.id): "DUMMY-1"},
        )
        self.assertEqual(updated, 1)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.send_jira, 1)
        self.assertEqual(refreshed.inform_step, "ST003")
        self.assertEqual(refreshed.jira_key, "DUMMY-1")
        self.assertIsNotNone(refreshed.informed_at)


class DroneSopInstantInformTests(TestCase):
    """즉시 인폼 요청 로직을 검증합니다."""

    def test_enqueue_instant_inform_marks_requested(self) -> None:
        """즉시 인폼 체크 요청 시 instant_inform/send_jira 값이 갱신되는지 확인합니다."""
        row = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="IN_PROGRESS",
            needtosend=0,
            send_jira=-1,
            instant_inform=-1,
            comment="base",
        )

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(row.id), comment="hello")
        self.assertTrue(result.queued)
        self.assertFalse(result.already_informed)
        self.assertEqual(result.updated_fields.get("comment"), "hello")
        self.assertEqual(result.updated_fields.get("instant_inform"), 1)
        self.assertEqual(result.updated_fields.get("send_jira"), 0)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.comment, "hello")
        self.assertEqual(refreshed.instant_inform, 1)
        self.assertEqual(refreshed.send_jira, 0)

    def test_enqueue_instant_inform_returns_already_informed(self) -> None:
        """이미 Jira 전송된 항목은 already_informed로 응답하는지 확인합니다."""
        row = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            instant_inform=0,
            jira_key="JIRA-1",
        )

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(row.id), comment="updated")
        self.assertTrue(result.already_informed)
        self.assertFalse(result.queued)
        self.assertEqual(result.jira_key, "JIRA-1")
        self.assertEqual(result.updated_fields.get("comment"), "updated")

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.comment, "updated")


class DroneEndpointTests(TestCase):
    """드론 API 엔드포인트 동작을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/클라이언트를 준비합니다."""
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S60000",
            password="test-password",
            knox_id="knox-60000",
        )
        self.client.force_login(self.user)

    @patch("api.drone.views.services.delete_early_inform_entry")
    def test_drone_early_inform_crud(self, mock_delete) -> None:
        """조기 알림 CRUD 플로우가 동작하는지 확인합니다."""
        create_response = self.client.post(
            reverse("drone-early-inform"),
            data='{"lineId":"L1","mainStep":"STEP1","customEndStep":"STEP2"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        entry_id = create_response.json()["entry"]["id"]

        list_response = self.client.get(reverse("drone-early-inform"), {"lineId": "L1"})
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["rowCount"], 1)

        update_response = self.client.patch(
            reverse("drone-early-inform"),
            data='{"id": %d, "customEndStep": "STEP3"}' % entry_id,
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)

        mock_delete.return_value = DroneEarlyInform.objects.get(id=entry_id)
        delete_response = self.client.delete(f"{reverse('drone-early-inform')}?id={entry_id}")
        self.assertEqual(delete_response.status_code, 200)

    @patch("api.drone.views.selectors.get_line_history_payload", return_value={"rows": []})
    def test_drone_line_history(self, _mock_history) -> None:
        """라인 히스토리 API가 정상 응답하는지 확인합니다."""
        response = self.client.get(reverse("line-dashboard-history"))
        self.assertEqual(response.status_code, 200)

    @patch("api.drone.views.selectors.list_distinct_line_ids", return_value=["L1"])
    def test_drone_line_ids(self, _mock_lines) -> None:
        """라인 ID 목록 API가 정상 응답하는지 확인합니다."""
        response = self.client.get(reverse("line-dashboard-line-ids"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lineIds"], ["L1"])

    @patch("api.drone.views.services.enqueue_drone_sop_jira_instant_inform")
    def test_drone_sop_instant_inform(self, mock_service) -> None:
        """즉시 인폼 API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            already_informed=False,
            queued=True,
            jira_key="JIRA-1",
            updated_fields={},
        )
        response = self.client.post(
            reverse("drone-sop-instant-inform", kwargs={"sop_id": 123}),
            data='{"comment":"test"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "queued")

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    @patch("api.drone.views.services.run_drone_sop_pop3_ingest_from_env")
    def test_drone_sop_pop3_trigger(self, mock_service) -> None:
        """POP3 트리거 API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            matched_mails=1,
            upserted_rows=1,
            deleted_mails=0,
            pruned_rows=0,
            skipped=False,
            skip_reason=None,
        )
        response = self.client.post(
            reverse("drone-sop-pop3-ingest-trigger"),
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    @patch("api.drone.views.services.run_drone_sop_jira_create_from_env")
    def test_drone_sop_jira_trigger(self, mock_service) -> None:
        """Jira 트리거 API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            candidates=1,
            created=1,
            updated_rows=0,
            skipped=False,
            skip_reason=None,
        )
        response = self.client.post(
            reverse("drone-sop-jira-trigger"),
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    @patch("api.drone.views.selectors.has_drone_sop_jira_candidates")
    def test_drone_sop_jira_precheck(self, mock_selector) -> None:
        """Jira precheck API가 정상 응답하는지 확인합니다."""
        mock_selector.return_value = True
        response = self.client.post(
            reverse("drone-sop-jira-precheck"),
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("hasCandidates"))

class DroneJiraKeyEndpointTests(TestCase):
    """Jira 키/템플릿 키 엔드포인트를 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/소속 데이터를 준비합니다."""
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S70000",
            password="test-password",
            knox_id="knox-70000",
        )
        self.superuser = User.objects.create_superuser(
            sabun="S70001",
            password="test-password",
            knox_id="knox-70001",
        )
        account_services.ensure_affiliation_option(
            department="Dept",
            line="L1",
            user_sdwt_prod="SDWT",
        )

    def test_jira_key_get_requires_authentication(self) -> None:
        """Jira 키 조회는 인증이 필요합니다."""
        response = self.client.get(reverse("line-dashboard-jira-keys"), {"userSdwtProd": "SDWT"})
        self.assertEqual(response.status_code, 401)

    def test_jira_key_get_returns_values(self) -> None:
        """Jira 키/템플릿 키 조회가 정상 응답하는지 확인합니다."""
        DroneSopJiraUserTemplate.objects.create(
            user_sdwt_prod="SDWT",
            template_key="line_a",
            jira_key="PROJ",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("line-dashboard-jira-keys"), {"userSdwtProd": "SDWT"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jiraKey"], "PROJ")
        self.assertEqual(response.json()["templateKey"], "line_a")

    def test_jira_key_update_requires_superuser(self) -> None:
        """Jira 키 갱신은 슈퍼유저만 가능해야 합니다."""
        payload = {"userSdwtProd": "SDWT", "jiraKey": "PROJ", "templateKey": "line_a"}

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        refreshed = DroneSopJiraUserTemplate.objects.get(user_sdwt_prod="SDWT")
        self.assertEqual(refreshed.jira_key, "PROJ")
        self.assertEqual(refreshed.template_key, "line_a")


class DroneSopJiraCreateProjectKeyTests(TestCase):
    """Jira 생성 시 프로젝트/템플릿 매핑을 검증합니다."""
    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.sop_jira._jira_session")
    def test_jira_create_uses_project_key_per_user_sdwt_prod_and_marks_missing_as_failed(
        self, mock_session: Mock
    ) -> None:
        """user_sdwt_prod 기준 프로젝트 키가 적용되고 누락은 실패 처리되는지 확인합니다."""
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"issues": [{"key": "PROJ1-1"}, {"key": "PROJ2-2"}]}
        session.post.return_value = resp
        mock_session.return_value = session

        account_services.ensure_affiliation_option(
            department="D",
            line="L1",
            user_sdwt_prod="SDWT1",
        )
        account_services.ensure_affiliation_option(
            department="D",
            line="L2",
            user_sdwt_prod="SDWT2",
        )
        account_services.ensure_affiliation_option(
            department="D",
            line="L3",
            user_sdwt_prod="SDWT3",
        )
        DroneSopJiraUserTemplate.objects.create(
            user_sdwt_prod="SDWT1",
            template_key="line_a",
            jira_key="PROJ1",
        )
        DroneSopJiraUserTemplate.objects.create(
            user_sdwt_prod="SDWT2",
            template_key="line_b",
            jira_key="PROJ2",
        )
        DroneSopJiraUserTemplate.objects.create(user_sdwt_prod="SDWT3", template_key="line_a")

        sop1 = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST001",
        )
        sop2 = DroneSOP.objects.create(
            line_id="L2",
            sdwt_prod="SDWT2",
            user_sdwt_prod="SDWT2",
            eqp_id="EQP2",
            chamber_ids="1",
            lot_id="LOT.2",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST002",
        )
        sop_missing = DroneSOP.objects.create(
            line_id="L3",
            sdwt_prod="SDWT3",
            user_sdwt_prod="SDWT3",
            eqp_id="EQP3",
            chamber_ids="1",
            lot_id="LOT.3",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST003",
        )

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 3)
        self.assertEqual(result.created, 2)

        session.post.assert_called_once()
        sent_payload = session.post.call_args.kwargs.get("json") or {}
        updates = sent_payload.get("issueUpdates") or []
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0].get("fields", {}).get("project", {}).get("key"), "PROJ1")
        self.assertEqual(updates[1].get("fields", {}).get("project", {}).get("key"), "PROJ2")

        refreshed1 = DroneSOP.objects.get(id=sop1.id)
        refreshed2 = DroneSOP.objects.get(id=sop2.id)
        refreshed_missing = DroneSOP.objects.get(id=sop_missing.id)

        self.assertEqual(refreshed1.send_jira, 1)
        self.assertEqual(refreshed1.jira_key, "PROJ1-1")
        self.assertEqual(refreshed2.send_jira, 1)
        self.assertEqual(refreshed2.jira_key, "PROJ2-2")
        self.assertEqual(refreshed_missing.send_jira, -1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.sop_jira._jira_session")
    def test_jira_create_uses_user_template_override(self, mock_session: Mock) -> None:
        """user_sdwt_prod 템플릿 매핑이 적용되는지 확인합니다."""
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"issues": [{"key": "PROJ1-1"}]}
        session.post.return_value = resp
        mock_session.return_value = session

        account_services.ensure_affiliation_option(
            department="D",
            line="L1",
            user_sdwt_prod="SDWT",
        )
        DroneSopJiraUserTemplate.objects.create(
            user_sdwt_prod="SDWT",
            template_key="line_a",
            jira_key="PROJ1",
        )

        sop1 = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 1)

        refreshed = DroneSOP.objects.get(id=sop1.id)
        self.assertEqual(refreshed.send_jira, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=False,
    )
    @patch("api.drone.services.sop_jira._jira_session")
    def test_jira_create_marks_missing_template_as_failed(self, mock_session: Mock) -> None:
        """템플릿 누락 시 실패로 마킹되는지 확인합니다."""
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"key": "PROJ1-1"}
        session.post.return_value = resp
        mock_session.return_value = session

        account_services.ensure_affiliation_option(
            department="D",
            line="L1",
            user_sdwt_prod="SDWT1",
        )
        account_services.ensure_affiliation_option(
            department="D",
            line="L2",
            user_sdwt_prod="SDWT2",
        )
        DroneSopJiraUserTemplate.objects.create(
            user_sdwt_prod="SDWT1",
            template_key="line_a",
            jira_key="PROJ1",
        )
        DroneSopJiraUserTemplate.objects.create(user_sdwt_prod="SDWT2", jira_key="PROJ2")

        sop1 = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST001",
        )
        sop2 = DroneSOP.objects.create(
            line_id="L2",
            sdwt_prod="SDWT2",
            user_sdwt_prod="SDWT2",
            eqp_id="EQP2",
            chamber_ids="1",
            lot_id="LOT.2",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST002",
        )

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.created, 1)

        session.post.assert_called_once()

        refreshed1 = DroneSOP.objects.get(id=sop1.id)
        refreshed2 = DroneSOP.objects.get(id=sop2.id)

        self.assertEqual(refreshed1.send_jira, 1)
        self.assertEqual(refreshed2.send_jira, -1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=False,
    )
    @patch("api.drone.services.sop_jira._jira_session")
    @patch("api.drone.services.sop_jira._single_create_jira_issues")
    def test_jira_create_marks_instant_inform_failed_when_create_fails(
        self,
        mock_single_create: Mock,
        mock_session: Mock,
    ) -> None:
        """즉시인폼 대상이 생성 실패 시 instant_inform이 실패로 표시되는지 확인합니다."""
        mock_session.return_value = Mock()

        DroneSopJiraUserTemplate.objects.create(
            user_sdwt_prod="SDWT1",
            template_key="line_a",
            jira_key="PROJ1",
        )
        DroneSopJiraUserTemplate.objects.create(
            user_sdwt_prod="SDWT2",
            template_key="line_a",
            jira_key="PROJ2",
        )

        instant = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="IN_PROGRESS",
            needtosend=0,
            send_jira=0,
            instant_inform=1,
            metro_current_step="ST001",
        )
        normal = DroneSOP.objects.create(
            line_id="L2",
            sdwt_prod="SDWT2",
            user_sdwt_prod="SDWT2",
            eqp_id="EQP2",
            chamber_ids="1",
            lot_id="LOT.2",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST002",
        )

        mock_single_create.return_value = ([normal.id], {normal.id: "PROJ2-1"})

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.created, 1)

        refreshed_instant = DroneSOP.objects.get(id=instant.id)
        refreshed_normal = DroneSOP.objects.get(id=normal.id)

        self.assertEqual(refreshed_instant.instant_inform, -1)
        self.assertEqual(refreshed_instant.send_jira, 0)
        self.assertEqual(refreshed_normal.send_jira, 1)
        mock_single_create.assert_called_once()

class DroneTriggerAuthTests(TestCase):
    """트리거 엔드포인트 인증을 검증합니다."""
    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.run_drone_sop_pop3_ingest_from_env")
    def test_pop3_ingest_trigger_requires_token(self, mock_run: Mock) -> None:
        """POP3 트리거가 토큰을 요구하는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            matched_mails=1,
            upserted_rows=2,
            deleted_mails=3,
            pruned_rows=4,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-pop3-ingest-trigger")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_run.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer wrong-token")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_run.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["matched"], 1)
        self.assertEqual(mock_run.call_count, 1)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.run_drone_sop_jira_create_from_env")
    def test_jira_trigger_requires_token(self, mock_run: Mock) -> None:
        """Jira 트리거가 토큰을 요구하는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            candidates=1,
            created=1,
            updated_rows=0,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-jira-trigger")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_run.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["created"], 1)
        mock_run.assert_called_once_with(limit=None)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.selectors.has_drone_sop_jira_candidates")
    def test_jira_precheck_requires_token(self, mock_selector: Mock) -> None:
        """Jira precheck가 토큰을 요구하는지 확인합니다."""
        mock_selector.return_value = True
        url = reverse("drone-sop-jira-precheck")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_selector.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("hasCandidates"))
        mock_selector.assert_called_once()

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.run_drone_sop_jira_create_from_env")
    def test_jira_trigger_prefers_payload_limit_over_query_param(self, mock_run: Mock) -> None:
        """payload limit가 query param보다 우선되는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            candidates=1,
            created=1,
            updated_rows=0,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-jira-trigger") + "?limit=5"
        payload = json.dumps({"limit": 2})
        resp = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )

        self.assertEqual(resp.status_code, 200)
        mock_run.assert_called_once_with(limit=2)


class DroneEarlyInformAuthTests(TestCase):
    """조기 알림 API 인증을 검증합니다."""

    def test_early_inform_requires_login(self) -> None:
        """로그인 없이 접근 시 401을 반환하는지 확인합니다."""
        url = reverse("drone-early-inform")
        resp = self.client.get(url, data={"lineId": "L1"})
        self.assertEqual(resp.status_code, 401)


class DroneSopPop3DummyModeDeleteTests(TestCase):
    """더미 모드 삭제 조건을 검증합니다."""
    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_INCLUDE_SUBJECT_PREFIXES="[drone_sop] a,[drone_sop] b,[drone_sop] c",
    )
    @patch("api.drone.services.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_deletes_only_successfully_upserted_mails(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
    ) -> None:
        """업서트 성공한 메일만 삭제되는지 확인합니다."""
        mock_list.return_value = [
            {"id": 1, "subject": "[drone_sop] a", "body_html": "<data><lot_id>LOT-1</lot_id></data>"},
            {"id": 2, "subject": "[drone_sop] b", "body_html": "<data><lot_id>LOT-FAIL</lot_id></data>"},
            {"id": 3, "subject": "[drone_sop] c", "body_html": "<data><lot_id>LOT-3</lot_id></data>"},
        ]

        def upsert_side_effect(*, rows: list[dict[str, object]]) -> int:
            lot_id = rows[0].get("lot_id") if rows else None
            if lot_id == "LOT-FAIL":
                raise RuntimeError("upsert failed")
            return 1

        mock_upsert.side_effect = upsert_side_effect
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_env()
        self.assertEqual(result.matched_mails, 3)
        self.assertEqual(result.upserted_rows, 2)
        self.assertEqual(result.deleted_mails, 2)

        called_mail_ids = mock_delete.call_args.kwargs.get("mail_ids")
        self.assertEqual(called_mail_ids, [1, 3])


class DroneSopPop3SubjectFilterTests(TestCase):
    """제목 필터 동작을 검증합니다."""
    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_INCLUDE_SUBJECT_PREFIXES="[DRONE_SOP] A,[drone_sop] c",
    )
    @patch("api.drone.services.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_filters_subject_case_insensitive(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
    ) -> None:
        """제목 필터가 대소문자를 무시하는지 확인합니다."""
        mock_list.return_value = [
            {"id": 1, "subject": "[drone_sop] a", "body_html": "<data><lot_id>LOT-1</lot_id></data>"},
            {"id": 2, "subject": "other", "body_html": "<data><lot_id>LOT-2</lot_id></data>"},
            {"id": 3, "subject": "[DRONE_SOP] c", "body_html": "<data><lot_id>LOT-3</lot_id></data>"},
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_env()

        self.assertEqual(result.matched_mails, 2)
        self.assertEqual(result.upserted_rows, 2)
        self.assertEqual(result.deleted_mails, 2)

        called_mail_ids = mock_delete.call_args.kwargs.get("mail_ids")
        self.assertEqual(called_mail_ids, [1, 3])

    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_INCLUDE_SUBJECT_PREFIXES="[drone_sop]",
    )
    @patch("api.drone.services.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_filters_subject_prefix(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
    ) -> None:
        """제목 prefix가 포함된 경우에도 필터가 동작하는지 확인합니다."""
        mock_list.return_value = [
            {"id": 1, "subject": "[drone_sop] alert-1", "body_html": "<data><lot_id>LOT-1</lot_id></data>"},
            {"id": 2, "subject": "other", "body_html": "<data><lot_id>LOT-2</lot_id></data>"},
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_env()

        self.assertEqual(result.matched_mails, 1)
        self.assertEqual(result.upserted_rows, 1)
        self.assertEqual(result.deleted_mails, 1)

        called_mail_ids = mock_delete.call_args.kwargs.get("mail_ids")
        self.assertEqual(called_mail_ids, [1])


class DroneSopJiraHtmlDescriptionTests(TestCase):
    """Jira 설명 HTML 렌더링을 검증합니다."""

    def test_build_jira_issue_fields_uses_html(self) -> None:
        """HTML 템플릿이 포함되는지 확인합니다."""
        from api.drone.services import sop_jira

        config = services.DroneJiraConfig(
            base_url="http://example.local/jira",
            token="dummy-token",
            issue_type="Task",
            use_bulk_api=False,
            bulk_size=20,
            connect_timeout=5,
            read_timeout=20,
        )
        row = {
            "sdwt_prod": "SDWT",
            "main_step": "ST003",
            "ppid": "PPID",
            "eqp_id": "EQP",
            "chamber_ids": "1",
            "lot_id": "LOT.1",
            "knox_id": "knox",
            "user_sdwt_prod": "prod",
            "comment": "hello",
            "defect_url": "https://example.com/defect",
        }

        fields = sop_jira._build_jira_issue_fields(
            row=row,
            project_key="DUMMY",
            template_key="line_a",
            config=config,
        )
        description = fields.get("description") or ""
        self.assertIn("<table", description)
        self.assertIn("CTTTM URL", description)
        self.assertIn("Defect URL", description)
        self.assertIn("https://example.com/defect", description)

    def test_build_jira_issue_fields_renders_ctttm_links(self) -> None:
        """CTTTM 링크가 렌더링되는지 확인합니다."""
        from api.drone.services import sop_jira

        config = services.DroneJiraConfig(
            base_url="http://example.local/jira",
            token="dummy-token",
            issue_type="Task",
            use_bulk_api=False,
            bulk_size=20,
            connect_timeout=5,
            read_timeout=20,
        )
        row = {
            "sdwt_prod": "SDWT",
            "main_step": "ST003",
            "ppid": "PPID",
            "eqp_id": "EQP",
            "chamber_ids": "1",
            "lot_id": "LOT.1",
            "knox_id": "knox",
            "user_sdwt_prod": "prod",
            "comment": "hello",
            "url": [{"eqp_id": "EQP-1", "url": "https://example.com/ctttm"}],
        }

        fields = sop_jira._build_jira_issue_fields(
            row=row,
            project_key="DUMMY",
            template_key="line_a",
            config=config,
        )
        description = fields.get("description") or ""
        self.assertIn("https://example.com/ctttm", description)
        self.assertIn(">EQP-1<", description)


class DroneSopJiraSummaryTests(TestCase):
    """Jira 요약 템플릿 적용을 검증합니다."""

    def test_build_jira_issue_fields_uses_template_summary(self) -> None:
        """템플릿별 summary 포맷이 적용되는지 확인합니다."""
        from api.drone.services import sop_jira

        config = services.DroneJiraConfig(
            base_url="http://example.local/jira",
            token="dummy-token",
            issue_type="Task",
            use_bulk_api=False,
            bulk_size=20,
            connect_timeout=5,
            read_timeout=20,
        )
        row = {
            "line_id": "L1",
            "sdwt_prod": "SDWT",
            "main_step": "ST003",
            "ppid": "PPID",
            "eqp_id": "EQP",
            "chamber_ids": "1",
            "lot_id": "LOT.1",
        }

        def build_line_a_summary(data: dict[str, object]) -> str:
            sdwt = str(data.get("sdwt_prod") or "?").strip() or "?"
            return f"{data.get('line_id')}-{sdwt[:1]}"

        def build_line_b_summary(data: dict[str, object]) -> str:
            sdwt = str(data.get("sdwt_prod") or "?").strip() or "?"
            step = str(data.get("main_step") or "??").strip() or "??"
            normalized_step = step[2:].upper() if len(step) >= 3 else step.upper()
            return f"{sdwt[:1]}-{normalized_step}"

        with patch.dict(
            sop_jira.SUMMARY_BUILDERS,
            {
                "line_a": build_line_a_summary,
                "line_b": build_line_b_summary,
            },
            clear=True,
        ):
            fields_a = sop_jira._build_jira_issue_fields(
                row=row,
                project_key="DUMMY",
                template_key="line_a",
                config=config,
            )
            fields_b = sop_jira._build_jira_issue_fields(
                row=row,
                project_key="DUMMY",
                template_key="line_b",
                config=config,
            )

        self.assertEqual(fields_a.get("summary"), "L1-S")
        self.assertEqual(fields_b.get("summary"), "S-003")
