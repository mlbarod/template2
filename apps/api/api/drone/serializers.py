# =============================================================================
# 모듈: 드론 직렬화 유틸
# 주요 함수: serialize_early_inform_entry
# 주요 가정: 응답 키는 camelCase로 반환합니다.
# =============================================================================
from __future__ import annotations

from typing import Any, Sequence

from .models import DroneEarlyInform

MAX_FIELD_LENGTH = 50


class DroneRequestValidationError(ValueError):
    """Drone API 요청 검증 실패를 표현하는 예외입니다."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        """응답 상태 코드와 메시지를 함께 보관합니다."""

        super().__init__(message)
        self.status_code = status_code


def normalize_short_text(
    value: Any,
    *,
    allow_non_str: bool = False,
    max_length: int = MAX_FIELD_LENGTH,
) -> str | None:
    """짧은 문자열 필드를 공백 제거와 길이 제한 기준으로 정규화합니다."""

    if isinstance(value, str):
        trimmed = value.strip()
    elif value is None:
        trimmed = ""
    elif allow_non_str:
        trimmed = str(value).strip()
    else:
        return None

    if not trimmed:
        return None
    return trimmed if len(trimmed) <= max_length else None


def normalize_text(value: Any, *, allow_non_str: bool = False) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if value is None:
        return None
    if not isinstance(value, str):
        if not allow_non_str:
            return None
        value = str(value)
    trimmed = value.strip()
    return trimmed if trimmed else None


def normalize_text_list(values: Sequence[Any], *, allow_non_str: bool = False) -> list[str]:
    """문자열 리스트를 공백 제거 기준으로 정규화합니다."""

    normalized: list[str] = []
    for value in values:
        cleaned = normalize_text(value, allow_non_str=allow_non_str)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def normalize_lookup_text(value: Any, *, allow_non_str: bool = False) -> str | None:
    """대소문자 비구분 비교용 문자열 키를 정규화합니다."""

    cleaned = normalize_text(value, allow_non_str=allow_non_str)
    return cleaned.casefold() if cleaned else None


def normalize_lookup_text_list(values: Sequence[Any], *, allow_non_str: bool = False) -> list[str]:
    """대소문자 비구분 비교용 문자열 키 리스트를 정규화합니다."""

    normalized: list[str] = []
    for value in values:
        cleaned = normalize_lookup_text(value, allow_non_str=allow_non_str)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def normalize_chatroom_id(value: Any) -> int | None:
    """채팅룸 ID 값을 양의 정수로 정규화합니다."""

    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def display_delivery_target(value: Any) -> str | None:
    """내부 marker target을 화면용 target 라벨로 변환합니다."""

    target = normalize_text(value)
    if target and target.startswith("__"):
        return "Target 미지정"
    return target


def collapse_display_values(values: Sequence[Any]) -> list[str]:
    """표시값을 유지하면서 대소문자 비구분 중복을 제거합니다."""

    display_by_key: dict[str, str] = {}
    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        display_by_key.setdefault(normalized.casefold(), normalized)
    return sorted(display_by_key.values())


def normalize_line_id(value: Any) -> str:
    """lineId 값을 공백 제거 기준으로 정규화합니다."""

    normalized = normalize_short_text(value)
    return normalized or ""


def normalize_main_step(value: Any) -> str | None:
    """mainStep 값을 공백 제거와 길이 제한 기준으로 정규화합니다."""

    return normalize_short_text(value, allow_non_str=True)


def normalize_target_text(value: Any) -> str:
    """target/user SDWT 계열 문자열을 공백 제거 기준으로 정규화합니다."""

    return value.strip() if isinstance(value, str) else ""


def normalize_custom_end_step(value: Any) -> str | None:
    """customEndStep 값을 빈 문자열은 None으로 처리해 정규화합니다."""

    if value is None:
        return None
    trimmed = value.strip() if isinstance(value, str) else str(value).strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_FIELD_LENGTH:
        raise DroneRequestValidationError("customEndStep must be 50 characters or fewer")
    return trimmed


def normalize_updated_by(value: Any) -> str | None:
    """updated_by 값을 공백 제거와 길이 제한 기준으로 정규화합니다."""

    return normalize_short_text(value)


def parse_limit_param(*, body_value: Any, query_value: Any) -> int | None:
    """JSON 바디와 쿼리 파라미터에서 limit 값을 파싱합니다."""

    raw_limit = body_value if body_value is not None else query_value
    if raw_limit is None:
        return None

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise DroneRequestValidationError("limit must be an integer") from exc

    return limit if limit > 0 else None


def parse_positive_int(value: Any, *, error_message: str = "A valid id is required") -> int:
    """양의 정수 입력 값을 파싱합니다."""

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DroneRequestValidationError(error_message) from exc
    if parsed <= 0:
        raise DroneRequestValidationError(error_message)
    return parsed


def parse_user_id_list(value: Any) -> list[int]:
    """userIds 값을 중복 제거된 양의 정수 리스트로 파싱합니다."""

    if not isinstance(value, list):
        raise DroneRequestValidationError("userIds must be a list")

    user_ids: list[int] = []
    seen: set[int] = set()
    for item in value:
        if isinstance(item, bool):
            raise DroneRequestValidationError("userIds must contain only integers")
        if isinstance(item, int):
            user_id = item
        elif isinstance(item, str):
            try:
                user_id = int(item.strip())
            except ValueError as exc:
                raise DroneRequestValidationError("userIds must contain only integers") from exc
        else:
            raise DroneRequestValidationError("userIds must contain only integers")

        if user_id <= 0:
            raise DroneRequestValidationError("userIds must contain only positive integers")
        if user_id in seen:
            continue
        seen.add(user_id)
        user_ids.append(user_id)
    return user_ids


def parse_optional_comment(payload: dict[str, Any]) -> str | None:
    """즉시 인폼 요청의 comment 필드를 파싱합니다."""

    raw_comment = payload.get("comment")
    if raw_comment is not None and not isinstance(raw_comment, str):
        raise DroneRequestValidationError("comment must be a string")
    return raw_comment.strip() if isinstance(raw_comment, str) else None


def parse_required_channel(payload: dict[str, Any]) -> str:
    """채널 재시도 요청의 channel 필드를 파싱합니다."""

    raw_channel = payload.get("channel")
    if not isinstance(raw_channel, str):
        raise DroneRequestValidationError("channel must be a string")
    channel = raw_channel.strip().lower()
    if not channel:
        raise DroneRequestValidationError("channel is required")
    return channel


def parse_optional_text_field(
    payload: dict[str, Any],
    *,
    field_name: str,
    max_length: int,
) -> tuple[bool, str | None]:
    """옵션 문자열 필드의 제공 여부와 정규화 값을 반환합니다."""

    if field_name not in payload:
        return False, None

    raw_value = payload.get(field_name)
    if raw_value is not None and not isinstance(raw_value, str):
        raise DroneRequestValidationError(f"{field_name} must be a string or null")

    normalized = raw_value.strip() if isinstance(raw_value, str) else ""
    if normalized and len(normalized) > max_length:
        raise DroneRequestValidationError(f"{field_name} must be {max_length} characters or fewer")
    return True, normalized or None


def parse_optional_bool_field(
    payload: dict[str, Any],
    *,
    field_name: str,
) -> tuple[bool, bool | None]:
    """옵션 boolean 필드의 제공 여부와 값을 반환합니다."""

    if field_name not in payload:
        return False, None
    raw_value = payload.get(field_name)
    if not isinstance(raw_value, bool):
        raise DroneRequestValidationError(f"{field_name} must be a boolean")
    return True, raw_value


def serialize_early_inform_entry(entry: DroneEarlyInform) -> dict[str, Any]:
    """DroneEarlyInform 모델을 API 응답 형태로 직렬화합니다.

    인자:
        entry: DroneEarlyInform 인스턴스.

    반환:
        직렬화된 dict.

    부작용:
        없음. 읽기 전용 변환입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 업데이트 시각 정규화
    # -----------------------------------------------------------------------------
    updated_at = entry.updated_at
    return {
        "id": int(entry.id),
        "lineId": entry.line_id,
        "mainStep": entry.main_step,
        "customEndStep": entry.custom_end_step,
        "updatedBy": entry.updated_by,
        "updatedAt": updated_at.isoformat() if hasattr(updated_at, "isoformat") and updated_at else None,
    }
