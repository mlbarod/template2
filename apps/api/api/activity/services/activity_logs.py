# =============================================================================
# 모듈 설명: 활동 로그 서비스 로직을 제공합니다.
# - 주요 함수: get_recent_activity_payload, get_app_access_stats_payload, record_app_access
# - 불변 조건: 조회는 셀렉터를 통해 수행하고, 쓰기는 activity 도메인 안에서 처리합니다.
# =============================================================================
from __future__ import annotations

import csv
import json
from datetime import UTC, date, datetime, time, timedelta
from io import StringIO
from typing import Any
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import ActivityLog, ExternalAppAccessDailyStat, ExternalAppUsageSyncState
from ..selectors import (
    APP_ACCESS_ACTION,
    get_external_app_usage_sync_state,
    get_recent_activity_logs,
    summarize_external_app_access_by_app,
    summarize_external_app_access_by_date,
    summarize_external_app_access_totals,
    summarize_app_access_by_app,
    summarize_app_access_by_date,
    summarize_app_access_totals,
)
from ..serializers import serialize_activity_log

KST = ZoneInfo("Asia/Seoul")
DEFAULT_STATS_DAYS = 7
MAX_STATS_DAYS = 90
DEFAULT_STATS_PERIOD = "day"
ALLOWED_STATS_PERIODS = {"day", "week", "month"}
MANUAL_SOURCE_TYPE = ExternalAppAccessDailyStat.SOURCE_TYPE_MANUAL
EXTERNAL_USAGE_SOURCE_TYPE = "external_api"
EXTERNAL_USAGE_SYNC_KEY = "external_app_usage"
EXTERNAL_USAGE_SYNC_THROTTLE = timedelta(hours=1)
EXTERNAL_USAGE_SYNC_LOOKBACK_DAYS = 365
MANUAL_PASTE_EXPECTED_COLUMNS = ["date", "appName", "accessCount", "uniqueUserCount", "memo"]

HEADER_ALIASES = {
    "date": "date",
    "stat_date": "date",
    "날짜": "date",
    "일자": "date",
    "app_id": "app_id",
    "appid": "app_id",
    "앱id": "app_id",
    "앱_id": "app_id",
    "앱아이디": "app_id",
    "app_name": "app_name",
    "appname": "app_name",
    "앱명": "app_name",
    "앱이름": "app_name",
    "access_count": "access_count",
    "accesscount": "access_count",
    "접속횟수": "access_count",
    "접속수": "access_count",
    "unique_user_count": "unique_user_count",
    "uniqueusercount": "unique_user_count",
    "접속사용자": "unique_user_count",
    "접속사용자수": "unique_user_count",
    "사용자수": "unique_user_count",
    "memo": "memo",
    "메모": "memo",
    "비고": "memo",
}
REQUIRED_MANUAL_COLUMNS = ["date", "app_name", "access_count", "unique_user_count"]
MANUAL_COLUMN_LABELS = {
    "date": "date",
    "app_name": "appName",
    "access_count": "accessCount",
    "unique_user_count": "uniqueUserCount",
}


def _parse_iso_date(value: str | None, *, field_name: str) -> date | None:
    """YYYY-MM-DD 문자열을 date로 변환합니다."""

    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _resolve_stats_range(
    *,
    from_value: str | None,
    to_value: str | None,
    now: datetime | None = None,
) -> tuple[date, date, datetime, datetime]:
    """KST 날짜 범위를 UTC datetime boundary로 변환합니다."""

    current = now or datetime.now(tz=UTC)
    today_kst = current.astimezone(KST).date()
    to_date = _parse_iso_date(to_value, field_name="to") or today_kst
    from_date = _parse_iso_date(from_value, field_name="from") or (to_date - timedelta(days=DEFAULT_STATS_DAYS - 1))

    if from_date > to_date:
        raise ValueError("from must be earlier than or equal to to")

    if (to_date - from_date).days + 1 > MAX_STATS_DAYS:
        raise ValueError(f"date range must be {MAX_STATS_DAYS} days or less")

    start_local = datetime.combine(from_date, time.min, tzinfo=KST)
    end_local = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=KST)
    return from_date, to_date, start_local.astimezone(UTC), end_local.astimezone(UTC)


