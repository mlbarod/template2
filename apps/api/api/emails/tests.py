# =============================================================================
# 모듈 설명: emails 도메인의 서비스/셀렉터/뷰 동작을 검증합니다.
# - 주요 범위: 소속 판별, 이동/삭제, Outbox 처리, API 엔드포인트
# - 불변 조건: 테스트는 DB 트랜잭션을 사용하며 시간은 timezone-aware입니다.
# =============================================================================

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone as dt_timezone
from email.message import EmailMessage
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

import api.account.services as account_services
from api.common.services import UNASSIGNED_USER_SDWT_PROD
from api.emails.models import Email, EmailAsset, EmailOutbox
from api.emails.selectors import get_filtered_emails, resolve_email_affiliation
from api.emails.services import (
    _parse_message_to_fields,
    claim_unassigned_emails_for_user,
    delete_single_email,
    enqueue_rag_index_for_emails,
    enqueue_rag_index,
    ingest_pop3_mailbox,
    move_emails_to_user_sdwt_prod,
    move_sender_emails_after,
    parse_datetime_value,
    process_email_outbox_batch,
    store_email_html_and_assets,
)
from api.rag.services import RAG_INDEX_EMAILS, resolve_rag_index_name

UTC = getattr(timezone, "utc", dt_timezone.utc)


def _set_current_affiliation(user, *, user_sdwt_prod: str) -> None:
    """테스트 사용자의 현재 앱 소속을 설정합니다."""

    account_services.set_current_affiliation_for_user(
        user=user,
        department="Dept",
        line="Line",
        user_sdwt_prod=user_sdwt_prod,
    )


@override_settings(TIME_ZONE="Asia/Seoul")
class EmailQueryFilterTests(SimpleTestCase):
    """emails.services.query_filters의 날짜 파싱을 검증합니다."""

    def test_parse_datetime_value_naive_is_utc(self) -> None:
        """타임존 없는 문자열이 KST로 해석되어 UTC로 변환되는지 확인합니다."""

        parsed = parse_datetime_value("2025-01-01T10:00:00")

        self.assertIsNotNone(parsed)
        self.assertTrue(timezone.is_aware(parsed))
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.hour, 1)

    def test_parse_datetime_value_with_offset_converts_to_utc(self) -> None:
        """오프셋이 포함된 입력이 UTC 기준으로 변환되는지 확인합니다."""

        parsed = parse_datetime_value("2025-01-01T10:00:00+09:00")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.hour, 1)

    def test_parse_datetime_value_date_only_returns_midnight_utc(self) -> None:
        """날짜만 입력된 경우 KST 자정을 UTC로 변환하는지 확인합니다."""

        parsed = parse_datetime_value("2025-01-01")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 12)
        self.assertEqual(parsed.day, 31)
        self.assertEqual(parsed.hour, 15)
        self.assertEqual(parsed.minute, 0)

    def test_parse_datetime_value_accepts_datetime(self) -> None:
        """datetime 입력이 UTC timezone-aware로 변환되는지 확인합니다."""

        parsed = parse_datetime_value(datetime(2025, 1, 1, 10, 0, 0))

        self.assertIsNotNone(parsed)
        self.assertTrue(timezone.is_aware(parsed))
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.hour, 1)

    def test_parse_datetime_value_accepts_date(self) -> None:
        """date 입력이 UTC 자정으로 변환되는지 확인합니다."""

        parsed = parse_datetime_value(date(2025, 1, 1))

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 12)
        self.assertEqual(parsed.day, 31)
        self.assertEqual(parsed.hour, 15)
        self.assertEqual(parsed.minute, 0)

    def test_parse_datetime_value_date_only_end_boundary(self) -> None:
        """종료일 경계가 KST 기준 하루 끝으로 변환되는지 확인합니다."""

        parsed = parse_datetime_value("2025-01-01", boundary="end")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.year, 2025)
        self.assertEqual(parsed.month, 1)
        self.assertEqual(parsed.day, 1)
        self.assertEqual(parsed.hour, 14)
        self.assertEqual(parsed.minute, 59)
        self.assertEqual(parsed.second, 59)
        self.assertEqual(parsed.microsecond, 999999)


class EmailAffiliationTests(TestCase):
    """emails.selectors / emails.services의 소속 판별/재분류 동작을 검증합니다."""

    def test_resolve_email_affiliation_uses_user_knox_id(self) -> None:
        """사용자 knox_id 기반 소속 판별이 우선 적용되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/소속 데이터 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S12345", password="test-password")
        user.knox_id = "loginid1"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        affiliation = resolve_email_affiliation(sender_id="loginid1", received_at=timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-a")

    def test_resolve_email_affiliation_unknown_sender_defaults_to_unassigned(self) -> None:
        """미확인 발신자는 UNASSIGNED로 분류되는지 확인합니다.

        입력:
            없음.
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        affiliation = resolve_email_affiliation(sender_id="unknown-sender", received_at=timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], UNASSIGNED_USER_SDWT_PROD)

    def test_resolve_email_affiliation_uses_external_prediction(self) -> None:
        """외부 예측 소속이 있는 경우 해당 값을 사용하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 예측 스냅샷 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        account_services.sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext",
                    "department": "Dept",
                    "user_sdwt_prod": "group-pred",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        affiliation = resolve_email_affiliation(sender_id="loginid-ext", received_at=timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-pred")

    def test_resolve_email_affiliation_uses_current_user_sdwt_prod(self) -> None:
        """현재 user_sdwt_prod가 최우선으로 유지되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/변경 이력 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S77777", password="test-password")
        user.knox_id = "loginid3"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-old")

        # -------------------------------------------------------------------------
        # 1) 소속 옵션 및 변경 요청 준비
        # -------------------------------------------------------------------------
        effective_from = timezone.now()
        option = account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-new",
        )
        approver = User.objects.create_user(sabun="S77778", password="test-password")
        _set_current_affiliation(approver, user_sdwt_prod="group-new")
        account_services.ensure_self_access(approver, role="manager")
        payload, status_code = account_services.request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=effective_from,
            timezone_name="Asia/Seoul",
        )
        self.assertEqual(status_code, 202)

        # -------------------------------------------------------------------------
        # 2) 승인 권한 보장 및 승인 처리
        # -------------------------------------------------------------------------
        approve_payload, approve_status = account_services.approve_affiliation_change(
            approver=approver,
            change_id=payload["changeId"],
        )
        self.assertEqual(approve_status, 200)
        self.assertEqual(approve_payload.get("status"), "approved")

        before = resolve_email_affiliation(sender_id="loginid3", received_at=effective_from - timedelta(hours=1))
        self.assertEqual(before["user_sdwt_prod"], "group-new")

        after = resolve_email_affiliation(sender_id="loginid3", received_at=effective_from + timedelta(hours=1))
        self.assertEqual(after["user_sdwt_prod"], "group-new")


