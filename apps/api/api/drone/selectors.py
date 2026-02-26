# =============================================================================
# 모듈: 드론 셀렉터
# 주요 함수: list_early_inform_entries, list_drone_sop_jira_candidates, has_drone_sop_jira_candidates, get_line_history_payload
# 주요 가정: 읽기 전용 쿼리만 수행합니다.
# =============================================================================
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from django.db import connection
from django.db.models import Q, QuerySet

import api.account.selectors as account_selectors
from api.common.services import DEFAULT_TABLE, DIMENSION_CANDIDATES, LINE_SDWT_TABLE_NAME, SAFE_IDENTIFIER
from api.common.services import run_query
from api.common.services import (
    build_date_range_filters,
    build_line_filters,
    ensure_date_bounds,
    find_column,
    normalize_date_only,
    normalize_line_id,
    resolve_table_schema,
    to_int,
)
from api.common.selectors import _get_user_sdwt_prod_values

from .models import (
    DroneEarlyInform,
    DroneSOP,
    DroneSopNeedToSendRule,
    DroneSopUserSdwtChannel,
    DroneSopUserSdwtProdMap,
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
    "comment",
    "defect_url",
    "defect_png_url",
    "needtosend",
    "instant_inform",
    "custom_end_step",
)
_DRONE_SOP_JIRA_CANDIDATE_FIELDS = (*_DRONE_SOP_COMMON_CANDIDATE_FIELDS, "send_jira")
_DRONE_SOP_INFORM_CANDIDATE_FIELDS = (
    *_DRONE_SOP_COMMON_CANDIDATE_FIELDS,
    "send_jira",
    "send_messenger",
    "send_mail",
)

# =============================================================================
# 공통 정규화 유틸
# =============================================================================
def _normalize_str(value: Any, *, allow_non_str: bool = False) -> str | None:
    """문자열 값을 정규화합니다.

    인자:
        value: 원본 값.
        allow_non_str: 문자열이 아닐 때 str() 변환 허용 여부.

    반환:
        정규화된 문자열 또는 None.

    부작용:
        없음. 순수 정규화입니다.
    """

    if value is None:
        return None
    if not isinstance(value, str):
        if not allow_non_str:
            return None
        value = str(value)
    trimmed = value.strip()
    return trimmed if trimmed else None


def _normalize_str_list(values: Sequence[Any], *, allow_non_str: bool = False) -> list[str]:
    """문자열 리스트를 정규화합니다.

    인자:
        values: 원본 값 시퀀스.
        allow_non_str: 문자열이 아닐 때 str() 변환 허용 여부.

    반환:
        정규화된 문자열 리스트.

    부작용:
        없음. 순수 정규화입니다.
    """

    normalized: list[str] = []
    for value in values:
        cleaned = _normalize_str(value, allow_non_str=allow_non_str)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _normalize_chatroom_id(value: Any) -> int | None:
    """채팅룸 ID 값을 정수로 정규화합니다.

    인자:
        value: 원본 값.

    반환:
        양의 정수 chatroom_id 또는 None.

    부작용:
        없음. 순수 정규화입니다.
    """

    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


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
    # 1) 활성 매핑 규칙 조회
    # -----------------------------------------------------------------------------
    rows = (
        DroneSopUserSdwtProdMap.objects.filter(is_active=True)
        .values("sdwt_prod", "user_sdwt_prod", "target_user_sdwt_prod")
        .order_by("id")
    )
    return list(rows)