def _resolve_stats_period(value: str | None) -> str:
    """통계 집계 단위를 정규화합니다."""

    if value is None or not value.strip():
        return DEFAULT_STATS_PERIOD
    period = value.strip().lower()
    if period not in ALLOWED_STATS_PERIODS:
        raise ValueError("period must be one of day, week, month")
    return period


def _get_period_start(value: date, *, period: str) -> date:
    """날짜가 속한 집계 기간의 시작일을 반환합니다."""

    if period == "week":
        return value - timedelta(days=value.weekday())
    if period == "month":
        return value.replace(day=1)
    return value


def _safe_text(value: Any, fallback: str) -> str:
    """집계 row의 문자열 값을 안전하게 반환합니다."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _serialize_datetime(value: Any) -> str | None:
    """datetime 값을 ISO 문자열로 변환합니다."""

    if isinstance(value, datetime):
        return value.astimezone(KST).isoformat()
    return None


def _serialize_date(value: Any) -> str:
    """date 값을 ISO 문자열로 변환합니다."""

    if isinstance(value, date):
        return value.isoformat()
    return ""


def _serialize_kst_date_end(value: Any) -> str | None:
    """KST 날짜의 종료 시각을 ISO 문자열로 변환합니다."""

    if isinstance(value, date):
        return datetime.combine(value, time.max, tzinfo=KST).isoformat()
    return None


def _normalize_external_usage_source_name(value: Any) -> str:
    """외부 사용량 API sourceName을 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip()[:80]


def _read_external_usage_api_config() -> tuple[list[dict[str, str]], int, str | None]:
    """외부 앱 사용량 API 설정을 Django settings에서 읽습니다."""

    urls_raw = getattr(settings, "EXTERNAL_APP_USAGE_API_URLS", "") or ""
    timeout = getattr(settings, "EXTERNAL_APP_USAGE_API_TIMEOUT_SECONDS", 10) or 10
    try:
        timeout_seconds = int(timeout)
    except (TypeError, ValueError):
        timeout_seconds = 10

    if str(urls_raw).strip():
        try:
            parsed = json.loads(str(urls_raw))
        except ValueError as exc:
            return [], max(timeout_seconds, 1), f"EXTERNAL_APP_USAGE_API_URLS JSON 형식이 올바르지 않습니다: {exc}"
        if not isinstance(parsed, list):
            return [], max(timeout_seconds, 1), "EXTERNAL_APP_USAGE_API_URLS는 JSON 배열이어야 합니다."

        sources: list[dict[str, str]] = []
        for index, item in enumerate(parsed, start=1):
            if not isinstance(item, dict):
                return [], max(timeout_seconds, 1), f"EXTERNAL_APP_USAGE_API_URLS[{index}]는 객체여야 합니다."
            source_name = _normalize_external_usage_source_name(item.get("sourceName"))
            url = str(item.get("url") or "").strip()
            if not source_name or not url:
                return [], max(timeout_seconds, 1), f"EXTERNAL_APP_USAGE_API_URLS[{index}]에는 sourceName과 url이 필요합니다."
            sources.append({"sourceName": source_name, "url": url})
        return sources, max(timeout_seconds, 1), None

    return [], max(timeout_seconds, 1), None


def _normalize_external_usage_app_name(value: Any) -> str:
    """외부 사용량 row의 앱 이름을 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip().upper()[:120]


def _parse_external_usage_date(value: Any) -> date | None:
    """외부 사용량 row의 날짜 값을 date로 변환합니다."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _parse_external_usage_access_count(value: Any) -> int | None:
    """외부 사용량 row의 accessCount 값을 0 이상의 정수로 변환합니다."""

    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(str(value).replace(",", "").strip())
    except ValueError:
        return None
    if parsed < 0:
        return None
    return parsed


def _normalize_external_usage_rows(
    *,
    payload: Any,
    from_date: date,
    to_date: date,
    app_id: str | None,
    source_name: str,
) -> tuple[list[dict[str, Any]], int]:
    """외부 사용량 API 응답을 기존 통계 집계 row 형태로 정규화합니다."""

    if not isinstance(payload, list):
        raise ValueError("External usage API response must be a list")

    rows: list[dict[str, Any]] = []
    skipped_count = 0
    for raw_row in payload:
        if not isinstance(raw_row, dict):
            skipped_count += 1
            continue

        app_name = _normalize_external_usage_app_name(raw_row.get("appName"))
        stat_date = _parse_external_usage_date(raw_row.get("date"))
        access_count = _parse_external_usage_access_count(raw_row.get("accessCount"))
        app_key = app_name
        if not app_name or stat_date is None or access_count is None:
            skipped_count += 1
            continue
        if stat_date < from_date or stat_date > to_date:
            continue
        if app_id and app_key != app_id:
            continue

        rows.append(
            {
                "app_id": app_key,
                "app_name": app_name,
                "stat_date": stat_date,
                "access_count": access_count,
                "unique_user_count": 0,
                "source_type": EXTERNAL_USAGE_SOURCE_TYPE,
                "source_name": source_name,
            }
        )

    return rows, skipped_count