class EmailMoveServiceTests(TestCase):
    """emails.services 이동/삭제 관련 동작을 검증합니다."""

    @patch("api.emails.services.insert_email_to_rag")
    def test_enqueue_rag_index_for_emails_reports_missing_ids(self, _mock_insert: Mock) -> None:
        """존재하지 않는 id가 ragMissing으로 집계되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="rag-missing-msg",
            received_at=timezone.now(),
            subject="Missing",
            sender="missing@example.com",
            sender_id="loginid-missing",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
            body_text="Body",
        )

        result = enqueue_rag_index_for_emails(
            email_ids=[email.id, 999999],
            target_user_sdwt_prod="group-a",
            previous_user_sdwt_prod_by_email_id=None,
        )

        self.assertEqual(result["ragRegistered"], 1)
        self.assertEqual(result["ragMissing"], 1)
        self.assertEqual(result["ragFailed"], 0)
        self.assertEqual(EmailOutbox.objects.count(), 0)

    @patch("api.emails.services.insert_email_to_rag")
    def test_move_emails_to_user_sdwt_prod_updates_rows(self, _mock_insert: Mock) -> None:
        """메일함 이동 시 user_sdwt_prod가 갱신되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성/수정.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email_a = Email.objects.create(
            message_id="move-msg-a",
            received_at=timezone.now(),
            subject="A",
            sender="a@example.com",
            sender_id="loginid-move",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A",
        )
        email_b = Email.objects.create(
            message_id="move-msg-b",
            received_at=timezone.now(),
            subject="B",
            sender="a@example.com",
            sender_id="loginid-move",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body B",
        )

        result = move_emails_to_user_sdwt_prod(
            email_ids=[email_a.id, email_b.id],
            to_user_sdwt_prod="group-new",
        )
        self.assertEqual(result["moved"], 2)

        email_a.refresh_from_db()
        email_b.refresh_from_db()
        self.assertEqual(email_a.user_sdwt_prod, "group-new")
        self.assertEqual(email_b.user_sdwt_prod, "group-new")
        self.assertTrue(bool(email_a.rag_doc_id))

    @patch("api.emails.services.insert_email_to_rag")
    def test_move_emails_to_user_sdwt_prod_reports_missing_ids(self, _mock_insert: Mock) -> None:
        """존재하지 않는 id가 ragMissing으로 집계되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성/수정.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="move-missing-msg",
            received_at=timezone.now(),
            subject="Missing",
            sender="missing@example.com",
            sender_id="loginid-move-missing",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        result = move_emails_to_user_sdwt_prod(
            email_ids=[email.id, 999999],
            to_user_sdwt_prod="group-b",
        )

        self.assertEqual(result["moved"], 1)
        self.assertEqual(result["ragRegistered"], 1)
        self.assertEqual(result["ragMissing"], 1)
        self.assertEqual(result["ragFailed"], 0)

        email.refresh_from_db()
        self.assertEqual(email.user_sdwt_prod, "group-b")

    @patch("api.emails.services.insert_email_to_rag")
    def test_move_sender_emails_after_filters_by_time(self, _mock_insert: Mock) -> None:
        """기준 시각 이후 메일만 이동되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성/수정.
        오류:
            조건 불일치 시 assertion 실패.
        """

        sender_id = "loginid-time"
        old = Email.objects.create(
            message_id="move-time-old",
            received_at=timezone.now() - timedelta(days=2),
            subject="Old",
            sender="a@example.com",
            sender_id=sender_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body Old",
        )
        new = Email.objects.create(
            message_id="move-time-new",
            received_at=timezone.now() - timedelta(hours=1),
            subject="New",
            sender="a@example.com",
            sender_id=sender_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body New",
        )

        cutoff = timezone.now() - timedelta(days=1)
        result = move_sender_emails_after(
            sender_id=sender_id,
            received_at_gte=cutoff,
            to_user_sdwt_prod="group-b",
        )
        self.assertEqual(result["moved"], 1)

        old.refresh_from_db()
        new.refresh_from_db()
        self.assertEqual(old.user_sdwt_prod, "group-a")
        self.assertEqual(new.user_sdwt_prod, "group-b")

    @patch("api.emails.services.insert_email_to_rag")
    def test_claim_unassigned_emails_for_user_includes_missing_count(self, _mock_insert: Mock) -> None:
        """UNASSIGNED 메일 귀속 결과 집계가 올바른지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S22222", password="test-password")
        user.knox_id = "loginid-claim"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-claim")

        Email.objects.create(
            message_id="claim-msg-a",
            received_at=timezone.now(),
            subject="Claim",
            sender="claim@example.com",
            sender_id="loginid-claim",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body",
        )

        result = claim_unassigned_emails_for_user(user=user)

        self.assertEqual(result["moved"], 1)
        self.assertEqual(result["ragRegistered"], 1)
        self.assertEqual(result["ragMissing"], 0)
        self.assertEqual(result["ragFailed"], 0)


