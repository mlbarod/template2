# =============================================================================
# 모듈 설명: common 서비스 유틸 테스트를 제공합니다.
# - 주요 대상: normalize_text, send_knox_mail_api, Knox 메신저 어댑터
# - 불변 조건: DB 접근 없이 순수 함수 동작만 검증합니다.
# =============================================================================

from __future__ import annotations

import base64
import gzip
import os
import struct
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from api.common.services import MailSendError, normalize_text, send_knox_mail_api
from api.common.services.messenger import (
    _KnoxContext,
    _knox_testutil_compress_java_compatible,
    knox_decrypt,
    knox_encrypt,
    resolve_user_ids_by_single_ids,
    send_chat_message,
)


class CommonNormalizationTests(SimpleTestCase):
    """공용 정규화 유틸 동작을 검증합니다."""

    def test_normalize_text_trims_text(self) -> None:
        """문자열 입력의 앞뒤 공백이 제거되는지 확인합니다."""

        self.assertEqual(normalize_text("  hello  "), "hello")

    def test_normalize_text_returns_empty_for_non_string(self) -> None:
        """문자열이 아니면 빈 문자열을 반환하는지 확인합니다."""

        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text(123), "")


class KnoxMailApiTests(SimpleTestCase):
    """공용 Knox 메일 발송 어댑터 동작을 검증합니다."""

    @patch.dict(
        os.environ,
        {
            "MAIL_API_URL": "http://mail.test/send",
            "MAIL_API_KEY": "ticket",
            "MAIL_API_SYSTEM_ID": "plane",
            "MAIL_API_KNOX_ID": "knox-user",
        },
        clear=False,
    )
    @patch("api.common.services.mail_api.requests.post")
    def test_send_knox_mail_api_returns_json(self, mock_post: Mock) -> None:
        """JSON 응답이 dict로 반환되는지 확인합니다."""

        response = Mock()
        response.ok = True
        response.status_code = 200
        response.text = ""
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"status": "ok"}
        mock_post.return_value = response

        result = send_knox_mail_api(
            sender_email="sender@example.com",
            receiver_emails=["a@example.com", "b@example.com"],
            subject="Subject",
            html_content="<p>Hello</p>",
        )
        self.assertEqual(result, {"status": "ok"})
        mock_post.assert_called_once_with(
            "http://mail.test/send",
            params={"systemId": "plane", "loginUser.login": "knox-user"},
            headers={"x-dep-ticket": "ticket"},
            json={
                "receiverList": [
                    {"email": "a@example.com", "recipientType": "TO"},
                    {"email": "b@example.com", "recipientType": "TO"},
                ],
                "title": "Subject",
                "content": "<p>Hello</p>",
                "senderMailAddress": "sender@example.com",
            },
            timeout=10,
        )

    @patch.dict(
        os.environ,
        {
            "MAIL_API_URL": "http://mail.test/send",
            "MAIL_API_KEY": "ticket",
            "MAIL_API_KNOX_ID": "knox-user",
        },
        clear=False,
    )
    @patch("api.common.services.mail_api.requests.post")
    def test_send_knox_mail_api_returns_ok_for_non_json(self, mock_post: Mock) -> None:
        """비 JSON 응답은 ok=True로 처리되는지 확인합니다."""

        response = Mock()
        response.ok = True
        response.status_code = 204
        response.text = ""
        response.headers = {"content-type": "text/plain"}
        mock_post.return_value = response

        result = send_knox_mail_api(
            sender_email="sender@example.com",
            receiver_emails=["a@example.com"],
            subject="Subject",
            html_content="<p>Hello</p>",
        )
        self.assertEqual(result, {"ok": True})

    @patch.dict(
        os.environ,
        {
            "MAIL_API_URL": "http://mail.test/send",
            "MAIL_API_KEY": "ticket",
            "MAIL_API_KNOX_ID": "knox-user",
        },
        clear=False,
    )
    @patch("api.common.services.mail_api.requests.post")
    def test_send_knox_mail_api_raises_on_http_error(self, mock_post: Mock) -> None:
        """HTTP 오류 응답 시 예외가 발생하는지 확인합니다."""

        response = Mock()
        response.ok = False
        response.status_code = 500
        response.text = "server error"
        response.headers = {"content-type": "text/plain"}
        mock_post.return_value = response

        with self.assertRaises(MailSendError) as ctx:
            send_knox_mail_api(
                sender_email="sender@example.com",
                receiver_emails=["a@example.com"],
                subject="Subject",
                html_content="<p>Hello</p>",
            )
        self.assertIn("메일 API 오류 500", str(ctx.exception))

    def test_send_knox_mail_api_raises_when_missing_env(self) -> None:
        """환경변수 누락 시 예외가 발생하는지 확인합니다."""

        with patch.dict(
            os.environ,
            {
                "MAIL_API_URL": "",
                "MAIL_API_KEY": "",
                "MAIL_API_SYSTEM_ID": "",
                "MAIL_API_KNOX_ID": "",
            },
            clear=False,
        ):
            with self.assertRaises(MailSendError):
                send_knox_mail_api(
                    sender_email="sender@example.com",
                    receiver_emails=["a@example.com"],
                    subject="Subject",
                    html_content="<p>Hello</p>",
                )


