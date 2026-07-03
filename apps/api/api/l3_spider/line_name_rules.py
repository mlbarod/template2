# =============================================================================
# 모듈: L3 Spider line_name 규칙 매핑
# (line_id, process_id, step_seq) → line_name 을 규칙표로 해석합니다.
# 규칙표는 코드/깃이 아니라 데이터 루트의 _meta/line_name_rules.csv 에서 읽습니다
# (민감값 분리). 파일 mtime이 바뀌면 자동 재로딩되며(재시작 불필요), 파일이 없거나
# 파싱 실패 시 빈 규칙 → 모든 값이 line_id 로 폴백됩니다.
#
# 성능: 정확(와일드카드 없는) 규칙은 dict 로 O(1) 조회, 와일드카드 규칙만 순서 리스트로
#       평가하고, (line_id, process_id, step_seq) 결과를 메모이즈합니다.
#       → 규칙이 수만 줄이어도 조회는 사실상 상수 시간.
#   우선순위: type=override 가 base 보다 먼저. 같은 type 안에서는 '정확 매칭'이
#            '와일드카드'보다 우선(= 구체적 규칙 우선), 와일드카드끼리는 파일 순서.
#
# CSV 형식:
#   type,line_id,process_id,step_seq,line_name
#     - type=override : (process_id, step_seq) 매칭(line_id 무관), base 보다 우선
#     - type=base     : (line_id, process_id) 매칭(step_seq 무관)
#     - 빈 칸 또는 % / * = 와일드카드, 대소문자 무시
#     - '#' 로 시작하는 줄과 빈 줄은 무시
# =============================================================================
from __future__ import annotations

import csv
import fnmatch
import logging
import os
import threading
from pathlib import Path

from . import selectors

logger = logging.getLogger(__name__)

_RULES_FILENAME = "line_name_rules.csv"
_lock = threading.Lock()
_cache: dict = {"mtime": None, "rules": None}


def rules_path() -> Path:
    """규칙 CSV 경로: {데이터 루트}/_meta/line_name_rules.csv"""
    return selectors.get_data_root() / "_meta" / _RULES_FILENAME


def _match(value: object, pattern: object) -> bool:
    """와일드카드 매칭: 빈 값/%/* = 모두 매칭, 그 외 fnmatch(%→*), 대소문자 무시."""
    pat = str(pattern or "").strip()
    if pat in ("", "%", "*"):
        return True
    return fnmatch.fnmatch(str(value).strip().lower(), pat.replace("%", "*").lower())


def _has_wild(*values: object) -> bool:
    """빈 값(=모두 매칭) 또는 % / * 가 있으면 와일드카드 규칙."""
    for value in values:
        text = str(value or "").strip()
        if text == "" or "%" in text or "*" in text:
            return True
    return False


def _empty_rules() -> dict:
    return {
        "override_exact": {},  # (process_id_lower, step_seq_lower) → line_name
        "override_wild": [],   # [(process_pat, step_pat, line_name)] 파일 순서
        "base_exact": {},      # (line_id_lower, process_id_lower) → line_name
        "base_wild": [],       # [(line_id_pat, process_pat, line_name)] 파일 순서
        "memo": {},            # (line_id, process_id, step_seq) → line_name 캐시
    }


def _load(path: Path) -> dict:
    rules = _empty_rules()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        lines = [ln for ln in fh if ln.strip() and not ln.lstrip().startswith("#")]
    for row in csv.DictReader(lines):
        line_id = str(row.get("line_id") or "").strip()
        process_id = str(row.get("process_id") or "").strip()
        step_seq = str(row.get("step_seq") or "").strip()
        line_name = str(row.get("line_name") or "").strip()
        if not line_name:
            continue
        rtype = str(row.get("type") or "").strip().lower()
        if rtype == "override":
            if _has_wild(process_id, step_seq):
                rules["override_wild"].append((process_id, step_seq, line_name))
            else:  # 정확 규칙: 첫 등장 우선
                rules["override_exact"].setdefault((process_id.lower(), step_seq.lower()), line_name)
        elif rtype == "base":
            if _has_wild(line_id, process_id):
                rules["base_wild"].append((line_id, process_id, line_name))
            else:
                rules["base_exact"].setdefault((line_id.lower(), process_id.lower()), line_name)
    return rules


def _get_rules() -> dict:
    """규칙을 반환(파일 mtime 변경 시 자동 재로딩). 파일 없으면 빈 규칙."""
    path = rules_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return _empty_rules()
    with _lock:
        if _cache["mtime"] != mtime or _cache["rules"] is None:
            try:
                _cache["rules"] = _load(path)  # memo 도 새로 비워짐
                _cache["mtime"] = mtime
            except Exception as exc:  # 파싱 실패 → 직전 캐시 유지(없으면 빈 규칙)
                logger.warning("L3Spider line_name_rules 로드 실패(%s): %s", path, exc)
                if _cache["rules"] is None:
                    return _empty_rules()
        return _cache["rules"]


def _resolve_uncached(rules: dict, line_id: object, process_id: object, step_seq: object) -> str:
    p_lower = str(process_id).strip().lower()
    s_lower = str(step_seq).strip().lower()
    l_lower = str(line_id).strip().lower()
    # 1) override: 정확(O(1)) → 없으면 와일드카드(파일 순서)
    hit = rules["override_exact"].get((p_lower, s_lower))
    if hit is not None:
        return hit
    for p_pat, s_pat, name in rules["override_wild"]:
        if _match(process_id, p_pat) and _match(step_seq, s_pat):
            return name
    # 2) base: 정확(O(1)) → 없으면 와일드카드
    hit = rules["base_exact"].get((l_lower, p_lower))
    if hit is not None:
        return hit
    for l_pat, p_pat, name in rules["base_wild"]:
        if _match(line_id, l_pat) and _match(process_id, p_pat):
            return name
    # 3) 폴백
    return str(line_id)


def resolve_line_name(line_id: object, process_id: object, step_seq: object) -> str:
    """(line_id, process_id, step_seq) → line_name. 규칙 미매칭 시 line_id 로 폴백."""
    rules = _get_rules()
    memo = rules["memo"]
    key = (str(line_id), str(process_id), str(step_seq))
    cached = memo.get(key)
    if cached is not None:
        return cached
    result = _resolve_uncached(rules, line_id, process_id, step_seq)
    memo[key] = result
    return result
