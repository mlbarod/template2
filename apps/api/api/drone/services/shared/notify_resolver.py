# =============================================================================
# 모듈: Drone SOP 사용자 소속 매핑 해석
# 주요 기능: sdwt_prod/user_sdwt_prod 조합을 target_user_sdwt_prod로 해석
# 주요 가정: 매핑 규칙은 selectors에서 읽어오며, 매핑이 없으면 실패 처리합니다.
# =============================================================================
"""Drone SOP 대상 소속 해석 유틸리티."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ... import selectors


def _normalize_user_sdwt_value(value: Any) -> str | None:
    """소속 값을 정규화합니다.

    인자:
        value: 원본 값.

    반환:
        정규화된 문자열 또는 None.

    부작용:
        없음. 순수 정규화입니다.
    """

    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed if trimmed else None
    trimmed = str(value).strip()
    return trimmed if trimmed else None


@dataclass(frozen=True)
class UserSdwtProdMapIndex:
    """사용자 소속 매핑 인덱스."""

    pair_map: dict[tuple[str, str], str]
    sdwt_only_map: dict[str, str]
    user_only_map: dict[str, str]


def load_user_sdwt_prod_map_index() -> UserSdwtProdMapIndex:
    """매핑 규칙을 인덱스로 로딩합니다.

    반환:
        UserSdwtProdMapIndex 인스턴스.

    부작용:
        selectors에서 DB 조회가 발생합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 매핑 규칙 로딩
    # -----------------------------------------------------------------------------
    rows = selectors.list_drone_sop_user_sdwt_maps()
    pair_map: dict[tuple[str, str], str] = {}
    sdwt_only_map: dict[str, str] = {}
    user_only_map: dict[str, str] = {}

    # -----------------------------------------------------------------------------
    # 2) 규칙 정규화 및 인덱싱
    # -----------------------------------------------------------------------------
    for row in rows:
        sdwt = _normalize_user_sdwt_value(row.get("sdwt_prod"))
        user = _normalize_user_sdwt_value(row.get("user_sdwt_prod"))
        target = _normalize_user_sdwt_value(row.get("target_user_sdwt_prod"))
        if not target:
            continue
        if sdwt and user:
            pair_map[(sdwt, user)] = target
        elif sdwt and not user:
            sdwt_only_map[sdwt] = target
        elif user and not sdwt:
            user_only_map[user] = target

    return UserSdwtProdMapIndex(
        pair_map=pair_map,
        sdwt_only_map=sdwt_only_map,
        user_only_map=user_only_map,
    )


def resolve_target_user_sdwt_prod(
    *,
    row: dict[str, Any],
    index: UserSdwtProdMapIndex,
) -> str | None:
    """단일 row에 대한 target_user_sdwt_prod를 해석합니다.

    인자:
        row: Drone SOP 행 dict.
        index: 매핑 인덱스.

    반환:
        매핑된 target_user_sdwt_prod 또는 None(매핑 없음).

    부작용:
        없음. 순수 해석입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    sdwt = _normalize_user_sdwt_value(row.get("sdwt_prod"))
    user = _normalize_user_sdwt_value(row.get("user_sdwt_prod"))

    # -----------------------------------------------------------------------------
    # 2) 우선순위 매칭
    # -----------------------------------------------------------------------------
    if sdwt and user:
        target = index.pair_map.get((sdwt, user))
        if target:
            return target
    if sdwt:
        target = index.sdwt_only_map.get(sdwt)
        if target:
            return target
    if user:
        target = index.user_only_map.get(user)
        if target:
            return target

    # -----------------------------------------------------------------------------
    # 3) 매핑 없음
    # -----------------------------------------------------------------------------
    return None


def annotate_target_user_sdwt_prod(
    *,
    rows: list[dict[str, Any]],
    index: UserSdwtProdMapIndex,
) -> None:
    """row 목록에 target_user_sdwt_prod 값을 주입합니다.

    인자:
        rows: Drone SOP 행 dict 목록.
        index: 매핑 인덱스.

    반환:
        없음.

    부작용:
        row dict에 target_user_sdwt_prod 키가 추가됩니다.
    """

    for row in rows:
        row["target_user_sdwt_prod"] = resolve_target_user_sdwt_prod(row=row, index=index)


def resolve_target_user_sdwt_prod_values(
    *,
    rows: list[dict[str, Any]],
    index: UserSdwtProdMapIndex | None = None,
) -> tuple[set[str], list[int]]:
    """row 목록을 해석하고 target_user_sdwt_prod 목록을 반환합니다.

    인자:
        rows: Drone SOP 행 dict 목록.
        index: 매핑 인덱스(옵션).

    반환:
        (target_user_sdwt_prod 집합, target 누락 row id 리스트) 튜플.

    부작용:
        row dict에 target_user_sdwt_prod 키가 추가됩니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 매핑 인덱스 준비
    # -----------------------------------------------------------------------------
    if index is None:
        index = load_user_sdwt_prod_map_index()

    # -----------------------------------------------------------------------------
    # 2) row별 target 해석 및 누락 집계
    # -----------------------------------------------------------------------------
    targets: set[str] = set()
    missing_ids: list[int] = []
    for row in rows:
        target = resolve_target_user_sdwt_prod(row=row, index=index)
        row["target_user_sdwt_prod"] = target

        if isinstance(target, str) and target.strip():
            targets.add(target.strip())
            continue

        row_id = row.get("id")
        if isinstance(row_id, int):
            missing_ids.append(row_id)

    return targets, missing_ids
