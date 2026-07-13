# =============================================================================
# 모듈: L3 Spider line name 규칙 매핑
# 주요 기능: DB 규칙으로 (line_id, process_id, step_seq) → line_name 해석
# 불변 조건: override → base, exact → wildcard, priority 순서를 유지합니다.
# =============================================================================
from __future__ import annotations

import fnmatch
import threading
import time

from api.l3_spider import selectors


_CACHE_TTL_SECONDS = 5.0
_lock = threading.Lock()
_cache: dict[str, object] = {"expires_at": 0.0, "rules": None}


def _match(value: object, pattern: object) -> bool:
    """빈 값·`%`·`*` wildcard를 포함해 대소문자 없이 규칙을 비교합니다."""

    normalized_pattern = str(pattern or "").strip()
    if normalized_pattern in ("", "%", "*"):
        return True
    return fnmatch.fnmatch(
        str(value).strip().casefold(),
        normalized_pattern.replace("%", "*").casefold(),
    )


def _has_wild(*values: object) -> bool:
    """하나 이상의 값에 wildcard가 포함됐는지 반환합니다."""

    for value in values:
        text = str(value or "").strip()
        if text == "" or "%" in text or "*" in text:
            return True
    return False


def _empty_rules() -> dict[str, object]:
    """조회 가능한 규칙이 없을 때 사용할 빈 lookup 구조를 반환합니다."""

    return {
        "override_exact": {},
        "override_wild": [],
        "base_exact": {},
        "base_wild": [],
        "memo": {},
    }


def _compile_rules(rows: list[dict[str, object]]) -> dict[str, object]:
    """DB 행을 기존 exact/wildcard 우선순위 lookup 구조로 변환합니다."""

    rules = _empty_rules()
    for row in rows:
        line_id = str(row.get("line_id") or "").strip()
        process_id = str(row.get("process_id") or "").strip()
        step_seq = str(row.get("step_seq") or "").strip()
        line_name = str(row.get("line_name") or "").strip()
        if not line_name:
            continue

        rule_type = str(row.get("rule_type") or "").strip().casefold()
        if rule_type == "override":
            if _has_wild(process_id, step_seq):
                rules["override_wild"].append((process_id, step_seq, line_name))
            else:
                rules["override_exact"].setdefault(
                    (process_id.casefold(), step_seq.casefold()),
                    line_name,
                )
        elif rule_type == "base":
            if _has_wild(line_id, process_id):
                rules["base_wild"].append((line_id, process_id, line_name))
            else:
                rules["base_exact"].setdefault(
                    (line_id.casefold(), process_id.casefold()),
                    line_name,
                )
    return rules


def clear_cache() -> None:
    """현재 프로세스의 규칙 snapshot과 조합별 memo를 즉시 비웁니다."""

    with _lock:
        _cache["expires_at"] = 0.0
        _cache["rules"] = None


def _get_rules() -> dict[str, object]:
    """활성 DB 규칙을 짧은 TTL snapshot으로 읽어 반환합니다."""

    now = time.monotonic()
    cached_rules = _cache["rules"]
    if cached_rules is not None and now < float(_cache["expires_at"]):
        return cached_rules

    with _lock:
        cached_rules = _cache["rules"]
        if cached_rules is not None and now < float(_cache["expires_at"]):
            return cached_rules
        rules = _compile_rules(selectors.list_active_line_name_rules())
        _cache["rules"] = rules
        _cache["expires_at"] = now + _CACHE_TTL_SECONDS
        return rules


def _resolve_uncached(
    rules: dict[str, object],
    line_id: object,
    process_id: object,
    step_seq: object,
) -> tuple[str, bool]:
    """규칙 우선순위에 따라 line name과 명시 매칭 여부를 반환합니다."""

    process_key = str(process_id).strip().casefold()
    step_key = str(step_seq).strip().casefold()
    line_key = str(line_id).strip().casefold()

    hit = rules["override_exact"].get((process_key, step_key))
    if hit is not None:
        return hit, True
    for process_pattern, step_pattern, name in rules["override_wild"]:
        if _match(process_id, process_pattern) and _match(step_seq, step_pattern):
            return name, True

    hit = rules["base_exact"].get((line_key, process_key))
    if hit is not None:
        return hit, True
    for line_pattern, process_pattern, name in rules["base_wild"]:
        if _match(line_id, line_pattern) and _match(process_id, process_pattern):
            return name, True
    return str(line_id), False


def resolve_line_name_mapping(
    line_id: object,
    process_id: object,
    step_seq: object,
) -> tuple[str, bool]:
    """line name과 DB 규칙 명시 매칭 여부를 함께 반환합니다."""

    rules = _get_rules()
    memo = rules["memo"]
    key = (str(line_id), str(process_id), str(step_seq))
    cached = memo.get(key)
    if cached is not None:
        return cached
    result = _resolve_uncached(rules, line_id, process_id, step_seq)
    memo[key] = result
    return result


def resolve_line_name(line_id: object, process_id: object, step_seq: object) -> str:
    """DB 규칙으로 line name을 반환하고 미매칭 시 원본 line id를 사용합니다."""

    line_name, _is_mapped = resolve_line_name_mapping(line_id, process_id, step_seq)
    return line_name


def get_configured_line_names() -> list[str]:
    """활성 DB 규칙의 line name 고유 목록을 반환합니다."""

    return selectors.list_configured_line_names()
