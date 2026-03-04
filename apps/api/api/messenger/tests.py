# =============================================================================
# 모듈: Knox 메신저 클라이언트 단위 테스트
# 주요 기능: 암복호화/압축 유틸 검증
# 주요 가정: 외부 API 호출은 수행하지 않음
# =============================================================================
"""Knox 메신저 유틸리티 테스트."""

from __future__ import annotations

import base64
import gzip
import struct

from unittest.mock import patch

from django.test import SimpleTestCase

from .services.knox_client import (
    _KnoxContext,
    _knox_testutil_compress_java_compatible,
    knox_decrypt,
    knox_encrypt,
    resolve_user_ids_by_single_ids,
    send_chat_message,
)


class KnoxClientUtilsTests(SimpleTestCase):
    """Knox 메신저 유틸 함수 단위 테스트."""

    def test_knox_encrypt_decrypt_roundtrip(self) -> None:
        """AES-CBC 암복호화 라운드트립을 검증합니다."""

        # ---------------------------------------------------------------------
        # 1) 테스트 입력 준비
        # ---------------------------------------------------------------------
        key = bytes.fromhex(
            "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
        )
        iv = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
        plaintext = "테스트 메시지"

        # ---------------------------------------------------------------------
        # 2) 암호화 후 복호화
        # ---------------------------------------------------------------------
        ciphertext = knox_encrypt(key, iv, plaintext)
        decrypted = knox_decrypt(key, iv, ciphertext)

        # ---------------------------------------------------------------------
        # 3) 결과 검증
        # ---------------------------------------------------------------------
        self.assertEqual(decrypted, plaintext)

    def test_knox_testutil_compress_java_compatible(self) -> None:
        """Java TestUtil.compress() 호환 압축 결과를 검증합니다."""

        # ---------------------------------------------------------------------
        # 1) 입력 준비 및 압축 수행
        # ---------------------------------------------------------------------
        value = "ABC가나다123"
        encoded = _knox_testutil_compress_java_compatible(value)
        raw = base64.b64decode(encoded)

        # ---------------------------------------------------------------------
        # 2) 헤더/본문 분리 및 헤더 값 검증
        # ---------------------------------------------------------------------
        header = raw[:4]
        gzipped = raw[4:]
        header_value = struct.unpack("<I", header)[0]
        self.assertEqual(header_value, int(len(value) * 1.2))

        # ---------------------------------------------------------------------
        # 3) gzip 복원 결과 검증
        # ---------------------------------------------------------------------
        restored = gzip.decompress(gzipped).decode("utf-8")
        self.assertEqual(restored, value)

    def test_send_chat_message_sends_given_msg_type_and_string(self) -> None:
        """send_chat_message가 전달받은 msg_type과 문자열 본문을 전송하는지 확인합니다."""

        # ---------------------------------------------------------------------
        # 1) 더미 컨텍스트 및 캡처 변수 준비
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # 2) 외부 호출을 패치하고 send_chat_message 실행
        # ---------------------------------------------------------------------
        with patch(
            "api.messenger.services.knox_client._prepare_knox_context",
            return_value=dummy_context,
        ), patch(
            "api.messenger.services.knox_client._post_encrypted",
            side_effect=_capture_payload,
        ):
            send_chat_message(chatroom_id=1, msg_type=7, chat_msg="{\"a\": 1}")

        # ---------------------------------------------------------------------
        # 3) payload 내용 검증
        # ---------------------------------------------------------------------
        payload = captured.get("payload")
        self.assertIsInstance(payload, dict)
        params = payload["chatMessageParams"][0]
        self.assertEqual(params["msgType"], 7)
        self.assertEqual(params["chatMsg"], "{\"a\": 1}")

    def test_resolve_user_ids_by_single_ids_casts_user_id_to_string(self) -> None:
        """singleID 조회 결과의 userID가 숫자여도 문자열로 반환하는지 확인합니다."""

        # ---------------------------------------------------------------------
        # 1) Knox 응답 모킹(숫자 userID 포함)
        # ---------------------------------------------------------------------
        mocked_results = [
            {"singleID": "abc.park", "userID": 123123123123},
            {"singleID": "def.park", "userID": "U-2"},
        ]

        # ---------------------------------------------------------------------
        # 2) userID 해석 실행
        # ---------------------------------------------------------------------
        with patch(
            "api.messenger.services.knox_client.search_user_ids_by_single_ids",
            return_value=mocked_results,
        ):
            resolved = resolve_user_ids_by_single_ids(single_ids=["abc.park", "def.park"])

        # ---------------------------------------------------------------------
        # 3) 문자열 결과 검증
        # ---------------------------------------------------------------------
        self.assertEqual(resolved, ["123123123123", "U-2"])
