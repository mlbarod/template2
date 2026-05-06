# =============================================================================
# 모듈 설명: emails 서비스 파사드(공개 API)를 제공합니다.
# - 주요 기능: 수집(POP3), 메일함 이동/삭제, RAG 인덱싱, 공용 메일 발송 호환 export
# - 불변 조건: 외부 호출/쓰기 로직은 서비스 계층에서만 수행합니다.
# =============================================================================

"""emails 서비스 파사드 모듈."""

from __future__ import annotations

from .constants import (
    EMAIL_CLASSIFICATION_CONFIRMED_USER,
    EMAIL_CLASSIFICATION_UNASSIGNED,
    EMAIL_RAG_INDEX_STATUS_INDEXED,
    EMAIL_RAG_INDEX_STATUS_PENDING,
    EMAIL_RAG_INDEX_STATUS_SKIPPED,
)
from .ingest import _parse_message_to_fields, ingest_pop3_mailbox, run_pop3_ingest, run_pop3_ingest_from_env
from .mail_api import MailSendError, requests, send_knox_mail_api
from .mailbox import get_mailbox_access_summary_for_user
from .ocr import claim_email_asset_ocr_tasks, update_email_asset_ocr_results
from .mutations import (
    SENT_MAILBOX_ID,
    bulk_delete_emails,
    claim_unassigned_emails_for_user,
    delete_single_email,
    move_emails_after_sender_affiliation_change,
    move_emails_for_user,
    move_emails_to_user_sdwt_prod,
    move_sender_emails_after,
)
from .query_filters import (
    build_email_filters,
    parse_datetime_value,
    parse_int,
    parse_mailbox_user_sdwt_prod,
)
from .rag import (
    enqueue_email_outbox,
    enqueue_rag_delete,
    enqueue_rag_index,
    enqueue_rag_index_for_emails,
    process_email_outbox_batch,
    register_email_to_rag,
    register_missing_rag_docs,
)
from .rag_exports import (
    RAG_INDEX_EMAILS,
    RAG_PUBLIC_GROUP,
    delete_rag_doc,
    insert_email_to_rag,
    resolve_rag_index_name,
)
from .storage import (
    delete_email_objects,
    load_email_asset,
    load_email_html,
    save_parsed_email,
    store_email_html_and_assets,
)

__all__ = [
    "MailSendError",
    "EMAIL_CLASSIFICATION_CONFIRMED_USER",
    "EMAIL_CLASSIFICATION_UNASSIGNED",
    "EMAIL_RAG_INDEX_STATUS_INDEXED",
    "EMAIL_RAG_INDEX_STATUS_PENDING",
    "EMAIL_RAG_INDEX_STATUS_SKIPPED",
    "RAG_INDEX_EMAILS",
    "RAG_PUBLIC_GROUP",
    "SENT_MAILBOX_ID",
    "_parse_message_to_fields",
    "bulk_delete_emails",
    "build_email_filters",
    "claim_email_asset_ocr_tasks",
    "claim_unassigned_emails_for_user",
    "delete_rag_doc",
    "delete_single_email",
    "enqueue_email_outbox",
    "enqueue_rag_delete",
    "enqueue_rag_index",
    "enqueue_rag_index_for_emails",
    "get_mailbox_access_summary_for_user",
    "ingest_pop3_mailbox",
    "insert_email_to_rag",
    "load_email_asset",
    "load_email_html",
    "move_emails_after_sender_affiliation_change",
    "move_emails_for_user",
    "move_emails_to_user_sdwt_prod",
    "move_sender_emails_after",
    "parse_datetime_value",
    "parse_int",
    "parse_mailbox_user_sdwt_prod",
    "process_email_outbox_batch",
    "register_email_to_rag",
    "register_missing_rag_docs",
    "requests",
    "resolve_rag_index_name",
    "run_pop3_ingest",
    "run_pop3_ingest_from_env",
    "save_parsed_email",
    "store_email_html_and_assets",
    "update_email_asset_ocr_results",
    "delete_email_objects",
    "send_knox_mail_api",
]
