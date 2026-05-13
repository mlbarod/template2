# =============================================================================
# 모듈: 드론 셀렉터
# 주요 함수: list_early_inform_entries, list_drone_sop_jira_candidates, has_drone_sop_jira_candidates, get_line_history_payload
# 주요 가정: 읽기 전용 쿼리만 수행합니다.
# =============================================================================
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from django.db import connection
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.db.models.functions import Lower

import api.account.selectors as account_selectors
from api.common.services.db import run_query

from .models import (
    DroneEarlyInform,
    DroneSOP,
    DroneSopDelivery,
    DroneSopNeedToSendRule,
    DroneSopTarget,
    DroneSopTargetChannelConfig,
    DroneSopTargetMapping,
    DroneSopTargetRecipient,
)
from .serializers import (
    collapse_display_values,
    display_delivery_target,
    normalize_chatroom_id,
    normalize_lookup_text,
    normalize_lookup_text_list,
    normalize_text,
    normalize_text_list,
)
from .services.table_schema import (
    DEFAULT_TABLE,
    LINE_SDWT_TABLE_NAME,
    build_line_filters,
    ensure_date_bounds,
    find_column,
    normalize_date_only,
    normalize_line_id,
    resolve_table_schema,
    sanitize_identifier,
)
from .services.history.payload import (
    build_breakdown_query,
    build_totals_query,
    build_where_clause,
    normalize_breakdown_row,
    normalize_daily_row,
)

_DRONE_SOP_COMMON_CANDIDATE_FIELDS = (
    "id",
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
    "needtosend",
    "instant_inform",
    "custom_end_step",
)
_DRONE_SOP_JIRA_CANDIDATE_FIELDS = _DRONE_SOP_COMMON_CANDIDATE_FIELDS
_DRONE_SOP_PIPELINE_CANDIDATE_FIELDS = _DRONE_SOP_COMMON_CANDIDATE_FIELDS

_DIMENSION_CANDIDATES = [
    "sdwt_prod",
    "proc_id",
    "ppid",
    "user_sdwt_prod",
    "eqp_id",
    "main_step",
    "sample_type",
    "line_id",
]

def _drone_sop_eligible_filter() -> Q:
    """Drone SOP 후보 공통 적합 조건 필터를 반환합니다."""

    return Q(needtosend=1, status="COMPLETE") | Q(instant_inform=1)


def list_early_inform_entries(*, line_id: str) -> QuerySet[DroneEarlyInform]:
    """조기 알림 설정을 라인 기준으로 조회합니다.

    인자:
        line_id: 라인 ID.

    반환:
        DroneEarlyInform QuerySet(조기 알림 목록).

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return DroneEarlyInform.objects.filter(line_id=line_id).order_by("main_step", "id")


def get_early_inform_entry_for_update(*, entry_id: int) -> DroneEarlyInform | None:
    """조기 알림 엔트리를 행 잠금(select_for_update)으로 조회합니다.

    인자:
        entry_id: DroneEarlyInform ID.

    반환:
        DroneEarlyInform 인스턴스 또는 None.

    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.

    오류:
        없음.
    """

    if entry_id <= 0:
        return None
    return DroneEarlyInform.objects.select_for_update().filter(id=entry_id).first()


def get_drone_sop_for_update(*, sop_id: int) -> DroneSOP | None:
    """DroneSOP 엔트리를 행 잠금(select_for_update)으로 조회합니다.

    인자:
        sop_id: DroneSOP ID.

    반환:
        DroneSOP 인스턴스 또는 None.

    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.

    오류:
        없음.
    """

    if sop_id <= 0:
        return None
    return DroneSOP.objects.select_for_update().filter(id=sop_id).first()


def list_drone_sop_user_sdwt_maps() -> list[dict[str, Any]]:
    """드론 SOP 사용자 매핑 규칙 목록을 조회합니다.

    반환:
        매핑 규칙 dict 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 매핑 규칙 조회
    # -----------------------------------------------------------------------------
    rows = (
        DroneSopTargetMapping.objects.values("sdwt_prod", "user_sdwt_prod", "target__target_user_sdwt_prod")
        .order_by("id")
    )
    return [
        {
            "sdwt_prod": row.get("sdwt_prod"),
            "user_sdwt_prod": row.get("user_sdwt_prod"),
            "target_user_sdwt_prod": row.get("target__target_user_sdwt_prod"),
        }
        for row in rows
    ]