class EmailOutboxTests(TestCase):
    """emails.services RAG Outbox 처리 동작을 검증합니다."""

    @patch("api.emails.services.insert_email_to_rag")
    def test_process_outbox_index_updates_email(self, mock_insert: Mock) -> None:
        """Outbox 인덱싱 처리 후 상태가 업데이트되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email/Outbox 생성 및 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="outbox-msg-1",
            received_at=timezone.now(),
            subject="Outbox",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
            body_text="Body",
        )

        enqueue_rag_index(email=email)

        result = process_email_outbox_batch(limit=10)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["succeeded"], 1)

        email.refresh_from_db()
        outbox_item = EmailOutbox.objects.get()
        self.assertEqual(outbox_item.status, EmailOutbox.Status.DONE)
        self.assertEqual(email.rag_index_status, Email.RagIndexStatus.INDEXED)
        self.assertTrue(bool(email.rag_doc_id))
        mock_insert.assert_called_once()
        args, kwargs = mock_insert.call_args
        self.assertEqual(args[0].id, email.id)
        self.assertEqual(kwargs.get("index_name"), resolve_rag_index_name(RAG_INDEX_EMAILS))
        self.assertEqual(kwargs.get("permission_groups"), ["group-a", "sender"])

    @patch("api.emails.services.delete_rag_doc")
    @patch("api.emails.services.mutations.delete_email_objects")
    def test_delete_email_enqueues_outbox(self, _mock_delete_objects: Mock, mock_delete: Mock) -> None:
        """삭제 시 Outbox가 적재되고 처리되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email/Outbox 생성 및 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="outbox-msg-2",
            received_at=timezone.now(),
            subject="Delete",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            rag_doc_id="email-outbox-2",
            body_text="Body",
        )

        delete_single_email(email.id)

        self.assertFalse(Email.objects.filter(id=email.id).exists())
        outbox_item = EmailOutbox.objects.get(action=EmailOutbox.Action.DELETE)
        self.assertEqual(outbox_item.payload.get("rag_doc_id"), "email-outbox-2")

        process_email_outbox_batch(limit=10)

        outbox_item.refresh_from_db()
        self.assertEqual(outbox_item.status, EmailOutbox.Status.DONE)
        mock_delete.assert_called_once_with(
            "email-outbox-2",
            index_name=resolve_rag_index_name(RAG_INDEX_EMAILS),
            permission_groups=["group-a", "sender"],
        )


