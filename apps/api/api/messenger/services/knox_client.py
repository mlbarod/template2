# =============================================================================
# 모듈: Knox 메신저 API 단일 유틸
# 주요 기능: 디바이스 등록, key/iv 발급, 암복호화, 채팅/메시지 전송
# 주요 가정: KNOX_MESSENGER_* 설정이 환경에 주입되어 있습니다.
# =============================================================================
"""Knox 메신저 API 유틸리티."""

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
_DEVICE_TYPE = "relation"


class KnoxMessengerError(RuntimeError):
    """Knox 메신저 API 오류."""


@dataclass(frozen=True)
class KnoxMessengerConfig:
    """Knox 메신저 설정값."""

    base_url: str
    authorization: str
    system_id: str
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "KnoxMessengerConfig":
        """환경에서 Knox 설정을 읽어옵니다."""

        timeout_raw = (
            getattr(settings, "KNOX_MESSENGER_TIMEOUT_SECONDS", "")
            or os.getenv("KNOX_MESSENGER_TIMEOUT_SECONDS")
            or _DEFAULT_TIMEOUT_SECONDS
        )
        try:
            timeout_seconds = int(timeout_raw)
        except (TypeError, ValueError):
            timeout_seconds = _DEFAULT_TIMEOUT_SECONDS

        return cls(
            base_url=str(
                getattr(settings, "KNOX_MESSENGER_API_BASE_URL", "")
                or os.getenv("KNOX_MESSENGER_API_BASE_URL")
                or ""
            ).strip(),
            authorization=str(
                getattr(settings, "KNOX_MESSENGER_AUTHORIZATION", "")
                or os.getenv("KNOX_MESSENGER_AUTHORIZATION")
                or ""
            ).strip(),
            system_id=str(
                getattr(settings, "KNOX_MESSENGER_SYSTEM_ID", "")
                or os.getenv("KNOX_MESSENGER_SYSTEM_ID")
                or ""
            ).strip(),
            timeout_seconds=timeout_seconds,
        )

    def is_ready(self) -> bool:
        """필수 설정 존재 여부를 반환합니다."""

        return bool(self.base_url and self.authorization and self.system_id)


@dataclass(frozen=True)
class _KnoxContext:
    """요청에 필요한 Knox 컨텍스트."""

    base_url: str
    headers: dict[str, str]
    key: bytes
    iv: bytes
    timeout_seconds: int


# =============================================================================
# 암호화 (AES-CBC + PKCS7 + Base64)
# =============================================================================
def knox_encrypt(key: bytes, iv: bytes, plaintext: str) -> bytes:
    """Knox 요청 본문을 암호화합니다."""

    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext)


def knox_decrypt(key: bytes, iv: bytes, ciphertext: str | bytes) -> str:
    """Knox 응답 본문을 복호화합니다."""

    raw = base64.b64decode(ciphertext)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(raw) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode("utf-8")


# =============================================================================
# 내부 유틸
# =============================================================================
def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/"


def _build_headers(config: KnoxMessengerConfig) -> dict[str, str]:
    return {
        "accept": "*/*",
        "Content-Type": "application/json",
        "Authorization": config.authorization,
        "System-ID": config.system_id,
    }


def _split_key_iv(key_hex: str) -> tuple[bytes, bytes]:
    keyplusiv = bytes.fromhex(key_hex)
    return keyplusiv[:32], keyplusiv[32:48]


