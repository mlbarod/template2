# =============================================================================
# 모듈: Knox 메신저 API 클라이언트
# 주요 기능: 디바이스 등록, 키/IV 발급, 암호화 요청, 메시지/채팅룸 제어
# 주요 가정: KNOX_MESSENGER_* 환경변수로 인증값을 주입받습니다.
# =============================================================================
"""Knox 메신저 API 클라이언트 유틸리티."""

from __future__ import annotations

import base64
import gzip
import json
import os
import struct
import time
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.conf import settings

_DEFAULT_TIMEOUT_SECONDS = 10
_DEFAULT_MESSAGE_TTL = 7200
_DEFAULT_MSG_TYPE = 0
_DEVICE_TYPE = "relation"


class KnoxMessengerError(RuntimeError):
    """Knox 메신저 API 처리 중 발생한 오류입니다."""


@dataclass(frozen=True)
class KnoxMessengerConfig:
    """Knox 메신저 API 설정입니다."""

    base_url: str
    authorization: str
    system_id: str
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_settings(cls) -> "KnoxMessengerConfig":
        """settings/env에서 Knox 메신저 설정을 로드합니다."""

        # ---------------------------------------------------------------------
        # 1) 기본 설정값 로드
        # ---------------------------------------------------------------------
        base_url = (
            getattr(settings, "KNOX_MESSENGER_API_BASE_URL", "")
            or os.getenv("KNOX_MESSENGER_API_BASE_URL")
            or ""
        ).strip()
        authorization = (
            getattr(settings, "KNOX_MESSENGER_AUTHORIZATION", "")
            or os.getenv("KNOX_MESSENGER_AUTHORIZATION")
            or ""
        ).strip()
        system_id = (
            getattr(settings, "KNOX_MESSENGER_SYSTEM_ID", "")
            or os.getenv("KNOX_MESSENGER_SYSTEM_ID")
            or ""
        ).strip()

        # ---------------------------------------------------------------------
        # 2) timeout_seconds 로드(없으면 기본값)
        # ---------------------------------------------------------------------
        timeout_raw = (
            getattr(settings, "KNOX_MESSENGER_TIMEOUT_SECONDS", None)
            or os.getenv("KNOX_MESSENGER_TIMEOUT_SECONDS")
            or ""
        )
        timeout_seconds = _DEFAULT_TIMEOUT_SECONDS
        if str(timeout_raw).strip():
            try:
                timeout_seconds = int(timeout_raw)
            except ValueError:
                timeout_seconds = _DEFAULT_TIMEOUT_SECONDS

        return cls(
            base_url=base_url,
            authorization=authorization,
            system_id=system_id,
            timeout_seconds=timeout_seconds,
        )

    def is_ready(self) -> bool:
        """필수 설정(base_url/authorization/system_id) 보유 여부를 반환합니다."""

        return bool(self.base_url and self.authorization and self.system_id)


@dataclass(frozen=True)
class _KnoxContext:
    """Knox 요청에 필요한 컨텍스트 묶음입니다."""

    base_url: str
    headers: dict[str, str]
    key: bytes
    iv: bytes
    timeout_seconds: int


def _normalize_base_url(base_url: str) -> str:
    """base_url을 요청에 쓰기 좋은 형태로 정규화합니다."""

    return base_url.rstrip("/") + "/"


def _build_headers(config: KnoxMessengerConfig) -> dict[str, str]:
    """Knox 공통 헤더를 구성합니다."""

    return {
        "accept": "*/*",
        "Content-Type": "application/json",
        "Authorization": config.authorization,
        "System-ID": config.system_id,
    }


def knox_encrypt(key: bytes, iv: bytes, plaintext: str) -> bytes:
    """AES-CBC + PKCS7로 Knox payload를 암호화합니다.

    인자:
        key: AES 키(32바이트).
        iv: AES IV(16바이트).
        plaintext: UTF-8 문자열 평문.

    반환:
        base64 인코딩된 암호문(bytes).

    부작용:
        없음. 순수 암호화입니다.
    """

    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext)


