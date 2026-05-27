# =============================================================================
# 모듈: Drone SOP POP3 persistence
# 주요 기능: DroneSOP upsert, delivery snapshot 생성, 오래된 행 정리
# 주요 가정: POP3 수집 orchestration은 이 모듈을 통해서만 DB 쓰기를 수행합니다.
# =============================================================================
"""Drone SOP POP3 persistence 헬퍼 모듈입니다."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Sequence

from django.db import connection, transaction
from django.utils import timezone

from ...models import DroneSOP, build_sop_key
from ..shared.delivery_state import ensure_channel_delivery_snapshots_for_rows
from ..shared.notify_resolver import (
    UserSdwtProdMapIndex,
    load_user_sdwt_prod_map_index,
    resolve_target_user_sdwt_prods,
)

logger = logging.getLogger(__name__)


def _ensure_snapshots_for_upserted_rows(*, source_by_sop_key: dict[str, dict[str, Any]]) -> None:
    """upsert 완료된 SOP에 delivery snapshot을 생성합니다."""

    if not source_by_sop_key:
        return

    db_rows = DroneSOP.objects.filter(sop_key__in=list(source_by_sop_key.keys())).values(
        "id",
        "sop_key",
        "sdwt_prod",
        "user_sdwt_prod",
        "target_user_sdwt_prod",
        "status",
        "needtosend",
        "instant_inform",
    )
    snapshot_rows: list[dict[str, Any]] = []
    for db_row in db_rows:
        sop_key = str(db_row.get("sop_key") or "").strip()
        source_row = source_by_sop_key.get(sop_key) or {}
        snapshot_row = dict(db_row)
        if isinstance(source_row.get("target_user_sdwt_prods"), list):
            snapshot_row["target_user_sdwt_prods"] = source_row["target_user_sdwt_prods"]
        elif source_row.get("target_user_sdwt_prod") is not None:
            snapshot_row["target_user_sdwt_prod"] = source_row.get("target_user_sdwt_prod")
        snapshot_rows.append(snapshot_row)

    ensure_channel_delivery_snapshots_for_rows(rows=snapshot_rows)


def upsert_drone_sop_rows(*, rows: Sequence[dict[str, Any]]) -> int:
    """Drone SOP row를 upsert 합니다.

    인자:
        rows: Drone SOP row dict 목록.

    반환:
        처리한 row 개수.

    부작용:
        DB에 INSERT/UPDATE가 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 입력 확인
    # -------------------------------------------------------------------------
    if not rows:
        return 0

    # -------------------------------------------------------------------------
    # 2) SQL 구성
    # -------------------------------------------------------------------------
    insert_cols = [
        "sop_key",
        "line_id",
        "sdwt_prod",
        "sample_type",
        "sample_group",
        "eqp_id",
        "chamber_ids",
        "lot_id",
        "proc_id",
        "ppid",
        "main_step",
        "metro_current_step",
        "metro_steps",
        "metro_end_step",
        "status",
        "knox_id",
        "user_sdwt_prod",
        "target_user_sdwt_prod",
        "comment",
        "defect_url",
        "ctttm_urls",
        "instant_inform",
        "needtosend",
        "custom_end_step",
    ]
    conflict_cols = ["sop_key"]
    exclude_update_cols = {"needtosend", "comment", "instant_inform", "sop_key"}

    placeholders = ",".join(["%s::jsonb" if col == "ctttm_urls" else "%s" for col in insert_cols])
    quoted_table = f'"{DroneSOP._meta.db_table}"'
    quoted_insert_cols = ", ".join(f'"{col}"' for col in insert_cols)
    conflict_target = ", ".join(f'"{col}"' for col in conflict_cols)

    update_parts: list[str] = []
    for col in insert_cols:
        if col in exclude_update_cols:
            continue
        if col == "defect_url":
            update_parts.append(f'"{col}" = EXCLUDED."{col}"')
            continue
        if col == "ctttm_urls":
            update_parts.append(f'"{col}" = COALESCE(EXCLUDED."{col}", {quoted_table}."{col}")')
            continue
        if col == "target_user_sdwt_prod":
            update_parts.append(f'"{col}" = COALESCE({quoted_table}."{col}", EXCLUDED."{col}")')
            continue
        update_parts.append(f'"{col}" = COALESCE(EXCLUDED."{col}", {quoted_table}."{col}")')
    update_parts.append('"updated_at" = NOW()')
    update_clause = ", ".join(update_parts)

    sql = f"""
        INSERT INTO {quoted_table} ({quoted_insert_cols})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_target})
        DO UPDATE SET {update_clause}
    """

    # -------------------------------------------------------------------------
    # 3) 바인드 파라미터 구성
    # -------------------------------------------------------------------------
    args = []
    source_by_sop_key: dict[str, dict[str, Any]] = {}
    user_sdwt_map_index: UserSdwtProdMapIndex | None = None
    for row in rows:
        values: list[Any] = []
        if not row.get("sop_key"):
            row["sop_key"] = build_sop_key(
                line_id=row.get("line_id"),
                eqp_id=row.get("eqp_id"),
                chamber_ids=row.get("chamber_ids"),
                lot_id=row.get("lot_id"),
                main_step=row.get("main_step"),
            )
        if not row.get("target_user_sdwt_prod"):
            if user_sdwt_map_index is None:
                user_sdwt_map_index = load_user_sdwt_prod_map_index()
            target_user_sdwt_prods = resolve_target_user_sdwt_prods(
                row=row,
                index=user_sdwt_map_index,
            )
            target_user_sdwt_prod = target_user_sdwt_prods[0] if target_user_sdwt_prods else None
            row["target_user_sdwt_prods"] = target_user_sdwt_prods
            row["target_user_sdwt_prod"] = target_user_sdwt_prod
        sop_key = str(row.get("sop_key") or "").strip()
        if sop_key:
            source_by_sop_key[sop_key] = dict(row)
        for col in insert_cols:
            value = row.get(col)
            if value is None and col == "instant_inform":
                value = 0
            if value is not None and col == "ctttm_urls":
                value = json.dumps(value, ensure_ascii=False)
            values.append(value)
        args.append(tuple(values))
    # -------------------------------------------------------------------------
    # 4) SQL 실행
    # -------------------------------------------------------------------------
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.executemany(sql, args)
        _ensure_snapshots_for_upserted_rows(source_by_sop_key=source_by_sop_key)

    return len(rows)