def get_drone_sop_needtosend_rule_by_target(
    *,
    target_user_sdwt_prod: str,
) -> DroneSopNeedToSendRule | None:
    """target_user_sdwt_prod 기준 needtosend 채널 설정을 조회합니다.

    인자:
        target_user_sdwt_prod: 대상 소속 문자열.

    반환:
        needtosend 설정이 있는 DroneSopNeedToSendRule 또는 None.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized = normalize_text(target_user_sdwt_prod, allow_non_str=True)
    if not normalized:
        return None

    # -----------------------------------------------------------------------------
    # 2) 채널 설정의 needtosend 규칙 조회
    # -----------------------------------------------------------------------------
    return (
        DroneSopNeedToSendRule.objects.select_related("target")
        .filter(
            target__target_user_sdwt_prod__iexact=normalized,
            enabled=True,
        )
        .exclude(comment_keyword__isnull=True)
        .exclude(comment_keyword__exact="")
        .order_by("id")
        .first()
    )


def list_drone_sop_user_sdwt_channels_by_targets(
    *,
    target_user_sdwt_prod_values: set[str] | list[str],
) -> dict[str, dict[str, str | bool | int | None]]:
    """target_user_sdwt_prod별 채널 설정 맵을 조회합니다.

    인자:
        target_user_sdwt_prod_values: target_user_sdwt_prod 집합 또는 리스트.

    반환:
        {target_user_sdwt_prod: {jira_key, chatroom_id, jira_template_key, mail_template_key, messenger_template_key, jira_enabled, messenger_enabled, mail_enabled}} 형태의 dict.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized_targets = normalize_lookup_text_list(target_user_sdwt_prod_values)
    if not normalized_targets:
        return {}

    # -----------------------------------------------------------------------------
    # 2) 채널 설정 조회 및 매핑 구성
    # -----------------------------------------------------------------------------
    rows = (
        DroneSopTarget.objects.annotate(target_user_sdwt_prod_lookup=Lower("target_user_sdwt_prod"))
        .filter(target_user_sdwt_prod_lookup__in=normalized_targets)
        .prefetch_related("channel_configs")
    )
    mapping: dict[str, dict[str, str | bool | int | None]] = {}
    for row in rows:
        target_lookup = normalize_lookup_text(row.target_user_sdwt_prod)
        if not target_lookup:
            continue
        config_by_channel = {config.channel: config for config in row.channel_configs.all()}
        jira_config = config_by_channel.get(DroneSopTargetChannelConfig.Channels.JIRA)
        messenger_config = config_by_channel.get(DroneSopTargetChannelConfig.Channels.MESSENGER)
        mail_config = config_by_channel.get(DroneSopTargetChannelConfig.Channels.MAIL)
        chatroom_id = normalize_chatroom_id(messenger_config.chatroom_id if messenger_config else None)
        mapping[target_lookup] = {
            "jira_key": normalize_text(jira_config.jira_project_key if jira_config else None),
            "chatroom_id": chatroom_id,
            "jira_template_key": normalize_text(jira_config.template_key if jira_config else None),
            "mail_template_key": normalize_text(mail_config.template_key if mail_config else None),
            "messenger_template_key": normalize_text(messenger_config.template_key if messenger_config else None),
            "jira_enabled": bool(jira_config.enabled) if jira_config else True,
            "messenger_enabled": bool(messenger_config.enabled) if messenger_config else True,
            "mail_enabled": bool(mail_config.enabled) if mail_config else True,
        }
    return mapping


def list_drone_sop_jira_templates_by_target_user_sdwt_prods(
    *,
    target_user_sdwt_prod_values: set[str] | list[str],
) -> dict[str, str | None]:
    """target_user_sdwt_prod별 Jira 템플릿 키 맵을 조회합니다.

    인자:
        target_user_sdwt_prod_values: target_user_sdwt_prod 집합 또는 리스트.

    반환:
        {target_user_sdwt_prod: template_key} 형태의 dict(없으면 None).

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    channels = list_drone_sop_user_sdwt_channels_by_targets(
        target_user_sdwt_prod_values=target_user_sdwt_prod_values,
    )
    normalized_targets = normalize_text_list(target_user_sdwt_prod_values)
    result: dict[str, str | None] = {}
    for target in normalized_targets:
        lookup_key = normalize_lookup_text(target)
        config = channels.get(lookup_key) if lookup_key else None
        result[target] = normalize_text(config.get("jira_template_key")) if config else None
    return result


def load_drone_sop_custom_end_step_map() -> dict[tuple[str, str], str | None]:
    """(user_sdwt_prod, main_step) → custom_end_step 맵을 로드합니다.

    drone_early_inform(line_id, main_step) 설정을 account_affiliation(line, user_sdwt_prod)와 조인해,
    Drone SOP 수집 시 custom_end_step 계산에 사용할 캐시 dict를 구성합니다.

    반환:
        {(user_sdwt_prod, main_step): custom_end_step} 형태의 dict.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 조기 알림 + 소속 매핑 조인 조회
    # -----------------------------------------------------------------------------
    rows = run_query(
        """
        SELECT
            aff.user_sdwt_prod AS user_sdwt_prod,
            ei.main_step AS main_step,
            ei.custom_end_step AS custom_end_step
        FROM drone_early_inform AS ei
        JOIN {table} AS aff
          ON aff.line = ei.line_id
        """.format(table=LINE_SDWT_TABLE_NAME)
    )

    # -----------------------------------------------------------------------------
    # 2) 결과 매핑 구성
    # -----------------------------------------------------------------------------
    mapping: dict[tuple[str, str], str | None] = {}
    for row in rows:
        user_sdwt_prod = row.get("user_sdwt_prod")
        main_step = row.get("main_step")
        if not isinstance(user_sdwt_prod, str) or not isinstance(main_step, str):
            continue
        normalized_user_sdwt_prod = normalize_lookup_text(user_sdwt_prod)
        normalized_main_step = main_step.strip()
        if not normalized_user_sdwt_prod or not normalized_main_step:
            continue
        key = (normalized_user_sdwt_prod, normalized_main_step)
        custom_end_step = row.get("custom_end_step")
        if custom_end_step is None:
            mapping[key] = None
        elif isinstance(custom_end_step, str):
            mapping[key] = custom_end_step.strip()
        else:
            mapping[key] = str(custom_end_step).strip()

    return mapping