def _register_device(config: KnoxMessengerConfig) -> dict[str, str]:
    if not config.is_ready():
        raise KnoxMessengerError("KNOX 설정 누락 (base_url/authorization/system_id)")

    base_url = _normalize_base_url(config.base_url)
    headers = _build_headers(config)

    response = requests.get(
        f"{base_url}contact/api/v2.0/device/o1/reg",
        headers=headers,
        verify=False,
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()

    device_id = response.json()["deviceServerID"]
    headers["x-device-id"] = str(device_id)
    headers["x-device-type"] = _DEVICE_TYPE
    return headers


def _fetch_key_iv(config: KnoxMessengerConfig, headers: dict[str, str]) -> tuple[bytes, bytes]:
    base_url = _normalize_base_url(config.base_url)

    response = requests.get(
        f"{base_url}msgctx/api/v2.0/key/getkeys",
        headers=headers,
        verify=False,
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()
    return _split_key_iv(response.json()["key"])


def _prepare_knox_context(config: KnoxMessengerConfig) -> _KnoxContext:
    headers = _register_device(config)
    key, iv = _fetch_key_iv(config, headers)
    return _KnoxContext(
        base_url=_normalize_base_url(config.base_url),
        headers=headers,
        key=key,
        iv=iv,
        timeout_seconds=config.timeout_seconds,
    )


def _post_encrypted(context: _KnoxContext, path: str, payload: dict[str, Any]) -> requests.Response:
    # body = base64(AES-CBC(PKCS7(json)))
    body = knox_encrypt(context.key, context.iv, json.dumps(payload)).decode("utf-8")

    response = requests.post(
        f"{context.base_url}{path.lstrip('/')}",
        headers=context.headers,
        data=body,
        verify=False,
        timeout=context.timeout_seconds,
    )
    response.raise_for_status()
    return response


# =============================================================================
# singleId 변환
# =============================================================================
def create_request_parameters(target_ids: Iterable[str]) -> dict[str, list[dict[str, str]]]:
    return {"singleIdList": [{"singleId": str(single_id)} for single_id in target_ids]}


def search_user_ids_by_single_ids(
    *,
    single_ids: Sequence[str],
    config: KnoxMessengerConfig | None = None,
) -> list[dict[str, Any]]:
    resolved = config or KnoxMessengerConfig.from_env()
    headers = _register_device(resolved)
    base_url = _normalize_base_url(resolved.base_url)

    payload = create_request_parameters(single_ids)
    request_url = f"{base_url}contact/api/v2.0/profile/o1/search/loginid"
    response = requests.post(
        request_url,
        headers=headers,
        data=json.dumps(payload),
        verify=False,
        timeout=resolved.timeout_seconds,
    )
    response.raise_for_status()
    return response.json()["userSearchResult"]["searchResultList"]


def resolve_user_ids_by_single_ids(
    *,
    single_ids: Sequence[str],
    config: KnoxMessengerConfig | None = None,
) -> list[str]:
    results = search_user_ids_by_single_ids(single_ids=single_ids, config=config)

    normalized_single_ids = [
        str(single_id).strip()
        for single_id in single_ids
        if str(single_id).strip()
    ]
    by_single = {
        str(item.get("singleID") or "").strip(): str(item.get("userID") or "").strip()
        for item in results
        if str(item.get("singleID") or "").strip() and str(item.get("userID") or "").strip()
    }
    resolved_user_ids = [by_single[single_id] for single_id in normalized_single_ids if single_id in by_single]
    return resolved_user_ids


# =============================================================================
# 메시지/채팅룸
# =============================================================================
def create_chatroom(
    *,
    user_ids: Sequence[str],
    title: str,
    chat_type: int = 1,
    config: KnoxMessengerConfig | None = None,
) -> int:
    resolved = config or KnoxMessengerConfig.from_env()
    context = _prepare_knox_context(resolved)

    payload = {
        "requestId": int(time.time() * 1000),
        "chatType": int(chat_type),
        "receivers": [str(user_id) for user_id in user_ids],
        "chatroomTitle": str(title),
    }
    response = _post_encrypted(context, "message/api/v2.0/message/createChatroomRequest", payload)
    decrypted = knox_decrypt(context.key, context.iv, response.text)
    return json.loads(decrypted)["chatroomId"]


def send_chat_message(
    *,
    chatroom_id: int,
    msg_type: int,
    chat_msg: str,
    ttl: int = _DEFAULT_MESSAGE_TTL,
    config: KnoxMessengerConfig | None = None,
) -> None:
    resolved = config or KnoxMessengerConfig.from_env()
    context = _prepare_knox_context(resolved)

    now_ms = int(time.time() * 1000)
    chat_msg_text = str(chat_msg)
    payload = {
        "requestId": now_ms,
        "chatroomId": int(chatroom_id),
        "chatMessageParams": [
            {
                "msgId": now_ms,
                "msgType": int(msg_type),
                "chatMsg": chat_msg_text,
                "msgTtl": int(ttl),
            }
        ],
    }
    _post_encrypted(context, "message/api/v2.0/message/chatRequest", payload)


def change_chatroom_title(
    *,
    chatroom_id: int,
    title: str,
    config: KnoxMessengerConfig | None = None,
) -> None:
    """채팅룸 제목을 변경합니다."""

    resolved = config or KnoxMessengerConfig.from_env()
    context = _prepare_knox_context(resolved)
    payload = {
        "requestId": int(time.time() * 1000),
        "chatroomId": int(chatroom_id),
        "title": str(title),
    }
    _post_encrypted(context, "message/api/v2.0/message/changeChatroomMetaRequest", payload)


# =============================================================================
# msgType=7 (Excel Table)
# =============================================================================
def _read_text_file(path: str, encoding: str = "utf-8") -> str:
    if not os.path.exists(path):
        raise KnoxMessengerError(f"HTML file not found: {path}")
    with open(path, "r", encoding=encoding) as file:
        return file.read()


def _knox_testutil_compress_java_compatible(value: str) -> str:
    """Java TestUtil.compress()와 동일한 형식으로 압축합니다."""

    raw = value.encode("utf-8")
    gz = gzip.compress(raw)

    header_value = int(len(value) * 1.2)
    header = struct.pack("<I", header_value)

    combined = header + gz
    return base64.b64encode(combined).decode("utf-8")


def send_excel_table_message_from_file(
    *,
    chatroom_id: int,
    html_path: str,
    ttl: int = _DEFAULT_MESSAGE_TTL,
    config: KnoxMessengerConfig | None = None,
    encoding: str = "utf-8",
    debug_print_plain: bool = True,
) -> None:
    """msgType=7(Table/Excel) 메시지를 HTML 파일로 전송합니다."""

    resolved = config or KnoxMessengerConfig.from_env()
    context = _prepare_knox_context(resolved)

    html = _read_text_file(html_path, encoding=encoding).strip()
    if not html:
        raise KnoxMessengerError(f"HTML file is empty: {html_path}")

    if len(html) > 40000:
        raise KnoxMessengerError("Message Length is too long (>40000 chars). Reduce table size.")

    compressed = _knox_testutil_compress_java_compatible(html)
    command_prefix = '<!-- {"COMMAND":"SNDCL", "SNDCL":{"KND":"CLDT", "TYPE":"CSV"}} -->'
    chat_msg = command_prefix + compressed

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

    if debug_print_plain:
        print("\n[PLAIN payload (before encryption) - head]")
        print(json.dumps(payload, ensure_ascii=False)[:1200])
        print("\n[chatMsg prefix head]")
        print(chat_msg[:120])
        print("\n[html length(chars)]", len(html), " / [compressed length(chars)]", len(compressed))

    _post_encrypted(context, "message/api/v2.0/message/chatRequest", payload)