def get_drone_sop_needtosend_rule_by_target(
    *,
    target_user_sdwt_prod: str,
) -> DroneSopNeedToSendRule | None:
    """target_user_sdwt_prod 기준 needtosend 규칙을 조회합니다.

    인자:
        target_user_sdwt_prod: 대상 소속 문자열.

    반환:
        DroneSopNeedToSendRule 인스턴스 또는 None.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized = _normalize_str(target_user_sdwt_prod, allow_non_str=True)
    if not normalized:
        return None

    # -----------------------------------------------------------------------------
    # 2) 활성 규칙 조회
    # -----------------------------------------------------------------------------
    return (
        DroneSopNeedToSendRule.objects.filter(target_user_sdwt_prod=normalized, is_active=True)
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
    normalized_targets = _normalize_str_list(target_user_sdwt_prod_values)
    if not normalized_targets:
        return {}

    # -----------------------------------------------------------------------------
    # 2) 채널 설정 조회 및 매핑 구성
    # -----------------------------------------------------------------------------
    rows = DroneSopUserSdwtChannel.objects.filter(
        target_user_sdwt_prod__in=normalized_targets,
        is_active=True,
    ).values(
        "target_user_sdwt_prod",
        "jira_key",
        "chatroom_id",
        "jira_template_key",
        "mail_template_key",
        "messenger_template_key",
        "jira_enabled",
        "messenger_enabled",
        "mail_enabled",
    )
    mapping: dict[str, dict[str, str | bool | int | None]] = {}
    for row in rows:
        target = _normalize_str(row.get("target_user_sdwt_prod"))
        if not target:
            continue
        chatroom_id = _normalize_chatroom_id(row.get("chatroom_id"))
        mapping[target] = {
            "jira_key": _normalize_str(row.get("jira_key")),
            "chatroom_id": chatroom_id,
            "jira_template_key": _normalize_str(row.get("jira_template_key")),
            "mail_template_key": _normalize_str(row.get("mail_template_key")),
            "messenger_template_key": _normalize_str(row.get("messenger_template_key")),
            "jira_enabled": bool(row.get("jira_enabled", True)),
            "messenger_enabled": bool(row.get("messenger_enabled", True)),
            "mail_enabled": bool(row.get("mail_enabled", True)),
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
    return {
        target: config.get("jira_template_key")
        for target, config in channels.items()
    }


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
        key = (user_sdwt_prod.strip(), main_step.strip())
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

    return DroneSOP.objects.filter(send_jira=0).filter(Q(needtosend=1, status="COMPLETE") | Q(instant_inform=1))


def _drone_sop_inform_candidates_queryset() -> QuerySet[DroneSOP]:
    """멀티 채널 전송 대상 DroneSOP 기본 QuerySet을 구성합니다.

    반환:
        DroneSOP QuerySet.

    부작용:
        없음. 읽기 전용 조회 조건만 생성합니다.
    """

    send_pending = (
        Q(send_jira=0)
        | Q(send_jira__isnull=True)
        | Q(send_messenger=0)
        | Q(send_messenger__isnull=True)
        | Q(send_mail=0)
        | Q(send_mail__isnull=True)
    )
    return DroneSOP.objects.filter(send_pending).filter(Q(needtosend=1, status="COMPLETE") | Q(instant_inform=1))


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
        - send_jira = 0 (미전송)
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


def list_drone_sop_inform_candidates(*, limit: int | None = None) -> list[dict[str, Any]]:
    """멀티 채널 전송 대상 DroneSOP 로우를 조회합니다.

    조건:
        - (send_jira=0 또는 NULL) 또는 (send_messenger=0 또는 NULL) 또는 (send_mail=0 또는 NULL)
        - (needtosend = 1 & status = 'COMPLETE') 또는 instant_inform = 1

    인자:
        limit: 최대 조회 건수(옵션).

    반환:
        DroneSOP row dict 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return _list_candidate_rows(
        queryset=_drone_sop_inform_candidates_queryset(),
        fields=_DRONE_SOP_INFORM_CANDIDATE_FIELDS,
        limit=limit,
    )


def has_drone_sop_jira_candidates() -> bool:
    """Jira 전송 대상 DroneSOP가 존재하는지 확인합니다.

    조건:
        - send_jira = 0 (미전송)
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


def has_drone_sop_inform_candidates() -> bool:
    """멀티 채널 전송 대상 DroneSOP가 존재하는지 확인합니다.

    조건:
        - (send_jira=0 또는 NULL) 또는 (send_messenger=0 또는 NULL) 또는 (send_mail=0 또는 NULL)
        - (needtosend = 1 & status = 'COMPLETE') 또는 instant_inform = 1

    반환:
        존재 여부(boolean).

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 쿼리 구성
    # -----------------------------------------------------------------------------
    qs = _drone_sop_inform_candidates_queryset()

    # -----------------------------------------------------------------------------
    # 2) 존재 여부 반환
    # -----------------------------------------------------------------------------
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
    table_name = str(ctttm_table or "").strip()
    if not table_name:
        return {}
    if not SAFE_IDENTIFIER.match(table_name):
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

    return _get_user_sdwt_prod_values(line_id)


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


