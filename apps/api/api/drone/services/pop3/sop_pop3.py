# =============================================================================
# 모듈: Drone SOP POP3 수집 서비스
# 주요 기능: POP3/더미 메일 수집, SOP upsert, 정리 작업
# 주요 가정: 오프라인 개발은 더미 메일 API로 대체합니다.
# =============================================================================
"""Drone SOP POP3 수집 헬퍼 모듈입니다."""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from django.utils import timezone

from ... import selectors
from ..jira.config import DroneCtttmConfig
from ..jira.ctttm import enrich_rows_with_ctttm_urls as _enrich_rows_with_ctttm_urls
from ..shared.notify_resolver import (
    UserSdwtProdMapIndex,
    load_user_sdwt_prod_map_index,
)
from ..shared.utils import _advisory_lock
from .config import (
    DroneSopPop3Config,
    DroneSopPop3IngestResult,
    NeedToSendRule,
)
from .defectmap_sidecar import post_defect_png_sidecar_if_needed
from .dummy_mail import (
    delete_dummy_mail_messages as _delete_dummy_mail_messages,
    list_dummy_mail_messages as _list_dummy_mail_messages,
)
from .mailbox import (
    authenticate_pop3_client as _authenticate_pop3_client,
    close_pop3_client as _close_pop3_client,
    create_pop3_client as _create_pop3_client,
    decode_header_value as _decode_header_value,
    extract_html_from_email as _extract_html_from_email,
    list_pop3_message_numbers as _list_pop3_message_numbers,
    mark_pop3_message_for_deletion as _mark_pop3_message_for_deletion,
    retrieve_pop3_message as _retrieve_pop3_message,
    rollback_pop3_deletions as _rollback_pop3_deletions,
    subject_matches as _subject_matches,
)
from .persistence import (
    safe_prune_rows as _safe_prune_rows,
    upsert_drone_sop_rows as _upsert_drone_sop_rows,
)
from .row_builder import build_drone_sop_row as _build_drone_sop_row

logger = logging.getLogger(__name__)


def build_drone_sop_row(
    *,
    html: str,
    early_inform_map: dict[tuple[str, str], Optional[str]],
    user_sdwt_map_index: UserSdwtProdMapIndex | None = None,
    needtosend_rule_cache: dict[str, NeedToSendRule | None] | None = None,
) -> Optional[dict[str, Any]]:
    """메일 HTML에서 Drone SOP row를 생성하는 공개 함수입니다."""

    row = _build_drone_sop_row(
        html=html,
        early_inform_map=early_inform_map,
        user_sdwt_map_index=user_sdwt_map_index,
        needtosend_rule_cache=needtosend_rule_cache,
    )
    if row is not None:
        _enrich_rows_with_ctttm_urls(rows=[row], config=DroneCtttmConfig.from_settings())
    return row


def upsert_drone_sop_rows(*, rows: Sequence[dict[str, Any]]) -> int:
    """Drone SOP row를 upsert 하는 공개 함수입니다."""

    return _upsert_drone_sop_rows(rows=rows)


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
        row = _build_drone_sop_row(
            html=html,
            early_inform_map=early_inform_map,
            user_sdwt_map_index=user_sdwt_map_index,
            needtosend_rule_cache=needtosend_rule_cache,
        )
        if row is not None:
            _enrich_rows_with_ctttm_urls(rows=[row], config=DroneCtttmConfig.from_settings())
        return row
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


def _post_sidecar_and_upsert_row(
    *,
    row: dict[str, Any],
    config: DroneSopPop3Config,
    error_label: str,
) -> int:
    """defectmap sidecar 전송 후 row upsert 결과를 반환합니다."""

    # 임시 부가기능: defectmap 전송(실패해도 메인 수집 흐름은 계속 진행합니다).
    post_defect_png_sidecar_if_needed(
        row=row,
        config=config,
        scanned_at=timezone.now(),
        error_label=error_label,
    )
    return _upsert_drone_sop_row_or_zero(row=row, error_label=error_label)


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

        upserted_count = _post_sidecar_and_upsert_row(
            row=parsed,
            config=config,
            error_label=f"dummy mail id={message.get('id')} subject={subject!r}",
        )
        matched += 1
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

    pruned = _safe_prune_rows(
        days=config.retention_days,
        batch_size=config.prune_batch_size,
        only_when_upserted=False,
        upserted_rows=upserted,
    )
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

    client = _create_pop3_client(config=config)
    matched = 0
    upserted = 0
    deleted = 0

    try:
        _authenticate_pop3_client(client=client, config=config)
        for msg_num in _list_pop3_message_numbers(client=client):
            msg = _retrieve_pop3_message(client=client, msg_num=msg_num)
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

            upserted_count = _post_sidecar_and_upsert_row(
                row=parsed,
                config=config,
                error_label=f"POP3 message #{msg_num} subject={subject!r}",
            )
            matched += 1
            upserted += upserted_count
            if upserted_count <= 0:
                continue

            try:
                _mark_pop3_message_for_deletion(client=client, msg_num=msg_num)
                deleted += 1
            except Exception:
                logger.exception("Failed to mark POP3 message #%s for deletion", msg_num)

        pruned = _safe_prune_rows(
            days=config.retention_days,
            batch_size=config.prune_batch_size,
            only_when_upserted=True,
            upserted_rows=upserted,
        )
        return DroneSopPop3IngestResult(
            matched_mails=matched,
            upserted_rows=upserted,
            deleted_mails=deleted,
            pruned_rows=pruned,
        )
    except Exception:
        logger.exception("Drone SOP POP3 ingest failed; rolling back POP3 deletions via rset()")
        try:
            _rollback_pop3_deletions(client=client)
        except Exception:
            logger.debug("POP3 rset failed")
        raise
    finally:
        try:
            _close_pop3_client(client=client)
        except Exception:
            pass


def run_drone_sop_pop3_ingest_from_env() -> DroneSopPop3IngestResult:
    """Drone SOP POP3 수집을 실행합니다.

    반환:
        DroneSopPop3IngestResult 결과 객체.

    부작용:
        - POP3(또는 더미 메일 API)에서 메일을 읽고 삭제합니다.
        - drone_sop 테이블에 upsert 합니다.
        - 보관 일수 초과 데이터는 상태와 무관하게 정리합니다.

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


__all__ = [
    "build_drone_sop_row",
    "run_drone_sop_pop3_ingest_from_env",
    "upsert_drone_sop_rows",
]
