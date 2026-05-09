"""Drone SOP POP3 needtosend 계산 helper."""

from __future__ import annotations

from typing import Any

from ... import selectors
from .config import NeedToSendRule


def normalize_user_sdwt_lookup_key(value: Any) -> str | None:
    """대소문자 비구분 비교용 user_sdwt_prod 키를 정규화합니다."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned.casefold()


def get_needtosend_rule_for_target(
    *,
    target_user_sdwt_prod: str,
    cache: dict[str, NeedToSendRule | None],
) -> NeedToSendRule | None:
    """target_user_sdwt_prod 기준 needtosend 룰을 조회/캐시합니다.

    인자:
        target_user_sdwt_prod: 해석된 대상 소속 값.
        cache: 규칙 캐시(dict).

    반환:
        NeedToSendRule 또는 None.

    부작용:
        첫 조회 시 DB 읽기가 발생할 수 있습니다.
    """

    # -------------------------------------------------------------------------
    # 1) 캐시 키 정규화 및 조회
    # -------------------------------------------------------------------------
    lookup_key = normalize_user_sdwt_lookup_key(target_user_sdwt_prod)
    if not lookup_key:
        return None

    cached = cache.get(lookup_key)
    if cached is not None or lookup_key in cache:
        return cached

    # -------------------------------------------------------------------------
    # 2) DB 규칙 조회 후 캐시 적재
    # -------------------------------------------------------------------------
    rule_model = selectors.get_drone_sop_needtosend_rule_by_target(
        target_user_sdwt_prod=target_user_sdwt_prod,
    )
    if not rule_model:
        cache[lookup_key] = None
        return None

    rule = NeedToSendRule(
        comment_last_at=str(rule_model.needtosend_comment_last_at or "").strip(),
        ignore_sample_type=bool(rule_model.needtosend_ignore_sample_type),
    )
    cache[lookup_key] = rule
    return rule


def compute_needtosend_by_target(
    *,
    row: dict[str, Any],
    target_user_sdwt_prod: str | None,
    rule_cache: dict[str, NeedToSendRule | None],
) -> int:
    """target_user_sdwt_prod 기준으로 needtosend 값을 계산합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).
        target_user_sdwt_prod: 매핑된 대상 소속(없으면 None).
        rule_cache: 규칙 캐시(dict).

    반환:
        needtosend 값(0/1).

    부작용:
        규칙 캐시 miss 시 DB 읽기가 발생할 수 있습니다.
    """

    # -------------------------------------------------------------------------
    # 1) 매핑 없음 → 발송 차단
    # -------------------------------------------------------------------------
    if not isinstance(target_user_sdwt_prod, str):
        return 0
    normalized = target_user_sdwt_prod.strip()
    if not normalized:
        return 0

    # -------------------------------------------------------------------------
    # 2) 활성 DB 규칙 적용 (없으면 발송 차단)
    # -------------------------------------------------------------------------
    rule = get_needtosend_rule_for_target(target_user_sdwt_prod=normalized, cache=rule_cache)
    if rule:
        return rule.compute(row)
    return 0


__all__ = [
    "compute_needtosend_by_target",
    "normalize_user_sdwt_lookup_key",
]
