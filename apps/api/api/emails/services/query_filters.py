# =============================================================================
# 모듈 설명: 이메일 조회용 쿼리 파라미터를 정규화합니다.
# - 주요 함수: parse_int, parse_datetime_value, build_email_filters
# - 불변 조건: 날짜는 timezone-aware(UTC)로 정규화됩니다.
# =============================================================================

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timezone as dt_timezone
from typing import Any, Dict, Mapping

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def parse_int(value: Any, default: int) -> int:
    """입력 값을 정수로 파싱하고 실패/0 이하일 때 기본값을 반환합니다.

    입력:
        value: 정수로 변환할 값.
        default: 변환 실패 또는 0 이하일 때 사용할 기본값.
    반환:
        유효한 양의 정수 또는 기본값.
    부작용:
        없음.
    오류:
        변환 실패 시 기본값 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 정수 변환 및 범위 확인
    # -----------------------------------------------------------------------------
    try:
        parsed = int(value)
        if parsed <= 0:
            return default
        return parsed
    except (TypeError, ValueError):
        return default


_UTC = getattr(timezone, "utc", dt_timezone.utc)


def _get_default_timezone():
    """Django 기본 타임존을 반환합니다."""

    return timezone.get_default_timezone()


def _normalize_to_utc(value: datetime) -> datetime:
    """datetime 값을 UTC timezone-aware로 정규화합니다.

    입력:
        value: datetime 값.
    반환:
        UTC timezone-aware datetime.
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 타임존 보정(기본 타임존 가정) 후 UTC 변환
    # -----------------------------------------------------------------------------
    if timezone.is_naive(value):
        value = timezone.make_aware(value, _get_default_timezone())
    return value.astimezone(_UTC)


def parse_datetime_value(value: Any, *, boundary: str = "start") -> datetime | None:
    """날짜/일시 입력을 UTC 기준 datetime으로 파싱합니다.

    입력:
        value: ISO 날짜/시간 문자열, date/datetime 객체 또는 None.
        boundary: date 입력일 때 시작/끝 경계("start" | "end").
    반환:
        timezone-aware datetime 또는 None(기본 타임존 기준 해석 후 UTC 변환).
    부작용:
        없음.
    오류:
        파싱 실패 시 None 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) boundary 정규화 및 타입별 처리
    # -----------------------------------------------------------------------------
    boundary = "end" if boundary == "end" else "start"
    if value is None:
        return None
    if isinstance(value, datetime):
        return _normalize_to_utc(value)
    if isinstance(value, date):
        time_value = dt_time.max if boundary == "end" else dt_time.min
        return _normalize_to_utc(datetime.combine(value, time_value))
    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None

    # -----------------------------------------------------------------------------
    # 2) date 단독 입력 처리
    # -----------------------------------------------------------------------------
    # Django 버전에 따라 parse_datetime("YYYY-MM-DD")가 datetime으로 파싱될 수 있어
    # 경계(boundary=end) 정보가 무시되지 않도록 date-only를 먼저 판별합니다.
    date_only = parse_date(raw)
    if date_only and "T" not in raw and " " not in raw and ":" not in raw:
        time_value = dt_time.max if boundary == "end" else dt_time.min
        return _normalize_to_utc(datetime.combine(date_only, time_value))

    dt = parse_datetime(raw)
    if dt:
        return _normalize_to_utc(dt)
    return None


def parse_mailbox_user_sdwt_prod(params: Mapping[str, Any]) -> str:
    """요청 쿼리에서 mailbox(user_sdwt_prod) 값을 추출/정규화합니다.

    입력:
        params: 요청 쿼리 매핑.
    반환:
        정규화된 user_sdwt_prod 문자열(없으면 빈 문자열).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) snake_case/camelCase 키 모두 허용
    # -----------------------------------------------------------------------------
    raw = params.get("user_sdwt_prod") or params.get("userSdwtProd") or ""
    return raw.strip() if isinstance(raw, str) else ""


def build_email_filters(
    *, params: Mapping[str, Any], default_page_size: int, max_page_size: int
) -> Dict[str, Any]:
    """이메일 목록 필터 값을 일관되게 정규화합니다.

    입력:
        params: 요청 쿼리 매핑.
        default_page_size: 기본 페이지 크기.
        max_page_size: 최대 페이지 크기 상한.
    반환:
        필터 dict (mailbox_user_sdwt_prod, search, sender, recipient, date_from/date_to, page, page_size).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 파라미터 정규화
    # -----------------------------------------------------------------------------
    return {
        "mailbox_user_sdwt_prod": parse_mailbox_user_sdwt_prod(params),
        "search": (params.get("q") or "").strip(),
        "sender": (params.get("sender") or "").strip(),
        "recipient": (params.get("recipient") or "").strip(),
        "date_from": parse_datetime_value(params.get("date_from"), boundary="start"),
        "date_to": parse_datetime_value(params.get("date_to"), boundary="end"),
        "page": parse_int(params.get("page"), 1),
        "page_size": min(parse_int(params.get("page_size"), default_page_size), max_page_size),
    }