def list_mail_receiver_emails_for_user_sdwt_prod(*, user_sdwt_prod: str) -> list[str]:
    """user_sdwt_prod에 해당하는 메일 수신자 이메일 목록을 조회합니다.

    인자:
        user_sdwt_prod: 최종 사용자 소속 값.

    반환:
        이메일 주소 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return account_selectors.list_active_user_emails_by_user_sdwt_prod(user_sdwt_prod=user_sdwt_prod)


def list_messenger_receiver_knox_ids_for_user_sdwt_prod(*, user_sdwt_prod: str) -> list[str]:
    """user_sdwt_prod에 해당하는 메신저 수신자 knox_id 목록을 조회합니다.

    인자:
        user_sdwt_prod: 최종 사용자 소속 값.

    반환:
        knox_id 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return account_selectors.list_active_user_knox_ids_by_user_sdwt_prod(user_sdwt_prod=user_sdwt_prod)


def get_drone_sop_channel_by_target_user_sdwt_prod(
    *,
    target_user_sdwt_prod: str,
) -> DroneSopUserSdwtChannel | None:
    """target_user_sdwt_prod에 해당하는 채널 설정을 조회합니다.

    인자:
        target_user_sdwt_prod: 최종 사용자 소속 값.

    반환:
        DroneSopUserSdwtChannel 또는 None.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    normalized = _normalize_str(target_user_sdwt_prod)
    if not normalized:
        return None

    # -----------------------------------------------------------------------------
    # 2) 채널 설정 조회
    # -----------------------------------------------------------------------------
    return DroneSopUserSdwtChannel.objects.filter(
        target_user_sdwt_prod=normalized,
        is_active=True,
    ).first()


def list_drone_sop_jira_target_user_sdwt_prods() -> list[str]:
    """활성 채널 설정에 등록된 target_user_sdwt_prod 목록을 조회합니다.

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
        DroneSopUserSdwtChannel.objects.filter(is_active=True)
        .exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .values_list("target_user_sdwt_prod", flat=True)
        .distinct()
        .order_by("target_user_sdwt_prod")
    )

    # -----------------------------------------------------------------------------
    # 2) 공백 제거 및 반환
    # -----------------------------------------------------------------------------
    return _normalize_str_list(rows)


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
    normalized = _normalize_str(target_user_sdwt_prod)
    if not normalized:
        return None

    # -----------------------------------------------------------------------------
    # 2) 비어있지 않은 키 조회
    # -----------------------------------------------------------------------------
    key = (
        DroneSopUserSdwtChannel.objects.filter(target_user_sdwt_prod=normalized, is_active=True)
        .values_list("jira_key", flat=True)
        .order_by("jira_key")
        .first()
    )
    normalized_key = _normalize_str(key)
    if normalized_key:
        return normalized_key
    # -----------------------------------------------------------------------------
    # 3) 기본값 반환
    # -----------------------------------------------------------------------------
    return None


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

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized_targets = _normalize_str_list(target_user_sdwt_prod_values)
    if not normalized_targets:
        return {}

    # -----------------------------------------------------------------------------
    # 2) 조회 및 매핑 생성
    # -----------------------------------------------------------------------------
    rows = DroneSopUserSdwtChannel.objects.filter(
        target_user_sdwt_prod__in=normalized_targets,
        is_active=True,
    ).values(
        "target_user_sdwt_prod",
        "jira_key",
    )
    mapping: dict[str, str | None] = {}
    for row in rows:
        sdwt = _normalize_str(row.get("target_user_sdwt_prod"))
        if not sdwt:
            continue
        normalized_key = _normalize_str(row.get("jira_key"))
        mapping[sdwt] = normalized_key

    return mapping


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
    normalized = _normalize_str(user_sdwt_prod)
    if not normalized:
        return []

    # -----------------------------------------------------------------------------
    # 2) 쿼리 실행 및 결과 정리
    # -----------------------------------------------------------------------------
    rows = run_query(
        """
        SELECT DISTINCT line AS line_id
        FROM {table}
        WHERE user_sdwt_prod = %s
          AND line IS NOT NULL
          AND line <> ''
        ORDER BY line_id
        """.format(table=LINE_SDWT_TABLE_NAME),
        [normalized],
    )
    return _normalize_str_list([row.get("line_id") for row in rows])


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
    return _normalize_str_list([row.get("line_id") for row in rows])


