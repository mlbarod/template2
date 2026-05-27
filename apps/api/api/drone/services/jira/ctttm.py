"""Drone SOP CTTTM URL 보강 helper."""

from __future__ import annotations

import logging
from typing import Any, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from ... import selectors
from .config import DroneCtttmConfig

logger = logging.getLogger(__name__)


def build_ctttm_url(*, base_url: str, workorder_id: str, line_id: str) -> str:
    """CTTTM URL을 구성합니다.

    인자:
        base_url: 기본 URL.
        workorder_id: 작업 지시 ID.
        line_id: 라인 ID.

    반환:
        쿼리 파라미터가 반영된 URL 문자열.

    부작용:
        없음. 순수 문자열 구성입니다.
    """

    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"wono": workorder_id, "lineId": line_id})
    return urlunparse(parsed._replace(query=urlencode(query)))


def _build_eqp_candidates_from_row(row: dict[str, Any]) -> list[str]:
    """Drone SOP row에서 CTTTM eqp_id 후보를 생성합니다."""

    eqp_id = str(row.get("eqp_id") or "").strip()
    chamber_ids = str(row.get("chamber_ids") or "").replace(",", "").strip()
    if not eqp_id or not chamber_ids:
        return []

    candidates: list[str] = []
    seen: set[str] = set()
    for chamber_id in chamber_ids:
        candidate = f"{eqp_id}-{chamber_id}"
        if candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates


def _build_url_entries_from_workorders(
    *,
    eqp_candidates: Sequence[str],
    workorders_by_eqp_id: dict[str, dict[str, str]],
    base_url: str,
) -> list[dict[str, str]]:
    """CTTTM workorder 조회 결과를 URL entry 목록으로 변환합니다."""

    entries: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for eqp_id in eqp_candidates:
        entry = workorders_by_eqp_id.get(eqp_id)
        if not entry:
            continue
        workorder_id = str(entry.get("workorder_id") or "").strip()
        line_id = str(entry.get("line_id") or "").strip()
        if not workorder_id or not line_id:
            continue
        url = build_ctttm_url(base_url=base_url, workorder_id=workorder_id, line_id=line_id)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        entries.append({"eqp_id": eqp_id, "url": url})
    return entries


def enrich_rows_with_ctttm_urls(*, rows: Sequence[dict[str, Any]], config: DroneCtttmConfig) -> None:
    """rows에 CTTTM URL 정보를 보강합니다.

    인자:
        rows: Drone SOP row 목록.
        config: CTTTM 설정.

    부작용:
        rows dict에 "ctttm_urls" 필드를 추가할 수 있습니다.
    """

    if not rows:
        return
    if not config.table_name or not config.base_url:
        return

    rows_missing_urls: list[tuple[dict[str, Any], list[str]]] = []
    eqp_candidates: list[str] = []
    for row in rows:
        if row.get("ctttm_urls"):
            continue

        row_eqp_candidates = _build_eqp_candidates_from_row(row)
        if not row_eqp_candidates:
            continue
        rows_missing_urls.append((row, row_eqp_candidates))
        eqp_candidates.extend(row_eqp_candidates)

    if not eqp_candidates:
        return

    try:
        workorders_by_eqp_id = selectors.load_drone_sop_ctttm_latest_workorders_by_eqp_ids(
            eqp_ids=eqp_candidates,
            ctttm_table=config.table_name,
        )
    except Exception:
        logger.exception("Failed to load CTTTM workorders (table=%r)", config.table_name)
        return

    for row, row_eqp_candidates in rows_missing_urls:
        url_entries = _build_url_entries_from_workorders(
            eqp_candidates=row_eqp_candidates,
            workorders_by_eqp_id=workorders_by_eqp_id,
            base_url=config.base_url,
        )
        if url_entries:
            row["ctttm_urls"] = url_entries


__all__ = [
    "build_ctttm_url",
    "enrich_rows_with_ctttm_urls",
]
