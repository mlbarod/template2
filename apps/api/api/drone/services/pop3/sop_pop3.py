# =============================================================================
# 모듈: Drone SOP POP3 수집 서비스
# 주요 기능: POP3/더미 메일 수집, SOP upsert, 정리 작업
# 주요 가정: 오프라인 개발은 더미 메일 API로 대체합니다.
# =============================================================================
"""Drone SOP POP3 수집 헬퍼 모듈입니다."""

from __future__ import annotations

import logging
import poplib
from datetime import timedelta
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.policy import default
from typing import Any, Optional, Sequence

import requests
from bs4 import BeautifulSoup

from django.db import connection, transaction
from django.utils import timezone

from ... import selectors
from ...models import DroneSOP, build_sop_key
from ..shared.notify_resolver import (
    UserSdwtProdMapIndex,
    load_user_sdwt_prod_map_index,
    resolve_target_user_sdwt_prod,
)
from ..shared.utils import _advisory_lock
from .config import (
    DEFAULT_NEEDTOSEND_RULE,
    DroneSopPop3Config,
    DroneSopPop3IngestResult,
    NeedToSendRule,
    _as_int_bool,
)
from .defectmap_sidecar import post_defect_png_sidecar_if_needed

logger = logging.getLogger(__name__)


def _normalize_blank(value: Any) -> Any:
    """빈 문자열을 None으로 정규화합니다.

    인자:
        value: 원본 값.

    반환:
        None 또는 원본/변환 값.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -------------------------------------------------------------------------
    # 1) None/빈 문자열 처리
    # -------------------------------------------------------------------------
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _sanitize_defect_url(value: Any) -> str | None:
    """결함 URL 값을 정규화합니다.

    인자:
        value: 원본 URL 값.

    반환:
        정규화된 URL 또는 None.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 문자열 정리 및 따옴표 제거
    # -------------------------------------------------------------------------
    if value is None:
        return None
    cleaned = str(value).replace('"', "").strip()
    return cleaned or None


def _extract_first_data_tag(html: str) -> dict[str, str]:
    """HTML에서 첫 번째 <data> 태그의 자식 정보를 추출합니다.

    인자:
        html: HTML 문자열.

    반환:
        태그명 → 텍스트 값을 담은 dict.

    부작용:
        없음. 파싱만 수행합니다.
    """

    # -------------------------------------------------------------------------
    # 1) HTML 파싱 및 data 태그 탐색
    # -------------------------------------------------------------------------
    soup = BeautifulSoup(html, "html.parser")
    data = soup.find("data")
    if not data:
        return {}
    # -------------------------------------------------------------------------
    # 2) 직계 자식 태그 텍스트 추출
    # -------------------------------------------------------------------------
    parsed: dict[str, str] = {}
    for child in data.find_all(recursive=False):
        if not child.name:
            continue
        parsed[str(child.name).lower()] = child.get_text(strip=True)
    return parsed


def _strip_prefix_num(value: Optional[str]) -> Optional[int]:
    """접두사 2자를 제외한 숫자 부분을 정수로 변환합니다.

    인자:
        value: 접두사가 포함된 문자열.

    반환:
        숫자 부분 정수 또는 None.

    부작용:
        없음. 순수 파싱입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 길이/형식 검증
    # -------------------------------------------------------------------------
    if not value or len(value) <= 2:
        return None
    numeric = value[2:]
    return int(numeric) if numeric.isdigit() else None


def _compute_needtosend_default(row: dict[str, Any]) -> int:
    """기본 needtosend 계산 로직을 적용합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).

    반환:
        needtosend 값(0/1).

    부작용:
        없음. 순수 계산입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 기본 규칙 적용
    # -------------------------------------------------------------------------
    return DEFAULT_NEEDTOSEND_RULE.compute(row)


