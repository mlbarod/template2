# =============================================================================
# 모듈: Airflow 실패 알림 callback
# 주요 기능: task 실패 시 Knox 메신저로 단순 장애 알림 전송
# 주요 가정: Knox API 설정과 수신자 Knox ID는 Airflow 환경 변수로 주입합니다.
# =============================================================================
"""Airflow DAG에서 사용하는 실패 알림 callback입니다."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Sequence

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 10
_DEFAULT_MESSAGE_TTL = 7200
_DEFAULT_CHATROOM_TITLE = "Airflow 실패 알림"
_DEFAULT_CHATROOM_ID_FILE = "/tmp/airflow_failure_alert_chatroom_id.json"
_TEXT_MESSAGE_TYPE = 0
_DEVICE_TYPE = "relation"
_MEMO_KEY_PREFIX = "airflow_failure_alert_chatroom"


def _env(name: str, default: str = "") -> str:
    """환경 변수 문자열을 공백 제거 후 반환합니다."""

    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    """환경 변수 값을 정수로 변환합니다."""

    try:
        value = int(_env(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _split_csv(value: str) -> list[str]:
    """쉼표 구분 값을 빈 항목 없이 반환합니다."""

    return [item.strip() for item in value.split(",") if item.strip()]


def _build_url(base_url: str, path: str) -> str:
    """Knox API base URL과 path를 결합합니다."""

    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _build_headers() -> dict[str, str] | None:
    """Knox API 공통 header를 구성합니다."""

    authorization = _env("KNOX_MESSENGER_AUTHORIZATION")
    system_id = _env("KNOX_MESSENGER_SYSTEM_ID")
    if not authorization or not system_id:
        logger.info("Airflow 실패 알림 스킵: KNOX_MESSENGER_AUTHORIZATION/SYSTEM_ID 미설정")
        return None
    return {
        "accept": "*/*",
        "Content-Type": "application/json",
        "Authorization": authorization,
        "System-ID": system_id,
    }


def _split_key_iv(key_hex: str) -> tuple[bytes, bytes]:
    """Knox key 값을 AES key/iv로 나눕니다."""

    keyplusiv = bytes.fromhex(key_hex)
    return keyplusiv[:32], keyplusiv[32:48]


def _encrypt_payload(*, key: bytes, iv: bytes, payload: dict[str, Any]) -> bytes:
    """Knox 암호화 요청 본문을 생성합니다."""

    plaintext = json.dumps(payload).encode("utf-8")
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext)


def _decrypt_response(*, key: bytes, iv: bytes, ciphertext: str | bytes) -> str:
    """Knox 암호화 응답 본문을 복호화합니다."""

    raw = base64.b64decode(ciphertext)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(raw) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode("utf-8")


def _prepare_knox_context() -> dict[str, Any] | None:
    """Knox device/header/key/iv context를 준비합니다."""

    base_url = _env("KNOX_MESSENGER_API_BASE_URL")
    if not base_url:
        logger.info("Airflow 실패 알림 스킵: KNOX_MESSENGER_API_BASE_URL 미설정")
        return None
    headers = _build_headers()
    if headers is None:
        return None
    timeout_seconds = _env_int("KNOX_MESSENGER_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS)

    device_response = requests.get(
        _build_url(base_url, "contact/api/v2.0/device/o1/reg"),
        headers=headers,
        verify=False,
        timeout=timeout_seconds,
    )
    device_response.raise_for_status()
    headers["x-device-id"] = str(device_response.json()["deviceServerID"])
    headers["x-device-type"] = _DEVICE_TYPE

    key_response = requests.get(
        _build_url(base_url, "msgctx/api/v2.0/key/getkeys"),
        headers=headers,
        verify=False,
        timeout=timeout_seconds,
    )
    key_response.raise_for_status()
    key, iv = _split_key_iv(key_response.json()["key"])
    return {
        "base_url": base_url,
        "headers": headers,
        "key": key,
        "iv": iv,
        "timeout_seconds": timeout_seconds,
    }


def _post_encrypted(*, context: dict[str, Any], path: str, payload: dict[str, Any]) -> requests.Response:
    """Knox 암호화 POST 요청을 보냅니다."""

    body = _encrypt_payload(key=context["key"], iv=context["iv"], payload=payload)
    response = requests.post(
        _build_url(context["base_url"], path),
        headers=context["headers"],
        data=body,
        verify=False,
        timeout=context["timeout_seconds"],
    )
    response.raise_for_status()
    return response


def _search_user_ids(*, single_ids: Sequence[str], context: dict[str, Any]) -> list[str]:
    """Knox singleId 목록을 userID 목록으로 변환합니다."""

    payload = {"singleIdList": [{"singleId": str(single_id)} for single_id in single_ids]}
    response = requests.post(
        _build_url(context["base_url"], "contact/api/v2.0/profile/o1/search/loginid"),
        headers=context["headers"],
        data=json.dumps(payload),
        verify=False,
        timeout=context["timeout_seconds"],
    )
    response.raise_for_status()
    results = response.json()["userSearchResult"]["searchResultList"]
    by_single = {
        str(item.get("singleID") or "").strip(): str(item.get("userID") or "").strip()
        for item in results
        if str(item.get("singleID") or "").strip() and str(item.get("userID") or "").strip()
    }
    return [by_single[single_id] for single_id in single_ids if single_id in by_single]


def _build_memo_key(*, knox_ids: Iterable[str], title: str) -> str:
    """수신자/제목 조합별 chatroom_id 메모 key를 생성합니다."""

    normalized = "|".join([*sorted(str(knox_id).strip() for knox_id in knox_ids), title])
    digest = sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"{_MEMO_KEY_PREFIX}:{digest}"


def _memo_path() -> Path:
    """chatroom_id 메모 파일 경로를 반환합니다."""

    return Path(_env("AIRFLOW_FAILURE_ALERT_CHATROOM_ID_FILE", _DEFAULT_CHATROOM_ID_FILE))


def _read_chatroom_memo(path: Path) -> dict[str, int]:
    """chatroom_id 메모 파일을 읽습니다."""

    if not path.exists():
        return {}
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Airflow 실패 알림 chatroom_id 메모 파일을 읽지 못했습니다: %s", path)
        return {}
    if not isinstance(raw_data, dict):
        return {}
    memo: dict[str, int] = {}
    for key, value in raw_data.items():
        try:
            chatroom_id = int(value)
        except (TypeError, ValueError):
            continue
        if chatroom_id > 0:
            memo[str(key)] = chatroom_id
    return memo


def _write_chatroom_memo(*, path: Path, key: str, chatroom_id: int) -> None:
    """chatroom_id 메모 파일을 갱신합니다."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        memo = _read_chatroom_memo(path)
        memo[key] = int(chatroom_id)
        tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp_path.write_text(json.dumps(memo, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_path, path)
    except Exception:
        logger.exception("Airflow 실패 알림 chatroom_id 메모 파일 저장 실패: %s", path)


def _get_or_create_chatroom_id(*, knox_ids: list[str], title: str, context: dict[str, Any]) -> int | None:
    """메모 파일에서 chatroom_id를 읽거나 Knox 채팅방을 최초 생성합니다."""

    key = _build_memo_key(knox_ids=knox_ids, title=title)
    path = _memo_path()
    memo = _read_chatroom_memo(path)
    chatroom_id = memo.get(key)
    if chatroom_id:
        return chatroom_id

    user_ids = _search_user_ids(single_ids=knox_ids, context=context)
    if not user_ids:
        logger.info("Airflow 실패 알림 스킵: Knox userID 조회 결과 없음")
        return None
    payload = {
        "requestId": int(time.time() * 1000),
        "chatType": 1,
        "receivers": [str(user_id) for user_id in user_ids],
        "chatroomTitle": title,
    }
    response = _post_encrypted(
        context=context,
        path="message/api/v2.0/message/createChatroomRequest",
        payload=payload,
    )
    decrypted = _decrypt_response(key=context["key"], iv=context["iv"], ciphertext=response.text)
    chatroom_id = int(json.loads(decrypted)["chatroomId"])
    _write_chatroom_memo(path=path, key=key, chatroom_id=chatroom_id)
    return chatroom_id


def _build_failure_message(context: dict[str, Any]) -> str:
    """Airflow task 실패 알림 메시지를 구성합니다."""

    task_instance = context.get("task_instance")
    exception = context.get("exception")
    dag = context.get("dag")
    dag_run = context.get("dag_run")
    dag_id = getattr(task_instance, "dag_id", getattr(dag, "dag_id", "unknown"))
    task_id = getattr(task_instance, "task_id", "unknown")
    run_id = context.get("run_id") or getattr(dag_run, "run_id", "")
    log_url = getattr(task_instance, "log_url", "")
    lines = [
        "[Airflow 실패 알림]",
        f"DAG: {dag_id}",
        f"Task: {task_id}",
    ]
    if run_id:
        lines.append(f"Run: {run_id}")
    if exception:
        lines.append(f"Error: {exception}")
    if log_url:
        lines.append(f"Log: {log_url}")
    return "\n".join(lines)


def _send_chat_message(*, chatroom_id: int, message: str, context: dict[str, Any]) -> None:
    """기존 채팅방에 평문 메시지를 전송합니다."""

    now_ms = int(time.time() * 1000)
    payload = {
        "requestId": now_ms,
        "chatroomId": int(chatroom_id),
        "chatMessageParams": [
            {
                "msgId": now_ms,
                "msgType": _TEXT_MESSAGE_TYPE,
                "chatMsg": str(message),
                "msgTtl": _env_int("AIRFLOW_FAILURE_ALERT_MESSAGE_TTL", _DEFAULT_MESSAGE_TTL),
            }
        ],
    }
    _post_encrypted(context=context, path="message/api/v2.0/message/chatRequest", payload=payload)


def notify_airflow_task_failure(context: dict[str, Any]) -> None:
    """Airflow `on_failure_callback` 진입점입니다."""

    knox_ids = _split_csv(_env("AIRFLOW_FAILURE_ALERT_KNOX_IDS"))
    if not knox_ids:
        logger.info("Airflow 실패 알림 스킵: AIRFLOW_FAILURE_ALERT_KNOX_IDS 미설정")
        return
    try:
        knox_context = _prepare_knox_context()
        if knox_context is None:
            return
        title = _env("AIRFLOW_FAILURE_ALERT_CHATROOM_TITLE", _DEFAULT_CHATROOM_TITLE)
        chatroom_id = _get_or_create_chatroom_id(knox_ids=knox_ids, title=title, context=knox_context)
        if chatroom_id is None:
            return
        _send_chat_message(
            chatroom_id=chatroom_id,
            message=_build_failure_message(context),
            context=knox_context,
        )
    except Exception:
        logger.exception("Airflow 실패 알림 전송 실패")
