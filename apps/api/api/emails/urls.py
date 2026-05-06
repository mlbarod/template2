# =============================================================================
# 모듈 설명: emails 기능의 라우팅을 정의합니다.
# - 주요 엔드포인트: inbox, sent, mailboxes, members, unassigned, ingest, outbox, bulk-delete, move, detail, html, assets, assets-ocr
# - 불변 조건: 비즈니스 로직 없이 View에 위임합니다.
# =============================================================================

from __future__ import annotations

from django.urls import path

from .views import (
    EmailAssetOcrClaimView,
    EmailAssetOcrUpdateView,
    EmailAssetView,
    EmailBulkDeleteView,
    EmailDetailView,
    EmailHtmlView,
    EmailIngestTriggerView,
    EmailInboxListView,
    EmailMailboxListView,
    EmailMailboxMembersView,
    EmailMailboxSummaryView,
    EmailMoveView,
    EmailOutboxProcessTriggerView,
    EmailSentListView,
    EmailUnassignedClaimView,
    EmailUnassignedSummaryView,
)

urlpatterns = [
    path("inbox/", EmailInboxListView.as_view(), name="emails-inbox"),
    path("sent/", EmailSentListView.as_view(), name="emails-sent"),
    path("mailboxes/", EmailMailboxListView.as_view(), name="emails-mailboxes"),
    path("mailboxes/summary/", EmailMailboxSummaryView.as_view(), name="emails-mailbox-summary"),
    path("mailboxes/members/", EmailMailboxMembersView.as_view(), name="emails-mailbox-members"),
    path("unassigned/", EmailUnassignedSummaryView.as_view(), name="emails-unassigned-summary"),
    path("unassigned/claim/", EmailUnassignedClaimView.as_view(), name="emails-unassigned-claim"),
    path("ingest/", EmailIngestTriggerView.as_view(), name="emails-ingest"),
    path("outbox/process/", EmailOutboxProcessTriggerView.as_view(), name="emails-outbox-process"),
    path("assets/ocr/claim/", EmailAssetOcrClaimView.as_view(), name="emails-assets-ocr-claim"),
    path("assets/ocr/update/", EmailAssetOcrUpdateView.as_view(), name="emails-assets-ocr-update"),
    path("bulk-delete/", EmailBulkDeleteView.as_view(), name="emails-bulk-delete"),
    path("move/", EmailMoveView.as_view(), name="emails-move"),
    path("<int:email_id>/", EmailDetailView.as_view(), name="emails-detail"),
    path("<int:email_id>/assets/<int:sequence>/", EmailAssetView.as_view(), name="emails-asset"),
    path("<int:email_id>/html/", EmailHtmlView.as_view(), name="emails-html"),
]
