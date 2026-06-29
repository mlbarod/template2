# =============================================================================
# 모듈 설명: 활동 로그 직렬화 유틸을 제공합니다.
# - 주요 함수: serialize_activity_log, normalize_app_access_payload
# - 불변 조건: API 응답에서 내부 브리지 IP는 제외합니다.
# =============================================================================
from __future__ import annotations

from typing import Any

from django.core.exceptions import ObjectDoesNotExist

from .models import ActivityLog

INTERNAL_BRIDGE_REMOTE_ADDR = "172.18.0.1"
MAX_APP_ID_LENGTH = 120
MAX_APP_NAME_LENGTH = 160
MAX_SOURCE_NAME_LENGTH = 80
MAX_PASTED_TEXT_LENGTH = 200_000


def _clean_text(value: Any, *, max_length: int) -> str:
    """문자열 입력값을 공백 제거와 길이 제한 기준으로 정리합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _get_user_role(user: Any | None) -> Any | None:
    """사용자 프로필 role 값을 안전하게 반환합니다."""

    if user is None:
        return None

    try:
        return getattr(user.profile, "role", None)
    except ObjectDoesNotExist:
        # 프로필이 없는 사용자는 예외 대신 None으로 처리합니다.
        return None


def _serialize_metadata(metadata: Any) -> Any:
    """응답에 노출할 ActivityLog metadata를 정리합니다."""

    normalized_metadata = metadata or {}
    if (
        isinstance(normalized_metadata, dict)
        and normalized_metadata.get("remote_addr") == INTERNAL_BRIDGE_REMOTE_ADDR
    ):
        # 도커 브리지 내부 IP는 의미가 없으므로 응답에서 제외합니다.
        return {
            key: value
            for key, value in normalized_metadata.items()
            if key != "remote_addr"
        }

    return normalized_metadata


def serialize_activity_log(entry: ActivityLog) -> dict[str, Any]:
    """ActivityLog 모델을 API 응답 형식으로 직렬화합니다.

    입력:
    - entry: ActivityLog 인스턴스

    반환:
    - dict[str, Any]: 활동 로그 API 응답 dict

    부작용:
    - 없음(읽기 전용 변환)

    오류:
    - 없음
    """

    user = entry.user
    username = user.get_username() if user else None

    return {
        "id": entry.id,
        "user": username,
        "role": _get_user_role(user),
        "action": entry.action,
        "path": entry.path,
        "method": entry.method,
        "status": entry.status_code,
        "metadata": _serialize_metadata(entry.metadata),
        "timestamp": entry.created_at.isoformat(),
    }


def normalize_app_access_payload(payload: Any) -> tuple[dict[str, str] | None, str | None]:
    """앱 접속 기록 요청 payload를 검증하고 정규화합니다.

    입력:
    - payload: JSON 요청 본문

    반환:
    - tuple[dict[str, str] | None, str | None]: 정규화된 값 또는 오류 메시지

    부작용:
    - 없음

    오류:
    - 없음(검증 실패는 오류 메시지로 반환)
    """

    if not isinstance(payload, dict):
        return None, "Invalid JSON body"

    app_id = _clean_text(payload.get("appId") or payload.get("app_id"), max_length=MAX_APP_ID_LENGTH)
    app_name = _clean_text(payload.get("appName") or payload.get("app_name"), max_length=MAX_APP_NAME_LENGTH)
    path = _clean_text(payload.get("path"), max_length=512)

    if not app_id:
        return None, "appId is required"
    if not app_name:
        return None, "appName is required"

    return {
        "app_id": app_id,
        "app_name": app_name,
        "path": path,
    }, None


def normalize_manual_app_access_paste_payload(payload: Any) -> tuple[dict[str, str] | None, str | None]:
    """외부 앱 수동 접속현황 붙여넣기 요청을 검증하고 정규화합니다.

    입력:
    - payload: JSON 요청 본문

    반환:
    - tuple[dict[str, str] | None, str | None]: pasted_text/source_name 또는 오류 메시지

    부작용:
    - 없음

    오류:
    - 없음(검증 실패는 오류 메시지로 반환)
    """

    if not isinstance(payload, dict):
        return None, "Invalid JSON body"

    pasted_text = payload.get("pastedText") or payload.get("pasted_text")
    if not isinstance(pasted_text, str) or not pasted_text.strip():
        return None, "pastedText is required"
    if len(pasted_text) > MAX_PASTED_TEXT_LENGTH:
        return None, f"pastedText must be {MAX_PASTED_TEXT_LENGTH} characters or less"

    source_name = _clean_text(
        payload.get("sourceName") or payload.get("source_name") or "manual",
        max_length=MAX_SOURCE_NAME_LENGTH,
    )
    if not source_name:
        source_name = "manual"

    return {
        "pasted_text": pasted_text,
        "source_name": source_name,
    }, None


__all__ = [
    "normalize_app_access_payload",
    "normalize_manual_app_access_paste_payload",
    "serialize_activity_log",
]