def _drone_sop_jira_candidates_queryset() -> QuerySet[DroneSOP]:
    """Jira 전송 대상 DroneSOP 기본 QuerySet을 구성합니다.

    반환:
        DroneSOP QuerySet.

    부작용:
        없음. 읽기 전용 조회 조건만 생성합니다.
    """

    pending_delivery = DroneSopDelivery.objects.filter(
        sop_id=OuterRef("pk"),
        channel=DroneSopDelivery.Channels.JIRA,
        status=DroneSopDelivery.Statuses.PENDING,
    )
    existing_delivery = DroneSopDelivery.objects.filter(
        sop_id=OuterRef("pk"),
        channel=DroneSopDelivery.Channels.JIRA,
    )
    needs_snapshot = ~Q(has_delivery=True)
    return (
        DroneSOP.objects.annotate(
            has_pending_delivery=Exists(pending_delivery),
            has_delivery=Exists(existing_delivery),
        )
        .filter(Q(has_pending_delivery=True) | needs_snapshot)
        .filter(_drone_sop_eligible_filter())
    )


def _drone_sop_pipeline_candidates_queryset() -> QuerySet[DroneSOP]:
    """고정 3채널 기준 DroneSOP 후보 QuerySet을 구성합니다."""

    pending_delivery = DroneSopDelivery.objects.filter(
        sop_id=OuterRef("pk"),
        status=DroneSopDelivery.Statuses.PENDING,
    )
    existing_delivery = DroneSopDelivery.objects.filter(sop_id=OuterRef("pk"))
    needs_snapshot = ~Q(has_delivery=True)
    return (
        DroneSOP.objects.annotate(
            has_pending_delivery=Exists(pending_delivery),
            has_delivery=Exists(existing_delivery),
        )
        .filter(Q(has_pending_delivery=True) | needs_snapshot)
        .filter(_drone_sop_eligible_filter())
    )