def knox_decrypt(key: bytes, iv: bytes, ciphertext: str | bytes) -> str:
    """AES-CBC + PKCS7로 Knox 응답을 복호화합니다.

    인자:
        key: AES 키(32바이트).
        iv: AES IV(16바이트).
        ciphertext: base64 인코딩된 암호문(str 또는 bytes).

    반환:
        복호화된 UTF-8 문자열.

    부작용:
        없음. 순수 복호화입니다.
    """

    raw = base64.b64decode(ciphertext)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(raw) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode("utf-8")


def _split_key_iv(key_hex: str) -> tuple[bytes, bytes]:
    """Knox 키 문자열을 key/iv로 분리합니다."""

    # -------------------------------------------------------------------------
    # 1) hex 문자열 검증 및 바이트 변환
    # -------------------------------------------------------------------------
    try:
        keyplusiv = bytes.fromhex(key_hex)
    except ValueError as exc:  # 예외 방어. pragma: no cover
        raise KnoxMessengerError("Knox key hex 변환 실패") from exc

    # -------------------------------------------------------------------------
    # 2) 길이 검증 후 key/iv 분리
    # -------------------------------------------------------------------------
    if len(keyplusiv) < 48:
        raise KnoxMessengerError("Knox key 길이가 부족합니다")

    return keyplusiv[:32], keyplusiv[32:48]


