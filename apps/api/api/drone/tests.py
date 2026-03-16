# =============================================================================
# 모듈: 드론 기능 테스트
# 주요 대상: POP3 파싱/업서트, Jira 생성, API 엔드포인트
# 주요 가정: 외부 호출은 mock으로 대체합니다.
# =============================================================================
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings
from django.urls import reverse

import api.account.services as account_services
from api.drone import selectors, services
from api.drone.models import (
    DroneEarlyInform,
    DroneSOP,
    DroneSopNeedToSendRule,
    DroneSopUserSdwtChannel,
    DroneSopUserSdwtProdMap,
)
from api.drone.services.jira.sop_jira import update_drone_sop_jira_status
from api.drone.services.pop3.sop_pop3 import build_drone_sop_row, upsert_drone_sop_rows

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


def _ensure_target_mapping(
    *,
    sdwt_prod: str | None,
    user_sdwt_prod: str | None,
    target_user_sdwt_prod: str | None = None,
) -> None:
    """테스트용 target_user_sdwt_prod 매핑을 생성합니다."""

    normalized_sdwt = sdwt_prod.strip() if isinstance(sdwt_prod, str) and sdwt_prod.strip() else None
    normalized_user = user_sdwt_prod.strip() if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip() else None
    resolved_target = target_user_sdwt_prod
    if not isinstance(resolved_target, str) or not resolved_target.strip():
        resolved_target = normalized_user or normalized_sdwt
    if not resolved_target:
        return

    DroneSopUserSdwtProdMap.objects.create(
        sdwt_prod=normalized_sdwt,
        user_sdwt_prod=normalized_user,
        target_user_sdwt_prod=resolved_target,
    )


def _create_drone_sop(**overrides: object) -> DroneSOP:
    """테스트용 DroneSOP 기본 행을 생성합니다."""

    payload: dict[str, object] = {
        "line_id": "L1",
        "eqp_id": "EQP1",
        "chamber_ids": "1",
        "lot_id": "LOT.1",
        "main_step": "MS",
        "status": "COMPLETE",
        "needtosend": 1,
        "send_jira": 0,
    }
    payload.update(overrides)
    return DroneSOP.objects.create(**payload)


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
            <defect_png_url>"https://example.com/defect.png"</defect_png_url>
          </data>
        </body></html>
        """

        early_inform_map = {("dummy-prod", "MS"): "ST002"}
        _ensure_target_mapping(sdwt_prod=None, user_sdwt_prod="dummy-prod", target_user_sdwt_prod="dummy-target")
        row = build_drone_sop_row(html=html, early_inform_map=early_inform_map)
        assert row is not None

        self.assertEqual(row["line_id"], "L1")
        self.assertEqual(row["chamber_ids"], "12")
        self.assertEqual(row["knox_id"], "knox")
        self.assertEqual(row["needtosend"], 0)
        self.assertEqual(row["status"], "COMPLETE")
        self.assertEqual(row["defect_url"], "https://example.com")
        self.assertEqual(row["defect_png_url"], "https://example.com/defect.png")
        self.assertEqual(row["custom_end_step"], "ST002")
        self.assertEqual(row["target_user_sdwt_prod"], "dummy-target")

    def test_build_drone_sop_row_fills_system_when_knox_and_user_missing(self) -> None:
        """knox_id/user_sdwt_prod 누락 시 기본값이 채워지는지 확인합니다."""
        html = """
        <data>
          <comment>system-comment</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "System")
        self.assertEqual(row["user_sdwt_prod"], "System")

    def test_build_drone_sop_row_keeps_system_knox_id_even_when_comment_is_long(self) -> None:
        """fallback 시 comment 길이와 무관하게 knox_id가 System인지 확인합니다."""
        html = """
        <data>
          <comment>abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "System")
        self.assertEqual(row["user_sdwt_prod"], "System")

    def test_build_drone_sop_row_applies_needtosend_db_rule(self) -> None:
        """DB 규칙이 needtosend 계산에 적용되는지 확인합니다."""
        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <user_sdwt_prod>prod-1</user_sdwt_prod>
          <comment>hello@$abc</comment>
        </data>
        """
        _ensure_target_mapping(sdwt_prod=None, user_sdwt_prod="prod-1", target_user_sdwt_prod="target-1")
        DroneSopNeedToSendRule.objects.create(
            target_user_sdwt_prod="target-1",
            comment_last_at="$abc",
            ignore_sample_type=False,
        )
        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 1)

    def test_build_drone_sop_row_needtosend_zero_when_db_rule_inactive(self) -> None:
        """DB 규칙이 비활성화되면 needtosend가 0인지 확인합니다."""
        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <user_sdwt_prod>prod-inactive</user_sdwt_prod>
          <comment>hello@$inactive</comment>
        </data>
        """
        _ensure_target_mapping(
            sdwt_prod=None,
            user_sdwt_prod="prod-inactive",
            target_user_sdwt_prod="target-inactive",
        )
        DroneSopNeedToSendRule.objects.create(
            target_user_sdwt_prod="target-inactive",
            comment_last_at="$inactive",
            ignore_sample_type=False,
            is_active=False,
        )

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 0)

    def test_build_drone_sop_row_needtosend_zero_when_mapping_missing(self) -> None:
        """매핑이 없으면 needtosend가 0인지 확인합니다."""
        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <user_sdwt_prod>no-map</user_sdwt_prod>
          <comment>hello@$SETUP_EQP</comment>
        </data>
        """
        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 0)
        self.assertIsNone(row["target_user_sdwt_prod"])

    def test_build_drone_sop_row_needtosend_zero_for_engr_production(self) -> None:
        """ENGR_PRODUCTION 샘플 타입의 needtosend가 0인지 확인합니다."""
        html = """
        <data>
          <sample_type>ENGR_PRODUCTION</sample_type>
          <user_sdwt_prod>prod-2</user_sdwt_prod>
          <comment>hello@$SETUP_EQP</comment>
        </data>
        """
        _ensure_target_mapping(sdwt_prod=None, user_sdwt_prod="prod-2", target_user_sdwt_prod="target-2")
        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 0)


class DroneSopUpsertTests(TestCase):
    """UPSERT 동작을 검증합니다."""

    def test_upsert_does_not_update_comment_or_needtosend_on_conflict(self) -> None:
        """충돌 시 comment/needtosend가 덮어쓰이지 않는지 확인합니다."""
        existing = _create_drone_sop(
            comment="old",
            needtosend=0,
            status="IN_PROGRESS",
            metro_current_step="ST001",
            defect_png_url="https://example.com/old.png",
            target_user_sdwt_prod="old-target",
        )

        upsert_drone_sop_rows(
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
                    "defect_png_url": "https://example.com/new.png",
                    "target_user_sdwt_prod": "new-target",
                }
            ]
        )

        refreshed = DroneSOP.objects.get(id=existing.id)
        self.assertEqual(refreshed.comment, "old")
        self.assertEqual(refreshed.needtosend, 0)
        self.assertEqual(refreshed.status, "COMPLETE")
        self.assertEqual(refreshed.metro_current_step, "ST002")
        self.assertEqual(refreshed.defect_png_url, "https://example.com/new.png")
        self.assertEqual(refreshed.target_user_sdwt_prod, "new-target")

    def test_upsert_overwrites_target_user_sdwt_prod_with_null(self) -> None:
        """target_user_sdwt_prod가 None이면 NULL로 덮어쓰는지 확인합니다."""
        existing = _create_drone_sop(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            target_user_sdwt_prod="old-target",
        )

        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "chamber_ids": "1",
                    "lot_id": "LOT.1",
                    "main_step": "MS",
                    "needtosend": 1,
                    "status": "COMPLETE",
                    "target_user_sdwt_prod": None,
                }
            ]
        )

        refreshed = DroneSOP.objects.get(id=existing.id)
        self.assertIsNone(refreshed.target_user_sdwt_prod)