def _list_candidate_rows(
    *,
    queryset: QuerySet[DroneSOP],
    fields: Sequence[str],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """대상 QuerySet에서 후보 row를 공통 방식으로 조회합니다."""

    ordered = queryset.order_by("id")
    if isinstance(limit, int) and limit > 0:
        ordered = ordered[:limit]
    return list(ordered.values(*fields))


def list_drone_sop_jira_candidates(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Jira 전송 대상 DroneSOP 로우를 조회합니다.

    조건:
        - Jira delivery pending 또는 delivery snapshot 미생성 row
        - (needtosend = 1 & status = 'COMPLETE') 또는 instant_inform = 1

    인자:
        limit: 최대 조회 건수(옵션).

    반환:
        DroneSOP row dict 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return _list_candidate_rows(
        queryset=_drone_sop_jira_candidates_queryset(),
        fields=_DRONE_SOP_JIRA_CANDIDATE_FIELDS,
        limit=limit,
    )


def list_drone_sop_pipeline_candidates(
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """고정 3채널 기준 DroneSOP 후보 row 목록을 조회합니다.

    인자:
        limit: 최대 조회 건수(옵션).

    반환:
        DroneSOP row dict 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    queryset = _drone_sop_pipeline_candidates_queryset()
    return _list_candidate_rows(
        queryset=queryset,
        fields=_DRONE_SOP_PIPELINE_CANDIDATE_FIELDS,
        limit=limit,
    )


def list_drone_sop_channel_delivery_rows_by_sop_ids(*, sop_ids: Sequence[int]) -> dict[int, list[dict[str, Any]]]:
    """SOP ID별 채널 delivery row 목록을 조회합니다.

    인자:
        sop_ids: DroneSOP ID 목록.

    반환:
        {sop_id: [delivery row dict, ...]} 형태의 dict.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 ID 정규화
    # -----------------------------------------------------------------------------
    normalized_ids: list[int] = []
    seen: set[int] = set()
    for raw_id in sop_ids:
        if not isinstance(raw_id, int) or raw_id <= 0 or raw_id in seen:
            continue
        seen.add(raw_id)
        normalized_ids.append(raw_id)
    if not normalized_ids:
        return {}

    # -----------------------------------------------------------------------------
    # 2) SOP별 최초 target의 delivery row만 조회합니다.
    # -----------------------------------------------------------------------------
    rows = (
        DroneSopDelivery.objects.filter(sop_id__in=normalized_ids)
        .order_by("sop_id", "id")
        .values(
            "id",
            "sop_id",
            "dispatch_id",
            "dispatch__target_code_snapshot",
            "dispatch__status",
            "dispatch__comment_override",
            "channel",
            "status",
            "reason",
            "external_key",
            "sent_comment",
            "sent_step",
            "sent_at",
            "updated_at",
        )
    )

    # -----------------------------------------------------------------------------
    # 3) API row에 붙이기 쉬운 camelCase payload로 변환
    # -----------------------------------------------------------------------------
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        sop_id = row.get("sop_id")
        if not isinstance(sop_id, int):
            continue
        target_user_sdwt_prod = display_delivery_target(row.get("dispatch__target_code_snapshot"))
        if not target_user_sdwt_prod:
            continue
        grouped.setdefault(sop_id, []).append(
            {
                "id": row.get("id"),
                "sopId": sop_id,
                "dispatchId": row.get("dispatch_id"),
                "targetUserSdwtProd": target_user_sdwt_prod,
                "dispatchStatus": row.get("dispatch__status"),
                "commentOverride": row.get("dispatch__comment_override"),
                "channel": row.get("channel"),
                "status": row.get("status"),
                "reason": row.get("reason"),
                "externalKey": row.get("external_key"),
                "sentComment": row.get("sent_comment"),
                "sentStep": row.get("sent_step"),
                "sentAt": row.get("sent_at"),
                "updatedAt": row.get("updated_at"),
            }
        )
    return grouped


def has_drone_sop_jira_candidates() -> bool:
    """Jira 전송 대상 DroneSOP가 존재하는지 확인합니다.

    조건:
        - Jira delivery pending 또는 delivery snapshot 미생성 row
        - (needtosend = 1 & status = 'COMPLETE') 또는 instant_inform = 1

    반환:
        존재 여부(boolean).

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 쿼리 구성
    # -----------------------------------------------------------------------------
    qs = _drone_sop_jira_candidates_queryset()

    # -----------------------------------------------------------------------------
    # 2) 존재 여부 반환
    # -----------------------------------------------------------------------------
    return qs.exists()


def has_drone_sop_pipeline_candidates() -> bool:
    """고정 3채널 기준 DroneSOP 후보 존재 여부를 확인합니다."""

    qs = _drone_sop_pipeline_candidates_queryset()
    return qs.exists()


def load_drone_sop_ctttm_workorders_map(
    *,
    sop_ids: Sequence[int],
    ctttm_table: str,
) -> dict[int, list[dict[str, str]]]:
    """Drone SOP row id 목록에 대해 CTTTM 최신 workorder 정보를 조회합니다.

    인자:
        sop_ids: Drone SOP ID 목록.
        ctttm_table: CTTTM 테이블명.

    반환:
        {sop_id: [{"eqp_id": "...", "workorder_id": "...", "line_id": "..."}]} 형태의 dict.

    부작용:
        없음. 읽기 전용 조회입니다.

    오류:
        테이블명이 허용된 패턴이 아니면 ValueError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력/환경 검증
    # -----------------------------------------------------------------------------
    if not sop_ids:
        return {}
    if connection.vendor != "postgresql":
        return {}

    # -----------------------------------------------------------------------------
    # 2) 테이블명/ID 정규화
    # -----------------------------------------------------------------------------
    raw_table_name = str(ctttm_table or "").strip()
    if not raw_table_name:
        return {}
    table_name = sanitize_identifier(raw_table_name)
    if not table_name:
        raise ValueError("CTTTM table name must match ^[A-Za-z0-9_]+$")

    normalized_ids: list[int] = []
    for raw_id in sop_ids:
        try:
            parsed = int(raw_id)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            normalized_ids.append(parsed)
    if not normalized_ids:
        return {}

    unique_ids = sorted(set(normalized_ids))

    # -----------------------------------------------------------------------------
    # 3) SQL 조회
    # -----------------------------------------------------------------------------
    rows = run_query(
        """
        WITH RECURSIVE seq AS (
            SELECT 1 AS n
            UNION ALL
            SELECT n + 1 FROM seq WHERE n < 100
        ),
        eqp_list_cte AS (
            SELECT
                sop.id AS sop_id,
                CONCAT(sop.eqp_id, '-', SUBSTRING(COALESCE(sop.chamber_ids, ''), n, 1)) AS eqp_list
            FROM drone_sop AS sop
            JOIN seq ON n <= CHAR_LENGTH(COALESCE(sop.chamber_ids, ''))
            WHERE sop.id = ANY(%s)
              AND sop.eqp_id IS NOT NULL
              AND sop.eqp_id <> ''
        ),
        latest_list AS (
            SELECT DISTINCT ON (eqp_id)
                eqp_id,
                inprg_date,
                workorder_id,
                line_id
            FROM {ctttm_table}
            WHERE eqp_id IN (SELECT eqp_list FROM eqp_list_cte)
            ORDER BY eqp_id, inprg_date DESC
        )
        SELECT
            eqp_list_cte.sop_id AS sop_id,
            latest_list.eqp_id AS eqp_id,
            latest_list.workorder_id AS workorder_id,
            latest_list.line_id AS line_id
        FROM latest_list
        JOIN eqp_list_cte ON eqp_list_cte.eqp_list = latest_list.eqp_id
        ORDER BY eqp_list_cte.sop_id ASC
        """.format(ctttm_table=table_name),
        [unique_ids],
    )

    # -----------------------------------------------------------------------------
    # 4) 결과 매핑 구성
    # -----------------------------------------------------------------------------
    mapping: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        sop_id = row.get("sop_id")
        if not isinstance(sop_id, int):
            try:
                sop_id = int(sop_id)
            except (TypeError, ValueError):
                continue
        if sop_id <= 0:
            continue

        eqp_id = row.get("eqp_id")
        workorder_id = row.get("workorder_id")
        line_id = row.get("line_id")

        if eqp_id is None or workorder_id is None or line_id is None:
            continue

        mapping.setdefault(sop_id, []).append(
            {
                "eqp_id": str(eqp_id).strip(),
                "workorder_id": str(workorder_id).strip(),
                "line_id": str(line_id).strip(),
            }
        )

    return mapping


def list_user_sdwt_prod_values_for_line(*, line_id: str) -> list[str]:
    """라인 ID에 매핑되는 user_sdwt_prod 값을 조회합니다.

    인자:
        line_id: 라인 ID.

    반환:
        user_sdwt_prod 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    rows = run_query(
        """
        SELECT DISTINCT user_sdwt_prod
        FROM {table}
        WHERE line = %s
          AND user_sdwt_prod IS NOT NULL
          AND user_sdwt_prod <> ''
        """.format(table=LINE_SDWT_TABLE_NAME),
        [line_id],
    )
    values: list[str] = []
    for row in rows:
        raw = row.get("user_sdwt_prod")
        if isinstance(raw, str):
            trimmed = raw.strip()
            if trimmed:
                values.append(trimmed)
    return values


def line_id_exists(*, line_id: str) -> bool:
    """account_affiliation에 등록된 line_id인지 확인합니다."""

    normalized_line_id = normalize_text(line_id)
    if not normalized_line_id:
        return False

    rows = run_query(
        """
        SELECT 1 AS exists_flag
        FROM {table}
        WHERE LOWER(line) = LOWER(%s)
          AND line IS NOT NULL
          AND line <> ''
        LIMIT 1
        """.format(table=LINE_SDWT_TABLE_NAME),
        [normalized_line_id],
    )
    return bool(rows)


def _derive_target_source(*, target_user_sdwt_prod: str) -> str:
    """account affiliation 존재 여부로 target source 표시값을 계산합니다."""

    return (
        DroneSopTarget.Sources.AFFILIATION
        if affiliation_exists_for_user_sdwt_prod(user_sdwt_prod=target_user_sdwt_prod)
        else DroneSopTarget.Sources.CUSTOM
    )


def list_drone_sop_notification_targets_for_line(*, line_id: str) -> list[dict[str, object]]:
    """라인별 Drone SOP 알림 target 목록을 조회합니다.

    account_affiliation 값은 초기 선택을 돕는 추천값으로만 병합하고,
    실제 설정 소유권은 DroneSopTarget.line_id를 기준으로 판단합니다.

    인자:
        line_id: 라인 ID.

    반환:
        target 정보 dict 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    normalized_line_id = normalize_text(line_id)
    if not normalized_line_id:
        return []

    targets_by_key: dict[str, dict[str, object]] = {}

    configured_rows = (
        DroneSopTarget.objects.filter(line_id__iexact=normalized_line_id)
        .exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .prefetch_related("channel_configs", "needtosend_rule")
        .order_by("target_user_sdwt_prod", "id")
    )
    for row in configured_rows:
        target_value = normalize_text(row.target_user_sdwt_prod)
        if not target_value:
            continue
        targets_by_key[target_value.casefold()] = {
            "lineId": row.line_id or normalized_line_id,
            "targetUserSdwtProd": target_value,
            "source": _derive_target_source(target_user_sdwt_prod=target_value),
            "isConfigured": True,
            "jiraKey": row.jira_key or None,
            "jiraEnabled": bool(row.jira_enabled),
            "messengerEnabled": bool(row.messenger_enabled),
            "mailEnabled": bool(row.mail_enabled),
        }

    for target_value in list_user_sdwt_prod_values_for_line(line_id=normalized_line_id):
        normalized_target = normalize_text(target_value)
        if not normalized_target:
            continue
        targets_by_key.setdefault(
            normalized_target.casefold(),
            {
                "lineId": normalized_line_id,
                "targetUserSdwtProd": normalized_target,
                "source": DroneSopTarget.Sources.AFFILIATION,
                "isConfigured": False,
                "jiraKey": None,
                "jiraEnabled": True,
                "messengerEnabled": True,
                "mailEnabled": True,
            },
        )

    for mapping in (
        DroneSopTargetMapping.objects.select_related("target")
        .exclude(target__target_user_sdwt_prod__isnull=True)
        .exclude(target__target_user_sdwt_prod__exact="")
        .order_by("sdwt_prod", "user_sdwt_prod", "id")
    ):
        target_value = normalize_text(mapping.target_user_sdwt_prod)
        target = targets_by_key.get(target_value.casefold())
        if target is None:
            continue
        mappings = target.setdefault("mappings", [])
        if isinstance(mappings, list):
            mappings.append(
                {
                    "sdwtProd": normalize_text(mapping.sdwt_prod),
                    "userSdwtProd": normalize_text(mapping.user_sdwt_prod),
                }
            )

    for target in targets_by_key.values():
        target.setdefault("mappings", [])

    return sorted(
        targets_by_key.values(),
        key=lambda item: (
            0 if item.get("isConfigured") else 1,
            str(item.get("targetUserSdwtProd") or "").casefold(),
        ),
    )


def affiliation_exists_for_user_sdwt_prod(*, user_sdwt_prod: str) -> bool:
    """user_sdwt_prod에 대응하는 소속 존재 여부를 확인합니다.

    인자:
        user_sdwt_prod: 사용자 소속 값.

    반환:
        소속 존재 여부(bool).

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return account_selectors.affiliation_exists_for_user_sdwt_prod(user_sdwt_prod=user_sdwt_prod)


def list_drone_sop_mapping_option_values_for_line(*, line_id: str) -> dict[str, list[str]]:
    """라인별 Drone SOP 지정 조합 드롭다운 옵션을 조회합니다.

    인자:
        line_id: 라인 ID.

    반환:
        {"userSdwtProds": [...], "sdwtProds": [...]} 형태의 옵션 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    normalized_line_id = normalize_text(line_id)
    if not normalized_line_id:
        return {"userSdwtProds": [], "sdwtProds": []}

    base_queryset = DroneSOP.objects.filter(line_id__iexact=normalized_line_id)
    user_sdwt_values = (
        base_queryset.exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .values_list("user_sdwt_prod", flat=True)
        .order_by("id")
    )
    sdwt_values = (
        base_queryset.exclude(sdwt_prod__isnull=True)
        .exclude(sdwt_prod__exact="")
        .values_list("sdwt_prod", flat=True)
        .order_by("id")
    )

    return {
        "userSdwtProds": collapse_display_values(user_sdwt_values),
        "sdwtProds": collapse_display_values(sdwt_values),
    }


def list_drone_sop_target_user_sdwt_prod_values() -> list[str]:
    """Drone SOP 설정 대상 user_sdwt_prod 목록을 조회합니다.

    인자:
        없음.

    반환:
        대상 user_sdwt_prod 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) account 사용자 pool과 Drone 설정 테이블의 대상값을 병합
    # -----------------------------------------------------------------------------
    values: list[Any] = list(account_selectors.list_distinct_active_user_sdwt_prod_values())
    values.extend(
        DroneSopTarget.objects.exclude(target_user_sdwt_prod="")
        .values_list("target_user_sdwt_prod", flat=True)
        .distinct()
    )
    values.extend(
        DroneSopTargetMapping.objects.exclude(target__target_user_sdwt_prod__isnull=True)
        .exclude(target__target_user_sdwt_prod="")
        .values_list("target__target_user_sdwt_prod", flat=True)
        .distinct()
    )
    return collapse_display_values(values)


def user_can_manage_drone_sop_recipients(*, user: Any) -> bool:
    """사용자가 Drone SOP 수신인 설정을 관리할 수 있는지 확인합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        관리 가능 여부.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 이번 범위에서는 별도 앱 권한 없이 전역 운영자만 허용
    # -----------------------------------------------------------------------------
    return account_selectors.is_operator_user(user=user)


def get_drone_sop_permission_context(*, user: Any) -> dict[str, object]:
    """프론트엔드에서 사용할 Drone SOP 권한 컨텍스트를 반환합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        운영자 여부와 관리 가능한 target_user_sdwt_prod 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    is_operator = user_can_manage_drone_sop_recipients(user=user)
    return {
        "isOperator": is_operator,
        "manageableUserSdwtProds": (
            list_drone_sop_target_user_sdwt_prod_values() if is_operator else []
        ),
    }


def list_mail_receiver_emails_for_user_sdwt_prod(*, line_id: str, user_sdwt_prod: str) -> list[str]:
    """Drone SOP 메일 수신자 이메일 목록을 조회합니다.

    인자:
        line_id: 호환성을 위해 받는 라인 ID. 실제 수신인은 target 기준으로 조회합니다.
        user_sdwt_prod: 최종 알림 대상 소속 값.

    반환:
        이메일 주소 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return _list_recipient_contact_values(
        target_user_sdwt_prod=user_sdwt_prod,
        channel=DroneSopTargetRecipient.Channels.MAIL,
        contact_field="email",
    )


def list_messenger_receiver_knox_ids_for_user_sdwt_prod(*, line_id: str, user_sdwt_prod: str) -> list[str]:
    """Drone SOP 메신저 수신자 knox_id 목록을 조회합니다.

    인자:
        line_id: 호환성을 위해 받는 라인 ID. 실제 수신인은 target 기준으로 조회합니다.
        user_sdwt_prod: 최종 알림 대상 소속 값.

    반환:
        knox_id 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return _list_recipient_contact_values(
        target_user_sdwt_prod=user_sdwt_prod,
        channel=DroneSopTargetRecipient.Channels.MESSENGER,
        contact_field="knox_id",
    )


def _list_recipient_contact_values(
    *,
    target_user_sdwt_prod: str,
    channel: str,
    contact_field: str,
) -> list[str]:
    """채널 수신인에서 사용자 연락처 값을 중복 없이 조회합니다."""

    normalized = normalize_text(target_user_sdwt_prod)
    if not normalized:
        return []

    rows = (
        DroneSopTargetRecipient.objects.filter(
            target__target_user_sdwt_prod__iexact=normalized,
            channel=channel,
            user__is_active=True,
        )
        .exclude(**{f"user__{contact_field}__isnull": True})
        .exclude(**{f"user__{contact_field}__exact": ""})
        .values_list(f"user__{contact_field}", flat=True)
        .order_by(f"user__{contact_field}")
        .distinct()
    )

    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in rows:
        cleaned = normalize_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized_values.append(cleaned)
    return normalized_values


def list_drone_sop_channel_recipients(
    *,
    line_id: str,
    target_user_sdwt_prod: str,
    channel: str,
) -> list[dict[str, object]]:
    """Drone SOP target/channel에 등록된 수신인을 조회합니다.

    커스텀 target_user_sdwt_prod를 허용하므로 account_affiliation 매핑은 요구하지 않습니다.

    인자:
        line_id: 호환성을 위해 받는 라인 ID. 실제 수신인은 target 기준으로 조회합니다.
        target_user_sdwt_prod: 최종 알림 대상 소속 값.
        channel: mail 또는 messenger.

    반환:
        사용자 정보가 포함된 수신인 dict 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    normalized = normalize_text(target_user_sdwt_prod)
    if not normalized:
        return []

    target_row = get_drone_sop_channel_by_target_user_sdwt_prod(target_user_sdwt_prod=normalized)
    response_line_id = (target_row.line_id if target_row and target_row.line_id else normalize_text(line_id)) or ""

    rows = list(
        DroneSopTargetRecipient.objects.filter(
            target__target_user_sdwt_prod__iexact=normalized,
            channel=channel,
            user__is_active=True,
        )
        .select_related("target", "user")
        .order_by(
            "user__username",
            "user_id",
        )
    )
    affiliation_by_user_id = account_selectors.get_current_affiliation_values_by_user_ids(
        user_ids=[row.user_id for row in rows]
    )

    recipients: list[dict[str, object]] = []
    for row in rows:
        user = row.user
        affiliation_values = affiliation_by_user_id.get(user.id, {})
        display_name = (
            getattr(user, "username", None)
            or getattr(user, "username_en", None)
            or getattr(user, "givenname", None)
            or getattr(user, "knox_id", None)
            or getattr(user, "sabun", None)
            or ""
        )
        recipients.append(
            {
                "id": row.id,
                "userId": user.id,
                "username": getattr(user, "username", None) or "",
                "displayName": display_name,
                "sabun": getattr(user, "sabun", None) or "",
                "knoxId": getattr(user, "knox_id", None) or "",
                "email": getattr(user, "email", None) or "",
                "department": affiliation_values.get("department") or "",
                "line": affiliation_values.get("line") or "",
                "userSdwtProd": affiliation_values.get("user_sdwt_prod") or "",
                "channel": row.channel,
                "lineId": response_line_id,
                "targetUserSdwtProd": row.target_user_sdwt_prod,
            }
        )
    return recipients


def get_drone_sop_channel_by_target_user_sdwt_prod(
    *,
    target_user_sdwt_prod: str,
) -> DroneSopTarget | None:
    """target_user_sdwt_prod에 해당하는 채널 설정을 조회합니다.

    인자:
        target_user_sdwt_prod: 최종 사용자 소속 값.

    반환:
        DroneSopTarget 또는 None.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    normalized = normalize_text(target_user_sdwt_prod)
    if not normalized:
        return None

    # -----------------------------------------------------------------------------
    # 2) 채널 설정 조회
    # -----------------------------------------------------------------------------
    return (
        DroneSopTarget.objects.filter(target_user_sdwt_prod__iexact=normalized)
        .prefetch_related("channel_configs", "needtosend_rule")
        .first()
    )


def list_drone_sop_jira_target_user_sdwt_prods() -> list[str]:
    """채널 설정에 등록된 target_user_sdwt_prod 목록을 조회합니다.

    반환:
        target_user_sdwt_prod 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) target_user_sdwt_prod 목록 조회
    # -----------------------------------------------------------------------------
    rows = (
        DroneSopTarget.objects.exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .values_list("target_user_sdwt_prod", flat=True)
        .distinct()
        .order_by("target_user_sdwt_prod")
    )

    # -----------------------------------------------------------------------------
    # 2) 공백 제거 및 반환
    # -----------------------------------------------------------------------------
    return normalize_text_list(rows)


def get_drone_sop_jira_project_key_for_target_user_sdwt_prod(*, target_user_sdwt_prod: str) -> str | None:
    """target_user_sdwt_prod에 해당하는 Jira project key를 조회합니다.

    인자:
        target_user_sdwt_prod: 사용자 소속 값.

    반환:
        Jira project key 문자열 또는 None.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    normalized = normalize_text(target_user_sdwt_prod)
    if not normalized:
        return None

    # -----------------------------------------------------------------------------
    # 2) 채널 설정 기반 Jira 키 조회
    # -----------------------------------------------------------------------------
    channel = get_drone_sop_channel_by_target_user_sdwt_prod(target_user_sdwt_prod=normalized)
    if channel is None:
        return None
    return normalize_text(channel.jira_key)


def list_drone_sop_jira_project_keys_by_target_user_sdwt_prods(
    *,
    target_user_sdwt_prod_values: set[str] | list[str],
) -> dict[str, str | None]:
    """target_user_sdwt_prod별 Jira project key 맵을 조회합니다.

    인자:
        target_user_sdwt_prod_values: target_user_sdwt_prod 집합 또는 리스트.

    반환:
        {target_user_sdwt_prod: jira_key} 형태의 dict.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    channels = list_drone_sop_user_sdwt_channels_by_targets(
        target_user_sdwt_prod_values=target_user_sdwt_prod_values,
    )
    normalized_targets = normalize_text_list(target_user_sdwt_prod_values)
    result: dict[str, str | None] = {}
    for target in normalized_targets:
        lookup_key = normalize_lookup_text(target)
        config = channels.get(lookup_key) if lookup_key else None
        result[target] = normalize_text(config.get("jira_key")) if config else None
    return result


def list_line_ids_for_user_sdwt_prod(*, user_sdwt_prod: str) -> list[str]:
    """user_sdwt_prod에 매핑되는 line_id 목록을 조회합니다.

    인자:
        user_sdwt_prod: 사용자 소속 값.

    반환:
        line_id 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    normalized = normalize_text(user_sdwt_prod)
    if not normalized:
        return []

    # -----------------------------------------------------------------------------
    # 2) 쿼리 실행 및 결과 정리
    # -----------------------------------------------------------------------------
    rows = run_query(
        """
        SELECT DISTINCT line AS line_id
        FROM {table}
        WHERE LOWER(user_sdwt_prod) = LOWER(%s)
          AND line IS NOT NULL
          AND line <> ''
        ORDER BY line_id
        """.format(table=LINE_SDWT_TABLE_NAME),
        [normalized],
    )
    return normalize_text_list([row.get("line_id") for row in rows])


def list_distinct_line_ids() -> list[str]:
    """사이드바 필터용 line_id 고유값 목록을 조회합니다.

    반환:
        line_id 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    rows = run_query(
        """
        SELECT DISTINCT line AS line_id
        FROM {table}
        WHERE line IS NOT NULL AND line <> ''
        ORDER BY line_id
        """.format(table=LINE_SDWT_TABLE_NAME)
    )
    return collapse_display_values([row.get("line_id") for row in rows])


def get_line_history_payload(
    *,
    table_param: Any,
    line_id_param: Any,
    from_param: Any,
    to_param: Any,
    range_days_param: Any,
    default_range_days: int = 14,
) -> dict[str, Any]:
    """라인 대시보드 차트용 시간 단위 합계/분해 집계를 조회합니다.

    인자:
        table_param: 테이블 파라미터.
        line_id_param: 라인 ID 파라미터.
        from_param: 시작 날짜 파라미터.
        to_param: 종료 날짜 파라미터.
        range_days_param: 기간 일수 파라미터.
        default_range_days: 기본 기간 일수.

    반환:
        라인 히스토리 집계 payload dict.

    부작용:
        없음. 읽기 전용 조회입니다.

    오류:
        테이블/컬럼 검증 실패 시 ValueError/LookupError가 발생할 수 있습니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 날짜/라인 파라미터 정규화
    # -----------------------------------------------------------------------------
    from_value = normalize_date_only(from_param)
    to_value = normalize_date_only(to_param)
    normalized_line_id = normalize_line_id(line_id_param)

    parsed_range = None
    if isinstance(range_days_param, str) and range_days_param.isdigit():
        parsed_range = int(range_days_param)
    range_days = parsed_range if parsed_range and parsed_range > 0 else default_range_days

    if not to_value:
        today = datetime.utcnow().date()
        to_value = today.isoformat()

    if not from_value and to_value:
        to_date = datetime.fromisoformat(f"{to_value}T00:00:00")
        from_date = to_date - timedelta(days=range_days - 1)
        from_value = from_date.date().isoformat()

    if from_value and to_value:
        from_value, to_value = ensure_date_bounds(from_value, to_value)

    # -----------------------------------------------------------------------------
    # 2) 테이블 스키마/컬럼 해석
    # -----------------------------------------------------------------------------
    schema = resolve_table_schema(
        table_param,
        default_table=DEFAULT_TABLE,
        require_timestamp=True,
    )
    table_name = schema.name
    column_names = schema.columns
    timestamp_column = schema.timestamp_column

    send_jira_column = find_column(column_names, "send_jira")
    dimension_columns = {
        candidate: resolved
        for candidate in _DIMENSION_CANDIDATES
        if (resolved := find_column(column_names, candidate))
    }

    # -----------------------------------------------------------------------------
    # 3) WHERE 절 구성
    # -----------------------------------------------------------------------------
    line_filter_result = build_line_filters(column_names, normalized_line_id)
    where_clause, query_params = build_where_clause(
        timestamp_column=timestamp_column,
        line_filters=line_filter_result["filters"],
        line_params=line_filter_result["params"],
        from_value=from_value,
        to_value=to_value,
    )

    # -----------------------------------------------------------------------------
    # 4) 합계(총합) 조회
    # -----------------------------------------------------------------------------
    totals_rows = run_query(
        build_totals_query(
            table_name=table_name,
            timestamp_column=timestamp_column,
            send_jira_column=send_jira_column,
            where_clause=where_clause,
        ),
        query_params,
    )
    totals = [normalize_daily_row(row) for row in totals_rows]

    # -----------------------------------------------------------------------------
    # 5) 분해(차원별) 조회
    # -----------------------------------------------------------------------------
    breakdowns: Dict[str, List[Dict[str, Any]]] = {}
    for dimension_key, column_name in dimension_columns.items():
        rows = run_query(
            build_breakdown_query(
                table_name=table_name,
                timestamp_column=timestamp_column,
                dimension_column=column_name,
                send_jira_column=send_jira_column,
                where_clause=where_clause,
            ),
            query_params,
        )
        breakdowns[dimension_key] = [normalize_breakdown_row(row) for row in rows]

    # -----------------------------------------------------------------------------
    # 6) 응답 payload 구성
    # -----------------------------------------------------------------------------
    return {
        "table": table_name,
        "from": from_value,
        "to": to_value,
        "lineId": normalized_line_id,
        "timestampColumn": timestamp_column,
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "totals": totals,
        "breakdowns": breakdowns,
    }
