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


def enrich_rows_with_ctttm_urls(*, rows: Sequence[dict[str, Any]], config: DroneCtttmConfig) -> None:
    """rows에 CTTTM URL 정보를 보강합니다.

    인자:
        rows: Drone SOP row 목록.
        config: CTTTM 설정.

    부작용:
        rows dict에 "url" 필드를 추가할 수 있습니다.
    """

    if not rows:
        return
    if not config.table_name or not config.base_url:
        return

    sop_ids: list[int] = []
    for row in rows:
        rid = row.get("id")
        if isinstance(rid, int) and rid > 0:
            sop_ids.append(rid)
    if not sop_ids:
        return

    try:
        workorders_by_id = selectors.load_drone_sop_ctttm_workorders_map(
            sop_ids=sop_ids,
            ctttm_table=config.table_name,
        )
    except Exception:
        logger.exception("Failed to load CTTTM workorders (table=%r)", config.table_name)
        return

    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int) or rid <= 0:
            continue
        entries = workorders_by_id.get(rid) or []
        url_entries: list[dict[str, str]] = []
        for entry in entries:
            eqp_id = str(entry.get("eqp_id") or "").strip()
            workorder_id = str(entry.get("workorder_id") or "").strip()
            line_id = str(entry.get("line_id") or "").strip()
            if not eqp_id or not workorder_id or not line_id:
                continue
            url_entries.append(
                {
                    "eqp_id": eqp_id,
                    "url": build_ctttm_url(base_url=config.base_url, workorder_id=workorder_id, line_id=line_id),
                }
            )
        if url_entries:
            row["url"] = url_entries


__all__ = [
    "build_ctttm_url",
    "enrich_rows_with_ctttm_urls",
]