def _register_device(config: KnoxMessengerConfig) -> dict[str, str]:
    """Knox 디바이스 등록 후 디바이스 헤더를 반환합니다."""

    # -------------------------------------------------------------------------
    # 1) 기본 헤더 구성 및 요청 준비
    # -------------------------------------------------------------------------
    if not config.is_ready():
        raise KnoxMessengerError("KNOX_MESSENGER_API_BASE_URL/AUTHORIZATION/SYSTEM_ID 미설정")

    base_url = _normalize_base_url(config.base_url)
    headers = _build_headers(config)

    # -------------------------------------------------------------------------
    # 2) 디바이스 등록 호출
    # -------------------------------------------------------------------------
    try:
        response = requests.get(
            f"{base_url}contact/api/v1.0/device/o1/reg",
            headers=headers,
            verify=False,
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise KnoxMessengerError(f"Knox device register 실패: {exc}") from exc

    data = response.json()
    device_id = data.get("deviceServerID")
    if not device_id:
        raise KnoxMessengerError("Knox deviceServerID 누락")

    headers["x-device-id"] = str(device_id)
    headers["x-device-type"] = _DEVICE_TYPE
    return headers


def _fetch_key_iv(config: KnoxMessengerConfig, headers: dict[str, str]) -> tuple[bytes, bytes]:
    """Knox 키/IV를 발급받아 반환합니다."""

    # -------------------------------------------------------------------------
    # 1) 키 발급 요청
    # -------------------------------------------------------------------------
    base_url = _normalize_base_url(config.base_url)
    try:
        response = requests.get(
            f"{base_url}msgctx/api/v1.0/key/getkeys",
            headers=headers,
            verify=False,
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise KnoxMessengerError(f"Knox key 발급 실패: {exc}") from exc

    # -------------------------------------------------------------------------
    # 2) key/iv 분리
    # -------------------------------------------------------------------------
    data = response.json()
    key_hex = data.get("key")
    if not key_hex:
        raise KnoxMessengerError("Knox key 응답 누락")

    return _split_key_iv(str(key_hex))


def _prepare_knox_context(config: KnoxMessengerConfig) -> _KnoxContext:
    """Knox 암호화 요청에 필요한 컨텍스트를 준비합니다."""

    # -------------------------------------------------------------------------
    # 1) 디바이스 등록 및 헤더 구성
    # -------------------------------------------------------------------------
    headers = _register_device(config)

    # -------------------------------------------------------------------------
    # 2) key/iv 발급
    # -------------------------------------------------------------------------
    key, iv = _fetch_key_iv(config, headers)

    # -------------------------------------------------------------------------
    # 3) 컨텍스트 묶음 반환
    # -------------------------------------------------------------------------
    return _KnoxContext(
        base_url=_normalize_base_url(config.base_url),
        headers=headers,
        key=key,
        iv=iv,
        timeout_seconds=config.timeout_seconds,
    )


def _post_encrypted(context: _KnoxContext, path: str, payload: dict[str, Any]) -> requests.Response:
    """Knox 암호화 POST 요청을 전송합니다."""

    # -------------------------------------------------------------------------
    # 1) payload 직렬화 및 암호화
    # -------------------------------------------------------------------------
    # body = base64(AES-CBC(PKCS7(json))) 형식
    body = knox_encrypt(context.key, context.iv, json.dumps(payload)).decode("utf-8")

    # -------------------------------------------------------------------------
    # 2) POST 호출 및 응답 반환
    # -------------------------------------------------------------------------
    try:
        response = requests.post(
            f"{context.base_url}{path.lstrip('/')}",
            headers=context.headers,
            data=body,
            verify=False,
            timeout=context.timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise KnoxMessengerError(f"Knox POST 실패: {exc}") from exc

    return response


def create_request_parameters(target_ids: Iterable[str]) -> dict[str, list[dict[str, str]]]:
    """singleIdList 형태의 검색 파라미터를 생성합니다.

    인자:
        target_ids: single ID 목록.

    반환:
        {"singleIdList": [{"singleId": "..."}]} 형태의 dict.

    부작용:
        없음. 순수 변환입니다.
    """

    single_id_list = [{"singleId": str(target_id)} for target_id in target_ids]
    return {"singleIdList": single_id_list}


def search_user_ids_by_single_ids(
    *,
    single_ids: Sequence[str],
    config: KnoxMessengerConfig | None = None,
) -> list[dict[str, Any]]:
    """single ID 목록을 Knox userID 목록으로 조회합니다.

    인자:
        single_ids: single ID 목록.
        config: Knox 메신저 설정(미지정 시 env 로드).

    반환:
        Knox 검색 결과 목록(list[dict]).

    부작용:
        외부 Knox 메신저 API 호출이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 설정 로드 및 디바이스 등록
    # -------------------------------------------------------------------------
    resolved_config = config or KnoxMessengerConfig.from_settings()
    headers = _register_device(resolved_config)
    base_url = _normalize_base_url(resolved_config.base_url)

    # -------------------------------------------------------------------------
    # 2) 검색 요청
    # -------------------------------------------------------------------------
    payload = create_request_parameters(single_ids)

    try:
        response = requests.post(
            f"{base_url}contact/api/v1.0/profile/o1/search/loginid",
            headers=headers,
            data=json.dumps(payload),
            verify=False,
            timeout=resolved_config.timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise KnoxMessengerError(f"Knox loginid 검색 실패: {exc}") from exc

    # -------------------------------------------------------------------------
    # 3) 응답 반환
    # -------------------------------------------------------------------------
    data = response.json()
    return data["userSearchResult"]["searchResultList"]


def resolve_user_ids_by_single_ids(
    *,
    single_ids: Sequence[str],
    config: KnoxMessengerConfig | None = None,
) -> list[str]:
    """single ID 순서를 보존한 userID 목록을 반환합니다.

    인자:
        single_ids: single ID 목록.
        config: Knox 메신저 설정(미지정 시 env 로드).

    반환:
        입력 순서를 보존한 userID 리스트.

    부작용:
        외부 Knox 메신저 API 호출이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 검색 결과를 맵으로 변환
    # -------------------------------------------------------------------------
    results = search_user_ids_by_single_ids(single_ids=single_ids, config=config)
    by_single_id = {item["singleID"]: item["userID"] for item in results}

    # -------------------------------------------------------------------------
    # 2) 입력 순서대로 userID 목록 구성
    # -------------------------------------------------------------------------
    return [by_single_id[single_id] for single_id in single_ids if single_id in by_single_id]


def send_chat_message(
    *,
    chatroom_id: int,
    chat_msg: Any,
    msg_type: int = _DEFAULT_MSG_TYPE,
    ttl: int = _DEFAULT_MESSAGE_TTL,
    config: KnoxMessengerConfig | None = None,
) -> None:
    """채팅룸에 메시지를 전송합니다.

    인자:
        chatroom_id: 채팅룸 ID.
        msg_type: 메시지 타입(정수, 기본 0).
        chat_msg: 메시지 본문(문자열로 변환하여 전송).
        ttl: 메시지 TTL(초).
        config: Knox 메신저 설정(미지정 시 env 로드).

    반환:
        없음.

    부작용:
        외부 Knox 메신저 API 호출이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 설정 로드 및 payload 구성
    # -------------------------------------------------------------------------
    resolved_config = config or KnoxMessengerConfig.from_settings()
    now_ms = int(time.time() * 1000)
    payload = {
        "requestId": now_ms,
        "chatroomId": int(chatroom_id),
        "chatMessageParams": [
            {
                "msgId": now_ms,
                "msgType": int(msg_type),
                "chatMsg": str(chat_msg),
                "msgTtl": int(ttl),
            }
        ],
    }

    # -------------------------------------------------------------------------
    # 2) 암호화 전송
    # -------------------------------------------------------------------------
    context = _prepare_knox_context(resolved_config)
    _post_encrypted(context, "message/api/v1.0/message/chatRequest", payload)


def change_chatroom_title(
    *,
    chatroom_id: int,
    title: str,
    config: KnoxMessengerConfig | None = None,
) -> None:
    """채팅룸 제목을 변경합니다.

    인자:
        chatroom_id: 채팅룸 ID.
        title: 변경할 채팅룸 제목.
        config: Knox 메신저 설정(미지정 시 env 로드).

    반환:
        없음.

    부작용:
        외부 Knox 메신저 API 호출이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 입력/설정 검증 및 payload 구성
    # -------------------------------------------------------------------------
    if not isinstance(chatroom_id, int):
        raise KnoxMessengerError("chatroom_id는 int 여야 합니다")
    if not isinstance(title, str) or not title.strip():
        raise KnoxMessengerError("title은 비어있을 수 없습니다")

    resolved_config = config or KnoxMessengerConfig.from_settings()
    if not resolved_config.is_ready():
        raise KnoxMessengerError("KNOX_MESSENGER_API_BASE_URL/AUTHORIZATION/SYSTEM_ID 미설정")

    payload = {
        "requestId": int(time.time() * 1000),
        "chatroomId": chatroom_id,
        "title": title.strip(),
    }

    # -------------------------------------------------------------------------
    # 2) 암호화 전송
    # -------------------------------------------------------------------------
    context = _prepare_knox_context(resolved_config)
    _post_encrypted(context, "message/api/v1.0/message/changeChatroomMetaRequest", payload)


def create_chatroom(
    *,
    user_ids: Sequence[str],
    title: str,
    chat_type: int = 1,
    config: KnoxMessengerConfig | None = None,
) -> int:
    """수신자 목록으로 채팅룸을 생성합니다.

    인자:
        user_ids: 수신자 userID 목록.
        title: 채팅룸 제목.
        chat_type: 채팅룸 타입(기본 1).
        config: Knox 메신저 설정(미지정 시 env 로드).

    반환:
        생성된 chatroom_id.

    부작용:
        외부 Knox 메신저 API 호출이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 설정 로드 및 payload 구성
    # -------------------------------------------------------------------------
    resolved_config = config or KnoxMessengerConfig.from_settings()
    payload = {
        "requestId": int(time.time() * 1000),
        "chatType": int(chat_type),
        "receivers": [str(item) for item in user_ids],
        "chatroomTitle": str(title),
    }

    # -------------------------------------------------------------------------
    # 2) 암호화 전송
    # -------------------------------------------------------------------------
    context = _prepare_knox_context(resolved_config)
    response = _post_encrypted(context, "message/api/v1.0/message/createChatroomRequest", payload)

    # -------------------------------------------------------------------------
    # 3) 응답 복호화 및 chatroomId 추출
    # -------------------------------------------------------------------------
    decrypted = knox_decrypt(context.key, context.iv, response.text)
    data = json.loads(decrypted)
    chatroom_id = data.get("chatroomId")
    if not isinstance(chatroom_id, int):
        raise KnoxMessengerError("chatroomId 응답 누락")

    return chatroom_id


def _read_text_file(path: str, encoding: str = "utf-8") -> str:
    """텍스트 파일을 읽어 문자열로 반환합니다."""

    # -------------------------------------------------------------------------
    # 1) 파일 존재 여부 확인
    # -------------------------------------------------------------------------
    if not os.path.exists(path):
        raise KnoxMessengerError(f"HTML file not found: {path}")

    # -------------------------------------------------------------------------
    # 2) 파일 읽기
    # -------------------------------------------------------------------------
    with open(path, "r", encoding=encoding) as file:
        return file.read()


def _knox_testutil_compress_java_compatible(value: str) -> str:
    """Java TestUtil.compress()와 동일한 포맷으로 문자열을 압축합니다.

    - GZIP + 4바이트 Little Endian 헤더 + Base64 조합
    - 헤더 값은 Java의 str.length()*1.2 규칙을 따릅니다.
    """

    # -------------------------------------------------------------------------
    # 1) gzip 압축
    # -------------------------------------------------------------------------
    raw = value.encode("utf-8")
    gzipped = gzip.compress(raw)

    # -------------------------------------------------------------------------
    # 2) 4바이트 Little Endian 헤더 생성 (문자 길이 기준)
    # -------------------------------------------------------------------------
    header_value = int(len(value) * 1.2)
    header = struct.pack("<I", header_value)

    # -------------------------------------------------------------------------
    # 3) 헤더 + gzip 바이트를 Base64로 인코딩
    # -------------------------------------------------------------------------
    combined = header + gzipped
    return base64.b64encode(combined).decode("utf-8")


def send_excel_table_message_from_file(
    *,
    chatroom_id: int,
    html_path: str,
    ttl: int = _DEFAULT_MESSAGE_TTL,
    config: KnoxMessengerConfig | None = None,
    encoding: str = "utf-8",
    debug_print_plain: bool = False,
) -> None:
    """msgType=7(Excel Table) 메시지를 HTML 파일로 전송합니다.

    - HTML 파일을 읽어 TestUtil.compress 형식으로 압축
    - <!-- COMMAND --> + 압축 문자열을 chatMsg에 합쳐 전송
    """

    # -------------------------------------------------------------------------
    # 1) 설정 로드 및 Knox 컨텍스트 준비
    # -------------------------------------------------------------------------
    resolved_config = config or KnoxMessengerConfig.from_settings()
    context = _prepare_knox_context(resolved_config)

    # -------------------------------------------------------------------------
    # 2) HTML 파일 로드 및 검증
    # -------------------------------------------------------------------------
    html = _read_text_file(html_path, encoding=encoding).strip()
    if not html:
        raise KnoxMessengerError(f"HTML file is empty: {html_path}")

    if len(html) > 40000:
        raise KnoxMessengerError("Message Length is too long (>40000 chars). Reduce table size.")

    # -------------------------------------------------------------------------
    # 3) Java TestUtil.compress 호환 압축 및 chatMsg 구성
    # -------------------------------------------------------------------------
    compressed = _knox_testutil_compress_java_compatible(html)
    command_prefix = '<!-- {"COMMAND":"SNDCL", "SNDCL":{"KND":"CLDT", "TYPE":"CSV"}} -->'
    chat_msg = command_prefix + compressed

    # -------------------------------------------------------------------------
    # 4) payload 구성
    # -------------------------------------------------------------------------
    now_ms = int(time.time() * 1000)
    payload = {
        "requestId": now_ms,
        "chatroomId": int(chatroom_id),
        "chatMessageParams": [
            {
                "msgId": int(time.time_ns()),
                "msgType": 7,
                "chatMsg": chat_msg,
                "msgTtl": int(ttl),
            }
        ],
    }

    # -------------------------------------------------------------------------
    # 5) 디버그 출력 (암호화 전)
    # -------------------------------------------------------------------------
    if debug_print_plain:
        print("\n[PLAIN payload (before encryption) - head]")
        print(json.dumps(payload, ensure_ascii=False)[:1200])
        print("\n[chatMsg prefix head]")
        print(chat_msg[:120])
        print("\n[html length(chars)]", len(html), " / [compressed length(chars)]", len(compressed))

    # -------------------------------------------------------------------------
    # 6) 암호화 전송
    # -------------------------------------------------------------------------
    _post_encrypted(context, "message/api/v1.0/message/chatRequest", payload)
