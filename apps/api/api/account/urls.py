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
    AccountAffiliationApprovalView,
    AccountAffiliationMembersView,
    AccountAffiliationView,
    AccountAffiliationRequestListView,
    AccountAffiliationReconfirmView,
    AccountExternalAffiliationSyncView,
    AccountGrantListView,
    AccountGrantView,
    AccountOverviewView,
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
