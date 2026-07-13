# =============================================================================
# 모듈 설명: account 도메인 URL 라우팅을 제공합니다.
# - 주요 대상: 소속/권한/개요 관련 API
# - 불변 조건: 상위 URLConf에서 /api/v1/account/ 프리픽스를 제공합니다.
# =============================================================================

"""계정 도메인 URL 라우팅 모음.

- 주요 대상: 소속/권한/개요 관련 API
- 주요 엔드포인트/클래스: AccountOverviewView 등
- 가정/불변 조건: 상위 URLConf에서 /api/v1/account/ 프리픽스를 제공함
"""
from __future__ import annotations

from django.urls import path

from .views import (
    AccountAccessAuditLogView,
    AccountAccessPolicyRuleView,
    AccountAccessRequestView,
    AccountAccessUserDecisionView,
    AccountAccessUserView,
    AccountAppAccessMatrixView,
    AccountAffiliationApprovalView,
    AccountAffiliationMembersView,
    AccountAffiliationView,
    AccountAffiliationRequestListView,
    AccountAffiliationReconfirmView,
    AccountExternalAffiliationSyncView,
    AccountGrantListView,
    AccountGrantView,
    AccountOverviewView,
    AccountPortalAccessApprovalView,
    AccountPortalAccessView,
    AccountUserPoolView,
    LineSdwtOptionsView,
)

urlpatterns = [
    path("overview", AccountOverviewView.as_view(), name="account-overview"),
    path("affiliation", AccountAffiliationView.as_view(), name="account-affiliation"),
    path(
        "affiliation/approve",
        AccountAffiliationApprovalView.as_view(),
        name="account-affiliation-approve",
    ),
    path(
        "affiliation/requests",
        AccountAffiliationRequestListView.as_view(),
        name="account-affiliation-requests",
    ),
    path(
        "affiliation/members",
        AccountAffiliationMembersView.as_view(),
        name="account-affiliation-members",
    ),
    path(
        "affiliation/reconfirm",
        AccountAffiliationReconfirmView.as_view(),
        name="account-affiliation-reconfirm",
    ),
    path("portal-access", AccountPortalAccessView.as_view(), name="account-portal-access"),
    path("access/request", AccountAccessRequestView.as_view(), name="account-access-request"),
    path(
        "portal-access/approvals",
        AccountPortalAccessApprovalView.as_view(),
        name="account-portal-access-approvals",
    ),
    path("access/users", AccountAccessUserView.as_view(), name="account-access-users"),
    path("access/matrix", AccountAppAccessMatrixView.as_view(), name="account-access-matrix"),
    path(
        "access/users/<int:user_id>/decision",
        AccountAccessUserDecisionView.as_view(),
        name="account-access-user-decision",
    ),
    path("access/policy-rules", AccountAccessPolicyRuleView.as_view(), name="account-access-policy-rules"),
    path(
        "access/policy-rules/<int:rule_id>",
        AccountAccessPolicyRuleView.as_view(),
        name="account-access-policy-rule-detail",
    ),
    path("access/audit-logs", AccountAccessAuditLogView.as_view(), name="account-access-audit-logs"),
    path(
        "external-affiliations/sync",
        AccountExternalAffiliationSyncView.as_view(),
        name="account-external-affiliation-sync",
    ),
    path("access/grants", AccountGrantView.as_view(), name="account-access-grant"),
    path("access/manageable", AccountGrantListView.as_view(), name="account-access-manageable"),
    path("users", AccountUserPoolView.as_view(), name="account-users"),
    path("line-sdwt-options", LineSdwtOptionsView.as_view(), name="account-line-sdwt-options"),
]
