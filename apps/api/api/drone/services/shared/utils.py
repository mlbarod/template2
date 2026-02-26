# =============================================================================
# 모듈: 드론 공통 유틸
# 주요 함수: _advisory_lock, _lock_key, _parse_bool, _truncate_text
# 주요 가정: PostgreSQL 환경에서 advisory lock을 사용합니다.
# =============================================================================
from __future__ import annotations

import logging
import zlib
from contextlib import contextmanager
from typing import Any, Iterator

from django.db import connection

logger = logging.getLogger(__name__)


def _lock_key(name: str) -> int:
    """문자열을 advisory lock용 정수 키로 변환합니다.

    인자:
        name: 락 이름 문자열.

    반환:
        CRC32 기반 정수 키.

    부작용:
        없음. 순수 계산입니다.
    """

    return int(zlib.crc32(name.encode("utf-8")))


def _try_advisory_lock(lock_id: int) -> bool:
    """PostgreSQL advisory lock 획득을 시도합니다.

    인자:
        lock_id: advisory lock ID(어드바이저리 락 ID).

    반환:
        획득 성공 여부(boolean).

    부작용:
        DB 커서 실행이 발생합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) PostgreSQL 여부 확인
    # -----------------------------------------------------------------------------
    if connection.vendor != "postgresql":
        return True

    # -----------------------------------------------------------------------------
    # 2) advisory lock 시도
    # -----------------------------------------------------------------------------
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
        row = cursor.fetchone()
    return bool(row and row[0])


def _release_advisory_lock(lock_id: int) -> None:
    """PostgreSQL advisory lock을 해제합니다.

    인자:
        lock_id: advisory lock ID(어드바이저리 락 ID).

    부작용:
        DB 커서 실행이 발생합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) PostgreSQL 여부 확인
    # -----------------------------------------------------------------------------
    if connection.vendor != "postgresql":
        return

    # -----------------------------------------------------------------------------
    # 2) advisory lock 해제 시도
    # -----------------------------------------------------------------------------
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
    except Exception:
        logger.exception("Failed to release advisory lock id=%s", lock_id)


@contextmanager
def _advisory_lock(name: str) -> Iterator[bool]:
    """어드바이저리 락 획득/해제를 묶는 컨텍스트 매니저입니다.

    인자:
        name: 락 이름 문자열.

    반환:
        획득 성공 여부(boolean)를 yield 합니다.

    부작용:
        DB 커서 실행이 발생합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 락 획득
    # -----------------------------------------------------------------------------
    lock_id = _lock_key(name)
    acquired = _try_advisory_lock(lock_id)
    try:
        yield acquired
    finally:
        # -------------------------------------------------------------------------
        # 2) 락 해제
        # -------------------------------------------------------------------------
        if acquired:
            _release_advisory_lock(lock_id)


def _parse_bool(value: Any, default: bool = False) -> bool:
    """값을 boolean으로 파싱합니다.

    인자:
        value: 원본 값.
        default: 파싱 실패 시 기본값.

    반환:
        boolean 값.

    부작용:
        없음. 순수 파싱입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) None/불리언 처리
    # -----------------------------------------------------------------------------
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    # -----------------------------------------------------------------------------
    # 2) 숫자/문자열 처리
    # -----------------------------------------------------------------------------
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _parse_int(value: Any, default: int) -> int:
    """값을 정수로 파싱합니다.

    인자:
        value: 원본 값.
        default: 파싱 실패 시 기본값.

    반환:
        정수 값.

    부작용:
        없음. 순수 파싱입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 정수 변환 시도
    # -----------------------------------------------------------------------------
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed


def _truncate_text(value: str, max_len: int) -> str:
    """문자열을 최대 길이로 자릅니다.

    인자:
        value: 원본 문자열.
        max_len: 최대 길이.

    반환:
        제한 길이를 적용한 문자열.

    부작용:
        없음. 순수 문자열 처리입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 길이 제한 적용
    # -----------------------------------------------------------------------------
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return value[:max_len]
    return value[: max_len - 3] + "..."


def _first_defined(*values: Any) -> Any:
    """None이 아닌 첫 번째 값을 반환합니다.

    인자:
        values: 후보 값들.

    반환:
        None이 아닌 첫 번째 값 또는 None.

    부작용:
        없음. 순수 유틸입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 순서대로 값 확인
    # -----------------------------------------------------------------------------
    for value in values:
        if value is not None:
            return value
    return None