def _load_external_usage_rows(
    *,
    from_date: date,
    to_date: date,
    app_id: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """외부 사용량 API에서 앱별 사용량 row를 가져옵니다."""

    sources, timeout_seconds, config_error = _read_external_usage_api_config()
    status = {
        "enabled": bool(sources),
        "rowCount": 0,
        "skippedRows": 0,
        "error": None,
        "sources": [],
    }
    if config_error:
        status["error"] = config_error
        return [], status
    if not sources:
        return [], status

    all_rows: list[dict[str, Any]] = []
    source_errors = 0
    source_successes = 0
    for source in sources:
        source_status = {
            "sourceName": source["sourceName"],
            "rowCount": 0,
            "skippedRows": 0,
            "error": None,
        }
        try:
            response = requests.get(source["url"], timeout=timeout_seconds, verify=False)
            response.raise_for_status()
            rows, skipped_count = _normalize_external_usage_rows(
                payload=response.json(),
                from_date=from_date,
                to_date=to_date,
                app_id=app_id,
                source_name=source["sourceName"],
            )
        except (requests.RequestException, ValueError) as exc:
            source_status["error"] = f"외부 사용량 API 요청에 실패했습니다: {exc}"
            source_errors += 1
        else:
            source_successes += 1
            source_status["rowCount"] = len(rows)
            source_status["skippedRows"] = skipped_count
            all_rows.extend(rows)
        status["sources"].append(source_status)

    status["rowCount"] = sum(source["rowCount"] for source in status["sources"])
    status["skippedRows"] = sum(source["skippedRows"] for source in status["sources"])
    if source_errors and not source_successes:
        status["error"] = "외부 사용량 API 요청에 실패해 외부 API 통계를 제외했습니다."
        status["rowCount"] = 0
        status["skippedRows"] = 0
        return [], status
    return all_rows, status


def _get_external_usage_sync_window(now: datetime) -> tuple[date, date]:
    """수동 동기화 대상 날짜 범위를 계산합니다."""

    today_kst = now.astimezone(KST).date()
    return today_kst - timedelta(days=EXTERNAL_USAGE_SYNC_LOOKBACK_DAYS), today_kst


def _serialize_external_usage_sync_state(state: ExternalAppUsageSyncState | None) -> dict[str, Any]:
    """외부 API 동기화 상태를 응답 payload 형태로 변환합니다."""

    last_synced_at = state.last_synced_at if state else None
    last_attempted_at = state.updated_at if state else None
    next_sync_available_at = (
        last_attempted_at + EXTERNAL_USAGE_SYNC_THROTTLE if last_attempted_at is not None else None
    )
    return {
        "syncKey": EXTERNAL_USAGE_SYNC_KEY,
        "lastSyncedAt": _serialize_datetime(last_synced_at),
        "lastAttemptedAt": _serialize_datetime(last_attempted_at),
        "nextSyncAvailableAt": _serialize_datetime(next_sync_available_at),
        "lastStatus": state.last_status if state else "never",
        "lastError": state.last_error if state else "",
    }


def _is_external_usage_sync_throttled(
    *,
    state: ExternalAppUsageSyncState,
    now: datetime,
) -> bool:
    """마지막 동기화 시도 후 1시간이 지나지 않았는지 확인합니다."""

    if state.updated_at is None:
        return False
    return now - state.updated_at < EXTERNAL_USAGE_SYNC_THROTTLE


def _upsert_external_usage_rows(
    *,
    rows: list[dict[str, Any]],
    user: Any | None,
) -> dict[str, int]:
    """외부 API row를 일별 집계 테이블에 저장합니다."""

    created_count = 0
    updated_count = 0
    with transaction.atomic():
        for row in rows:
            _, created = ExternalAppAccessDailyStat.objects.update_or_create(
                app_id=_safe_text(row.get("app_id"), "unknown"),
                stat_date=row["stat_date"],
                source_name=_safe_text(row.get("source_name"), EXTERNAL_USAGE_SOURCE_TYPE),
                defaults={
                    "app_name": _safe_text(row.get("app_name"), _safe_text(row.get("app_id"), "unknown")),
                    "access_count": int(row.get("access_count") or 0),
                    "unique_user_count": int(row.get("unique_user_count") or 0),
                    "source_type": EXTERNAL_USAGE_SOURCE_TYPE,
                    "memo": "외부 API 수동 동기화",
                    "raw_payload": {
                        **row,
                        "stat_date": _serialize_date(row.get("stat_date")),
                    },
                    "updated_by": user if getattr(user, "is_authenticated", False) else None,
                    "created_by": user if getattr(user, "is_authenticated", False) else None,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
    return {"createdRows": created_count, "updatedRows": updated_count}


def sync_external_app_usage_stats(
    *,
    user: Any | None = None,
    now: datetime | None = None,
    bypass_throttle: bool = False,
) -> dict[str, Any]:
    """외부 앱 사용량 API를 수동 동기화합니다.

    입력:
    - user: 동기화 요청 사용자
    - now: 테스트용 현재 시각
    - bypass_throttle: 1시간 제한 우회 여부

    반환:
    - dict[str, Any]: 동기화 결과와 마지막 상태

    부작용:
    - 외부 API를 호출하고 ExternalAppAccessDailyStat/ExternalAppUsageSyncState를 갱신합니다.

    오류:
    - 없음. 실패 정보는 payload의 error/status에 담습니다.
    """

    current = now or timezone.now()
    with transaction.atomic():
        state, created = ExternalAppUsageSyncState.objects.select_for_update().get_or_create(
            sync_key=EXTERNAL_USAGE_SYNC_KEY,
            defaults={"last_status": "never"},
        )
        if not created and not bypass_throttle and _is_external_usage_sync_throttled(state=state, now=current):
            return {
                "synced": False,
                "skipped": True,
                "reason": "최근 1시간 내 외부 API 동기화 이력이 있습니다.",
                "syncState": _serialize_external_usage_sync_state(state),
                "commit": {"createdRows": 0, "updatedRows": 0},
            }
        state.last_status = "running"
        state.last_error = ""
        state.save(update_fields=["last_status", "last_error", "updated_at"])

    from_date, to_date = _get_external_usage_sync_window(current)
    rows, status = _load_external_usage_rows(from_date=from_date, to_date=to_date, app_id=None)
    if status.get("error"):
        with transaction.atomic():
            state = ExternalAppUsageSyncState.objects.select_for_update().get(sync_key=EXTERNAL_USAGE_SYNC_KEY)
            state.last_status = "failed"
            state.last_error = str(status["error"])
            state.save(update_fields=["last_status", "last_error", "updated_at"])
        return {
            "synced": False,
            "skipped": False,
            "reason": str(status["error"]),
            "syncState": _serialize_external_usage_sync_state(state),
            "externalUsage": status,
            "commit": {"createdRows": 0, "updatedRows": 0},
        }

    commit = _upsert_external_usage_rows(rows=rows, user=user)
    with transaction.atomic():
        state = ExternalAppUsageSyncState.objects.select_for_update().get(sync_key=EXTERNAL_USAGE_SYNC_KEY)
        state.last_synced_at = current
        state.last_status = "success"
        state.last_error = ""
        state.save(update_fields=["last_synced_at", "last_status", "last_error", "updated_at"])

    return {
        "synced": True,
        "skipped": False,
        "reason": "",
        "syncState": _serialize_external_usage_sync_state(state),
        "externalUsage": status,
        "commit": commit,
    }


def _normalize_header(value: Any) -> str:
    """붙여넣기 헤더 이름을 내부 컬럼명으로 정규화합니다."""

    if not isinstance(value, str):
        return ""
    key = value.strip().lstrip("\ufeff").lower().replace(" ", "").replace("-", "_")
    return HEADER_ALIASES.get(key, key)


def _detect_paste_delimiter(pasted_text: str) -> str:
    """붙여넣기 원문에서 TSV/CSV 구분자를 판별합니다."""

    first_line = next((line for line in pasted_text.splitlines() if line.strip()), "")
    return "\t" if "\t" in first_line else ","


def _read_paste_rows(pasted_text: str) -> tuple[list[str], list[list[str]]]:
    """붙여넣기 원문을 헤더와 데이터 행으로 분리합니다."""

    delimiter = _detect_paste_delimiter(pasted_text)
    reader = csv.reader(StringIO(pasted_text), delimiter=delimiter)
    rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _parse_manual_date(value: str) -> tuple[date | None, str | None]:
    """수동 입력 날짜 값을 검증합니다."""

    if not value:
        return None, "date is required"
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, "date must be YYYY-MM-DD"


def _parse_manual_count(value: str, *, field_name: str) -> tuple[int | None, str | None]:
    """수동 입력 숫자 값을 0 이상의 정수로 검증합니다."""

    if value == "":
        return None, f"{field_name} is required"
    try:
        parsed = int(value.replace(",", ""))
    except ValueError:
        return None, f"{field_name} must be a number"
    if parsed < 0:
        return None, f"{field_name} must be greater than or equal to 0"
    return parsed, None


def _build_manual_row(
    *,
    row_number: int,
    headers: list[str],
    cells: list[str],
) -> dict[str, Any]:
    """붙여넣기 데이터 한 행을 미리보기 row로 변환합니다."""

    values_by_header = {header: cells[index].strip() if index < len(cells) else "" for index, header in enumerate(headers)}
    errors: list[str] = []

    stat_date, date_error = _parse_manual_date(values_by_header.get("date", ""))
    if date_error:
        errors.append(date_error)

    app_name = _normalize_external_usage_app_name(values_by_header.get("app_name", ""))
    if not app_name:
        errors.append("appName is required")

    access_count, access_error = _parse_manual_count(values_by_header.get("access_count", ""), field_name="accessCount")
    if access_error:
        errors.append(access_error)

    unique_user_count, unique_error = _parse_manual_count(
        values_by_header.get("unique_user_count", ""),
        field_name="uniqueUserCount",
    )
    if unique_error:
        errors.append(unique_error)

    if access_count is not None and unique_user_count is not None and unique_user_count > access_count:
        errors.append("uniqueUserCount must be less than or equal to accessCount")

    return {
        "rowNumber": row_number,
        "values": {
            "date": _serialize_date(stat_date),
            "appId": app_name,
            "appName": app_name,
            "accessCount": access_count if access_count is not None else values_by_header.get("access_count", ""),
            "uniqueUserCount": unique_user_count
            if unique_user_count is not None
            else values_by_header.get("unique_user_count", ""),
            "memo": values_by_header.get("memo", "").strip(),
        },
        "errors": errors,
    }


def build_manual_app_access_preview(*, pasted_text: str, source_name: str) -> dict[str, Any]:
    """수동 붙여넣기 원문을 검증 미리보기 payload로 변환합니다.

    입력:
    - pasted_text: 스프레드시트에서 복사한 TSV/CSV 원문
    - source_name: 입력 출처 이름

    반환:
    - dict[str, Any]: summary/rows/errors preview payload

    부작용:
    - 없음

    오류:
    - 없음(검증 실패는 payload errors로 반환)
    """

    raw_headers, raw_rows = _read_paste_rows(pasted_text)
    headers = [_normalize_header(header) for header in raw_headers]
    missing_columns = [
        MANUAL_COLUMN_LABELS.get(column, column)
        for column in REQUIRED_MANUAL_COLUMNS
        if column not in headers
    ]
    top_level_errors = [f"Missing required columns: {', '.join(missing_columns)}"] if missing_columns else []

    preview_rows: list[dict[str, Any]] = []
    if not top_level_errors:
        preview_rows = [
            _build_manual_row(row_number=index + 2, headers=headers, cells=row)
            for index, row in enumerate(raw_rows)
        ]

    error_rows = sum(1 for row in preview_rows if row["errors"])
    valid_rows = len(preview_rows) - error_rows
    if not preview_rows and not top_level_errors:
        top_level_errors.append("No data rows found")

    return {
        "sourceType": MANUAL_SOURCE_TYPE,
        "sourceName": source_name,
        "expectedColumns": MANUAL_PASTE_EXPECTED_COLUMNS,
        "summary": {
            "totalRows": len(preview_rows),
            "validRows": valid_rows,
            "errorRows": error_rows + (1 if top_level_errors else 0),
        },
        "errors": top_level_errors,
        "rows": preview_rows,
    }


def _has_preview_errors(preview: dict[str, Any]) -> bool:
    """미리보기 payload에 저장 차단 오류가 있는지 확인합니다."""

    if preview.get("errors"):
        return True
    return any(row.get("errors") for row in preview.get("rows", []))


def commit_manual_app_access_stats(
    *,
    pasted_text: str,
    source_name: str,
    user: Any,
) -> dict[str, Any]:
    """검증된 수동 외부 앱 접속 집계를 저장합니다.

    입력:
    - pasted_text: 스프레드시트에서 복사한 TSV/CSV 원문
    - source_name: 입력 출처 이름
    - user: 저장 요청 사용자

    반환:
    - dict[str, Any]: 반영 요약과 preview payload

    부작용:
    - ExternalAppAccessDailyStat rows를 생성하거나 갱신합니다.

    오류:
    - ValueError: preview 오류가 있어 저장할 수 없을 때
    """

    preview = build_manual_app_access_preview(pasted_text=pasted_text, source_name=source_name)
    if _has_preview_errors(preview):
        error = ValueError("Manual access stats contain invalid rows")
        error.preview = preview  # type: ignore[attr-defined]
        raise error

    created_count = 0
    updated_count = 0
    now = timezone.now()
    with transaction.atomic():
        for row in preview["rows"]:
            values = row["values"]
            stat, created = ExternalAppAccessDailyStat.objects.update_or_create(
                app_id=values["appId"],
                stat_date=date.fromisoformat(values["date"]),
                source_name=source_name,
                defaults={
                    "app_name": values["appName"],
                    "access_count": values["accessCount"],
                    "unique_user_count": values["uniqueUserCount"],
                    "source_type": MANUAL_SOURCE_TYPE,
                    "memo": values["memo"],
                    "raw_payload": {"rowNumber": row["rowNumber"], "source": "spreadsheet_paste"},
                    "updated_by": user,
                    "updated_at": now,
                },
            )
            if created:
                stat.created_by = user
                stat.created_at = now
                stat.save(update_fields=["created_by", "created_at"])
                created_count += 1
            else:
                updated_count += 1

    return {
        **preview,
        "commit": {
            "createdRows": created_count,
            "updatedRows": updated_count,
        },
    }


def _merge_source_labels(existing: set[str], value: str) -> str:
    """집계 row의 source label을 병합해 단일 표시값을 반환합니다."""

    existing.add(value)
    if len(existing) == 1:
        return next(iter(existing))
    return "mixed"


def _append_app_summary(
    *,
    merged: dict[str, dict[str, Any]],
    app_id: str,
    app_name: str,
    access_count: int,
    unique_user_count: int,
    last_accessed_at: str | None,
    source_type: str,
    source_name: str,
) -> None:
    """앱별 집계 row를 app_id 기준으로 누적합니다."""

    row = merged.setdefault(
        app_id,
        {
            "appId": app_id,
            "appName": app_name,
            "accessCount": 0,
            "uniqueUserCount": 0,
            "avgAccessPerUser": 0,
            "lastAccessedAt": None,
            "sourceType": source_type,
            "sourceName": source_name,
            "_sourceTypes": set(),
            "_sourceNames": set(),
        },
    )
    row["accessCount"] += access_count
    row["uniqueUserCount"] += unique_user_count
    row["sourceType"] = _merge_source_labels(row["_sourceTypes"], source_type)
    row["sourceName"] = _merge_source_labels(row["_sourceNames"], source_name)
    if last_accessed_at and (row["lastAccessedAt"] is None or last_accessed_at > row["lastAccessedAt"]):
        row["lastAccessedAt"] = last_accessed_at


def _finalize_app_summaries(merged: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """누적된 앱별 집계 row를 API 응답 형태로 정리합니다."""

    apps = []
    for row in merged.values():
        access_count = int(row["accessCount"] or 0)
        unique_user_count = int(row["uniqueUserCount"] or 0)
        row["avgAccessPerUser"] = round(access_count / unique_user_count, 1) if unique_user_count else 0
        row.pop("_sourceTypes", None)
        row.pop("_sourceNames", None)
        apps.append(row)
    return sorted(apps, key=lambda item: (-item["accessCount"], item["appName"], item["appId"]))


def _append_series_summary(
    *,
    merged: dict[tuple[str, str], dict[str, Any]],
    bucket_date: str,
    app_id: str,
    app_name: str,
    access_count: int,
    source_type: str,
    source_name: str,
) -> None:
    """날짜/앱별 집계 row를 누적합니다."""

    key = (bucket_date, app_id)
    row = merged.setdefault(
        key,
        {
            "date": bucket_date,
            "appId": app_id,
            "appName": app_name,
            "accessCount": 0,
            "sourceType": source_type,
            "sourceName": source_name,
            "_sourceTypes": set(),
            "_sourceNames": set(),
        },
    )
    row["accessCount"] += access_count
    row["sourceType"] = _merge_source_labels(row["_sourceTypes"], source_type)
    row["sourceName"] = _merge_source_labels(row["_sourceNames"], source_name)


def _finalize_series_summaries(merged: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    """누적된 날짜/앱별 집계 row를 API 응답 형태로 정리합니다."""

    rows = []
    for row in merged.values():
        row.pop("_sourceTypes", None)
        row.pop("_sourceNames", None)
        rows.append(row)
    return sorted(rows, key=lambda item: (item["date"], item["appName"], item["appId"]))


def record_activity_log(
    *,
    user: Any | None,
    action: str,
    path: str,
    method: str,
    status_code: int,
    metadata: dict[str, Any],
) -> ActivityLog:
    """ActivityLog 행을 생성합니다.

    입력:
    - user: 인증 사용자 또는 None
    - action: 요청을 설명하는 액션 이름
    - path: 요청 경로
    - method: HTTP 메서드
    - status_code: 응답 상태 코드
    - metadata: 요청/응답 부가 정보

    반환:
    - ActivityLog: 생성된 활동 로그 인스턴스

    부작용:
    - ActivityLog 테이블에 행을 생성합니다.

    오류:
    - DB 저장 실패 시 Django ORM 예외가 발생할 수 있습니다.
    """

    return ActivityLog.objects.create(
        user=user,
        action=action,
        path=path,
        method=method,
        status_code=status_code,
        metadata=metadata,
    )


def record_app_access(
    *,
    user: Any,
    app_id: str,
    app_name: str,
    path: str,
) -> ActivityLog:
    """앱 화면 진입 이벤트를 ActivityLog에 기록합니다.

    입력:
    - user: 인증 사용자
    - app_id: 앱 식별자
    - app_name: 앱 표시 이름
    - path: 프론트엔드 경로

    반환:
    - ActivityLog: 생성된 앱 접속 이벤트

    부작용:
    - ActivityLog 테이블에 APP_ACCESS 행을 생성합니다.

    오류:
    - DB 저장 실패 시 Django ORM 예외가 발생할 수 있습니다.
    """

    return record_activity_log(
        user=user,
        action=APP_ACCESS_ACTION,
        path=path or f"/app-access/{app_id}",
        method="EVENT",
        status_code=200,
        metadata={
            "event_type": "app_access",
            "app_id": app_id,
            "app_name": app_name,
            "knox_id": getattr(user, "knox_id", "") or "",
        },
    )


def get_recent_activity_payload(*, limit: int) -> list[dict[str, Any]]:
    """최근 ActivityLog 목록을 직렬화해 반환합니다.

    입력:
    - limit: 최대 반환 개수

    반환:
    - list[dict[str, Any]]: 직렬화된 activity log 리스트

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    logs = get_recent_activity_logs(limit=limit)
    return [serialize_activity_log(entry) for entry in logs]


def get_app_access_stats_payload(
    *,
    from_value: str | None,
    to_value: str | None,
    app_id: str | None = None,
    period_value: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """앱별 접속 통계 payload를 생성합니다.

    입력:
    - from_value/to_value: KST 기준 YYYY-MM-DD 쿼리 문자열
    - app_id: 특정 앱 id 필터(선택)
    - period_value: chart series 집계 단위(day/week/month)
    - now: 테스트용 현재 시각(선택)

    반환:
    - dict[str, Any]: 대시보드 API 응답 payload

    부작용:
    - 없음(읽기 전용)

    오류:
    - ValueError: 날짜 형식/범위가 유효하지 않을 때
    """

    clean_app_id = app_id.strip() if isinstance(app_id, str) and app_id.strip() else None
    external_app_id = _normalize_external_usage_app_name(clean_app_id) if clean_app_id else None
    period = _resolve_stats_period(period_value)
    from_date, to_date, start_at, end_at = _resolve_stats_range(
        from_value=from_value,
        to_value=to_value,
        now=now,
    )
    app_rows = summarize_app_access_by_app(start_at=start_at, end_at=end_at, app_id=clean_app_id)
    external_app_rows = summarize_external_app_access_by_app(
        start_date=from_date,
        end_date=to_date,
        app_id=external_app_id,
    )
    series_rows = summarize_app_access_by_date(start_at=start_at, end_at=end_at, app_id=clean_app_id)
    external_series_rows = summarize_external_app_access_by_date(
        start_date=from_date,
        end_date=to_date,
        app_id=external_app_id,
    )
    totals = summarize_app_access_totals(start_at=start_at, end_at=end_at, app_id=clean_app_id)
    external_totals = summarize_external_app_access_totals(
        start_date=from_date,
        end_date=to_date,
        app_id=external_app_id,
    )
    merged_apps: dict[str, dict[str, Any]] = {}
    for row in app_rows:
        app_key = _safe_text(row.get("metadata__app_id"), "unknown")
        app_name = _safe_text(row.get("metadata__app_name"), app_key)
        access_count = int(row.get("access_count") or 0)
        unique_user_count = int(row.get("unique_user_count") or 0)
        _append_app_summary(
            merged=merged_apps,
            app_id=app_key,
            app_name=app_name,
            access_count=access_count,
            unique_user_count=unique_user_count,
            last_accessed_at=_serialize_datetime(row.get("last_accessed_at")),
            source_type="internal",
            source_name="portal",
        )

    for row in external_app_rows:
        app_key = _safe_text(row.get("app_id"), "unknown")
        app_name = _safe_text(row.get("app_name"), app_key)
        _append_app_summary(
            merged=merged_apps,
            app_id=app_key,
            app_name=app_name,
            access_count=int(row.get("access_count") or 0),
            unique_user_count=int(row.get("unique_user_count") or 0),
            last_accessed_at=_serialize_kst_date_end(row.get("last_stat_date")),
            source_type=_safe_text(row.get("source_type"), MANUAL_SOURCE_TYPE),
            source_name=_safe_text(row.get("source_name"), MANUAL_SOURCE_TYPE),
        )

    apps = _finalize_app_summaries(merged_apps)

    merged_series: dict[tuple[str, str], dict[str, Any]] = {}
    for row in series_rows:
        app_key = _safe_text(row.get("metadata__app_id"), "unknown")
        local_date = row.get("local_date")
        bucket_date = _get_period_start(local_date, period=period) if isinstance(local_date, date) else None
        _append_series_summary(
            merged=merged_series,
            bucket_date=_serialize_date(bucket_date),
            app_id=app_key,
            app_name=_safe_text(row.get("metadata__app_name"), app_key),
            access_count=int(row.get("access_count") or 0),
            source_type="internal",
            source_name="portal",
        )

    for row in external_series_rows:
        app_key = _safe_text(row.get("app_id"), "unknown")
        stat_date = row.get("stat_date")
        bucket_date = _get_period_start(stat_date, period=period) if isinstance(stat_date, date) else None
        _append_series_summary(
            merged=merged_series,
            bucket_date=_serialize_date(bucket_date),
            app_id=app_key,
            app_name=_safe_text(row.get("app_name"), app_key),
            access_count=int(row.get("access_count") or 0),
            source_type=_safe_text(row.get("source_type"), MANUAL_SOURCE_TYPE),
            source_name=_safe_text(row.get("source_name"), MANUAL_SOURCE_TYPE),
        )

    series = _finalize_series_summaries(merged_series)

    top_app = apps[0] if apps else None
    sync_state = get_external_app_usage_sync_state(sync_key=EXTERNAL_USAGE_SYNC_KEY)

    return {
        "timezone": "Asia/Seoul",
        "period": period,
        "range": {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        },
        "summary": {
            "totalAccessCount": totals["access_count"] + external_totals["access_count"],
            "uniqueUserCount": totals["unique_user_count"] + external_totals["unique_user_count"],
            "activeAppCount": len(apps),
            "topApp": top_app,
        },
        "externalUsage": _serialize_external_usage_sync_state(sync_state),
        "apps": apps,
        "series": series,
    }