class DroneSopJiraCandidateTests(TestCase):
    """Jira 후보 조회 로직을 검증합니다."""

    def test_list_drone_sop_jira_candidates_filters_rows(self) -> None:
        """send_jira/needtosend/status/instant_inform 조건이 반영되는지 확인합니다."""
        _create_drone_sop(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
        )
        _create_drone_sop(
            line_id="L2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            status="IN_PROGRESS",
            needtosend=1,
            send_jira=0,
        )
        _create_drone_sop(
            line_id="L3",
            eqp_id="EQP3",
            lot_id="LOT.3",
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
        _create_drone_sop()

        self.assertTrue(selectors.has_drone_sop_jira_candidates())

    def test_has_drone_sop_jira_candidates_returns_false_when_empty(self) -> None:
        """Jira 후보가 없으면 False를 반환하는지 확인합니다."""
        self.assertFalse(selectors.has_drone_sop_jira_candidates())


class DroneSopJiraUpdateTests(TestCase):
    """Jira 상태 업데이트 로직을 검증합니다."""

    def test_update_drone_sop_jira_status_sets_send_jira_and_key(self) -> None:
        """send_jira/jira_key/inform_step이 갱신되는지 확인합니다."""
        row = _create_drone_sop(
            send_jira=0,
            metro_current_step="ST003",
        )

        updated = update_drone_sop_jira_status(
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


class DroneSelectorCaseInsensitiveTests(TestCase):
    """sdwt/user/target 소속 비교의 대소문자 비구분 동작을 검증합니다."""

    def test_selector_lookups_ignore_case_for_user_sdwt_prod_and_target(self) -> None:
        """소속/채널/수신자 조회가 대소문자를 무시하는지 확인합니다."""
        User = get_user_model()
        User.objects.create_user(
            sabun="S71000",
            password="test-password",
            knox_id="knox-71000",
            email="user71000@example.com",
            user_sdwt_prod="TARGET-SDWT",
        )
        account_services.ensure_affiliation_option(
            department="Dept",
            line="L1",
            user_sdwt_prod="TARGET-SDWT",
        )
        DroneSopNeedToSendRule.objects.create(
            target_user_sdwt_prod="TARGET-SDWT",
            comment_last_at="$END",
            ignore_sample_type=False,
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="TARGET-SDWT",
            jira_key="PROJ",
            jira_template_key="common",
        )

        rule = selectors.get_drone_sop_needtosend_rule_by_target(target_user_sdwt_prod="target-sdwt")
        channel = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(
            target_user_sdwt_prod="target-sdwt"
        )
        line_ids = selectors.list_line_ids_for_user_sdwt_prod(user_sdwt_prod="target-sdwt")
        emails = selectors.list_mail_receiver_emails_for_user_sdwt_prod(user_sdwt_prod="target-sdwt")
        knox_ids = selectors.list_messenger_receiver_knox_ids_for_user_sdwt_prod(
            user_sdwt_prod="target-sdwt"
        )

        self.assertIsNotNone(rule)
        if rule is None:
            return
        self.assertEqual(rule.comment_last_at, "$END")
        self.assertIsNotNone(channel)
        if channel is None:
            return
        self.assertEqual(channel.jira_key, "PROJ")
        self.assertEqual(line_ids, ["L1"])
        self.assertEqual(emails, ["user71000@example.com"])
        self.assertEqual(knox_ids, ["knox-71000"])

    def test_build_drone_sop_row_applies_custom_end_step_case_insensitively(self) -> None:
        """조기 알림 custom_end_step 매핑이 user_sdwt_prod 대소문자를 무시하는지 확인합니다."""
        account_services.ensure_affiliation_option(
            department="Dept",
            line="L1",
            user_sdwt_prod="TARGET-SDWT",
        )
        DroneEarlyInform.objects.create(
            line_id="L1",
            main_step="MS",
            custom_end_step="ST003",
        )

        early_inform_map = selectors.load_drone_sop_custom_end_step_map()
        row = build_drone_sop_row(
            html=(
                "<html><body><data>"
                "<line_id>L1</line_id>"
                "<main_step>MS</main_step>"
                "<metro_current_step>ST003</metro_current_step>"
                "<status>IN_PROGRESS</status>"
                "<user_sdwt_prod>target-sdwt</user_sdwt_prod>"
                "</data></body></html>"
            ),
            early_inform_map=early_inform_map,
        )

        self.assertIsNotNone(row)
        if row is None:
            return
        self.assertEqual(row["custom_end_step"], "ST003")
        self.assertEqual(row["status"], "COMPLETE")


class DroneSopInstantInformTests(TestCase):
    """즉시 인폼 요청 로직을 검증합니다."""

    def test_enqueue_instant_inform_marks_requested(self) -> None:
        """즉시 인폼 체크 요청 시 instant_inform과 target 보정이 반영되는지 확인합니다."""
        _ensure_target_mapping(
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            target_user_sdwt_prod="TARGET-SDWT",
        )
        row = _create_drone_sop(
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
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
        self.assertEqual(result.updated_fields.get("target_user_sdwt_prod"), "TARGET-SDWT")
        self.assertIsNone(result.updated_fields.get("send_jira"))

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.comment, "hello")
        self.assertEqual(refreshed.instant_inform, 1)
        self.assertEqual(refreshed.target_user_sdwt_prod, "TARGET-SDWT")
        self.assertEqual(refreshed.send_jira, -1)

    def test_enqueue_instant_inform_resolves_target_case_insensitively(self) -> None:
        """즉시 인폼 대상 매핑이 sdwt/user 소속 대소문자를 무시하는지 확인합니다."""
        _ensure_target_mapping(
            sdwt_prod="SDWT",
            user_sdwt_prod="USR",
            target_user_sdwt_prod="TARGET-SDWT",
        )
        row = _create_drone_sop(
            sdwt_prod="sdwt",
            user_sdwt_prod="usr",
            status="IN_PROGRESS",
            needtosend=0,
            send_jira=-1,
            instant_inform=-1,
        )

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(row.id), comment=None)

        self.assertTrue(result.queued)
        self.assertEqual(result.updated_fields.get("target_user_sdwt_prod"), "TARGET-SDWT")

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.target_user_sdwt_prod, "TARGET-SDWT")

    def test_enqueue_instant_inform_returns_already_informed(self) -> None:
        """이미 Jira 전송된 항목도 instant_inform을 1로 유지하는지 확인합니다."""
        row = _create_drone_sop(
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            send_jira=1,
            instant_inform=0,
            jira_key="JIRA-1",
        )

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(row.id), comment="updated")
        self.assertTrue(result.already_informed)
        self.assertFalse(result.queued)
        self.assertEqual(result.jira_key, "JIRA-1")
        self.assertEqual(result.updated_fields.get("comment"), "updated")
        self.assertEqual(result.updated_fields.get("instant_inform"), 1)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.comment, "updated")
        self.assertEqual(refreshed.instant_inform, 1)