class EmailMailboxAccessViewTests(TestCase):
    """emails 뷰에서 user_sdwt_prod 기반 접근 제어를 검증합니다."""

    def test_user_only_sees_own_mailbox_by_default(self) -> None:
        """일반 사용자가 기본적으로 자신의 메일함만 보는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S11111", password="test-password")
        user.knox_id = "knox-11111"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        Email.objects.create(
            message_id="msg-a",
            received_at=timezone.now(),
            subject="A",
            sender="a@example.com",
            sender_id="a",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A",
        )
        Email.objects.create(
            message_id="msg-b",
            received_at=timezone.now(),
            subject="B",
            sender="b@example.com",
            sender_id="b",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body B",
        )

        self.client.force_login(user)

        response = self.client.get(reverse("emails-inbox"))
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-a"})

        detail = self.client.get(reverse("emails-detail", kwargs={"email_id": Email.objects.get(message_id="msg-b").id}))
        self.assertEqual(detail.status_code, 403)

    def test_missing_knox_id_is_forbidden(self) -> None:
        """knox_id가 없으면 접근이 거부되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S11110", password="test-password")
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        self.client.force_login(user)

        response = self.client.get(reverse("emails-inbox"))
        self.assertEqual(response.status_code, 403)

    def test_sender_can_access_sent_email_without_mailbox_access(self) -> None:
        """발신자는 메일함 접근 권한 없이도 보낸메일 접근이 가능한지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S11113", password="test-password")
        user.knox_id = "loginid-sender"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        sent_email = Email.objects.create(
            message_id="msg-sent-1",
            received_at=timezone.now(),
            subject="Sent",
            sender="sender@example.com",
            sender_id="loginid-sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body",
        )

        self.client.force_login(user)

        detail = self.client.get(reverse("emails-detail", kwargs={"email_id": sent_email.id}))
        self.assertEqual(detail.status_code, 200)

        sent_list = self.client.get(reverse("emails-sent"))
        self.assertEqual(sent_list.status_code, 200)
        results = sent_list.json()["results"]
        self.assertTrue(any(item["id"] == sent_email.id for item in results))

    def test_sent_rejects_knox_id_query_param(self) -> None:
        """보낸메일 조회에서 knox_id 파라미터가 거부되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S11114", password="test-password")
        user.knox_id = "loginid-sender"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        self.client.force_login(user)

        response = self.client.get(reverse("emails-sent"), {"knox_id": "loginid-sender"})
        self.assertEqual(response.status_code, 400)

    def test_mailbox_list_includes_empty_granted_mailbox(self) -> None:
        """접근 권한만 있는 빈 메일함도 목록에 포함되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/접근 권한 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S11112", password="test-password")
        user.knox_id = "knox-11112"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        manager = User.objects.create_user(sabun="S11113", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-empty")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-empty",
            target_user=user,
            action="grant",
            role="member",
        )
        self.assertEqual(status_code, 200)

        self.client.force_login(user)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200)
        self.assertIn("__sent__", mailbox_list.json()["results"])
        self.assertIn("group-a", mailbox_list.json()["results"])
        self.assertIn("group-empty", mailbox_list.json()["results"])

    def test_user_can_select_granted_mailbox(self) -> None:
        """접근 권한이 있는 메일함을 선택해 조회할 수 있는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email/권한 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S22222", password="test-password")
        user.knox_id = "knox-22222"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        manager = User.objects.create_user(sabun="S22223", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=user,
            action="grant",
            role="member",
        )
        self.assertEqual(status_code, 200)

        Email.objects.create(
            message_id="msg-a2",
            received_at=timezone.now(),
            subject="A2",
            sender="a@example.com",
            sender_id="a",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A2",
        )
        Email.objects.create(
            message_id="msg-b2",
            received_at=timezone.now(),
            subject="B2",
            sender="b@example.com",
            sender_id="b",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body B2",
        )

        self.client.force_login(user)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200)
        self.assertEqual(mailbox_list.json()["results"], ["__sent__", "group-a", "group-b"])

        response = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": "group-b"})
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-b"})

    def test_user_can_view_mailbox_members_for_accessible_mailbox(self) -> None:
        """접근 가능한 메일함의 멤버 목록을 조회할 수 있는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email/권한 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        requester = User.objects.create_user(sabun="S33333", password="test-password")
        requester.username = "홍길동"
        requester.knox_id = "loginid-requester"
        requester.save(update_fields=["username", "knox_id"])
        _set_current_affiliation(requester, user_sdwt_prod="group-a")

        affiliated = User.objects.create_user(sabun="S33334", password="test-password")
        affiliated.username = "김철수"
        affiliated.knox_id = "loginid-affiliated"
        affiliated.save(update_fields=["username", "knox_id"])
        _set_current_affiliation(affiliated, user_sdwt_prod="group-a")

        granted = User.objects.create_user(sabun="S33335", password="test-password")
        granted.username = "이영희"
        granted.knox_id = "loginid-granted"
        granted.save(update_fields=["username", "knox_id"])
        _set_current_affiliation(granted, user_sdwt_prod="group-b")
        manager = User.objects.create_user(sabun="S33336", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-a")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-a",
            target_user=granted,
            action="grant",
            role="manager",
        )
        self.assertEqual(status_code, 200)

        Email.objects.create(
            message_id="mailbox-members-1",
            received_at=timezone.now(),
            subject="Requester mail 1",
            sender="requester@example.com",
            sender_id=requester.knox_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        Email.objects.create(
            message_id="mailbox-members-2",
            received_at=timezone.now(),
            subject="Requester mail 2",
            sender="requester@example.com",
            sender_id=requester.knox_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        Email.objects.create(
            message_id="mailbox-members-3",
            received_at=timezone.now(),
            subject="Affiliated mail 1",
            sender="affiliated@example.com",
            sender_id=affiliated.knox_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        Email.objects.create(
            message_id="mailbox-members-outside",
            received_at=timezone.now(),
            subject="Outside mailbox",
            sender="requester@example.com",
            sender_id=requester.knox_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body",
        )

        self.client.force_login(requester)

        response = self.client.get(reverse("emails-mailbox-members"), {"user_sdwt_prod": "group-a"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        members = payload["members"]
        member_ids = {item["userId"] for item in members}
        self.assertEqual(member_ids, {requester.id, affiliated.id, granted.id, manager.id})

        requester_member = next(item for item in members if item["userId"] == requester.id)
        self.assertEqual(requester_member["emailCount"], 2)
        self.assertEqual(requester_member["username"], requester.username)
        self.assertEqual(requester_member["knoxId"], requester.knox_id)

        affiliated_member = next(item for item in members if item["userId"] == affiliated.id)
        self.assertEqual(affiliated_member["emailCount"], 1)
        self.assertEqual(affiliated_member["username"], affiliated.username)
        self.assertEqual(affiliated_member["knoxId"], affiliated.knox_id)

        granted_member = next(item for item in members if item["userId"] == granted.id)
        self.assertEqual(granted_member["role"], "manager")
        self.assertEqual(granted_member["emailCount"], 0)
        self.assertEqual(granted_member["username"], granted.username)
        self.assertEqual(granted_member["knoxId"], granted.knox_id)

    def test_user_cannot_view_mailbox_members_for_ungranted_mailbox(self) -> None:
        """권한 없는 메일함의 멤버 목록은 거부되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S44444", password="test-password")
        user.knox_id = "knox-44444"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        other = User.objects.create_user(sabun="S44445", password="test-password")
        other.knox_id = "knox-44445"
        other.save(update_fields=["knox_id"])
        _set_current_affiliation(other, user_sdwt_prod="group-b")

        self.client.force_login(user)

        response = self.client.get(reverse("emails-mailbox-members"), {"user_sdwt_prod": "group-b"})
        self.assertEqual(response.status_code, 403)

    def test_user_can_view_mailbox_members_for_granted_mailbox(self) -> None:
        """권한이 있는 메일함의 멤버 목록을 조회할 수 있는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/권한 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S55555", password="test-password")
        user.knox_id = "knox-55555"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        mailbox_owner = User.objects.create_user(sabun="S55556", password="test-password")
        mailbox_owner.knox_id = "knox-55556"
        mailbox_owner.save(update_fields=["knox_id"])
        _set_current_affiliation(mailbox_owner, user_sdwt_prod="group-b")

        manager = User.objects.create_user(sabun="S55557", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=user,
            action="grant",
            role="member",
        )
        self.assertEqual(status_code, 200)

        self.client.force_login(user)

        response = self.client.get(reverse("emails-mailbox-members"), {"user_sdwt_prod": "group-b"})
        self.assertEqual(response.status_code, 200)
        members = response.json()["members"]
        self.assertIn(mailbox_owner.id, {item["userId"] for item in members})

        forbidden = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": "group-c"})
        self.assertEqual(forbidden.status_code, 403)

    def test_staff_mailboxes_list_includes_unassigned(self) -> None:
        """스태프가 UNASSIGNED 메일함을 포함해 조회하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        staff = User.objects.create_user(sabun="S33333", password="test-password", is_staff=True)
        staff.knox_id = "knox-33333"
        staff.save(update_fields=["knox_id"])

        account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-empty",
        )

        Email.objects.create(
            message_id="msg-staff-a",
            received_at=timezone.now(),
            subject="A3",
            sender="a@example.com",
            sender_id="a",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A3",
        )
        Email.objects.create(
            message_id="msg-staff-b",
            received_at=timezone.now(),
            subject="B3",
            sender="b@example.com",
            sender_id="b",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body B3",
        )
        unassigned_email = Email.objects.create(
            message_id="msg-staff-unassigned",
            received_at=timezone.now(),
            subject="U",
            sender="u@example.com",
            sender_id="u",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body U",
        )

        self.client.force_login(staff)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200)
        self.assertIn("__sent__", mailbox_list.json()["results"])
        self.assertIn("group-a", mailbox_list.json()["results"])
        self.assertIn("group-b", mailbox_list.json()["results"])
        self.assertIn("group-empty", mailbox_list.json()["results"])
        self.assertIn(UNASSIGNED_USER_SDWT_PROD, mailbox_list.json()["results"])

        response = self.client.get(reverse("emails-inbox"))
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-a", "group-b", UNASSIGNED_USER_SDWT_PROD})

        unassigned_list = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": UNASSIGNED_USER_SDWT_PROD})
        self.assertEqual(unassigned_list.status_code, 200)

        detail = self.client.get(reverse("emails-detail", kwargs={"email_id": unassigned_email.id}))
        self.assertEqual(detail.status_code, 200)

        filtered = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": "group-b"})
        self.assertEqual(filtered.status_code, 200)
        results = filtered.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-b"})

    def test_superuser_mailboxes_list_includes_unassigned(self) -> None:
        """슈퍼유저가 UNASSIGNED 메일함을 포함해 조회하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        superuser = User.objects.create_superuser(sabun="S33334", password="test-password")
        superuser.knox_id = "knox-33334"
        superuser.save(update_fields=["knox_id"])

        account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-empty",
        )

        Email.objects.create(
            message_id="msg-su-a",
            received_at=timezone.now(),
            subject="A4",
            sender="a@example.com",
            sender_id="a",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A4",
        )
        Email.objects.create(
            message_id="msg-su-unassigned",
            received_at=timezone.now(),
            subject="U4",
            sender="u@example.com",
            sender_id="u",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body U4",
        )

        self.client.force_login(superuser)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200)
        self.assertIn("__sent__", mailbox_list.json()["results"])
        self.assertIn("group-a", mailbox_list.json()["results"])
        self.assertIn("group-empty", mailbox_list.json()["results"])
        self.assertIn(UNASSIGNED_USER_SDWT_PROD, mailbox_list.json()["results"])

        unassigned_list = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": UNASSIGNED_USER_SDWT_PROD})
        self.assertEqual(unassigned_list.status_code, 200)
        results = unassigned_list.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {UNASSIGNED_USER_SDWT_PROD})

    def test_user_can_claim_unassigned_emails(self) -> None:
        """UNASSIGNED 메일 귀속 처리 플로우가 동작하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성 및 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S44444", password="test-password")
        user.knox_id = "loginid-claim"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        unassigned = Email.objects.create(
            message_id="msg-unassigned",
            received_at=timezone.now(),
            subject="U",
            sender="loginid-claim@example.com",
            sender_id="loginid-claim",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body U",
        )
        classified = Email.objects.create(
            message_id="msg-classified",
            received_at=timezone.now(),
            subject="C",
            sender="loginid-claim@example.com",
            sender_id="loginid-claim",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body C",
        )

        self.client.force_login(user)

        summary = self.client.get(reverse("emails-unassigned-summary"))
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["count"], 1)

        claimed = self.client.post(reverse("emails-unassigned-claim"))
        self.assertEqual(claimed.status_code, 200)
        self.assertEqual(claimed.json()["moved"], 1)

        unassigned.refresh_from_db()
        classified.refresh_from_db()
        self.assertEqual(unassigned.user_sdwt_prod, "group-a")
        self.assertEqual(classified.user_sdwt_prod, "group-b")

        after_summary = self.client.get(reverse("emails-unassigned-summary"))
        self.assertEqual(after_summary.status_code, 200)
        self.assertEqual(after_summary.json()["count"], 0)

    def test_claim_unassigned_requires_user_sdwt_prod(self) -> None:
        """user_sdwt_prod 미설정 시 귀속이 실패하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S55555", password="test-password")
        user.knox_id = "loginid-no-sdwt"
        user.save(update_fields=["knox_id"])

        Email.objects.create(
            message_id="msg-unassigned-2",
            received_at=timezone.now(),
            subject="U2",
            sender="loginid-no-sdwt@example.com",
            sender_id="loginid-no-sdwt",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body U2",
        )

        self.client.force_login(user)
        claimed = self.client.post(reverse("emails-unassigned-claim"))
        self.assertEqual(claimed.status_code, 400)


class RagIndexNameTests(SimpleTestCase):
    """RAG 인덱스 이름 해석 규칙을 검증합니다."""

    def test_resolve_rag_index_name_returns_explicit_value(self) -> None:
        """명시 값이 있으면 그대로 반환하는지 확인합니다.

        입력:
            없음.
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        self.assertEqual(resolve_rag_index_name("rp-emails"), "rp-emails")

    def test_resolve_rag_index_name_falls_back_to_default(self) -> None:
        """기본 인덱스로 폴백하는지 확인합니다.

        입력:
            없음(설정 패치).
        반환:
            없음.
        부작용:
            모듈 상수 패치.
        오류:
            조건 불일치 시 assertion 실패.
        """

        with patch("api.rag.services.RAG_INDEX_DEFAULT", "rp-unclassified"):
            self.assertEqual(resolve_rag_index_name(None), "rp-unclassified")

    def test_resolve_rag_index_name_uses_first_index_list_when_default_missing(self) -> None:
        """기본값이 없으면 목록 첫 항목으로 폴백하는지 확인합니다.

        입력:
            없음(설정 패치).
        반환:
            없음.
        부작용:
            모듈 상수 패치.
        오류:
            조건 불일치 시 assertion 실패.
        """

        with patch("api.rag.services.RAG_INDEX_DEFAULT", ""), patch(
            "api.rag.services.RAG_INDEX_LIST", ["rp-a", "rp-b"]
        ):
            self.assertEqual(resolve_rag_index_name(None), "rp-a")