class KnoxMessengerClientUtilsTests(SimpleTestCase):
    """Knox 메신저 유틸 함수 단위 테스트."""

    def test_knox_encrypt_decrypt_roundtrip(self) -> None:
        """AES-CBC 암복호화 라운드트립을 검증합니다."""

        key = bytes.fromhex(
            "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
        )
        iv = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
        plaintext = "테스트 메시지"

        ciphertext = knox_encrypt(key, iv, plaintext)
        decrypted = knox_decrypt(key, iv, ciphertext)

        self.assertEqual(decrypted, plaintext)

    def test_knox_testutil_compress_java_compatible(self) -> None:
        """Java TestUtil.compress() 호환 압축 결과를 검증합니다."""

        value = "ABC가나다123"
        encoded = _knox_testutil_compress_java_compatible(value)
        raw = base64.b64decode(encoded)

        header = raw[:4]
        gzipped = raw[4:]
        header_value = struct.unpack("<I", header)[0]
        self.assertEqual(header_value, int(len(value) * 1.2))

        restored = gzip.decompress(gzipped).decode("utf-8")
        self.assertEqual(restored, value)

    def test_send_chat_message_sends_given_msg_type_and_string(self) -> None:
        """send_chat_message가 전달받은 msg_type과 문자열 본문을 전송하는지 확인합니다."""

        dummy_context = _KnoxContext(
            base_url="http://example.local/",
            headers={},
            key=b"0" * 32,
            iv=b"1" * 16,
            timeout_seconds=1,
        )
        captured: dict[str, object] = {}

        def _capture_payload(context: _KnoxContext, path: str, payload: dict[str, object]) -> object:
            captured["path"] = path
            captured["payload"] = payload
            return object()

        with patch(
            "api.common.services.messenger._prepare_knox_context",
            return_value=dummy_context,
        ), patch(
            "api.common.services.messenger._post_encrypted",
            side_effect=_capture_payload,
        ):
            send_chat_message(chatroom_id=1, msg_type=7, chat_msg="{\"a\": 1}")

        payload = captured.get("payload")
        self.assertIsInstance(payload, dict)
        params = payload["chatMessageParams"][0]
        self.assertEqual(params["msgType"], 7)
        self.assertEqual(params["chatMsg"], "{\"a\": 1}")

    def test_resolve_user_ids_by_single_ids_casts_user_id_to_string(self) -> None:
        """singleID 조회 결과의 userID가 숫자여도 문자열로 반환하는지 확인합니다."""

        mocked_results = [
            {"singleID": "abc.park", "userID": 123123123123},
            {"singleID": "def.park", "userID": "U-2"},
        ]

        with patch(
            "api.common.services.messenger.search_user_ids_by_single_ids",
            return_value=mocked_results,
        ):
            resolved = resolve_user_ids_by_single_ids(single_ids=["abc.park", "def.park"])

        self.assertEqual(resolved, ["123123123123", "U-2"])