class DroneSopRetryChannelTests(TestCase):
    """단건 채널 재시도 요청 로직을 검증합니다."""

    def test_retry_channel_resets_failed_state_to_pending(self) -> None:
        """실패 채널(send=-1)을 재시도 시 대기(0)로 복구하는지 확인합니다."""
        row = _create_drone_sop(
            send_jira=-1,
            jira_reason="send_failed",
            instant_inform=1,
        )

        result = services.retry_drone_sop_channel(sop_id=int(row.id), channel="jira")
        self.assertTrue(result.queued)
        self.assertFalse(result.already_pending)
        self.assertFalse(result.already_sent)
        self.assertEqual(result.updated_fields.get("send_jira"), 0)
        self.assertIsNone(result.updated_fields.get("jira_reason"))

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.send_jira, 0)
        self.assertIsNone(refreshed.jira_reason)
        self.assertEqual(refreshed.instant_inform, 1)

    def test_retry_channel_returns_already_pending_when_not_failed(self) -> None:
        """실패 상태가 아니면 이미 대기 상태로 응답하는지 확인합니다."""
        row = _create_drone_sop(
            send_messenger=0,
            messenger_reason=None,
        )

        result = services.retry_drone_sop_channel(sop_id=int(row.id), channel="messenger")
        self.assertFalse(result.queued)
        self.assertTrue(result.already_pending)
        self.assertFalse(result.already_sent)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.send_messenger, 0)
        self.assertIsNone(refreshed.messenger_reason)

    def test_retry_channel_rejects_invalid_channel(self) -> None:
        """지원하지 않는 채널 키는 오류로 거부하는지 확인합니다."""
        row = _create_drone_sop(send_mail=-1, mail_reason="send_failed")

        with self.assertRaises(ValueError):
            services.retry_drone_sop_channel(sop_id=int(row.id), channel="sms")


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

    @patch(
        "api.drone.views.selectors.list_drone_sop_jira_target_user_sdwt_prods",
        return_value=["SDWT-A", "SDWT-B"],
    )
    def test_drone_jira_user_sdwt_prods(self, _mock_user_sdwt) -> None:
        """Jira user_sdwt_prod 목록 API가 정상 응답하는지 확인합니다."""
        response = self.client.get(reverse("line-dashboard-jira-user-sdwt-prods"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["userSdwtProds"], ["SDWT-A", "SDWT-B"])

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

    @patch("api.drone.views.services.retry_drone_sop_channel")
    def test_drone_sop_retry_channel(self, mock_service) -> None:
        """채널 재시도 API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            channel="jira",
            queued=True,
            already_pending=False,
            already_sent=False,
            updated_fields={"send_jira": 0, "jira_reason": None},
        )
        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 123}),
            data='{"channel":"jira"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "queued")
        self.assertEqual(response.json().get("channel"), "jira")

    def test_drone_sop_retry_channel_rejects_invalid_channel(self) -> None:
        """지원하지 않는 채널 요청은 400으로 거부하는지 확인합니다."""
        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 123}),
            data='{"channel":"sms"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "channel must be one of: jira, messenger, mail")

    @patch("api.drone.views.services.retry_drone_sop_channel")
    def test_drone_sop_retry_channel_returns_bad_request_when_sop_missing(self, mock_service) -> None:
        """서비스가 SOP 미존재 오류를 반환하면 400으로 응답하는지 확인합니다."""
        mock_service.side_effect = ValueError("DroneSOP not found")

        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 999999}),
            data='{"channel":"jira"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "DroneSOP not found")

    @patch("api.drone.views.services.retry_drone_sop_channel")
    def test_drone_sop_retry_channel_returns_already_pending(self, mock_service) -> None:
        """대기 상태 응답이 API status=already_pending으로 매핑되는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            channel="mail",
            queued=False,
            already_pending=True,
            already_sent=False,
            updated_fields={"send_mail": 0, "mail_reason": None},
        )

        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 123}),
            data='{"channel":"mail"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "already_pending")
        self.assertFalse(response.json().get("queued"))
        self.assertTrue(response.json().get("alreadyPending"))
        self.assertFalse(response.json().get("alreadySent"))

    @patch("api.drone.views.services.retry_drone_sop_channel")
    def test_drone_sop_retry_channel_returns_already_sent(self, mock_service) -> None:
        """완료 상태 응답이 API status=already_sent로 매핑되는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            channel="messenger",
            queued=False,
            already_pending=False,
            already_sent=True,
            updated_fields={"send_messenger": 1, "messenger_reason": None},
        )

        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 123}),
            data='{"channel":"messenger"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "already_sent")
        self.assertFalse(response.json().get("queued"))
        self.assertFalse(response.json().get("alreadyPending"))
        self.assertTrue(response.json().get("alreadySent"))

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
    @patch("api.drone.views.services.run_drone_sop_pipeline_from_env")
    def test_drone_sop_pipeline_trigger(self, mock_service) -> None:
        """통합 파이프라인 트리거 API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            candidates=1,
            jira_created=1,
            jira_updated_rows=0,
            messenger_sent=0,
            mail_sent=0,
            skipped=False,
            skip_reason=None,
        )
        response = self.client.post(
            reverse("drone-sop-pipeline-trigger"),
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    @patch("api.drone.views.services.has_drone_sop_pipeline_candidates")
    def test_drone_sop_pipeline_precheck(self, mock_service) -> None:
        """통합 파이프라인 precheck API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = True
        response = self.client.post(
            reverse("drone-sop-pipeline-precheck"),
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
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            jira_key="PROJ",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("line-dashboard-jira-keys"), {"userSdwtProd": "SDWT"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jiraKey"], "PROJ")
        self.assertEqual(response.json()["templateKey"], "common")

    def test_jira_key_get_matches_user_sdwt_prod_case_insensitively(self) -> None:
        """GET 조회가 userSdwtProd 대소문자를 구분하지 않는지 확인합니다."""
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            jira_key="PROJ",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("line-dashboard-jira-keys"), {"userSdwtProd": "sdwt"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jiraKey"], "PROJ")
        self.assertEqual(response.json()["templateKey"], "common")

    def test_jira_key_get_ignores_inactive_channel(self) -> None:
        """비활성 채널 설정은 조회 응답에서 제외되는지 확인합니다."""
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            jira_key="PROJ",
            is_active=False,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("line-dashboard-jira-keys"), {"userSdwtProd": "SDWT"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["jiraKey"])
        self.assertIsNone(response.json()["templateKey"])

    def test_jira_key_get_rejects_snake_case_query_key(self) -> None:
        """GET 조회는 user_sdwt_prod(snake_case) 쿼리 키를 허용하지 않는지 확인합니다."""

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("line-dashboard-jira-keys"),
            {"user_sdwt_prod": "SDWT"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "userSdwtProd is required")

    def test_jira_key_update_requires_superuser(self) -> None:
        """Jira 키 갱신은 슈퍼유저만 가능해야 합니다."""
        payload = {"userSdwtProd": "SDWT", "jiraKey": "PROJ", "templateKey": "common"}

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

        refreshed = DroneSopUserSdwtChannel.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(refreshed.jira_key, "PROJ")
        self.assertEqual(refreshed.jira_template_key, "common")
        self.assertEqual(refreshed.messenger_template_key, "common")

    def test_jira_key_update_reuses_existing_channel_case_insensitively(self) -> None:
        """POST 갱신이 target_user_sdwt_prod 대소문자를 무시하고 기존 채널을 재사용하는지 확인합니다."""
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT",
            jira_template_key="old",
            jira_key="OLD",
        )

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "userSdwtProd": "sdwt",
                    "jiraKey": "PROJ",
                    "templateKey": "common",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DroneSopUserSdwtChannel.objects.count(), 1)
        refreshed = DroneSopUserSdwtChannel.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(refreshed.jira_key, "PROJ")
        self.assertEqual(refreshed.jira_template_key, "common")

    def test_jira_key_post_rejects_snake_case_user_sdwt_prod(self) -> None:
        """POST 갱신은 user_sdwt_prod(snake_case) 키를 허용하지 않는지 확인합니다."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "user_sdwt_prod": "SDWT",
                    "jiraKey": "PROJ2",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "userSdwtProd is required")

    def test_jira_key_post_rejects_snake_case_jira_template_keys(self) -> None:
        """POST 갱신은 jira_key/template_key(snake_case) 키를 허용하지 않는지 확인합니다."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "userSdwtProd": "SDWT",
                    "jira_key": "PROJ2",
                    "template_key": "H1",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "jiraKey or templateKey is required")

    def test_jira_key_post_keeps_existing_messenger_template_key(self) -> None:
        """Jira 템플릿 갱신 시 기존 메신저 템플릿 키는 덮어쓰지 않는지 확인합니다."""
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT",
            messenger_template_key="H1",
        )

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "userSdwtProd": "SDWT",
                    "templateKey": "common",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        refreshed = DroneSopUserSdwtChannel.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(refreshed.jira_template_key, "common")
        self.assertEqual(refreshed.messenger_template_key, "H1")

    def test_jira_key_post_rejects_non_string_jira_key(self) -> None:
        """POST 갱신은 jiraKey에 문자열/Null 외 타입을 허용하지 않는지 확인합니다."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "userSdwtProd": "SDWT",
                    "jiraKey": 123,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "jiraKey must be a string or null")

    def test_jira_key_post_rejects_non_string_template_key(self) -> None:
        """POST 갱신은 templateKey에 문자열/Null 외 타입을 허용하지 않는지 확인합니다."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "userSdwtProd": "SDWT",
                    "templateKey": ["common"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "templateKey must be a string or null")

    def test_jira_key_post_reactivates_inactive_channel(self) -> None:
        """비활성 채널이 갱신 요청 시 자동 재활성화되는지 확인합니다."""
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            jira_key="OLD",
            is_active=False,
        )

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps({"userSdwtProd": "SDWT", "jiraKey": "NEW"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jiraKey"], "NEW")

        refreshed = DroneSopUserSdwtChannel.objects.get(target_user_sdwt_prod="SDWT")
        self.assertTrue(refreshed.is_active)
        self.assertEqual(refreshed.jira_key, "NEW")


class DroneSopJiraCreateProjectKeyTests(TestCase):
    """Jira 생성 시 프로젝트/템플릿 매핑을 검증합니다."""
    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
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
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT2",
            jira_template_key="H1",
            jira_key="PROJ2",
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT3",
            jira_template_key="common",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")
        _ensure_target_mapping(sdwt_prod="SDWT2", user_sdwt_prod="SDWT2")
        _ensure_target_mapping(sdwt_prod="SDWT3", user_sdwt_prod="SDWT3")

        sop1 = _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            metro_current_step="ST001",
        )
        sop2 = _create_drone_sop(
            line_id="L2",
            sdwt_prod="SDWT2",
            user_sdwt_prod="SDWT2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            metro_current_step="ST002",
        )
        sop_missing = _create_drone_sop(
            line_id="L3",
            sdwt_prod="SDWT3",
            user_sdwt_prod="SDWT3",
            eqp_id="EQP3",
            lot_id="LOT.3",
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
        self.assertIsNone(refreshed1.jira_reason)
        self.assertEqual(refreshed1.jira_key, "PROJ1-1")
        self.assertEqual(refreshed2.send_jira, 1)
        self.assertIsNone(refreshed2.jira_reason)
        self.assertEqual(refreshed2.jira_key, "PROJ2-2")
        self.assertEqual(refreshed_missing.send_jira, -1)
        self.assertEqual(refreshed_missing.jira_reason, "channel_config_invalid")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
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
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        _ensure_target_mapping(sdwt_prod="SDWT", user_sdwt_prod="SDWT")

        sop1 = _create_drone_sop(
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
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
    @patch("api.drone.services.jira.sop_jira._jira_session")
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
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT2",
            jira_key="PROJ2",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")
        _ensure_target_mapping(sdwt_prod="SDWT2", user_sdwt_prod="SDWT2")

        sop1 = _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            metro_current_step="ST001",
        )
        sop2 = _create_drone_sop(
            line_id="L2",
            sdwt_prod="SDWT2",
            user_sdwt_prod="SDWT2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            metro_current_step="ST002",
        )

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.created, 1)

        session.post.assert_called_once()

        refreshed1 = DroneSOP.objects.get(id=sop1.id)
        refreshed2 = DroneSOP.objects.get(id=sop2.id)

        self.assertEqual(refreshed1.send_jira, 1)
        self.assertIsNone(refreshed1.jira_reason)
        self.assertEqual(refreshed2.send_jira, -1)
        self.assertEqual(refreshed2.jira_reason, "channel_config_invalid")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_uses_target_user_sdwt_mapping(self, mock_session: Mock) -> None:
        """target_user_sdwt_prod 매핑이 적용되는지 확인합니다."""
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"issues": [{"key": "PROJ-1"}]}
        session.post.return_value = resp
        mock_session.return_value = session

        DroneSopUserSdwtProdMap.objects.create(
            sdwt_prod="SDWTX",
            user_sdwt_prod="USERX",
            target_user_sdwt_prod="TARGET",
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="TARGET",
            jira_template_key="common",
            jira_key="PROJ",
        )

        sop = _create_drone_sop(
            sdwt_prod="SDWTX",
            user_sdwt_prod="USERX",
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 1)

        session.post.assert_called_once()
        sent_payload = session.post.call_args.kwargs.get("json") or {}
        updates = sent_payload.get("issueUpdates") or []
        self.assertEqual(updates[0].get("fields", {}).get("project", {}).get("key"), "PROJ")

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, 1)
        self.assertEqual(refreshed.target_user_sdwt_prod, "TARGET")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_skips_when_no_channel_config(self, mock_session: Mock) -> None:
        """채널 설정이 없으면 스킵되는지 확인합니다."""
        mock_session.return_value = Mock()

        sop = _create_drone_sop(
            sdwt_prod="SDWT_NO",
            user_sdwt_prod="SDWT_NO",
            metro_current_step="ST001",
        )
        _ensure_target_mapping(sdwt_prod="SDWT_NO", user_sdwt_prod="SDWT_NO")

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 0)
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, -1)
        self.assertEqual(refreshed.jira_reason, "channel_config_missing")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_disabled_channel_without_failure(self, mock_session: Mock) -> None:
        """비활성화된 Jira 채널은 실패(-1) 없이 비활성 사유만 기록하는지 확인합니다."""
        mock_session.return_value = Mock()

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=False,
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

        sop = DroneSOP.objects.create(
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

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 0)
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, 0)
        self.assertEqual(refreshed.jira_reason, "disabled_by_policy")

    @override_settings(DRONE_JIRA_BASE_URL="")
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_failed_when_base_url_missing(self, mock_session: Mock) -> None:
        """Jira 설정이 없으면 실패로 마킹되는지 확인합니다."""
        mock_session.return_value = Mock()

        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            instant_inform=1,
            metro_current_step="ST001",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

        result = services.run_drone_sop_jira_create_from_env()
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "jira_disabled")
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, -1)
        self.assertEqual(refreshed.jira_reason, "config_missing")
        self.assertEqual(refreshed.instant_inform, 1)

    @override_settings(DRONE_JIRA_BASE_URL="")
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_disabled_when_base_url_missing(self, mock_session: Mock) -> None:
        """Jira 설정이 없어도 비활성 채널은 실패 대신 비활성 사유를 기록하는지 확인합니다."""
        mock_session.return_value = Mock()

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=False,
        )

        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            instant_inform=1,
            metro_current_step="ST001",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

        result = services.run_drone_sop_jira_create_from_env()
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "jira_disabled")
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, 0)
        self.assertEqual(refreshed.jira_reason, "disabled_by_policy")
        self.assertEqual(refreshed.instant_inform, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_missing_target_as_failed(self, mock_session: Mock) -> None:
        """sdwt_prod/user_sdwt_prod가 모두 없으면 실패 처리되는지 확인합니다."""
        mock_session.return_value = Mock()

        sop = _create_drone_sop(
            sdwt_prod=None,
            user_sdwt_prod=None,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 0)
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "no_valid_targets")
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, -1)
        self.assertEqual(refreshed.jira_reason, "target_missing")
        self.assertEqual(refreshed.instant_inform, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=False,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    @patch("api.drone.services.jira.sop_jira._single_create_jira_issues")
    def test_jira_create_keeps_instant_inform_when_create_fails(
        self,
        mock_single_create: Mock,
        mock_session: Mock,
    ) -> None:
        """즉시인폼 대상이 생성 실패해도 instant_inform이 유지되는지 확인합니다."""
        mock_session.return_value = Mock()

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT2",
            jira_template_key="common",
            jira_key="PROJ2",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")
        _ensure_target_mapping(sdwt_prod="SDWT2", user_sdwt_prod="SDWT2")

        instant = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            status="IN_PROGRESS",
            needtosend=0,
            instant_inform=1,
            metro_current_step="ST001",
        )
        normal = _create_drone_sop(
            line_id="L2",
            sdwt_prod="SDWT2",
            user_sdwt_prod="SDWT2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            metro_current_step="ST002",
        )

        mock_single_create.return_value = ([normal.id], {normal.id: "PROJ2-1"})

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.created, 1)

        refreshed_instant = DroneSOP.objects.get(id=instant.id)
        refreshed_normal = DroneSOP.objects.get(id=normal.id)

        self.assertEqual(refreshed_instant.instant_inform, 1)
        self.assertEqual(refreshed_instant.send_jira, 0)
        self.assertEqual(refreshed_normal.send_jira, 1)
        mock_single_create.assert_called_once()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=False,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_keeps_pending_when_request_error_occurs(
        self,
        mock_session: Mock,
    ) -> None:
        """일부 요청 예외가 나도 성공 건은 반영하고 실패 건은 0 유지하는지 확인합니다."""
        session = Mock()
        mock_session.return_value = session

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT_ENABLED_1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=True,
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT_ENABLED_2",
            jira_template_key="common",
            jira_key="PROJ2",
            jira_enabled=True,
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT_DISABLED",
            jira_template_key="common",
            jira_key="PROJ3",
            jira_enabled=False,
        )
        _ensure_target_mapping(sdwt_prod="SDWT_ENABLED_1", user_sdwt_prod="SDWT_ENABLED_1")
        _ensure_target_mapping(sdwt_prod="SDWT_ENABLED_2", user_sdwt_prod="SDWT_ENABLED_2")
        _ensure_target_mapping(sdwt_prod="SDWT_DISABLED", user_sdwt_prod="SDWT_DISABLED")

        enabled_row_1 = _create_drone_sop(
            sdwt_prod="SDWT_ENABLED_1",
            user_sdwt_prod="SDWT_ENABLED_1",
            metro_current_step="ST001",
        )
        enabled_row_2 = _create_drone_sop(
            line_id="L2",
            sdwt_prod="SDWT_ENABLED_2",
            user_sdwt_prod="SDWT_ENABLED_2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            metro_current_step="ST001",
        )
        disabled_row = _create_drone_sop(
            line_id="L3",
            sdwt_prod="SDWT_DISABLED",
            user_sdwt_prod="SDWT_DISABLED",
            eqp_id="EQP3",
            lot_id="LOT.3",
            metro_current_step="ST001",
        )

        ok_resp = Mock(status_code=201)
        ok_resp.json.return_value = {"key": "PROJ2-1"}

        def _post_side_effect(*args: Any, **kwargs: Any) -> Mock:
            payload = kwargs.get("json") or {}
            project_key = (
                payload.get("fields", {})
                .get("project", {})
                .get("key")
            )
            if project_key == "PROJ1":
                raise requests.Timeout("jira unavailable")
            return ok_resp

        session.post.side_effect = _post_side_effect

        result = services.run_drone_sop_jira_create_from_env()
        self.assertEqual(result.candidates, 3)
        self.assertEqual(result.created, 1)

        refreshed_enabled_1 = DroneSOP.objects.get(id=enabled_row_1.id)
        refreshed_enabled_2 = DroneSOP.objects.get(id=enabled_row_2.id)
        refreshed_disabled = DroneSOP.objects.get(id=disabled_row.id)

        self.assertEqual(refreshed_enabled_1.send_jira, 0)
        self.assertIsNone(refreshed_enabled_1.jira_reason)
        self.assertEqual(refreshed_enabled_2.send_jira, 1)
        self.assertIsNone(refreshed_enabled_2.jira_reason)
        self.assertEqual(refreshed_disabled.send_jira, 0)
        self.assertEqual(refreshed_disabled.jira_reason, "disabled_by_policy")
        self.assertEqual(session.post.call_count, 2)


class DroneSopInformPolicyTests(TestCase):
    """멀티 채널 알림 정책을 검증합니다."""

    def setUp(self) -> None:
        """테스트에 필요한 기본 매핑을 준비합니다."""

        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

    @override_settings(DRONE_JIRA_BASE_URL="http://example.local/jira")
    @patch("api.drone.services.mail.mail_sender.send_drone_sop_mail")
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_inform_marks_missing_target_as_failed(
        self,
        mock_session: Mock,
        mock_messenger: Mock,
        mock_mail: Mock,
    ) -> None:
        """sdwt_prod/user_sdwt_prod가 없으면 실패 처리되는지 확인합니다."""
        mock_session.return_value = Mock()

        sop = _create_drone_sop(
            sdwt_prod=None,
            user_sdwt_prod=None,
            send_messenger=0,
            send_mail=0,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "no_valid_targets")

        mock_session.assert_not_called()
        mock_messenger.assert_not_called()
        mock_mail.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, -1)
        self.assertEqual(refreshed.send_messenger, -1)
        self.assertEqual(refreshed.send_mail, -1)
        self.assertEqual(refreshed.jira_reason, "target_missing")
        self.assertEqual(refreshed.messenger_reason, "target_missing")
        self.assertEqual(refreshed.mail_reason, "target_missing")
        self.assertEqual(refreshed.instant_inform, 1)

    def test_inform_persists_target_for_non_jira_pending_channel(self) -> None:
        """Jira 미대상 행도 target_user_sdwt_prod가 저장되는지 확인합니다."""
        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_jira=-1,
            send_messenger=0,
            send_mail=1,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.target_user_sdwt_prod, "SDWT1")
        self.assertEqual(refreshed.send_jira, -1)

    @override_settings(DRONE_JIRA_BASE_URL="")
    def test_inform_marks_jira_failed_when_base_url_missing(self) -> None:
        """Jira 설정이 없으면 send_jira가 실패 처리되는지 확인합니다."""
        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_messenger=1,
            send_mail=1,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, -1)
        self.assertEqual(refreshed.jira_reason, "config_missing")
        self.assertEqual(refreshed.instant_inform, 1)
        self.assertEqual(refreshed.send_messenger, 1)
        self.assertEqual(refreshed.send_mail, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    def test_inform_marks_jira_disabled_when_base_url_missing(self) -> None:
        """Jira 설정이 없어도 비활성 채널은 실패 대신 비활성 사유를 기록하는지 확인합니다."""
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=False,
        )

        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_messenger=1,
            send_mail=1,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, 0)
        self.assertEqual(refreshed.jira_reason, "disabled_by_policy")
        self.assertEqual(refreshed.instant_inform, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="",
    )
    @patch.dict(os.environ, {"DRONE_MAIL_SENDER": ""})
    def test_inform_marks_mail_failed_when_sender_missing(self) -> None:
        """메일 발신자 미설정 시 send_mail이 실패 처리되는지 확인합니다."""
        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_jira=1,
            send_messenger=1,
            send_mail=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_mail, -1)
        self.assertEqual(refreshed.mail_reason, "config_missing")
        self.assertEqual(refreshed.send_jira, 1)
        self.assertEqual(refreshed.send_messenger, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="",
    )
    def test_inform_marks_mail_disabled_when_sender_missing(self) -> None:
        """메일 발신자 설정이 없어도 비활성 채널은 실패 대신 비활성 사유를 기록하는지 확인합니다."""
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            mail_template_key="common",
            mail_enabled=False,
        )

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=1,
            send_mail=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_mail, 0)
        self.assertEqual(refreshed.mail_reason, "disabled_by_policy")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch.dict(
        os.environ,
        {
            "KNOX_MESSENGER_API_BASE_URL": "http://example.local/messenger/",
            "KNOX_MESSENGER_AUTHORIZATION": "dummy-auth",
            "KNOX_MESSENGER_SYSTEM_ID": "dummy-system",
        },
    )
    def test_inform_marks_messenger_failed_when_channel_missing(self) -> None:
        """채널 설정이 없으면 send_messenger가 실패 처리되는지 확인합니다."""
        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_messenger, -1)
        self.assertEqual(refreshed.messenger_reason, "channel_config_missing")
        self.assertEqual(refreshed.send_jira, 1)
        self.assertEqual(refreshed.send_mail, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch.dict(
        os.environ,
        {
            "KNOX_MESSENGER_API_BASE_URL": "http://example.local/messenger/",
            "KNOX_MESSENGER_AUTHORIZATION": "dummy-auth",
            "KNOX_MESSENGER_SYSTEM_ID": "dummy-system",
        },
    )
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_failed_when_template_missing(self, mock_messenger: Mock) -> None:
        """메신저 템플릿 키가 없으면 send_messenger가 실패 처리되는지 확인합니다."""
        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            chatroom_id=12345,
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_messenger, -1)
        self.assertEqual(refreshed.messenger_reason, "template_missing")
        mock_messenger.assert_not_called()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch.dict(
        os.environ,
        {
            "KNOX_MESSENGER_API_BASE_URL": "",
            "KNOX_MESSENGER_AUTHORIZATION": "",
            "KNOX_MESSENGER_SYSTEM_ID": "",
        },
    )
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_failed_when_knox_config_missing(self, mock_messenger: Mock) -> None:
        """Knox 메신저 설정이 없으면 send_messenger가 실패 처리되는지 확인합니다."""
        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            chatroom_id=12345,
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_messenger, -1)
        self.assertEqual(refreshed.messenger_reason, "config_missing")
        mock_messenger.assert_not_called()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch.dict(
        os.environ,
        {
            "KNOX_MESSENGER_API_BASE_URL": "",
            "KNOX_MESSENGER_AUTHORIZATION": "",
            "KNOX_MESSENGER_SYSTEM_ID": "",
        },
    )
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_disabled_when_knox_config_missing(self, mock_messenger: Mock) -> None:
        """Knox 설정이 없어도 비활성 채널은 실패 대신 비활성 사유를 기록하는지 확인합니다."""
        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            chatroom_id=12345,
            messenger_enabled=False,
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_messenger, 0)
        self.assertEqual(refreshed.messenger_reason, "disabled_by_policy")
        mock_messenger.assert_not_called()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_inform_marks_jira_disabled_without_failure(self, mock_session: Mock) -> None:
        """비활성화된 Jira 채널은 실패(-1) 없이 비활성 사유만 기록하는지 확인합니다."""
        mock_session.return_value = Mock()

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=False,
        )

        sop = DroneSOP.objects.create(
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
            send_messenger=1,
            send_mail=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, 0)
        self.assertEqual(refreshed.jira_reason, "disabled_by_policy")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.run_drone_sop_jira_create_from_rows")
    def test_inform_uses_shared_jira_service_path(self, mock_run_jira: Mock) -> None:
        """inform 경로가 공통 Jira 서비스 함수를 사용해 결과를 반영하는지 확인합니다."""
        mock_run_jira.return_value = services.DroneSopJiraCreateResult(
            candidates=1,
            created=1,
            updated_rows=1,
        )

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        DroneSOP.objects.create(
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
            send_messenger=1,
            send_mail=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.jira_created, 1)
        self.assertEqual(result.jira_updated_rows, 1)
        mock_run_jira.assert_called_once()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch.dict(
        os.environ,
        {
            "KNOX_MESSENGER_API_BASE_URL": "http://example.local/messenger/",
            "KNOX_MESSENGER_AUTHORIZATION": "dummy-auth",
            "KNOX_MESSENGER_SYSTEM_ID": "dummy-system",
        },
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.run_drone_sop_jira_create_from_rows")
    def test_inform_continues_messenger_when_jira_pipeline_fails(
        self,
        mock_run_jira: Mock,
        mock_messenger: Mock,
    ) -> None:
        """Jira 처리 예외가 발생해도 메신저 채널 처리가 계속되는지 확인합니다."""
        mock_run_jira.side_effect = RuntimeError("jira unavailable")

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            messenger_template_key="common",
            chatroom_id=12345,
        )
        sop = DroneSOP.objects.create(
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
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.jira_created, 0)
        self.assertEqual(result.messenger_sent, 1)
        mock_run_jira.assert_called_once()
        mock_messenger.assert_called_once()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_jira, 0)
        self.assertIsNone(refreshed.jira_reason)
        self.assertEqual(refreshed.send_messenger, 1)
        self.assertIsNotNone(refreshed.informed_at)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.mail.mail_sender.send_drone_sop_mail")
    def test_inform_sets_informed_at_when_mail_succeeds(self, mock_mail: Mock) -> None:
        """메일 전송 성공 시 informed_at이 설정되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(sabun="S84001", password="test-password")
        user.user_sdwt_prod = "SDWT1"
        user.email = "user84001@example.com"
        user.save(update_fields=["user_sdwt_prod", "email"])

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            mail_template_key="common",
        )

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=1,
            send_mail=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)
        mock_mail.assert_called_once()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_mail, 1)
        self.assertIsNotNone(refreshed.informed_at)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch.dict(
        os.environ,
        {
            "KNOX_MESSENGER_API_BASE_URL": "http://example.local/messenger/",
            "KNOX_MESSENGER_AUTHORIZATION": "dummy-auth",
            "KNOX_MESSENGER_SYSTEM_ID": "dummy-system",
        },
    )
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_disabled_without_failure(self, mock_messenger: Mock) -> None:
        """비활성화된 메신저 채널은 실패(-1) 없이 비활성 사유만 기록하는지 확인합니다."""
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
            chatroom_id=12345,
            messenger_enabled=False,
        )

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)
        mock_messenger.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_messenger, 0)
        self.assertEqual(refreshed.messenger_reason, "disabled_by_policy")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.mail.mail_sender.send_drone_sop_mail")
    def test_inform_marks_mail_disabled_without_failure(self, mock_mail: Mock) -> None:
        """비활성화된 메일 채널은 실패(-1) 없이 비활성 사유만 기록하는지 확인합니다."""
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            mail_template_key="common",
            mail_enabled=False,
        )

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=1,
            send_mail=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)
        mock_mail.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.send_mail, 0)
        self.assertEqual(refreshed.mail_reason, "disabled_by_policy")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch.dict(
        os.environ,
        {
            "KNOX_MESSENGER_API_BASE_URL": "http://example.local/messenger/",
            "KNOX_MESSENGER_AUTHORIZATION": "dummy-auth",
            "KNOX_MESSENGER_SYSTEM_ID": "dummy-system",
        },
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.messenger_services.create_chatroom")
    @patch("api.drone.services.inform.sop_inform.messenger_services.resolve_user_ids_by_single_ids")
    def test_inform_creates_chatroom_when_chatroom_id_missing(
        self,
        mock_resolve_user_ids: Mock,
        mock_create_chatroom: Mock,
        mock_messenger: Mock,
    ) -> None:
        """chatroom_id가 없으면 채팅방을 생성하고 전송하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) Knox userID/채팅방 생성 mock 준비
        # -----------------------------------------------------------------------------
        mock_resolve_user_ids.return_value = ["user-001", "user-002"]
        mock_create_chatroom.return_value = 4567

        # -----------------------------------------------------------------------------
        # 2) 수신자 사용자/채널/SOP 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user_a = User.objects.create_user(sabun="S83001", password="test-password")
        user_a.user_sdwt_prod = "SDWT1"
        user_a.knox_id = "knox-001"
        user_a.save(update_fields=["user_sdwt_prod", "knox_id"])

        user_b = User.objects.create_user(sabun="S83002", password="test-password")
        user_b.user_sdwt_prod = "SDWT1"
        user_b.knox_id = " knox-002 "
        user_b.save(update_fields=["user_sdwt_prod", "knox_id"])

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
        )

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )

        # -----------------------------------------------------------------------------
        # 3) 멀티 채널 전송 실행
        # -----------------------------------------------------------------------------
        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.messenger_sent, 1)

        # -----------------------------------------------------------------------------
        # 4) 채팅방 생성/전송/상태 반영 검증
        # -----------------------------------------------------------------------------
        mock_resolve_user_ids.assert_called_once()
        self.assertEqual(
            mock_resolve_user_ids.call_args.kwargs.get("single_ids"),
            ["knox-001", "knox-002"],
        )

        mock_create_chatroom.assert_called_once()
        self.assertEqual(
            mock_create_chatroom.call_args.kwargs.get("user_ids"),
            ["user-001", "user-002"],
        )
        self.assertEqual(
            mock_create_chatroom.call_args.kwargs.get("title"),
            "Drone SOP - SDWT1",
        )

        mock_messenger.assert_called_once()
        self.assertEqual(
            mock_messenger.call_args.kwargs.get("chatroom_id"),
            4567,
        )
        self.assertEqual(
            mock_messenger.call_args.kwargs.get("messenger_template_key"),
            "common",
        )

        refreshed_channel = DroneSopUserSdwtChannel.objects.get(target_user_sdwt_prod="SDWT1")
        self.assertEqual(refreshed_channel.chatroom_id, 4567)

        refreshed_sop = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed_sop.send_messenger, 1)
        self.assertIsNone(refreshed_sop.messenger_reason)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch.dict(
        os.environ,
        {
            "KNOX_MESSENGER_API_BASE_URL": "http://example.local/messenger/",
            "KNOX_MESSENGER_AUTHORIZATION": "dummy-auth",
            "KNOX_MESSENGER_SYSTEM_ID": "dummy-system",
        },
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.messenger_services.create_chatroom")
    @patch("api.drone.services.inform.sop_inform.messenger_services.resolve_user_ids_by_single_ids")
    def test_inform_creates_chatroom_once_per_target_with_multiple_rows(
        self,
        mock_resolve_user_ids: Mock,
        mock_create_chatroom: Mock,
        mock_messenger: Mock,
    ) -> None:
        """동일 target 다건 처리 시 채팅방을 1회만 생성하는지 확인합니다."""
        mock_resolve_user_ids.return_value = ["user-001", "user-002"]
        mock_create_chatroom.return_value = 4567

        User = get_user_model()
        user_a = User.objects.create_user(sabun="S83003", password="test-password")
        user_a.user_sdwt_prod = "SDWT1"
        user_a.knox_id = "knox-003"
        user_a.save(update_fields=["user_sdwt_prod", "knox_id"])

        user_b = User.objects.create_user(sabun="S83004", password="test-password")
        user_b.user_sdwt_prod = "SDWT1"
        user_b.knox_id = "knox-004"
        user_b.save(update_fields=["user_sdwt_prod", "knox_id"])

        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
        )

        sop_1 = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.11",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )
        sop_2 = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.12",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.messenger_sent, 2)

        mock_resolve_user_ids.assert_called_once()
        mock_create_chatroom.assert_called_once()
        self.assertEqual(mock_messenger.call_count, 2)

        refreshed_channel = DroneSopUserSdwtChannel.objects.get(target_user_sdwt_prod="SDWT1")
        self.assertEqual(refreshed_channel.chatroom_id, 4567)

        refreshed_1 = DroneSOP.objects.get(id=sop_1.id)
        refreshed_2 = DroneSOP.objects.get(id=sop_2.id)
        self.assertEqual(refreshed_1.send_messenger, 1)
        self.assertEqual(refreshed_2.send_messenger, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch.dict(
        os.environ,
        {
            "KNOX_MESSENGER_API_BASE_URL": "http://example.local/messenger/",
            "KNOX_MESSENGER_AUTHORIZATION": "dummy-auth",
            "KNOX_MESSENGER_SYSTEM_ID": "dummy-system",
        },
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.messenger_services.create_chatroom")
    @patch("api.drone.services.inform.sop_inform.messenger_services.resolve_user_ids_by_single_ids")
    def test_inform_reuses_chatroom_id_when_present(
        self,
        mock_resolve_user_ids: Mock,
        mock_create_chatroom: Mock,
        mock_messenger: Mock,
    ) -> None:
        """chatroom_id가 있으면 채팅방 생성 없이 재사용하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 채널/SOP 데이터 준비
        # -----------------------------------------------------------------------------
        DroneSopUserSdwtChannel.objects.create(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
            chatroom_id=12345,
        )

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            metro_current_step="ST001",
        )

        # -----------------------------------------------------------------------------
        # 2) 멀티 채널 전송 실행
        # -----------------------------------------------------------------------------
        result = services.run_drone_sop_pipeline_from_env()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.messenger_sent, 1)

        # -----------------------------------------------------------------------------
        # 3) 채팅방 재사용/전송 검증
        # -----------------------------------------------------------------------------
        mock_resolve_user_ids.assert_not_called()
        mock_create_chatroom.assert_not_called()
        mock_messenger.assert_called_once()
        self.assertEqual(
            mock_messenger.call_args.kwargs.get("chatroom_id"),
            12345,
        )
        self.assertEqual(
            mock_messenger.call_args.kwargs.get("messenger_template_key"),
            "common",
        )

        refreshed_channel = DroneSopUserSdwtChannel.objects.get(target_user_sdwt_prod="SDWT1")
        self.assertEqual(refreshed_channel.chatroom_id, 12345)

        refreshed_sop = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed_sop.send_messenger, 1)
        self.assertIsNone(refreshed_sop.messenger_reason)


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
    @patch("api.drone.views.services.run_drone_sop_pipeline_from_env")
    def test_pipeline_trigger_requires_token(self, mock_run: Mock) -> None:
        """통합 파이프라인 트리거가 토큰을 요구하는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            candidates=1,
            jira_created=1,
            jira_updated_rows=0,
            messenger_sent=0,
            mail_sent=0,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-pipeline-trigger")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_run.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["jiraCreated"], 1)
        mock_run.assert_called_once_with(limit=None)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.run_drone_sop_pipeline_from_env")
    def test_legacy_inform_trigger_alias_is_removed(self, mock_run: Mock) -> None:
        """레거시 inform 트리거 경로가 제거되었는지 확인합니다."""

        url = "/api/v1/line-dashboard/sop/inform/trigger"
        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 404)
        mock_run.assert_not_called()

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.has_drone_sop_pipeline_candidates")
    def test_pipeline_precheck_requires_token(self, mock_service: Mock) -> None:
        """통합 파이프라인 precheck가 토큰을 요구하는지 확인합니다."""
        mock_service.return_value = True
        url = reverse("drone-sop-pipeline-precheck")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_service.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("hasCandidates"))
        mock_service.assert_called_once_with()

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.run_drone_sop_pipeline_from_env")
    def test_pipeline_trigger_prefers_payload_limit_over_query_param(self, mock_run: Mock) -> None:
        """통합 파이프라인에서 payload limit가 query param보다 우선되는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            candidates=1,
            jira_created=1,
            jira_updated_rows=1,
            messenger_sent=1,
            mail_sent=1,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-pipeline-trigger") + "?limit=5"
        payload = json.dumps({"limit": 2})
        resp = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )

        self.assertEqual(resp.status_code, 200)
        mock_run.assert_called_once_with(limit=2)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.run_drone_sop_pipeline_from_env")
    def test_pipeline_trigger_ignores_channels_payload(self, mock_run: Mock) -> None:
        """통합 파이프라인 트리거는 channels 입력을 무시하는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            candidates=1,
            jira_created=1,
            jira_updated_rows=1,
            messenger_sent=1,
            mail_sent=1,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-pipeline-trigger")
        payload = json.dumps({"channels": ["jira", "mail"]})
        resp = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("channels", resp.json())
        mock_run.assert_called_once_with(limit=None)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.has_drone_sop_pipeline_candidates")
    def test_pipeline_precheck_ignores_channels_payload(self, mock_service: Mock) -> None:
        """통합 파이프라인 precheck는 channels 입력을 무시하는지 확인합니다."""
        mock_service.return_value = True
        url = reverse("drone-sop-pipeline-precheck")
        payload = json.dumps({"channels": ["messenger"]})
        resp = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("channels", resp.json())
        mock_service.assert_called_once_with()


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
    )
    @patch.dict(os.environ, {"DRONE_SOP_POP3_SUBJECT": "[drone_sop] a,[drone_sop] b,[drone_sop] c"})
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
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
    )
    @patch.dict(os.environ, {"DRONE_SOP_POP3_SUBJECT": "[DRONE_SOP] A,[drone_sop] c"})
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
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
    )
    @patch.dict(os.environ, {"DRONE_SOP_POP3_SUBJECT": "[drone_sop]"})
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
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

    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
    )
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_skips_all_when_subject_env_missing(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
    ) -> None:
        """제목 환경변수가 없으면 기본 fallback 없이 전체 스킵하는지 확인합니다."""
        mock_list.return_value = [
            {"id": 1, "subject": "[drone_sop] alert-1", "body_html": "<data><lot_id>LOT-1</lot_id></data>"},
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        with patch.dict(os.environ, {"DRONE_SOP_POP3_SUBJECT": ""}, clear=False):
            result = services.run_drone_sop_pop3_ingest_from_env()

        self.assertEqual(result.matched_mails, 0)
        self.assertEqual(result.upserted_rows, 0)
        self.assertEqual(result.deleted_mails, 0)
        mock_upsert.assert_not_called()
        mock_delete.assert_not_called()


class DroneSopDefectMapPostTests(TestCase):
    """defectmap POST 연동을 검증합니다."""

    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_SOP_DEFECTMAP_URL="http://10.172.114.185:30912/defectmap",
    )
    @patch.dict(os.environ, {"DRONE_SOP_POP3_SUBJECT": "[drone_sop]"})
    @patch("api.drone.services.pop3.defectmap_sidecar.requests.post")
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    @patch(
        "api.drone.services.pop3.sop_pop3.timezone.now",
        return_value=datetime(2026, 2, 5, 4, 0, 0, 750000, tzinfo=dt_timezone.utc),
    )
    def test_dummy_mode_posts_defect_png_url_to_defectmap(
        self,
        _mock_now: Mock,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
        mock_post: Mock,
    ) -> None:
        """defect_png_url이 있으면 지정 payload로 POST 요청을 보내는지 확인합니다."""
        mock_list.return_value = [
            {
                "id": 1,
                "subject": "[drone_sop] alert-1",
                "body_html": (
                    "<data>"
                    "<lot_id>LOT-1</lot_id>"
                    "<metro_current_step>ST003</metro_current_step>"
                    '<defect_png_url>"https://example.com/defect.png"</defect_png_url>'
                    "</data>"
                ),
            }
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_env()

        self.assertEqual(result.matched_mails, 1)
        self.assertEqual(result.upserted_rows, 1)
        self.assertEqual(result.deleted_mails, 1)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.args[0], "http://10.172.114.185:30912/defectmap")
        self.assertEqual(
            mock_post.call_args.kwargs.get("json"),
            {
                "lotid": "LOT-1",
                "scandate": "2026-02-05 13:00:00.750 +0900",
                "step": "",
                "stepid": "ST003",
                "data": "https://example.com/defect.png",
            },
        )

    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_SOP_DEFECTMAP_URL="http://10.172.114.185:30912/defectmap",
    )
    @patch.dict(os.environ, {"DRONE_SOP_POP3_SUBJECT": "[drone_sop]"})
    @patch("api.drone.services.pop3.defectmap_sidecar.requests.post")
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_skips_defectmap_post_when_defect_png_url_empty(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
        mock_post: Mock,
    ) -> None:
        """defect_png_url이 없으면 POST 요청을 보내지 않는지 확인합니다."""
        mock_list.return_value = [
            {
                "id": 1,
                "subject": "[drone_sop] alert-1",
                "body_html": "<data><lot_id>LOT-1</lot_id><metro_current_step>ST003</metro_current_step></data>",
            }
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_env()

        self.assertEqual(result.matched_mails, 1)
        self.assertEqual(result.upserted_rows, 1)
        self.assertEqual(result.deleted_mails, 1)
        mock_post.assert_not_called()


class DroneSopJiraHtmlDescriptionTests(TestCase):
    """Jira 설명 HTML 렌더링을 검증합니다."""

    def test_build_jira_issue_fields_uses_html(self) -> None:
        """HTML 템플릿이 포함되는지 확인합니다."""
        from api.drone.services.jira import delivery as jira_delivery

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

        fields = jira_delivery._build_jira_issue_fields(
            row=row,
            project_key="DUMMY",
            template_key="common",
            config=config,
        )
        description = fields.get("description") or ""
        self.assertIn("<table", description)
        self.assertIn("CTTTM URL", description)
        self.assertIn("Defect URL", description)
        self.assertIn("https://example.com/defect", description)

    def test_build_jira_issue_fields_renders_ctttm_links(self) -> None:
        """CTTTM 링크가 렌더링되는지 확인합니다."""
        from api.drone.services.jira import delivery as jira_delivery

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

        fields = jira_delivery._build_jira_issue_fields(
            row=row,
            project_key="DUMMY",
            template_key="common",
            config=config,
        )
        description = fields.get("description") or ""
        self.assertIn("https://example.com/ctttm", description)
        self.assertIn(">EQP-1<", description)


class DroneSopJiraSummaryTests(TestCase):
    """Jira 요약 템플릿 적용을 검증합니다."""

    def test_build_jira_issue_fields_uses_template_summary(self) -> None:
        """템플릿별 summary 포맷이 적용되는지 확인합니다."""
        from api.drone.services.jira import delivery as jira_delivery

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

        def build_common_summary(data: dict[str, object]) -> str:
            sdwt = str(data.get("sdwt_prod") or "?").strip() or "?"
            return f"{data.get('line_id')}-{sdwt[:1]}"

        def build_H1_summary(data: dict[str, object]) -> str:
            sdwt = str(data.get("sdwt_prod") or "?").strip() or "?"
            step = str(data.get("main_step") or "??").strip() or "??"
            normalized_step = step[2:].upper() if len(step) >= 3 else step.upper()
            return f"{sdwt[:1]}-{normalized_step}"

        with patch.dict(
            jira_delivery.SUMMARY_BUILDERS,
            {
                "common": build_common_summary,
                "H1": build_H1_summary,
            },
            clear=True,
        ):
            fields_a = jira_delivery._build_jira_issue_fields(
                row=row,
                project_key="DUMMY",
                template_key="common",
                config=config,
            )
            fields_b = jira_delivery._build_jira_issue_fields(
                row=row,
                project_key="DUMMY",
                template_key="H1",
                config=config,
            )

        self.assertEqual(fields_a.get("summary"), "L1-S")
        self.assertEqual(fields_b.get("summary"), "S-003")

    def test_H1_summary_uses_layer_main_step_lot_id(self) -> None:
        """H1 summary가 layer/main_step/lot_id 규칙을 반영하는지 확인합니다."""
        from api.drone.services.jira.templates import jira_template_h1

        row = {
            "sdwt_prod": "SDWT",
            "main_step": "A-000320",
            "ppid": "N000000",
            "lot_id": "LOT.1",
        }
        summary = jira_template_h1.build_summary(row)

        self.assertEqual(summary, "S FA A-000320 LOT.1")

    def test_H1_find_layer_supports_zero_padded_rule_bounds(self) -> None:
        """H1 layer 규칙에서 선행 0 문자열 범위를 처리하는지 확인합니다."""
        from api.drone.services.jira.templates import jira_template_h1

        with patch.object(
            jira_template_h1,
            "_LAYER_RULES",
            (("A", "000320", "058120", "AA"),),
        ):
            self.assertEqual(jira_template_h1.find_layer("AB000320"), "AA")
            self.assertEqual(jira_template_h1.find_layer("AB058120"), "AA")
            self.assertEqual(jira_template_h1.find_layer("AB058121"), "[BEOL 인폼 필요]")

    def test_mail_template_h1_reuses_jira_layer_summary(self) -> None:
        """mail H1 템플릿이 Jira H1의 layer 요약 함수를 재사용하는지 확인합니다."""
        from api.drone.services.mail.templates import mail_template_h1

        row = {
            "sdwt_prod": "SDWT",
            "main_step": "A-000320",
            "ppid": "N000000",
            "lot_id": "LOT.1",
        }
        self.assertEqual(mail_template_h1.find_layer("AB000320"), "FA")
        self.assertEqual(mail_template_h1.build_summary(row), "S FA A-000320 LOT.1")


class DroneSopMessengerLineATemplateTests(TestCase):
    """common 메신저 템플릿의 Excel Table 전송 경로를 검증합니다."""

    @patch("api.drone.services.messenger.templates.messenger_template_common.messenger_services.send_excel_table_message_from_file")
    def test_send_excel_table_message_uses_knox_excel_sender(self, mock_send_excel: Mock) -> None:
        """common 템플릿이 Excel Table API를 호출하는지 확인합니다."""

        from api.drone.services.messenger.templates import messenger_template_common as common_template
        from api.messenger import services as messenger_services

        captured: dict[str, str] = {}

        def _capture_excel_payload(**kwargs: object) -> None:
            html_path = str(kwargs.get("html_path") or "")
            with open(html_path, "r", encoding="utf-8") as file:
                captured["html"] = file.read()
            captured["html_path"] = html_path

        mock_send_excel.side_effect = _capture_excel_payload
        config = messenger_services.KnoxMessengerConfig(
            base_url="http://example.local/messenger/",
            authorization="Bearer test",
            system_id="sys-test",
            timeout_seconds=5,
        )

        common_template.send_excel_table_message(
            chatroom_id=123,
            context={
                "sop_id": "1",
                "main_step": "ST003",
                "ppid": "PPID",
                "eqp_cb": "EQP-1",
                "lot_id": "LOT-1",
                "user_sdwt_prod": "SDWT",
                "knoxid": "knox",
                "comment_raw": "코멘트",
            },
            actions=[
                {
                    "type": "Action.OpenUrl",
                    "title": "CTTTM",
                    "url": "https://example.com/ctttm",
                }
            ],
            ttl=900,
            config=config,
        )

        mock_send_excel.assert_called_once()
        self.assertIn("<table ", captured.get("html", ""))
        self.assertIn("Step_seq", captured.get("html", ""))
        self.assertIn("📄 CTTTM URL", captured.get("html", ""))
        self.assertIn("https://example.com/ctttm", captured.get("html", ""))
        self.assertFalse(os.path.exists(captured.get("html_path", "")))


class DroneSopMessengerLineBTemplateTests(TestCase):
    """H1 메신저 템플릿의 Excel Table 전송 경로를 검증합니다."""

    @patch("api.drone.services.messenger.templates.messenger_template_h1.messenger_services.send_excel_table_message_from_file")
    def test_send_excel_table_message_uses_knox_excel_sender(self, mock_send_excel: Mock) -> None:
        """H1 템플릿이 Excel Table API를 호출하는지 확인합니다."""

        from api.drone.services.messenger.templates import messenger_template_h1 as H1_template
        from api.messenger import services as messenger_services

        captured: dict[str, str] = {}

        def _capture_excel_payload(**kwargs: object) -> None:
            html_path = str(kwargs.get("html_path") or "")
            with open(html_path, "r", encoding="utf-8") as file:
                captured["html"] = file.read()
            captured["html_path"] = html_path

        mock_send_excel.side_effect = _capture_excel_payload
        config = messenger_services.KnoxMessengerConfig(
            base_url="http://example.local/messenger/",
            authorization="Bearer test",
            system_id="sys-test",
            timeout_seconds=5,
        )

        H1_template.send_excel_table_message(
            chatroom_id=456,
            context={
                "main_step": "A-000320",
                "ppid": "AB000320",
                "eqp_cb": "EQP-9",
                "lot_id": "LOT-9",
                "user_sdwt_prod": "SDWT-B",
                "knoxid": "knox-b",
                "comment_raw": "H1 코멘트",
            },
            actions=[
                {
                    "type": "Action.OpenUrl",
                    "title": "Defect",
                    "url": "https://example.com/defect",
                }
            ],
            ttl=1200,
            config=config,
        )

        mock_send_excel.assert_called_once()
        self.assertIn("<table ", captured.get("html", ""))
        self.assertIn("Step_seq", captured.get("html", ""))
        self.assertIn("🧩 Layer : ", captured.get("html", ""))
        self.assertIn("</span>FA</td>", captured.get("html", ""))
        self.assertIn("💿 Defect URL", captured.get("html", ""))
        self.assertIn("https://example.com/defect", captured.get("html", ""))
        self.assertFalse(os.path.exists(captured.get("html_path", "")))


class DroneSopMessengerApiRoutingTests(TestCase):
    """템플릿 키별 메신저 전송 라우팅을 검증합니다."""

    def _build_config(self):
        from api.drone.services.messenger import messenger_api
        from api.messenger import services as messenger_services

        return messenger_api.DroneMessengerConfig(
            ttl=1800,
            knox_config=messenger_services.KnoxMessengerConfig(
                base_url="http://example.local/messenger/",
                authorization="Bearer test",
                system_id="sys-test",
                timeout_seconds=5,
            ),
        )

    @patch("api.drone.services.messenger.messenger_api.build_drone_sop_messenger_template_inputs")
    def test_common_uses_excel_table_sender(self, mock_build_inputs: Mock) -> None:
        """common는 Excel Table sender를 사용하는지 확인합니다."""

        from api.drone.services.messenger import messenger_api

        config = self._build_config()
        row = {"id": 1}
        mock_build_inputs.return_value = ({"sop_id": "1"}, [])
        mock_sender = Mock()

        with patch.dict(
            messenger_api.EXCEL_TABLE_TEMPLATE_SENDERS,
            {"common": mock_sender},
            clear=False,
        ):
            messenger_api.send_drone_sop_messenger_message(
                row=row,
                chatroom_id=777,
                messenger_template_key="common",
                config=config,
            )

        mock_build_inputs.assert_called_once_with(row=row)
        mock_sender.assert_called_once_with(
            chatroom_id=777,
            context={"sop_id": "1"},
            actions=[],
            ttl=1800,
            config=config.knox_config,
        )

    @patch("api.drone.services.messenger.messenger_api.build_drone_sop_messenger_template_inputs")
    def test_H1_uses_excel_table_sender(self, mock_build_inputs: Mock) -> None:
        """H1도 Excel Table sender를 사용하는지 확인합니다."""

        from api.drone.services.messenger import messenger_api

        config = self._build_config()
        row = {"id": 2}
        mock_build_inputs.return_value = ({"main_step": "ST009"}, [])
        mock_sender = Mock()

        with patch.dict(
            messenger_api.EXCEL_TABLE_TEMPLATE_SENDERS,
            {"H1": mock_sender},
            clear=False,
        ):
            messenger_api.send_drone_sop_messenger_message(
                row=row,
                chatroom_id=888,
                messenger_template_key="H1",
                config=config,
            )

        mock_build_inputs.assert_called_once_with(row=row)
        mock_sender.assert_called_once_with(
            chatroom_id=888,
            context={"main_step": "ST009"},
            actions=[],
            ttl=1800,
            config=config.knox_config,
        )

    def test_unsupported_template_key_raises_error(self) -> None:
        """미지원 템플릿 키는 ValueError를 발생시키는지 확인합니다."""

        from api.drone.services.messenger import messenger_api

        config = self._build_config()
        with self.assertRaises(ValueError):
            messenger_api.send_drone_sop_messenger_message(
                row={"id": 3},
                chatroom_id=999,
                messenger_template_key="unknown-template",
                config=config,
            )


class DroneTableSchemaHelpersTests(SimpleTestCase):
    """Drone 테이블 스키마 유틸 정규화/필터 규칙을 검증합니다."""

    def test_sanitize_identifier_returns_value_when_valid(self) -> None:
        """유효한 식별자는 그대로 반환되는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertEqual(table_schema.sanitize_identifier(" table_1 "), "table_1")

    def test_sanitize_identifier_uses_fallback_when_invalid(self) -> None:
        """유효하지 않은 값은 fallback으로 대체되는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertEqual(table_schema.sanitize_identifier("table-name", "fallback_table"), "fallback_table")

    def test_sanitize_identifier_rejects_invalid_fallback(self) -> None:
        """fallback도 유효하지 않으면 None을 반환하는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertIsNone(table_schema.sanitize_identifier(None, "bad-name"))

    def test_sanitize_identifier_trims_fallback(self) -> None:
        """fallback 공백이 제거되어 반환되는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertEqual(table_schema.sanitize_identifier(123, "  ok_table "), "ok_table")

    def test_build_line_filters_returns_empty_when_line_missing(self) -> None:
        """lineId가 없으면 필터가 비어있는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(["sdwt_prod", "line_id"], None)

        self.assertEqual(result["filters"], [])
        self.assertEqual(result["params"], [])

    def test_normalize_line_filter_mode_defaults_to_target_when_invalid(self) -> None:
        """lineFilterMode가 유효하지 않으면 target_user_sdwt_prod 기본값으로 보정되는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertEqual(
            table_schema.normalize_line_filter_mode("invalid-mode"),
            table_schema.LINE_FILTER_MODE_TARGET_USER_SDWT,
        )

    def test_build_line_filters_prefers_sdwt_prod(self) -> None:
        """sdwt_prod가 있으면 sdwt_prod 기준 필터를 사용하는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(["user_sdwt_prod", "sdwt_prod", "line_id"], "L1")

        expected = (
            "LOWER(sdwt_prod) IN ("
            f"SELECT LOWER(user_sdwt_prod) FROM {table_schema.LINE_SDWT_TABLE_NAME} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1"])

    def test_build_line_filters_uses_target_user_sdwt_prod_when_requested(self) -> None:
        """target_user_sdwt_prod 모드에서 target_user_sdwt_prod 기준 필터를 사용하는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(
            ["target_user_sdwt_prod", "sdwt_prod", "user_sdwt_prod", "line_id"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_TARGET_USER_SDWT,
        )

        expected = (
            "LOWER(target_user_sdwt_prod) IN ("
            f"SELECT LOWER(user_sdwt_prod) FROM {table_schema.LINE_SDWT_TABLE_NAME} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1"])

    def test_build_line_filters_uses_user_sdwt_prod_when_requested(self) -> None:
        """user_sdwt_prod 모드에서 user_sdwt_prod 기준 필터를 사용하는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(
            ["target_user_sdwt_prod", "sdwt_prod", "user_sdwt_prod", "line_id"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_USER_SDWT,
        )

        expected = (
            "LOWER(user_sdwt_prod) IN ("
            f"SELECT LOWER(user_sdwt_prod) FROM {table_schema.LINE_SDWT_TABLE_NAME} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1"])

    def test_build_line_filters_uses_sdwt_prod_only_when_requested(self) -> None:
        """sdwt_prod 모드에서 sdwt_prod 기준 필터를 사용하는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(
            ["target_user_sdwt_prod", "sdwt_prod", "user_sdwt_prod", "line_id"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_SDWT,
        )

        expected = (
            "LOWER(sdwt_prod) IN ("
            f"SELECT LOWER(user_sdwt_prod) FROM {table_schema.LINE_SDWT_TABLE_NAME} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1"])

    def test_build_line_filters_uses_user_sdwt_prod_when_sdwt_missing(self) -> None:
        """sdwt_prod가 없으면 user_sdwt_prod 기준 필터를 사용하는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(["user_sdwt_prod", "line_id"], "L1")

        expected = (
            "LOWER(user_sdwt_prod) IN ("
            f"SELECT LOWER(user_sdwt_prod) FROM {table_schema.LINE_SDWT_TABLE_NAME} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1"])

    def test_build_line_filters_falls_back_to_line_id(self) -> None:
        """sdwt_prod가 없으면 line_id 직접 비교로 fallback 되는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(["line_id", "created_at"], "L1")

        self.assertEqual(result["filters"], ["line_id = %s"])
        self.assertEqual(result["params"], ["L1"])


class DroneTablesEndpointTests(TestCase):
    """라인 대시보드 테이블 엔드포인트를 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/클라이언트를 준비합니다."""

        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S41000",
            password="test-password",
            knox_id="knox-41000",
        )
        self.client.force_login(self.user)

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_returns_payload(self, mock_schema: Mock, mock_fetch_rows: Mock) -> None:
        """테이블 목록 조회가 정상 응답하는지 확인합니다."""

        mock_schema.return_value = SimpleNamespace(
            name="demo_table",
            columns=["id", "created_at"],
            timestamp_column="created_at",
        )
        mock_fetch_rows.return_value = [{"id": 1, "created_at": "2024-01-01 00:00:00"}]

        response = self.client.get(reverse("drone-tables"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["table"], "demo_table")
        self.assertEqual(payload["rowCount"], 1)

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.build_line_filters")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_defaults_to_target_user_sdwt_filter_mode(
        self,
        mock_schema: Mock,
        mock_build_line_filters: Mock,
        mock_fetch_rows: Mock,
    ) -> None:
        """lineFilterMode 미지정 시 target_user_sdwt_prod 모드가 기본 적용되는지 확인합니다."""

        from api.drone.services import table_schema

        mock_schema.return_value = SimpleNamespace(
            name="demo_table",
            columns=["id", "created_at", "target_user_sdwt_prod"],
            timestamp_column="created_at",
        )
        mock_build_line_filters.return_value = {"filters": [], "params": []}
        mock_fetch_rows.return_value = []

        response = self.client.get(reverse("drone-tables"), {"lineId": "L1"})
        self.assertEqual(response.status_code, 200)
        mock_build_line_filters.assert_called_once_with(
            ["id", "created_at", "target_user_sdwt_prod"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_TARGET_USER_SDWT,
        )

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.build_line_filters")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_accepts_sdwt_filter_mode_override(
        self,
        mock_schema: Mock,
        mock_build_line_filters: Mock,
        mock_fetch_rows: Mock,
    ) -> None:
        """lineFilterMode=sdwt_prod가 전달되면 sdwt_prod 모드로 조회하는지 확인합니다."""

        from api.drone.services import table_schema

        mock_schema.return_value = SimpleNamespace(
            name="demo_table",
            columns=["id", "created_at", "sdwt_prod"],
            timestamp_column="created_at",
        )
        mock_build_line_filters.return_value = {"filters": [], "params": []}
        mock_fetch_rows.return_value = []

        response = self.client.get(
            reverse("drone-tables"),
            {"lineId": "L1", "lineFilterMode": table_schema.LINE_FILTER_MODE_SDWT},
        )
        self.assertEqual(response.status_code, 200)
        mock_build_line_filters.assert_called_once_with(
            ["id", "created_at", "sdwt_prod"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_SDWT,
        )

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.build_line_filters")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_accepts_user_sdwt_filter_mode_override(
        self,
        mock_schema: Mock,
        mock_build_line_filters: Mock,
        mock_fetch_rows: Mock,
    ) -> None:
        """lineFilterMode=user_sdwt_prod가 전달되면 user_sdwt_prod 모드로 조회하는지 확인합니다."""

        from api.drone.services import table_schema

        mock_schema.return_value = SimpleNamespace(
            name="demo_table",
            columns=["id", "created_at", "user_sdwt_prod"],
            timestamp_column="created_at",
        )
        mock_build_line_filters.return_value = {"filters": [], "params": []}
        mock_fetch_rows.return_value = []

        response = self.client.get(
            reverse("drone-tables"),
            {"lineId": "L1", "lineFilterMode": table_schema.LINE_FILTER_MODE_USER_SDWT},
        )
        self.assertEqual(response.status_code, 200)
        mock_build_line_filters.assert_called_once_with(
            ["id", "created_at", "user_sdwt_prod"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_USER_SDWT,
        )

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_returns_raw_reason_columns_without_aliases(
        self,
        mock_schema: Mock,
        mock_fetch_rows: Mock,
    ) -> None:
        """테이블 조회 응답은 reason 원본 컬럼만 반환하고 별칭을 추가하지 않는지 확인합니다."""

        mock_schema.return_value = SimpleNamespace(
            name="drone_sop",
            columns=["id", "created_at", "jira_reason", "messenger_reason", "mail_reason"],
            timestamp_column="created_at",
        )
        mock_fetch_rows.return_value = [
            {
                "id": 1,
                "created_at": "2024-01-01 00:00:00",
                "jira_reason": "disabled_by_policy",
                "messenger_reason": None,
                "mail_reason": "send_failed",
            }
        ]

        response = self.client.get(reverse("drone-tables"), {"table": "drone_sop"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["columns"],
            ["id", "created_at", "jira_reason", "messenger_reason", "mail_reason"],
        )
        row = payload["rows"][0]
        self.assertEqual(row["jira_reason"], "disabled_by_policy")
        self.assertIsNone(row["messenger_reason"])
        self.assertEqual(row["mail_reason"], "send_failed")
        self.assertNotIn("jiraReason", row)
        self.assertNotIn("messengerReason", row)
        self.assertNotIn("mailReason", row)

    @patch("api.drone.services.table_ops.execute")
    @patch("api.drone.services.table_ops._fetch_row")
    @patch("api.drone.services.table_ops.table_schema.list_table_columns")
    def test_tables_update_returns_success(
        self,
        mock_columns: Mock,
        mock_fetch_row: Mock,
        mock_execute: Mock,
    ) -> None:
        """테이블 업데이트가 성공 응답을 반환하는지 확인합니다."""

        mock_columns.return_value = ["id", "comment"]
        mock_execute.return_value = (1, None)
        mock_fetch_row.side_effect = [{"id": 10, "comment": "before"}, {"id": 10, "comment": "updated"}]

        response = self.client.patch(
            reverse("drone-tables-update"),
            data='{"table":"demo_table","id":10,"updates":{"comment":"updated"}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    @patch("api.drone.services.table_ops.execute")
    def test_tables_update_rejects_values_alias(self, mock_execute: Mock) -> None:
        """values 별칭만 전달하면 400 오류를 반환하는지 확인합니다."""

        response = self.client.patch(
            reverse("drone-tables-update"),
            data='{"table":"demo_table","id":11,"values":{"comment":"updated"}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "Updates must be an object")
        mock_execute.assert_not_called()