class EmailParsingTests(SimpleTestCase):
    """메일 파싱 유틸 동작을 검증합니다."""

    def test_parse_message_to_fields_includes_cc_and_recipient_lists(self) -> None:
        """To/Cc가 리스트로 파싱되는지 확인합니다.

        입력:
            없음(테스트 메시지 생성).
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg["From"] = "Sender <sender@example.com>"
        msg["To"] = "Jane <jane@x.com>, Bob <bob@y.com>"
        msg["Cc"] = "Team <team@corp.com>"
        msg["Date"] = "Mon, 01 Jan 2024 00:00:00 +0000"
        msg["Message-ID"] = "<msg-parse-1>"
        msg.set_content("Hello")

        fields = _parse_message_to_fields(msg)

        self.assertEqual(fields["recipient"], ["Jane <jane@x.com>", "Bob <bob@y.com>"])
        self.assertEqual(fields["cc"], ["Team <team@corp.com>"])

    def test_parse_message_to_fields_strips_signature_elements_from_html(self) -> None:
        """HTML 본문에서 제외 대상 서명 요소가 제거되는지 확인합니다.

        입력:
            없음(HTML 메시지 생성).
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg["From"] = "Sender <sender@example.com>"
        msg["To"] = "Receiver <receiver@example.com>"
        msg["Date"] = "Mon, 01 Jan 2024 00:00:00 +0000"
        msg["Message-ID"] = "<msg-parse-html-1>"
        msg.set_content("Plain")

        html = (
            "<html><body>"
            "<p>Hello</p>"
            "<img id='standardSignature' src='cid:sig'>"
            "<table id='bannersignImg'><tr><td>Banner</td></tr></table>"
            "<table id='confidentialsignimg'><tr><td>Confidential</td></tr></table>"
            "<p>Bye</p>"
            "</body></html>"
        )
        msg.add_alternative(html, subtype="html")

        fields = _parse_message_to_fields(msg)

        self.assertIn("Hello", fields["body_text"])
        self.assertIn("Bye", fields["body_text"])
        self.assertNotIn("Banner", fields["body_text"])
        self.assertNotIn("Confidential", fields["body_text"])
        self.assertNotIn("standardSignature", fields["body_html"])
        self.assertNotIn("bannersignImg", fields["body_html"])
        self.assertNotIn("confidentialsignimg", fields["body_html"])

    def test_parse_message_to_fields_strips_signature_markers_from_text(self) -> None:
        """텍스트 본문에서 제외 대상 서명 마커가 제거되는지 확인합니다.

        입력:
            없음(텍스트 메시지 생성).
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg["From"] = "Sender <sender@example.com>"
        msg["To"] = "Receiver <receiver@example.com>"
        msg["Date"] = "Mon, 01 Jan 2024 00:00:00 +0000"
        msg["Message-ID"] = "<msg-parse-text-1>"
        msg.set_content(
            "Hello\n"
            "<img id='standardSignature'>\n"
            "Keep\n"
            "<table id=\"bannersignImg\"></table>\n"
            "<table id=\"confidentialsignimg\"></table>\n"
            "Bye\n"
        )

        fields = _parse_message_to_fields(msg)
        lowered = fields["body_text"].lower()

        self.assertIn("Hello", fields["body_text"])
        self.assertIn("Bye", fields["body_text"])
        self.assertIn("Keep", fields["body_text"])
        self.assertNotIn("standardsignature", lowered)
        self.assertNotIn("bannersignimg", lowered)
        self.assertNotIn("confidentialsignimg", lowered)


class EmailSearchSelectorTests(TestCase):
    """메일 검색 필터 동작을 검증합니다."""

    def test_get_filtered_emails_search_includes_to_and_cc(self) -> None:
        """검색이 To/Cc에도 적용되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        Email.objects.create(
            message_id="search-1",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["Jane <jane@x.com>"],
            cc=["Team <team@corp.com>"],
            participants_search="jane <jane@x.com>\nteam <team@corp.com>",
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        Email.objects.create(
            message_id="search-2",
            received_at=timezone.now(),
            subject="Other",
            sender="other@example.com",
            sender_id="other",
            recipient=["Alice <alice@z.com>"],
            participants_search="alice <alice@z.com>",
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        by_name = get_filtered_emails(
            accessible_user_sdwt_prods=set(),
            is_privileged=True,
            can_view_unassigned=True,
            mailbox_user_sdwt_prod="",
            search="JANE",
            sender="",
            recipient="",
            date_from=None,
            date_to=None,
        )
        self.assertEqual(set(by_name.values_list("message_id", flat=True)), {"search-1"})

        by_cc = get_filtered_emails(
            accessible_user_sdwt_prods=set(),
            is_privileged=True,
            can_view_unassigned=True,
            mailbox_user_sdwt_prod="",
            search="",
            sender="",
            recipient="TEAM@corp.com",
            date_from=None,
            date_to=None,
        )
        self.assertEqual(set(by_cc.values_list("message_id", flat=True)), {"search-1"})

    def test_get_filtered_emails_returns_none_for_empty_accessible_set(self) -> None:
        """접근 가능 집합이 비어 있으면 결과가 없는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        Email.objects.create(
            message_id="search-guard-1",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        results = get_filtered_emails(
            accessible_user_sdwt_prods=set(),
            is_privileged=False,
            can_view_unassigned=False,
            mailbox_user_sdwt_prod="",
            search="",
            sender="",
            recipient="",
            date_from=None,
            date_to=None,
        )
        self.assertEqual(results.count(), 0)


class EmailEndpointTests(TestCase):
    """emails API 엔드포인트의 기본 동작을 검증합니다."""

    def setUp(self) -> None:
        """공통 테스트 데이터와 로그인 상태를 준비합니다.

        입력:
            없음.
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성, 클라이언트 로그인.
        오류:
            없음.
        """

        User = get_user_model()
        self.user = User.objects.create_user(sabun="S11111", password="test-password")
        self.user.knox_id = "knox-11111"
        self.user.save(update_fields=["knox_id"])
        _set_current_affiliation(self.user, user_sdwt_prod="group-a")

        self.email = Email.objects.create(
            message_id="msg-111",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
            body_html_object_key="html/1.html",
        )
        Email.objects.create(
            message_id="msg-unassigned",
            received_at=timezone.now(),
            subject="Unassigned",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body",
        )

        self.client.force_login(self.user)

    def test_email_list_detail_html_and_delete(self) -> None:
        """목록/상세/HTML/삭제 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청 및 DB 삭제.
        오류:
            조건 불일치 시 assertion 실패.
        """

        with patch("api.emails.views.load_email_html", return_value=b"<html>body</html>"), patch(
            "api.emails.services.mutations.delete_email_objects"
        ):
            list_response = self.client.get(reverse("emails-inbox"))
            self.assertEqual(list_response.status_code, 200)

            detail_response = self.client.get(reverse("emails-detail", kwargs={"email_id": self.email.id}))
            self.assertEqual(detail_response.status_code, 200)

            html_response = self.client.get(reverse("emails-html", kwargs={"email_id": self.email.id}))
            self.assertEqual(html_response.status_code, 200)
            self.assertIn("<html>", html_response.content.decode("utf-8"))

            delete_response = self.client.delete(reverse("emails-detail", kwargs={"email_id": self.email.id}))
            self.assertEqual(delete_response.status_code, 200)

    def test_email_asset_endpoint(self) -> None:
        """이미지 자산 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        EmailAsset.objects.create(
            email=self.email,
            sequence=1,
            object_key="assets/1/1.png",
            content_type="image/png",
            source=EmailAsset.Source.CID,
        )

        with patch("api.emails.views.load_email_asset", return_value=b"png-data"):
            response = self.client.get(
                reverse("emails-asset", kwargs={"email_id": self.email.id, "sequence": 1})
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")
    def test_email_sent_list(self) -> None:
        """보낸메일 목록 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        sent_response = self.client.get(reverse("emails-sent"))
        self.assertEqual(sent_response.status_code, 200)
        results = sent_response.json()["results"]
        self.assertTrue(any(item["id"] == self.email.id for item in results))

    def test_email_mailboxes_and_members(self) -> None:
        """메일함 목록/멤버 조회가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        manager = User.objects.create_user(sabun="S11112", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=self.user,
            action="grant",
            role="member",
        )
        self.assertEqual(status_code, 200)

        mailbox_response = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_response.status_code, 200)

        summary_response = self.client.get(reverse("emails-mailbox-summary"))
        self.assertEqual(summary_response.status_code, 200)
        summary_rows = summary_response.json()["results"]
        self.assertIn("group-a", {row["userSdwtProd"] for row in summary_rows})
        summary_by_mailbox = {row["userSdwtProd"]: row for row in summary_rows}
        self.assertEqual(summary_by_mailbox["group-a"]["accessSource"], "self")
        self.assertEqual(summary_by_mailbox["group-b"]["accessSource"], "grant")

        members_response = self.client.get(
            reverse("emails-mailbox-members"),
            {"user_sdwt_prod": "group-a"},
        )
        self.assertEqual(members_response.status_code, 200)

    def test_email_unassigned_summary_and_claim(self) -> None:
        """UNASSIGNED 요약/귀속 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청 및 DB 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        summary = self.client.get(reverse("emails-unassigned-summary"))
        self.assertEqual(summary.status_code, 200)

        claim = self.client.post(reverse("emails-unassigned-claim"))
        self.assertEqual(claim.status_code, 200)

    def test_email_bulk_delete(self) -> None:
        """일괄 삭제 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성 및 삭제.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="msg-bulk",
            received_at=timezone.now(),
            subject="Bulk",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        with patch("api.emails.services.mutations.delete_email_objects"):
            response = self.client.post(
                reverse("emails-bulk-delete"),
                data='{"email_ids":[%d]}' % email.id,
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

    @patch("api.emails.services.insert_email_to_rag")
    def test_email_move_endpoint(self, _mock_insert: Mock) -> None:
        """메일 이동 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성/수정.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        manager = User.objects.create_user(sabun="S77779", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=self.user,
            action="grant",
            role="member",
        )
        self.assertEqual(status_code, 200)

        email = Email.objects.create(
            message_id="msg-move",
            received_at=timezone.now(),
            subject="Move",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        response = self.client.post(
            reverse("emails-move"),
            data='{"email_ids":[%d],"to_user_sdwt_prod":"group-b"}' % email.id,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        email.refresh_from_db()
        self.assertEqual(email.user_sdwt_prod, "group-b")

    @patch("api.emails.views.run_pop3_ingest_from_env", return_value={"deleted": 1, "reindexed": 2})
    def test_email_ingest_trigger(self, _mock_ingest) -> None:
        """POP3 수집 트리거 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(서비스 모킹).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        response = self.client.post(reverse("emails-ingest"))
        self.assertEqual(response.status_code, 200)


class EmailAssetOcrClaimViewTests(TestCase):
    """OCR 작업 클레임 엔드포인트 동작을 검증합니다."""

    @override_settings(
        EMAIL_OCR_INTERNAL_TOKEN="expected-token",
        EMAIL_OCR_CLAIM_LIMIT=50,
        EMAIL_OCR_LEASE_SECONDS=1800,
        EMAIL_OCR_MAX_ATTEMPTS=3,
    )
    def test_ocr_claim_assigns_lock(self) -> None:
        """OCR 클레임 시 자산 락이 부여되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            EmailAsset OCR 상태/락 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="ocr-claim-1",
            received_at=timezone.now(),
            subject="OCR Claim",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.INDEXED,
            body_text="Body",
        )
        asset = EmailAsset.objects.create(
            email=email,
            sequence=1,
            object_key="assets/1/1.png",
            content_type="image/png",
            source=EmailAsset.Source.CID,
        )

        response = self.client.post(
            reverse("emails-assets-ocr-claim"),
            data="{}",
            content_type="application/json",
            HTTP_X_INTERNAL_TOKEN="expected-token",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload.get("tasks", [])), 1)
        self.assertEqual(payload["tasks"][0]["asset_id"], asset.id)

        asset.refresh_from_db()
        self.assertEqual(asset.ocr_status, EmailAsset.OcrStatus.PROCESSING)
        self.assertIsNotNone(asset.ocr_lock_token)
        self.assertIsNotNone(asset.ocr_lock_expires_at)
        self.assertEqual(asset.ocr_attempt_count, 1)


class EmailAssetOcrUpdateViewTests(TestCase):
    """OCR 결과 업데이트 엔드포인트 동작을 검증합니다."""

    @override_settings(EMAIL_OCR_INTERNAL_TOKEN="expected-token", EMAIL_OCR_MAX_ATTEMPTS=3)
    def test_ocr_update_enqueues_rag(self) -> None:
        """OCR 결과가 반영되고 RAG 재인덱싱이 요청되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            EmailAsset/Outbox 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="ocr-msg-1",
            received_at=timezone.now(),
            subject="OCR",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.INDEXED,
            body_text="Body",
        )
        asset = EmailAsset.objects.create(
            email=email,
            sequence=1,
            object_key="assets/1/1.png",
            content_type="image/png",
            source=EmailAsset.Source.CID,
            ocr_status=EmailAsset.OcrStatus.PROCESSING,
            ocr_lock_token="lock-token",
            ocr_lock_expires_at=timezone.now() + timedelta(minutes=30),
            ocr_attempt_count=1,
        )

        response = self.client.post(
            reverse("emails-assets-ocr-update"),
            data='{"results":[{"asset_id":%d,"lock_token":"lock-token","status":"DONE","text":"ocr-text"}]}'
            % asset.id,
            content_type="application/json",
            HTTP_X_INTERNAL_TOKEN="expected-token",
        )
        self.assertEqual(response.status_code, 200)

        asset.refresh_from_db()
        self.assertEqual(asset.ocr_status, EmailAsset.OcrStatus.DONE)
        self.assertEqual(asset.ocr_text, "ocr-text")
        self.assertEqual(EmailOutbox.objects.filter(action=EmailOutbox.Action.INDEX).count(), 1)


class EmailOutboxTriggerAuthTests(TestCase):
    """Outbox 트리거 인증/파라미터 동작을 검증합니다."""

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.emails.views.process_email_outbox_batch")
    def test_outbox_trigger_requires_token(self, mock_process: Mock) -> None:
        """토큰 인증이 필수로 적용되는지 확인합니다.

        입력:
            없음(토큰/서비스 모킹).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        mock_process.return_value = {"processed": 1, "succeeded": 1, "failed": 0}

        url = reverse("emails-outbox-process")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_process.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer wrong-token")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_process.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("processed"), 1)
        mock_process.assert_called_once_with()

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.emails.views.process_email_outbox_batch")
    def test_outbox_trigger_accepts_limit(self, mock_process: Mock) -> None:
        """limit 파라미터가 전달되는지 확인합니다.

        입력:
            없음(토큰/서비스 모킹).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        mock_process.return_value = {"processed": 0, "succeeded": 0, "failed": 0}

        url = reverse("emails-outbox-process")

        resp = self.client.post(
            url,
            data='{"limit": 123}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )
        self.assertEqual(resp.status_code, 200)
        mock_process.assert_called_once_with(limit=123)


class EmailHtmlStorageTests(TestCase):
    """HTML/이미지 자산 저장 규칙을 검증합니다."""

    @patch("api.emails.services.storage.upload_bytes")
    def test_store_email_html_preserves_external_urls(self, mock_upload: Mock) -> None:
        """외부 URL 이미지는 원문 유지되고 자산으로 기록되는지 확인합니다.

        입력:
            없음(테스트 Email/HTML 준비).
        반환:
            없음.
        부작용:
            테스트 DB에 Email/EmailAsset 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="msg-html-1",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="knox-html-1",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        external_url = "https://example.com/external.png"
        payload = base64.b64encode(b"image-bytes").decode("ascii")
        body_html = (
            f"<html><body><img src=\"{external_url}\" />"
            f"<img src=\"data:image/png;base64,{payload}\" /></body></html>"
        )

        store_email_html_and_assets(email=email, body_html=body_html, cid_map={})

        html_uploads = [
            call.kwargs
            for call in mock_upload.call_args_list
            if str(call.kwargs.get("content_type", "")).startswith("text/html")
        ]
        self.assertEqual(len(html_uploads), 1)
        uploaded_html = html_uploads[0]["data"].decode("utf-8")
        self.assertIn(external_url, uploaded_html)
        self.assertIn(f"/api/v1/emails/{email.id}/assets/", uploaded_html)
        self.assertNotIn("data:image/png;base64", uploaded_html)

        external_asset = EmailAsset.objects.get(email=email, source=EmailAsset.Source.EXTERNAL_URL)
        self.assertEqual(external_asset.original_url, external_url)
        self.assertIsNone(external_asset.object_key)

        data_asset = EmailAsset.objects.get(email=email, source=EmailAsset.Source.DATA_URL)
        self.assertIsNotNone(data_asset.object_key)


class EmailIngestHtmlRetryTests(TestCase):
    """POP3 수집 시 HTML 저장 재시도 조건을 검증합니다."""

    def test_ingest_calls_store_when_html_key_missing(self) -> None:
        """HTML 키가 비어 있으면 생성 여부와 무관하게 저장을 시도하는지 확인합니다.

        입력:
            없음(세션/서비스 모킹).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="msg-pop3-1",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="knox-pop3-1",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        fields = {
            "message_id": email.message_id,
            "received_at": email.received_at,
            "subject": email.subject,
            "sender": email.sender,
            "sender_id": email.sender_id,
            "recipient": email.recipient,
            "cc": [],
            "body_text": email.body_text,
            "body_html": "<html><body>Body</body></html>",
            "cid_map": {},
        }

        session = Mock()

        with patch("api.emails.services.ingest._iter_pop3_messages", return_value=[(1, Mock())]), patch(
            "api.emails.services.ingest._extract_subject_header", return_value=email.subject
        ), patch("api.emails.services.ingest._is_excluded_subject", return_value=False), patch(
            "api.emails.services.ingest._parse_message_to_fields", return_value=fields
        ), patch(
            "api.emails.services.ingest.resolve_email_affiliation",
            return_value={
                "user_sdwt_prod": "group-a",
                "classification_source": Email.ClassificationSource.UNASSIGNED,
            },
        ), patch(
            "api.emails.services.ingest.save_parsed_email", return_value=(email, False)
        ), patch(
            "api.emails.services.ingest.store_email_html_and_assets"
        ) as mock_store, patch(
            "api.emails.services.ingest._delete_pop3_messages"
        ) as mock_delete:
            ingest_pop3_mailbox(session)

        mock_store.assert_called_once_with(
            email=email,
            body_html=fields["body_html"],
            cid_map=fields["cid_map"],
        )
        mock_delete.assert_called_once_with(session, [1])