def prune_old_drone_sop_rows(
    *,
    days: int,
    batch_size: int = 1000,
    dry_run: bool = False,
    max_batches: int | None = None,
) -> int:
    """지정 일수보다 오래된 DroneSOP 레코드를 상태와 무관하게 정리합니다.

    인자:
        days: 보관 일수.
        batch_size: 한 번에 삭제할 DroneSOP 행 수.
        dry_run: True이면 삭제하지 않고 후보 수만 반환합니다.
        max_batches: 최대 배치 횟수. None이면 후보가 없어질 때까지 수행합니다.

    반환:
        삭제 또는 삭제 예정인 DroneSOP 레코드 수.

    부작용:
        dry_run=False이면 DB 삭제가 발생합니다.
    """

    if days <= 0:
        raise ValueError("days must be greater than 0")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    if max_batches is not None and max_batches <= 0:
        raise ValueError("max_batches must be greater than 0")

    cutoff = timezone.now() - timedelta(days=days)
    base_queryset = DroneSOP.objects.filter(created_at__lt=cutoff)
    if dry_run:
        return int(base_queryset.count())

    deleted_total = 0
    batches = 0
    while max_batches is None or batches < max_batches:
        ids = list(
            base_queryset.order_by("created_at", "id")
            .values_list("id", flat=True)[:batch_size]
        )
        if not ids:
            break
        DroneSOP.objects.filter(id__in=ids).delete()
        deleted_total += len(ids)
        batches += 1
    return deleted_total


def safe_prune_rows(
    *,
    days: int,
    only_when_upserted: bool,
    upserted_rows: int,
    batch_size: int = 1000,
) -> int:
    """오래된 DroneSOP 행 정리를 안전하게 수행합니다."""

    if only_when_upserted and upserted_rows <= 0:
        return 0
    try:
        return prune_old_drone_sop_rows(days=days, batch_size=batch_size)
    except Exception:
        logger.exception("Failed to prune old DroneSOP rows")
        return 0


__all__ = ["prune_old_drone_sop_rows", "safe_prune_rows", "upsert_drone_sop_rows"]