def _normalize_bucket_value(value: Any) -> Optional[str]:
    """날짜/시간 버킷 값을 ISO-like 문자열로 정규화합니다.

    인자:
        value: datetime/date/str/기타 입력.

    반환:
        ISO-like 문자열 또는 None.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) None 처리
    # -----------------------------------------------------------------------------
    if value is None:
        return None

    # -----------------------------------------------------------------------------
    # 2) datetime/date 타입 처리
    # -----------------------------------------------------------------------------
    if isinstance(value, datetime):
        return value.replace(minute=0, second=0, microsecond=0).isoformat()

    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()

    # -----------------------------------------------------------------------------
    # 3) 문자열 처리 및 ISO 변환 시도
    # -----------------------------------------------------------------------------
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        candidate = cleaned
        if " " in candidate and "T" not in candidate:
            candidate = candidate.replace(" ", "T")

        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.replace(minute=0, second=0, microsecond=0).isoformat()
        except ValueError:
            return cleaned

    return None


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
        for candidate in DIMENSION_CANDIDATES
        if (resolved := find_column(column_names, candidate))
    }

    # -----------------------------------------------------------------------------
    # 3) WHERE 절 구성
    # -----------------------------------------------------------------------------
    line_filter_result = build_line_filters(column_names, normalized_line_id)
    where_clause, query_params = _build_where_clause(
        timestamp_column,
        line_filter_result["filters"],
        line_filter_result["params"],
        from_value,
        to_value,
    )

    # -----------------------------------------------------------------------------
    # 4) 합계(총합) 조회
    # -----------------------------------------------------------------------------
    totals_rows = run_query(
        _build_totals_query(table_name, timestamp_column, send_jira_column, where_clause),
        query_params,
    )
    totals = [_normalize_daily_row(row) for row in totals_rows]

    # -----------------------------------------------------------------------------
    # 5) 분해(차원별) 조회
    # -----------------------------------------------------------------------------
    breakdowns: Dict[str, List[Dict[str, Any]]] = {}
    for dimension_key, column_name in dimension_columns.items():
        rows = run_query(
            _build_breakdown_query(
                table_name,
                timestamp_column,
                column_name,
                send_jira_column,
                where_clause,
            ),
            query_params,
        )
        breakdowns[dimension_key] = [_normalize_breakdown_row(row) for row in rows]

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


def _build_where_clause(
    timestamp_column: str,
    line_filters: Sequence[str],
    line_params: Sequence[Any],
    from_value: Optional[str],
    to_value: Optional[str],
) -> tuple[str, List[Any]]:
    """라인/날짜 조건을 합쳐 WHERE 절을 구성합니다.

    인자:
        timestamp_column: 타임스탬프 컬럼명.
        line_filters: 라인 필터 조건 문자열 목록.
        line_params: 라인 필터 바인드 파라미터 목록.
        from_value: 시작 날짜(ISO).
        to_value: 종료 날짜(ISO).

    반환:
        (where_clause, params) 튜플.

    부작용:
        없음. 순수 문자열/파라미터 구성입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 조건/파라미터 구성
    # -----------------------------------------------------------------------------
    conditions = list(line_filters)
    params = list(line_params)

    # -----------------------------------------------------------------------------
    # 2) 날짜 조건 추가
    # -----------------------------------------------------------------------------
    date_conditions, date_params = build_date_range_filters(timestamp_column, from_value, to_value)
    conditions.extend(date_conditions)
    params.extend(date_params)

    # -----------------------------------------------------------------------------
    # 3) WHERE 절 문자열 생성
    # -----------------------------------------------------------------------------
    clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return clause, params