def _get_needtosend_rule_for_target(
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
    # 1) 캐시 조회
    # -------------------------------------------------------------------------
    cached = cache.get(target_user_sdwt_prod)
    if cached is not None or target_user_sdwt_prod in cache:
        return cached

    # -------------------------------------------------------------------------
    # 2) DB 규칙 조회 후 캐시 적재
    # -------------------------------------------------------------------------
    rule_model = selectors.get_drone_sop_needtosend_rule_by_target(
        target_user_sdwt_prod=target_user_sdwt_prod,
    )
    if not rule_model:
        cache[target_user_sdwt_prod] = None
        return None

    rule = NeedToSendRule(
        comment_last_at=str(rule_model.comment_last_at or "").strip(),
        ignore_sample_type=bool(rule_model.ignore_sample_type),
    )
    cache[target_user_sdwt_prod] = rule
    return rule


def _compute_needtosend_by_target(
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
        없음. 순수 계산입니다.
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
    # 2) DB 규칙 적용 (없으면 기본 규칙)
    # -------------------------------------------------------------------------
    rule = _get_needtosend_rule_for_target(target_user_sdwt_prod=normalized, cache=rule_cache)
    if rule:
        return rule.compute(row)
    return _compute_needtosend_default(row)


def _extract_html_from_email(msg: Any) -> Optional[str]:
    """이메일 메시지에서 HTML 본문을 추출합니다.

    인자:
        msg: email.message 객체.

    반환:
        HTML 문자열 또는 None.

    부작용:
        없음. 순수 추출입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 멀티파트 메시지에서 HTML 파트 탐색
    # -------------------------------------------------------------------------
    html = next(
        (part.get_content() for part in msg.walk() if part.get_content_type() == "text/html"),
        None,
    )
    if html:
        return html
    # -------------------------------------------------------------------------
    # 2) 단일 파트 HTML 처리
    # -------------------------------------------------------------------------
    if getattr(msg, "get_content_type", lambda: None)() == "text/html":
        return msg.get_content()
    return None


def _decode_header_value(raw_value: Any) -> str:
    """메일 헤더 값을 디코딩합니다.

    인자:
        raw_value: 헤더 원본 값.

    반환:
        디코딩된 문자열.

    부작용:
        없음. 순수 디코딩입니다.
    """

    # -------------------------------------------------------------------------
    # 1) None 처리 및 디코딩 시도
    # -------------------------------------------------------------------------
    if raw_value is None:
        return ""
    try:
        return str(make_header(decode_header(str(raw_value))))
    except Exception:
        return str(raw_value)


def _subject_matches(subject: str, include_subjects: Sequence[str]) -> bool:
    """제목이 허용된 prefix로 시작하는지 확인합니다.

    인자:
        subject: 메일 제목.
        include_subjects: 허용 제목 목록.

    반환:
        포함 여부(boolean).

    부작용:
        없음. 순수 비교입니다.
    """

    # -------------------------------------------------------------------------
    # 1) 제목 정규화 및 prefix 매칭
    # -------------------------------------------------------------------------
    normalized_subject = subject.strip().lower()
    if not normalized_subject:
        return False
    for prefix in include_subjects:
        if not isinstance(prefix, str):
            continue
        normalized_prefix = prefix.strip().lower()
        if not normalized_prefix:
            continue
        if normalized_subject.startswith(normalized_prefix):
            return True
    return False


def _build_drone_sop_row(
    *,
    html: str,
    early_inform_map: dict[tuple[str, str], Optional[str]],
    user_sdwt_map_index: UserSdwtProdMapIndex | None = None,
    needtosend_rule_cache: dict[str, NeedToSendRule | None] | None = None,
) -> Optional[dict[str, Any]]:
    """메일 HTML에서 Drone SOP row를 생성합니다.

    인자:
        html: 메일 HTML 본문.
        early_inform_map: (user_sdwt_prod, main_step) → custom_end_step 매핑.
        user_sdwt_map_index: target_user_sdwt_prod 매핑 인덱스(옵션).
        needtosend_rule_cache: target_user_sdwt_prod 규칙 캐시(옵션).

    반환:
        Drone SOP row dict 또는 None.

    부작용:
        없음. 순수 파싱입니다.
    """

    # -------------------------------------------------------------------------
    # 1) <data> 태그 파싱
    # -------------------------------------------------------------------------
    data = _extract_first_data_tag(html)
    if not data:
        return None

    # -------------------------------------------------------------------------
    # 2) 필드 정규화 및 row 구성
    # -------------------------------------------------------------------------
    normalized = {key: _normalize_blank(value) for key, value in data.items()}
    knox_value = normalized.get("knox_id") or normalized.get("knoxid")

    row: dict[str, Any] = {
        "line_id": normalized.get("line_id"),
        "sdwt_prod": normalized.get("sdwt_prod"),
        "sample_type": normalized.get("sample_type"),
        "sample_group": normalized.get("sample_group"),
        "eqp_id": normalized.get("eqp_id"),
        "chamber_ids": (str(normalized.get("chamber_ids") or "").replace(",", "")) or None,
        "lot_id": normalized.get("lot_id"),
        "proc_id": normalized.get("proc_id"),
        "ppid": normalized.get("ppid"),
        "main_step": normalized.get("main_step"),
        "metro_current_step": normalized.get("metro_current_step"),
        "metro_steps": normalized.get("metro_steps"),
        "metro_end_step": normalized.get("metro_end_step"),
        "status": normalized.get("status"),
        "knox_id": knox_value,
        "user_sdwt_prod": normalized.get("user_sdwt_prod"),
        "comment": normalized.get("comment"),
        "defect_url": _sanitize_defect_url(normalized.get("defect_url")),
        "defect_png_url": _sanitize_defect_url(normalized.get("defect_png_url")),
        "instant_inform": 0,
    }
    # -------------------------------------------------------------------------
    # 3) sop_key 생성
    # -------------------------------------------------------------------------
    row["sop_key"] = build_sop_key(
        line_id=row.get("line_id"),
        eqp_id=row.get("eqp_id"),
        chamber_ids=row.get("chamber_ids"),
        lot_id=row.get("lot_id"),
        main_step=row.get("main_step"),
    )

    # -------------------------------------------------------------------------
    # 4) 조기 알림 기준 custom_end_step 적용
    # -------------------------------------------------------------------------
    user_sdwt_prod = str(row.get("user_sdwt_prod") or "").strip()
    main_step = str(row.get("main_step") or "").strip()
    custom_end_step = early_inform_map.get((user_sdwt_prod, main_step))
    if custom_end_step is not None:
        row["custom_end_step"] = custom_end_step
        current_num = _strip_prefix_num(str(row.get("metro_current_step") or "").strip() or None)
        end_num = _strip_prefix_num(str(custom_end_step).strip() or None)
        if current_num is not None and end_num is not None and current_num >= end_num:
            row["status"] = "COMPLETE"

    # -------------------------------------------------------------------------
    # 5) needtosend 계산
    # -------------------------------------------------------------------------
    if user_sdwt_map_index is None:
        user_sdwt_map_index = load_user_sdwt_prod_map_index()
    if needtosend_rule_cache is None:
        needtosend_rule_cache = {}

    target_user_sdwt_prod = resolve_target_user_sdwt_prod(row=row, index=user_sdwt_map_index)
    row["target_user_sdwt_prod"] = target_user_sdwt_prod
    row["needtosend"] = _compute_needtosend_by_target(
        row=row,
        target_user_sdwt_prod=target_user_sdwt_prod,
        rule_cache=needtosend_rule_cache,
    )
    return row


def _list_dummy_mail_messages(*, url: str, timeout: int) -> list[dict[str, Any]]:
    """더미 메일 API에서 메시지 목록을 조회합니다.

    인자:
        url: 더미 메일 API URL.
        timeout: 요청 타임아웃(초).

    반환:
        메시지 dict 리스트.

    부작용:
        외부 HTTP 요청이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 메시지 목록 조회
    # -------------------------------------------------------------------------
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    messages = data.get("messages")
    if not isinstance(messages, list):
        return []
    # -------------------------------------------------------------------------
    # 2) dict 필터링 및 정렬
    # -------------------------------------------------------------------------
    normalized: list[dict[str, Any]] = []
    for entry in messages:
        if isinstance(entry, dict):
            normalized.append(entry)
    normalized.sort(key=lambda item: int(item.get("id") or 0))
    return normalized


def _delete_dummy_mail_messages(*, url: str, mail_ids: Sequence[int], timeout: int) -> int:
    """더미 메일 API에서 메시지를 삭제합니다.

    인자:
        url: 더미 메일 API URL.
        mail_ids: 삭제할 메시지 ID 목록.
        timeout: 요청 타임아웃(초).

    반환:
        삭제된 메시지 수.

    부작용:
        외부 HTTP 요청이 발생합니다.
    """

    # -------------------------------------------------------------------------
    # 1) 메시지 삭제 요청
    # -------------------------------------------------------------------------
    deleted = 0
    for mail_id in mail_ids:
        resp = requests.delete(f"{url.rstrip('/')}/{mail_id}", timeout=timeout)
        if resp.status_code in {200, 204}:
            deleted += 1
    return deleted


def _upsert_drone_sop_rows(*, rows: Sequence[dict[str, Any]]) -> int:
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
        "defect_png_url",
        "instant_inform",
        "needtosend",
        "custom_end_step",
    ]
    conflict_cols = ["sop_key"]
    exclude_update_cols = {"needtosend", "comment", "instant_inform", "sop_key"}

    placeholders = ",".join(["%s"] * len(insert_cols))
    quoted_table = f'"{DroneSOP._meta.db_table}"'
    quoted_insert_cols = ", ".join(f'"{col}"' for col in insert_cols)
    conflict_target = ", ".join(f'"{col}"' for col in conflict_cols)

    update_parts: list[str] = []
    for col in insert_cols:
        if col in exclude_update_cols:
            continue
        if col == "target_user_sdwt_prod":
            update_parts.append(f'"{col}" = EXCLUDED."{col}"')
            continue
        update_parts.append(
            f'"{col}" = COALESCE(EXCLUDED."{col}", {quoted_table}."{col}")'
        )
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
        for col in insert_cols:
            value = row.get(col)
            if value is None and col == "instant_inform":
                value = 0
            values.append(value)
        args.append(tuple(values))
    # -------------------------------------------------------------------------
    # 4) SQL 실행
    # -------------------------------------------------------------------------
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.executemany(sql, args)

    return len(rows)


def _prune_old_drone_sop_rows(*, days: int) -> int:
    """지정 일수보다 오래된 DroneSOP 레코드를 정리합니다.

    인자:
        days: 보관 일수.

    반환:
        삭제된 레코드 수.

    부작용:
        DB 삭제가 발생합니다.
    """

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = DroneSOP.objects.filter(created_at__lt=cutoff).delete()
    return int(deleted or 0)


def _safe_prune_rows(*, days: int, only_when_upserted: bool, upserted_rows: int) -> int:
    """오래된 DroneSOP 행 정리를 안전하게 수행합니다."""

    if only_when_upserted and upserted_rows <= 0:
        return 0
    try:
        return _prune_old_drone_sop_rows(days=days)
    except Exception:
        logger.exception("Failed to prune old DroneSOP rows")
        return 0


def _parse_drone_sop_row_or_none(
    *,
    html: str,
    early_inform_map: dict[tuple[str, str], Optional[str]],
    user_sdwt_map_index: UserSdwtProdMapIndex,
    needtosend_rule_cache: dict[str, NeedToSendRule | None],
    error_label: str,
) -> Optional[dict[str, Any]]:
    """HTML 본문을 Drone SOP row로 파싱합니다."""

    try:
        return _build_drone_sop_row(
            html=html,
            early_inform_map=early_inform_map,
            user_sdwt_map_index=user_sdwt_map_index,
            needtosend_rule_cache=needtosend_rule_cache,
        )
    except Exception:
        logger.exception("Failed to parse %s", error_label)
        return None


def _upsert_drone_sop_row_or_zero(*, row: dict[str, Any], error_label: str) -> int:
    """Drone SOP row upsert를 수행하고 실패 시 0을 반환합니다."""

    try:
        return _upsert_drone_sop_rows(rows=[row])
    except Exception:
        logger.exception("Failed to upsert %s", error_label)
        return 0


def _run_dummy_mode_ingest(
    *,
    config: DroneSopPop3Config,
    early_inform_map: dict[tuple[str, str], Optional[str]],
    user_sdwt_map_index: UserSdwtProdMapIndex,
    needtosend_rule_cache: dict[str, NeedToSendRule | None],
) -> DroneSopPop3IngestResult:
    """더미 메일 API 기반 수집을 실행합니다."""

    if not config.dummy_mail_messages_url:
        raise ValueError("DRONE_SOP_DUMMY_MAIL_MESSAGES_URL 미설정")

    matched = 0
    upserted = 0
    delete_targets: list[int] = []
    messages = _list_dummy_mail_messages(url=config.dummy_mail_messages_url, timeout=config.timeout)
    for message in messages:
        subject = _decode_header_value(message.get("subject"))
        if not _subject_matches(subject, config.include_subjects):
            continue

        body_html = str(message.get("body_html") or message.get("body_text") or "")
        if not body_html:
            continue

        parsed = _parse_drone_sop_row_or_none(
            html=body_html,
            early_inform_map=early_inform_map,
            user_sdwt_map_index=user_sdwt_map_index,
            needtosend_rule_cache=needtosend_rule_cache,
            error_label=f"dummy mail id={message.get('id')} subject={subject!r}",
        )
        if not parsed:
            continue

        # 임시 부가기능: defectmap 전송(실패해도 메인 수집 흐름은 계속 진행합니다).
        post_defect_png_sidecar_if_needed(
            row=parsed,
            config=config,
            scanned_at=timezone.now(),
            error_label=f"dummy mail id={message.get('id')} subject={subject!r}",
        )
        matched += 1
        upserted_count = _upsert_drone_sop_row_or_zero(
            row=parsed,
            error_label=f"dummy mail id={message.get('id')} subject={subject!r}",
        )
        upserted += upserted_count
        if upserted_count <= 0:
            continue

        try:
            delete_targets.append(int(message.get("id")))
        except (TypeError, ValueError):
            continue

    if matched == 0:
        return DroneSopPop3IngestResult(
            matched_mails=0,
            upserted_rows=0,
            deleted_mails=0,
            pruned_rows=0,
        )

    pruned = _safe_prune_rows(days=90, only_when_upserted=False, upserted_rows=upserted)
    deleted = 0
    if delete_targets:
        deleted = _delete_dummy_mail_messages(
            url=config.dummy_mail_messages_url,
            mail_ids=delete_targets,
            timeout=config.timeout,
        )

    return DroneSopPop3IngestResult(
        matched_mails=matched,
        upserted_rows=upserted,
        deleted_mails=deleted,
        pruned_rows=pruned,
    )


def _run_pop3_mode_ingest(
    *,
    config: DroneSopPop3Config,
    early_inform_map: dict[tuple[str, str], Optional[str]],
    user_sdwt_map_index: UserSdwtProdMapIndex,
    needtosend_rule_cache: dict[str, NeedToSendRule | None],
) -> DroneSopPop3IngestResult:
    """실 POP3 기반 수집을 실행합니다."""

    if not config.host or not config.username or not config.password:
        raise ValueError("POP3 connection info is incomplete (host/username/password required)")

    client_cls = poplib.POP3_SSL if config.use_ssl else poplib.POP3
    client = client_cls(config.host, config.port, timeout=config.timeout)
    matched = 0
    upserted = 0
    deleted = 0

    try:
        client.user(config.username)
        client.pass_(config.password)
        num_msgs = len(client.list()[1])
        for msg_num in range(1, num_msgs + 1):
            _, lines, _ = client.retr(msg_num)
            msg = BytesParser(policy=default).parsebytes(b"\r\n".join(lines))
            subject = _decode_header_value(msg.get("Subject"))
            if not _subject_matches(subject, config.include_subjects):
                continue

            html = _extract_html_from_email(msg)
            if not html:
                continue

            parsed = _parse_drone_sop_row_or_none(
                html=html,
                early_inform_map=early_inform_map,
                user_sdwt_map_index=user_sdwt_map_index,
                needtosend_rule_cache=needtosend_rule_cache,
                error_label=f"POP3 message #{msg_num} subject={subject!r}",
            )
            if not parsed:
                continue

            # 임시 부가기능: defectmap 전송(실패해도 메인 수집 흐름은 계속 진행합니다).
            post_defect_png_sidecar_if_needed(
                row=parsed,
                config=config,
                scanned_at=timezone.now(),
                error_label=f"POP3 message #{msg_num} subject={subject!r}",
            )
            matched += 1
            upserted_count = _upsert_drone_sop_row_or_zero(
                row=parsed,
                error_label=f"POP3 message #{msg_num} subject={subject!r}",
            )
            upserted += upserted_count
            if upserted_count <= 0:
                continue

            try:
                client.dele(msg_num)
                deleted += 1
            except Exception:
                logger.exception("Failed to mark POP3 message #%s for deletion", msg_num)

        pruned = _safe_prune_rows(days=90, only_when_upserted=True, upserted_rows=upserted)
        return DroneSopPop3IngestResult(
            matched_mails=matched,
            upserted_rows=upserted,
            deleted_mails=deleted,
            pruned_rows=pruned,
        )
    except Exception:
        logger.exception("Drone SOP POP3 ingest failed; rolling back POP3 deletions via rset()")
        try:
            client.rset()
        except Exception:
            logger.debug("POP3 rset failed")
        raise
    finally:
        try:
            client.quit()
        except Exception:
            pass


def run_drone_sop_pop3_ingest_from_env() -> DroneSopPop3IngestResult:
    """Drone SOP POP3 수집을 실행합니다.

    반환:
        DroneSopPop3IngestResult 결과 객체.

    부작용:
        - POP3(또는 더미 메일 API)에서 메일을 읽고 삭제합니다.
        - drone_sop 테이블에 upsert 합니다.
        - 90일 초과 데이터는 정리합니다.

    오류:
        설정 누락 또는 POP3 오류 시 예외가 발생할 수 있습니다.
    """

    # -------------------------------------------------------------------------
    # 1) 설정/캐시 준비
    # -------------------------------------------------------------------------
    config = DroneSopPop3Config.from_settings()
    early_inform_map = selectors.load_drone_sop_custom_end_step_map()
    user_sdwt_map_index = load_user_sdwt_prod_map_index()
    needtosend_rule_cache: dict[str, NeedToSendRule | None] = {}

    # -------------------------------------------------------------------------
    # 2) 락 획득 후 모드별 실행
    # -------------------------------------------------------------------------
    with _advisory_lock("drone_sop_pop3_ingest") as acquired:
        if not acquired:
            return DroneSopPop3IngestResult(skipped=True, skip_reason="already_running")

        if config.dummy_mode:
            return _run_dummy_mode_ingest(
                config=config,
                early_inform_map=early_inform_map,
                user_sdwt_map_index=user_sdwt_map_index,
                needtosend_rule_cache=needtosend_rule_cache,
            )
        return _run_pop3_mode_ingest(
            config=config,
            early_inform_map=early_inform_map,
            user_sdwt_map_index=user_sdwt_map_index,
            needtosend_rule_cache=needtosend_rule_cache,
        )
