# =============================================================================
# 모듈 설명: account 서비스 파사드(공용 진입점)를 제공합니다.
# - 주요 대상: 소속/권한/요청 처리 서비스 함수
# - 불변 조건: 서비스 구현은 services/* 모듈로 위임합니다.
# =============================================================================

"""account 서비스 파사드 모듈입니다."""

from __future__ import annotations

from .access import ensure_self_access, get_manageable_groups_with_members, grant_or_revoke_access
from .affiliations import (
    auto_approve_affiliation_from_snapshot,
    ensure_affiliation_option,
    get_affiliation_overview,
    get_affiliation_reconfirm_status,
    get_line_sdwt_options_payload,
    submit_affiliation_reconfirm_response,
)
from .affiliation_requests import (
    approve_affiliation_change,
    get_affiliation_change_requests,
    get_current_user_sdwt_prod_change,
    get_pending_user_sdwt_prod_change,
    reject_affiliation_change,
    request_affiliation_change,
)
from .email_claims import claim_unassigned_emails_for_user
from .external_sync import sync_external_affiliations
from .overview import get_account_overview
from .users import ensure_user_profile, get_user_by_knox_id, resolve_target_user

__all__ = [
    "approve_affiliation_change",
    "auto_approve_affiliation_from_snapshot",
    "ensure_self_access",
    "ensure_affiliation_option",
    "ensure_user_profile",
    "get_current_user_sdwt_prod_change",
    "get_account_overview",
    "get_affiliation_change_requests",
    "get_affiliation_overview",
    "get_affiliation_reconfirm_status",
    "get_line_sdwt_options_payload",
    "get_manageable_groups_with_members",
    "get_pending_user_sdwt_prod_change",
    "get_user_by_knox_id",
    "grant_or_revoke_access",
    "reject_affiliation_change",
    "request_affiliation_change",
    "resolve_target_user",
    "submit_affiliation_reconfirm_response",
    "sync_external_affiliations",
    "claim_unassigned_emails_for_user",
]