def _build_totals_query(
    table_name: str,
    timestamp_column: str,
    send_jira_column: Optional[str],
    where_clause: str,
) -> str:
    """시간 단위 합계 쿼리를 생성합니다.

    인자:
        table_name: 대상 테이블명.
        timestamp_column: 타임스탬프 컬럼명.
        send_jira_column: send_jira 컬럼명(없으면 None).
        where_clause: WHERE 절 문자열.

    반환:
        SQL 문자열.

    부작용:
        없음. 순수 문자열 생성입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) SELECT 컬럼 구성
    # -----------------------------------------------------------------------------
    bucket_expr = f"DATE_TRUNC('hour', {timestamp_column})"
    totals_select = [f"{bucket_expr} AS bucket", "COUNT(*) AS row_count"]
    if send_jira_column:
        totals_select.append(
            "SUM(CASE WHEN {col} > 0 THEN 1 ELSE 0 END) AS send_jira_count".format(col=send_jira_column)
        )
    else:
        totals_select.append("0 AS send_jira_count")

    # -----------------------------------------------------------------------------
    # 2) SQL 문자열 반환
    # -----------------------------------------------------------------------------
    return """
        SELECT {select_clause}
        FROM {table}
        {where_clause}
        GROUP BY bucket
        ORDER BY bucket ASC
    """.format(
        select_clause=", ".join(totals_select),
        table=table_name,
        where_clause=where_clause,
    )


def _build_breakdown_query(
    table_name: str,
    timestamp_column: str,
    dimension_column: str,
    send_jira_column: Optional[str],
    where_clause: str,
) -> str:
    """시간 단위 분해(차원별) 쿼리를 생성합니다.

    인자:
        table_name: 대상 테이블명.
        timestamp_column: 타임스탬프 컬럼명.
        dimension_column: 분해 기준 컬럼명.
        send_jira_column: send_jira 컬럼명(없으면 None).
        where_clause: WHERE 절 문자열.

    반환:
        SQL 문자열.

    부작용:
        없음. 순수 문자열 생성입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) SELECT 컬럼 구성
    # -----------------------------------------------------------------------------
    bucket_expr = f"DATE_TRUNC('hour', {timestamp_column})"
    select_parts = [
        f"{bucket_expr} AS bucket",
        f"COALESCE(CAST({dimension_column} AS TEXT), 'Unspecified') AS category",
        "COUNT(*) AS row_count",
    ]

    if send_jira_column:
        select_parts.append(
            "SUM(CASE WHEN {col} > 0 THEN 1 ELSE 0 END) AS send_jira_count".format(col=send_jira_column)
        )
    else:
        select_parts.append("0 AS send_jira_count")

    # -----------------------------------------------------------------------------
    # 2) SQL 문자열 반환
    # -----------------------------------------------------------------------------
    return """
        SELECT {select_clause}
        FROM {table}
        {where_clause}
        GROUP BY bucket, category
        ORDER BY bucket ASC, category ASC
    """.format(
        select_clause=", ".join(select_parts),
        table=table_name,
        where_clause=where_clause,
    )


def _normalize_daily_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """합계 row를 응답 형식으로 정규화합니다.

    인자:
        row: 원본 row dict.

    반환:
        정규화된 합계 dict.

    부작용:
        없음. 순수 변환입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 버킷/카운트 정규화
    # -----------------------------------------------------------------------------
    date_str = _normalize_bucket_value(row.get("bucket") or row.get("day") or row.get("date"))
    return {
        "date": date_str,
        "rowCount": to_int(row.get("row_count", 0)),
        "sendJiraCount": to_int(row.get("send_jira_count", 0)),
    }


def _normalize_breakdown_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """분해 row를 응답 형식으로 정규화합니다.

    인자:
        row: 원본 row dict.

    반환:
        정규화된 분해 dict.

    부작용:
        없음. 순수 변환입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 날짜 버킷 정규화
    # -----------------------------------------------------------------------------
    date_str = _normalize_bucket_value(row.get("bucket") or row.get("day") or row.get("date"))

    # -----------------------------------------------------------------------------
    # 2) 카테고리 정규화
    # -----------------------------------------------------------------------------
    category = row.get("category") or row.get("dimension") or "Unspecified"
    if not isinstance(category, str) or not category.strip():
        category = "Unspecified"

    return {
        "date": date_str,
        "category": category.strip() if isinstance(category, str) else str(category),
        "rowCount": to_int(row.get("row_count", 0)),
        "sendJiraCount": to_int(row.get("send_jira_count", 0)),
    }
