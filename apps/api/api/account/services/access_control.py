# =============================================================================
# 모듈 설명: scope 기반 접근 권한 판정/요청/결정 서비스 로직을 제공합니다.
# - 주요 대상: AccessScope, AccessPolicyRule, UserAccess
# - 불변 조건: 기존 account 테이블은 정책 판정 근거로 재사용합니다.
# =============================================================================

"""scope 기반 접근 권한 서비스 모음."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.db import IntegrityError, transaction
from django.utils import timezone

from .. import selectors
from ..models import (
    ACCESS_SCOPE_PORTAL,
    MANAGE_ACCESS_PERMISSION,
    AccessAuditLog,
    AccessPolicyRule,
    AccessRole,
    AccessScope,
    AccessSource,
    UserAccess,
    UserProfile,
)


_APPROVE_DECISIONS = {"approve", "approved", "allow", "allowed"}
_REJECT_DECISIONS = {"reject", "rejected", "deny", "denied"}
_GRANT_ACTIONS = {"approve", "grant", "allow"}
_REVOKE_ACTIONS = {"reject", "revoke", "deny"}
_ACCESS_STATUSES = {"allowed", "pending", "denied", "not_requested", "inactive"}


def can_manage_access(*, user: Any) -> bool:
    """사용자가 portal/app 접근 권한을 관리할 수 있는지 확인합니다."""

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return bool(user.has_perm(MANAGE_ACCESS_PERMISSION))


def has_access_bypass(*, user: Any) -> bool:
    """사용자가 portal/app 접근 제한을 우회할 수 있는지 확인합니다."""

    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_superuser", False)
    )


def get_access_payload(*, user: Any, scope_key: str = ACCESS_SCOPE_PORTAL) -> dict[str, object]:
    """현재 사용자의 scope 접근 상태를 반환합니다."""

    scope = selectors.get_access_scope_by_key(scope_key=scope_key)
    department = _get_user_department(user=user)
    can_manage = can_manage_access(user=user)
    can_bypass = has_access_bypass(user=user)

    if scope is None:
        return {
            "allowed": can_bypass,
            "scope": scope_key,
            "reason": AccessSource.SUPERUSER_BYPASS if can_bypass else AccessSource.SCOPE_NOT_FOUND,
            "department": department,
            "departmentAllowed": False,
            "status": None,
            "role": AccessRole.ADMIN if can_bypass else None,
            "requestId": None,
            "requestedAt": None,
            "decidedAt": None,
            "rejectionReason": None,
            "canRequest": False,
            "canManage": can_manage,
            "effectiveStatus": "allowed" if can_bypass else "inactive",
            "explicitStatus": None,
            "source": AccessSource.SUPERUSER_BYPASS if can_bypass else AccessSource.SCOPE_NOT_FOUND,
            "policyMatched": False,
            "policy": None,
        }

    user_access = selectors.get_user_access_for_scope(user=user, scope=scope)
    policy_rules = selectors.list_active_access_policy_rules(scope=scope)
    return _build_access_payload(
        user=user,
        scope=scope,
        user_access=user_access,
        policy_rules=policy_rules,
    )


def _build_access_payload(
    *,
    user: Any,
    scope: AccessScope,
    user_access: UserAccess | None,
    policy_rules: list[AccessPolicyRule],
    include_management_capability: bool = True,
) -> dict[str, object]:
    """사용자 접근 row와 정책 규칙을 합쳐 최종 접근 상태를 계산합니다."""

    is_app_scope = scope.scope_type == AccessScope.ScopeTypes.APP
    department = _get_user_department(user=user)
    can_manage = can_manage_access(user=user) if include_management_capability else False
    can_bypass = has_access_bypass(user=user)
    policy_result = _evaluate_policy_rules(user=user, scope=scope, rules=policy_rules)
    policy_allowed = policy_result["allowed"]
    status = user_access.status if user_access else None
    role = (
        user_access.role
        if user_access and user_access.status == UserAccess.Status.ALLOWED
        else policy_result["role"]
    )

    if can_bypass:
        allowed = True
        reason = AccessSource.SUPERUSER_BYPASS
        role = AccessRole.ADMIN
        source = AccessSource.SUPERUSER_BYPASS
        effective_status = "allowed"
    elif not scope.is_active:
        allowed = False
        reason = "scope_inactive"
        source = AccessSource.SCOPE_INACTIVE
        effective_status = "inactive"
    elif status == UserAccess.Status.DENIED:
        allowed = False
        reason = "denied"
        source = AccessSource.EXPLICIT_DENIED
        effective_status = "denied"
    elif status == UserAccess.Status.ALLOWED:
        allowed = True
        reason = "allowed"
        source = AccessSource.EXPLICIT_ALLOWED
        effective_status = "allowed"
    elif status == UserAccess.Status.PENDING:
        allowed = False
        reason = "pending"
        source = AccessSource.EXPLICIT_PENDING
        effective_status = "pending"
    elif policy_allowed:
        allowed = True
        reason = policy_result["reason"]
        source = policy_result["source"]
        effective_status = "allowed"
    else:
        allowed = False
        reason = "not_requested"
        source = AccessSource.NONE
        effective_status = "not_requested"

    payload = {
        "allowed": allowed,
        "scope": scope.key,
        "reason": reason,
        "department": department,
        "departmentAllowed": policy_result["departmentAllowed"],
        "status": status,
        "requestId": user_access.id if user_access else None,
        "requestedAt": user_access.requested_at.isoformat() if user_access else None,
        "decidedAt": user_access.decided_at.isoformat() if user_access and user_access.decided_at else None,
        "rejectionReason": user_access.reason if user_access and status == UserAccess.Status.DENIED else None,
        "effectiveStatus": effective_status,
        "explicitStatus": status,
        "source": source,
        "policyMatched": bool(policy_allowed),
        "policy": _serialize_policy_match(policy_result, include_role=not is_app_scope),
        "canRequest": bool(
            getattr(user, "is_authenticated", False)
            and scope.is_active
            and scope.requestable
            and not allowed
            and status != UserAccess.Status.PENDING
        ),
    }
    if include_management_capability:
        payload["canManage"] = can_manage
    if not is_app_scope:
        payload["role"] = role
    return payload


def get_portal_access_payload(*, user: Any) -> dict[str, object]:
    """기존 auth 응답 계약용 portal 접근 상태를 반환합니다."""

    return get_access_payload(user=user, scope_key=ACCESS_SCOPE_PORTAL)


def get_app_access_payloads(*, user: Any) -> dict[str, dict[str, object]]:
    """현재 사용자의 활성 앱 scope별 최종 접근 상태를 반환합니다."""

    scopes = selectors.list_active_app_access_scopes()
    policy_rules = selectors.list_active_access_policy_rules_for_scopes(scopes=scopes)
    policy_rules_by_scope: dict[int, list[AccessPolicyRule]] = {scope.id: [] for scope in scopes}
    for rule in policy_rules:
        policy_rules_by_scope.setdefault(rule.scope_id, []).append(rule)

    access_rows = selectors.list_user_access_rows_for_scopes_and_users(
        scopes=scopes,
        user_ids=[getattr(user, "id", 0)],
    )
    access_by_scope_id = {access.scope_id: access for access in access_rows}
    return {
        scope.key: _build_access_payload(
            user=user,
            scope=scope,
            user_access=access_by_scope_id.get(scope.id),
            policy_rules=policy_rules_by_scope.get(scope.id, []),
            include_management_capability=False,
        )
        for scope in scopes
    }


def request_access(*, user: Any, scope_key: str = ACCESS_SCOPE_PORTAL) -> tuple[dict[str, object], int]:
    """현재 사용자에 대한 scope 접근 요청을 생성합니다."""

    if not user or not getattr(user, "is_authenticated", False):
        return {"error": "unauthorized"}, 401

    with transaction.atomic():
        # 같은 사용자의 동시 요청을 직렬화해 중복 생성과 재요청 덮어쓰기를 막습니다.
        locked_user = selectors.get_user_by_id_for_update(user_id=getattr(user, "pk", 0))
        if locked_user is None:
            return {"error": "user_not_found"}, 404

        scope = selectors.get_access_scope_by_key(scope_key=scope_key)
        if scope is None or not scope.is_active:
            return {"error": "scope_not_found"}, 404
        if not scope.requestable:
            return {"error": "not_requestable"}, 400

        user_access = selectors.get_user_access_for_scope_for_update(user=locked_user, scope=scope)
        policy_rules = selectors.list_active_access_policy_rules(scope=scope)
        current_payload = _build_access_payload(
            user=locked_user,
            scope=scope,
            user_access=user_access,
            policy_rules=policy_rules,
        )
        if current_payload["allowed"]:
            return {"status": "already_allowed", "portalAccess": current_payload}, 200
        if user_access is not None and user_access.status == UserAccess.Status.PENDING:
            return {"status": "pending", "portalAccess": current_payload}, 200

        department = _get_user_department(user=locked_user)
        before = _serialize_user_access(user_access) if user_access else {}
        if user_access is None:
            user_access = UserAccess.objects.create(
                scope=scope,
                user=locked_user,
                department=department,
                status=UserAccess.Status.PENDING,
                role=scope.default_role or AccessRole.VIEWER,
            )
        else:
            user_access.department = department
            user_access.status = UserAccess.Status.PENDING
            user_access.role = scope.default_role or AccessRole.VIEWER
            user_access.requested_at = timezone.now()
            user_access.decided_by = None
            user_access.decided_at = None
            user_access.reason = None
            user_access.save(
                update_fields=[
                    "department",
                    "status",
                    "role",
                    "requested_at",
                    "decided_by",
                    "decided_at",
                    "reason",
                    "updated_at",
                ]
            )

        after = _serialize_user_access(user_access)
        _create_access_audit_log(
            scope=scope,
            actor=locked_user,
            target_user=locked_user,
            policy_rule=None,
            action=AccessAuditLog.Actions.REQUEST,
            before=before,
            after=after,
            reason=None,
        )
        portal_access = _build_access_payload(
            user=locked_user,
            scope=scope,
            user_access=user_access,
            policy_rules=policy_rules,
        )

    return {"status": "pending", "portalAccess": portal_access}, 200


def request_portal_access(*, user: Any) -> tuple[dict[str, object], int]:
    """기존 API 계약용 portal 접근 요청을 생성합니다."""

    return request_access(user=user, scope_key=ACCESS_SCOPE_PORTAL)


def decide_access(
    *,
    actor: Any,
    access_id: int,
    decision: str,
    reason: str | None,
    role: str | None = None,
    scope_key: str | None = None,
) -> tuple[dict[str, object], int]:
    """사용자 접근 요청을 allowed/denied 상태로 결정합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    normalized_decision = (decision or "").strip().lower()
    if normalized_decision in _REJECT_DECISIONS:
        next_status = UserAccess.Status.DENIED
        audit_action = AccessAuditLog.Actions.REJECT
    elif normalized_decision in _APPROVE_DECISIONS:
        next_status = UserAccess.Status.ALLOWED
        audit_action = AccessAuditLog.Actions.APPROVE
    else:
        return {"error": "invalid_decision"}, 400

    with transaction.atomic():
        user_access = selectors.get_user_access_by_id_for_update(access_id=access_id)
        if user_access is None:
            return {"error": "not_found"}, 404
        if scope_key and user_access.scope.key != scope_key:
            return {"error": "not_found"}, 404
        if user_access.status != UserAccess.Status.PENDING:
            return {
                "error": "invalid_status_transition",
                "currentStatus": user_access.status,
            }, 409

        is_app_scope = user_access.scope.scope_type == AccessScope.ScopeTypes.APP
        if is_app_scope and (role or "").strip():
            return {"error": "app_role_not_supported"}, 400

        normalized_role = (
            AccessRole.VIEWER
            if is_app_scope
            else _normalize_access_role(role or user_access.role or user_access.scope.default_role)
        )
        if normalized_role is None:
            return {"error": "invalid_role"}, 400

        before = _serialize_user_access(user_access)
        user_access.status = next_status
        user_access.role = normalized_role
        user_access.decided_by = actor
        user_access.decided_at = timezone.now()
        user_access.reason = (reason or "").strip() if next_status == UserAccess.Status.DENIED else None
        user_access.save(update_fields=["status", "role", "decided_by", "decided_at", "reason", "updated_at"])
        after = _serialize_user_access(user_access)
        _create_access_audit_log(
            scope=user_access.scope,
            actor=actor,
            target_user=user_access.user,
            policy_rule=None,
            action=audit_action,
            before=before,
            after=after,
            reason=user_access.reason,
        )

    return {"status": "ok", "approval": _serialize_user_access(user_access)}, 200


def decide_portal_access(
    *,
    actor: Any,
    approval_id: int,
    decision: str,
    rejection_reason: str | None,
    role: str | None = None,
) -> tuple[dict[str, object], int]:
    """기존 API 계약용 portal 접근 요청을 결정합니다."""

    return decide_access(
        actor=actor,
        access_id=approval_id,
        decision=decision,
        reason=rejection_reason,
        role=role,
        scope_key=ACCESS_SCOPE_PORTAL,
    )


def get_access_requests(
    *,
    actor: Any,
    scope_key: str | None,
    status: str | None,
    search: str | None,
    page: int,
    page_size: int,
) -> tuple[dict[str, object], int]:
    """권한 관리자용 사용자 접근 상태 목록을 반환합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    queryset = selectors.list_user_access_rows(scope_key=scope_key, status=status, search=search)
    paginator = Paginator(queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    return {
        "results": [_serialize_user_access(row) for row in page_obj.object_list],
        "pagination": {
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        },
    }, 200


def get_portal_access_approvals(
    *,
    actor: Any,
    status: str | None,
    search: str | None,
    page: int,
    page_size: int,
) -> tuple[dict[str, object], int]:
    """기존 API 계약용 portal 접근 상태 목록을 반환합니다."""

    return get_access_requests(
        actor=actor,
        scope_key=ACCESS_SCOPE_PORTAL,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )


def get_access_users(
    *,
    actor: Any,
    scope_key: str | None,
    status: str | None,
    source: str | None,
    search: str | None,
    department: str | None,
    page: int,
    page_size: int,
) -> tuple[dict[str, object], int]:
    """권한 관리자용 전체 사용자 접근 상태 목록을 반환합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    scope = selectors.get_access_scope_by_key(scope_key=scope_key or ACCESS_SCOPE_PORTAL)
    if scope is None:
        return {"error": "scope_not_found"}, 404

    normalized_status = (status or "").strip().lower()
    if normalized_status in {"all", ""} or normalized_status not in _ACCESS_STATUSES:
        normalized_status = ""
    normalized_source = (source or "").strip().lower()
    if normalized_source in {"all", ""}:
        normalized_source = ""
    elif normalized_source == "admin":
        # 이전 API 필터 값은 새 superuser 우회 source로 정규화합니다.
        normalized_source = AccessSource.SUPERUSER_BYPASS

    user_queryset = selectors.list_access_management_users(search=search, department=department)
    user_queryset, is_fast_filtered = selectors.filter_access_management_users_for_fast_access_filter(
        queryset=user_queryset,
        scope=scope,
        status=normalized_status,
        source=normalized_source,
    )
    needs_computed_filter = bool(normalized_status or normalized_source) and not is_fast_filtered
    policy_rules = selectors.list_active_access_policy_rules(scope=scope)

    if needs_computed_filter:
        users = list(user_queryset)
        rows = _build_effective_access_rows(
            users=users,
            scope=scope,
            policy_rules=policy_rules,
            status=normalized_status,
            source=normalized_source,
        )
        paginator = Paginator(rows, page_size)
    else:
        paginator = Paginator(user_queryset, page_size)

    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    if needs_computed_filter:
        page_rows = list(page_obj.object_list)
        summary = _summarize_access_rows(page_rows)
        summary["total"] = paginator.count
        summary["pageTotal"] = len(page_rows)
    else:
        page_users = list(page_obj.object_list)
        page_rows = _build_effective_access_rows(
            users=page_users,
            scope=scope,
            policy_rules=policy_rules,
            status="",
            source="",
        )
        summary = _summarize_access_rows(page_rows)
        summary["total"] = paginator.count
        summary["pageTotal"] = len(page_rows)

    return {
        "scope": _serialize_scope(scope),
        "results": page_rows,
        "summary": summary,
        "pagination": {
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        },
    }, 200


def get_app_access_matrix(
    *,
    actor: Any,
    search: str | None,
    department: str | None,
    page: int,
    page_size: int,
) -> tuple[dict[str, object], int]:
    """권한 관리자용 사용자별 앱 접근 권한 매트릭스를 반환합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    scopes = selectors.list_active_app_access_scopes()
    user_queryset = selectors.list_access_management_users(search=search, department=department)
    paginator = Paginator(user_queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    users = list(page_obj.object_list)
    policy_rules = selectors.list_active_access_policy_rules_for_scopes(scopes=scopes)
    policy_rules_by_scope: dict[int, list[AccessPolicyRule]] = {scope.id: [] for scope in scopes}
    for rule in policy_rules:
        policy_rules_by_scope.setdefault(rule.scope_id, []).append(rule)

    access_rows = selectors.list_user_access_rows_for_scopes_and_users(
        scopes=scopes,
        user_ids=[user.id for user in users],
    )
    access_by_scope_and_user = {
        (access.scope_id, access.user_id): access
        for access in access_rows
    }

    results = []
    for target_user in users:
        accesses = {
            scope.key: _build_access_payload(
                user=target_user,
                scope=scope,
                user_access=access_by_scope_and_user.get((scope.id, target_user.id)),
                policy_rules=policy_rules_by_scope.get(scope.id, []),
                include_management_capability=False,
            )
            for scope in scopes
        }
        results.append({"user": _serialize_access_user(target_user), "accesses": accesses})

    return {
        "scopes": [_serialize_scope(scope) for scope in scopes],
        "results": results,
        "pagination": {
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        },
    }, 200


def decide_user_access(
    *,
    actor: Any,
    user_id: int,
    scope_key: str | None,
    action: str,
    reason: str | None,
    role: str | None = None,
) -> tuple[dict[str, object], int]:
    """권한 관리자가 특정 사용자의 scope 접근 상태를 변경합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    scope = selectors.get_access_scope_by_key(scope_key=scope_key or ACCESS_SCOPE_PORTAL)
    if scope is None:
        return {"error": "scope_not_found"}, 404

    target_user = selectors.get_user_by_id(user_id=user_id)
    if target_user is None:
        return {"error": "user_not_found"}, 404

    normalized_action = (action or "").strip().lower()
    normalized_reason = (reason or "").strip()
    is_app_scope = scope.scope_type == AccessScope.ScopeTypes.APP
    if is_app_scope and (
        normalized_action == AccessAuditLog.Actions.CHANGE_ROLE
        or (role or "").strip()
    ):
        return {"error": "app_role_not_supported"}, 400
    if normalized_action == AccessAuditLog.Actions.RESET_TO_POLICY:
        return _reset_user_access_to_policy(
            actor=actor,
            target_user=target_user,
            scope=scope,
            reason=normalized_reason,
        )

    explicit_role = None
    if normalized_action == AccessAuditLog.Actions.CHANGE_ROLE:
        if not (role or "").strip():
            return {"error": "role_required"}, 400
        explicit_role = _normalize_access_role(role)
        if explicit_role is None:
            return {"error": "invalid_role"}, 400
        next_status = UserAccess.Status.ALLOWED
        audit_action = AccessAuditLog.Actions.CHANGE_ROLE
    elif normalized_action in _GRANT_ACTIONS:
        next_status = UserAccess.Status.ALLOWED
        audit_action = AccessAuditLog.Actions.APPROVE if normalized_action == "approve" else AccessAuditLog.Actions.GRANT
    elif normalized_action in _REVOKE_ACTIONS:
        next_status = UserAccess.Status.DENIED
        audit_action = AccessAuditLog.Actions.REJECT if normalized_action == "reject" else AccessAuditLog.Actions.REVOKE
    else:
        return {"error": "invalid_action"}, 400

    with transaction.atomic():
        target_user = selectors.get_user_by_id_for_update(user_id=user_id)
        if target_user is None:
            return {"error": "user_not_found"}, 404

        user_access = selectors.get_user_access_for_scope_for_update(user=target_user, scope=scope)
        if normalized_action in {"approve", "reject"} and (
            user_access is None or user_access.status != UserAccess.Status.PENDING
        ):
            return {
                "error": "invalid_status_transition",
                "currentStatus": user_access.status if user_access else None,
            }, 409

        policy_rules = selectors.list_active_access_policy_rules(scope=scope)
        if normalized_action == AccessAuditLog.Actions.CHANGE_ROLE:
            current_access = _build_access_payload(
                user=target_user,
                scope=scope,
                user_access=user_access,
                policy_rules=policy_rules,
            )
            if (
                not current_access["allowed"]
                or current_access["source"] == AccessSource.SUPERUSER_BYPASS
            ):
                return {
                    "error": "invalid_status_transition",
                    "currentStatus": current_access["effectiveStatus"],
                }, 409

        before = _serialize_user_access(user_access) if user_access else {}
        if user_access is None:
            user_access = UserAccess(
                scope=scope,
                user=target_user,
                department=_get_user_department(user=target_user),
            )

        normalized_role = (
            AccessRole.VIEWER
            if is_app_scope
            else explicit_role or _normalize_access_role(role or user_access.role or scope.default_role)
        )
        if normalized_role is None:
            return {"error": "invalid_role"}, 400

        user_access.department = _get_user_department(user=target_user)
        user_access.status = next_status
        user_access.role = normalized_role
        user_access.decided_by = actor
        user_access.decided_at = timezone.now()
        user_access.reason = normalized_reason if next_status == UserAccess.Status.DENIED else None
        user_access.save()
        after = _serialize_user_access(user_access)
        _create_access_audit_log(
            scope=scope,
            actor=actor,
            target_user=target_user,
            policy_rule=None,
            action=audit_action,
            before=before,
            after=after,
            reason=user_access.reason,
        )

    return {
        "status": "ok",
        "row": _serialize_effective_access_user(
            user=target_user,
            scope=scope,
            user_access=user_access,
            policy_rules=policy_rules,
        ),
    }, 200


def get_access_policy_rules(
    *,
    actor: Any,
    scope_key: str | None,
) -> tuple[dict[str, object], int]:
    """권한 관리자용 접근 정책 규칙 목록을 반환합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    return {
        "results": [
            _serialize_access_policy_rule(rule)
            for rule in selectors.list_access_policy_rules(scope_key=scope_key or ACCESS_SCOPE_PORTAL)
        ]
    }, 200


def create_access_policy_rule(
    *,
    actor: Any,
    scope_key: str | None,
    rule_type: str | None,
    value: str | None,
    role: str | None,
    is_active: bool | None,
) -> tuple[dict[str, object], int]:
    """접근 정책 규칙을 생성합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    with transaction.atomic():
        scope = selectors.get_access_scope_by_key_for_update(scope_key=scope_key or ACCESS_SCOPE_PORTAL)
        if scope is None:
            return {"error": "scope_not_found"}, 404

        if rule_type not in AccessPolicyRule.RuleTypes.values:
            return {"error": "invalid_rule_type"}, 400
        is_app_scope = scope.scope_type == AccessScope.ScopeTypes.APP
        if is_app_scope and (role or "").strip():
            return {"error": "app_role_not_supported"}, 400
        normalized_role = (
            AccessRole.VIEWER
            if is_app_scope
            else _normalize_access_role(role or scope.default_role)
        )
        if normalized_role is None:
            return {"error": "invalid_role"}, 400

        rule = AccessPolicyRule(
            scope=scope,
            rule_type=rule_type,
            value=(value or "").strip(),
            role=normalized_role,
            is_active=True if is_active is None else bool(is_active),
        )
        validation_error = _clean_policy_rule(rule)
        if validation_error:
            return validation_error, 400

        try:
            # 경쟁 삽입의 IntegrityError가 바깥 트랜잭션을 깨뜨리지 않게 savepoint를 둡니다.
            with transaction.atomic():
                rule.save()
        except IntegrityError:
            return {"error": "duplicate_policy_rule"}, 400

        after = _serialize_access_policy_rule(rule)
        _create_access_audit_log(
            scope=rule.scope,
            actor=actor,
            target_user=None,
            policy_rule=rule,
            action=AccessAuditLog.Actions.POLICY_CREATE,
            before={},
            after=after,
            reason=None,
        )

    return {"status": "ok", "policyRule": after}, 201


def update_access_policy_rule(
    *,
    actor: Any,
    rule_id: int,
    scope_key: str | None,
    rule_type: str | None,
    value: str | None,
    role: str | None,
    is_active: bool | None,
) -> tuple[dict[str, object], int]:
    """접근 정책 규칙을 수정합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    with transaction.atomic():
        rule = selectors.get_access_policy_rule_by_id_for_update(rule_id=rule_id)
        if rule is None:
            return {"error": "not_found"}, 404

        before = _serialize_access_policy_rule(rule)
        if scope_key:
            scope = selectors.get_access_scope_by_key(scope_key=scope_key)
            if scope is None:
                return {"error": "scope_not_found"}, 404
            rule.scope = scope
        is_app_scope = rule.scope.scope_type == AccessScope.ScopeTypes.APP
        if rule_type is not None:
            if rule_type not in AccessPolicyRule.RuleTypes.values:
                return {"error": "invalid_rule_type"}, 400
            rule.rule_type = rule_type
        if value is not None:
            rule.value = value.strip()
        if role is not None:
            if is_app_scope and role.strip():
                return {"error": "app_role_not_supported"}, 400
            normalized_role = _normalize_access_role(role)
            if normalized_role is None:
                return {"error": "invalid_role"}, 400
            rule.role = normalized_role
        if is_app_scope:
            rule.role = AccessRole.VIEWER
        if is_active is not None:
            rule.is_active = bool(is_active)

        validation_error = _clean_policy_rule(rule)
        if validation_error:
            return validation_error, 400

        try:
            with transaction.atomic():
                rule.save()
        except IntegrityError:
            return {"error": "duplicate_policy_rule"}, 400

        after = _serialize_access_policy_rule(rule)
        _create_access_audit_log(
            scope=rule.scope,
            actor=actor,
            target_user=None,
            policy_rule=rule,
            action=AccessAuditLog.Actions.POLICY_UPDATE,
            before=before,
            after=after,
            reason=None,
        )

    return {"status": "ok", "policyRule": after}, 200


def delete_access_policy_rule(
    *,
    actor: Any,
    rule_id: int,
) -> tuple[dict[str, object], int]:
    """접근 정책 규칙을 삭제합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    with transaction.atomic():
        rule = selectors.get_access_policy_rule_by_id_for_update(rule_id=rule_id)
        if rule is None:
            return {"error": "not_found"}, 404

        before = _serialize_access_policy_rule(rule)
        scope = rule.scope
        _create_access_audit_log(
            scope=scope,
            actor=actor,
            target_user=None,
            policy_rule=rule,
            action=AccessAuditLog.Actions.POLICY_DELETE,
            before=before,
            after={},
            reason=None,
        )
        rule.delete()

    return {"status": "ok"}, 200


def get_access_audit_logs(
    *,
    actor: Any,
    scope_key: str | None,
    user_id: int | None,
    action: str | None,
    page: int,
    page_size: int,
) -> tuple[dict[str, object], int]:
    """권한 관리자용 접근 권한 감사 로그 목록을 반환합니다."""

    if not can_manage_access(user=actor):
        return {"error": "forbidden"}, 403

    normalized_scope = (scope_key or "").strip()
    if normalized_scope.casefold() == "all":
        normalized_scope = ""

    queryset = selectors.list_access_audit_logs(
        scope_key=normalized_scope or None,
        user_id=user_id,
        action=action,
    )
    paginator = Paginator(queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    return {
        "results": [_serialize_access_audit_log(row) for row in page_obj.object_list],
        "pagination": {
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        },
    }, 200


def _evaluate_policy_rules(
    *,
    user: Any,
    scope: AccessScope,
    rules: list[AccessPolicyRule] | None = None,
) -> dict[str, object]:
    """사용자 부서와 scope의 활성 부서 규칙을 비교합니다."""

    department = _get_user_department(user=user)
    policy_rules = rules if rules is not None else selectors.list_active_access_policy_rules(scope=scope)
    for rule in policy_rules:
        if rule.rule_type != AccessPolicyRule.RuleTypes.DEPARTMENT:
            continue
        if department and department.casefold() == rule.value.strip().casefold():
            return _build_policy_result(
                rule=rule,
                reason="department_allowed",
                source=AccessSource.POLICY_DEPARTMENT,
                department_allowed=True,
            )

    return {
        "allowed": False,
        "reason": "not_requested",
        "source": AccessSource.NONE,
        "role": scope.default_role,
        "departmentAllowed": False,
        "rule": None,
    }


def _reset_user_access_to_policy(
    *,
    actor: Any,
    target_user: Any,
    scope: AccessScope,
    reason: str,
) -> tuple[dict[str, object], int]:
    """사용자 명시 접근 row를 제거해 정책 판정 상태로 되돌립니다."""

    with transaction.atomic():
        locked_target_user = selectors.get_user_by_id_for_update(user_id=target_user.id)
        if locked_target_user is None:
            return {"error": "user_not_found"}, 404

        user_access = selectors.get_user_access_for_scope_for_update(
            user=locked_target_user,
            scope=scope,
        )
        before = _serialize_user_access(user_access) if user_access else {}
        if user_access is not None:
            user_access.delete()

        policy_rules = selectors.list_active_access_policy_rules(scope=scope)
        after_payload = _build_access_payload(
            user=locked_target_user,
            scope=scope,
            user_access=None,
            policy_rules=policy_rules,
        )
        _create_access_audit_log(
            scope=scope,
            actor=actor,
            target_user=locked_target_user,
            policy_rule=None,
            action=AccessAuditLog.Actions.RESET_TO_POLICY,
            before=before,
            after=after_payload,
            reason=reason or None,
        )

    return {
        "status": "ok",
        "row": _serialize_effective_access_user(
            user=locked_target_user,
            scope=scope,
            user_access=None,
            policy_rules=selectors.list_active_access_policy_rules(scope=scope),
        ),
    }, 200


def _build_policy_result(
    *,
    rule: AccessPolicyRule,
    reason: str,
    source: str,
    department_allowed: bool,
) -> dict[str, object]:
    """정책 규칙 매칭 결과를 표준 dict로 반환합니다."""

    return {
        "allowed": True,
        "reason": reason,
        "source": source,
        "role": rule.role,
        "departmentAllowed": department_allowed,
        "rule": rule,
    }


def _serialize_policy_match(
    policy_result: dict[str, object],
    *,
    include_role: bool = True,
) -> dict[str, object]:
    """정책 매칭 결과를 API 응답 형태로 직렬화합니다."""

    rule = policy_result.get("rule")
    payload = {
        "matched": bool(policy_result.get("allowed")),
        "reason": policy_result.get("reason"),
        "source": policy_result.get("source"),
        "ruleId": rule.id if isinstance(rule, AccessPolicyRule) else None,
        "ruleType": rule.rule_type if isinstance(rule, AccessPolicyRule) else None,
        "value": rule.value if isinstance(rule, AccessPolicyRule) else None,
    }
    if include_role:
        payload["role"] = rule.role if isinstance(rule, AccessPolicyRule) else policy_result.get("role")
    return payload


def _serialize_scope(scope: AccessScope) -> dict[str, object]:
    """접근 scope를 API 응답 형태로 직렬화합니다."""

    payload = {
        "key": scope.key,
        "name": scope.name,
        "scopeType": scope.scope_type,
        "isActive": scope.is_active,
        "requestable": scope.requestable,
    }
    if scope.scope_type != AccessScope.ScopeTypes.APP:
        payload["defaultRole"] = scope.default_role
    return payload


def _serialize_effective_access_user(
    *,
    user: Any,
    scope: AccessScope,
    user_access: UserAccess | None,
    policy_rules: list[AccessPolicyRule],
) -> dict[str, object]:
    """사용자와 최종 접근 상태를 한 행으로 직렬화합니다."""

    return {
        "user": _serialize_access_user(user),
        "access": _build_access_payload(
            user=user,
            scope=scope,
            user_access=user_access,
            policy_rules=policy_rules,
            include_management_capability=False,
        ),
    }


def _build_effective_access_rows(
    *,
    users: list[Any],
    scope: AccessScope,
    policy_rules: list[AccessPolicyRule],
    status: str,
    source: str,
) -> list[dict[str, object]]:
    """사용자 목록을 최종 접근 상태 행 목록으로 변환하고 계산 필터를 적용합니다."""

    access_rows = selectors.list_user_access_rows_by_scope_and_user_ids(
        scope=scope,
        user_ids=[user.id for user in users],
    )
    access_by_user_id = {row.user_id: row for row in access_rows}

    rows: list[dict[str, object]] = []
    for target_user in users:
        row = _serialize_effective_access_user(
            user=target_user,
            scope=scope,
            user_access=access_by_user_id.get(target_user.id),
            policy_rules=policy_rules,
        )
        access = row["access"]
        if status and access["effectiveStatus"] != status:
            continue
        if source and access["source"] != source:
            continue
        rows.append(row)
    return rows


def _serialize_access_user(user: Any) -> dict[str, object]:
    """권한 관리 화면 사용자 정보를 직렬화합니다."""

    current_affiliation = getattr(user, "current_affiliation", None)
    affiliation = getattr(current_affiliation, "affiliation", None)
    display_name = (
        getattr(user, "username", None)
        or getattr(user, "username_en", None)
        or getattr(user, "givenname", None)
        or getattr(user, "knox_id", None)
        or getattr(user, "sabun", None)
        or ""
    )
    return {
        "id": user.id,
        "userId": user.id,
        "username": getattr(user, "username", None) or "",
        "displayName": display_name,
        "sabun": getattr(user, "sabun", None) or "",
        "knoxId": getattr(user, "knox_id", None) or "",
        "email": getattr(user, "email", None) or "",
        "department": _get_user_department(user=user),
        "accountDepartment": getattr(user, "department", None) or "",
        "line": getattr(affiliation, "line", "") or "",
        "userSdwtProd": getattr(affiliation, "user_sdwt_prod", "") or "",
        "profileRole": _get_user_profile_role(user=user),
        "isStaff": bool(getattr(user, "is_staff", False)),
        "isSuperuser": bool(getattr(user, "is_superuser", False)),
    }


def _summarize_access_rows(rows: list[dict[str, object]]) -> dict[str, int]:
    """권한 관리 목록의 상태별 건수를 계산합니다."""

    summary = {
        "total": len(rows),
        "allowed": 0,
        "pending": 0,
        "denied": 0,
        "notRequested": 0,
        "inactive": 0,
        "policyAllowed": 0,
        "explicitAllowed": 0,
        "explicitDenied": 0,
    }
    for row in rows:
        access = row.get("access", {}) if isinstance(row, dict) else {}
        status = access.get("effectiveStatus")
        if status == "allowed":
            summary["allowed"] += 1
        elif status == "pending":
            summary["pending"] += 1
        elif status == "denied":
            summary["denied"] += 1
        elif status == "inactive":
            summary["inactive"] += 1
        else:
            summary["notRequested"] += 1

        source = access.get("source")
        if isinstance(source, str) and source.startswith("policy_"):
            summary["policyAllowed"] += 1
        if source == AccessSource.EXPLICIT_ALLOWED:
            summary["explicitAllowed"] += 1
        if source == AccessSource.EXPLICIT_DENIED:
            summary["explicitDenied"] += 1
    return summary


def _clean_policy_rule(rule: AccessPolicyRule) -> dict[str, object] | None:
    """정책 규칙 모델 검증을 수행하고 오류 payload를 반환합니다."""

    try:
        rule.full_clean()
    except ValidationError as error:
        details = getattr(error, "message_dict", None) or {"__all__": error.messages}
        return {"error": "invalid_policy_rule", "details": details}
    return None


def _serialize_access_policy_rule(rule: AccessPolicyRule) -> dict[str, object]:
    """접근 정책 규칙을 API 응답 형태로 직렬화합니다."""

    payload = {
        "id": rule.id,
        "scope": rule.scope.key,
        "scopeName": rule.scope.name,
        "ruleType": rule.rule_type,
        "value": rule.value,
        "isActive": rule.is_active,
        "createdAt": rule.created_at.isoformat() if rule.created_at else None,
        "updatedAt": rule.updated_at.isoformat() if rule.updated_at else None,
    }
    if rule.scope.scope_type != AccessScope.ScopeTypes.APP:
        payload["role"] = rule.role
    return payload


def _create_access_audit_log(
    *,
    scope: AccessScope | None,
    actor: Any,
    target_user: Any | None,
    policy_rule: AccessPolicyRule | None,
    action: str,
    before: dict[str, object],
    after: dict[str, object],
    reason: str | None,
) -> None:
    """접근 권한 변경 감사 로그를 생성합니다."""

    AccessAuditLog.objects.create(
        scope=scope,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        target_user=target_user,
        policy_rule=policy_rule,
        action=action,
        before=before or {},
        after=after or {},
        reason=(reason or "").strip() or None,
    )


def _serialize_access_audit_log(row: AccessAuditLog) -> dict[str, object]:
    """접근 권한 감사 로그를 API 응답 형태로 직렬화합니다."""

    policy_rule = row.policy_rule
    policy_snapshot = _get_policy_rule_snapshot(row=row)
    return {
        "id": row.id,
        "scope": getattr(row.scope, "key", None),
        "scopeName": getattr(row.scope, "name", None),
        "action": row.action,
        "reason": row.reason,
        "before": row.before or {},
        "after": row.after or {},
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "actor": _serialize_access_actor(row.actor),
        "targetUser": _serialize_access_actor(row.target_user),
        "policyRule": policy_snapshot or ({
            "id": policy_rule.id,
            "ruleType": policy_rule.rule_type,
            "value": policy_rule.value,
            "role": policy_rule.role,
        } if policy_rule else None),
    }


def _get_policy_rule_snapshot(*, row: AccessAuditLog) -> dict[str, object] | None:
    """삭제된 정책 규칙 정보를 감사 로그 JSON snapshot에서 복원합니다."""

    for snapshot in (row.after, row.before):
        if not isinstance(snapshot, dict):
            continue
        rule_type = snapshot.get("ruleType")
        value = snapshot.get("value")
        if rule_type or value:
            return {
                "id": snapshot.get("id"),
                "ruleType": rule_type,
                "value": value,
                "role": snapshot.get("role"),
            }
    return None


def _serialize_access_actor(user: Any | None) -> dict[str, object] | None:
    """감사 로그 사용자 요약 정보를 직렬화합니다."""

    if user is None:
        return None
    return {
        "id": user.id,
        "knoxId": getattr(user, "knox_id", None),
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
    }


def _get_user_department(*, user: Any) -> str:
    """포털 정책 판정에 사용할 사용자 부서를 반환합니다."""

    department = (getattr(user, "department", None) or "").strip()
    if department:
        return department
    current_affiliation = getattr(user, "current_affiliation", None)
    affiliation = getattr(current_affiliation, "affiliation", None)
    return (getattr(affiliation, "department", None) or "").strip()


def _get_user_profile_role(*, user: Any) -> str:
    """로드된 profile을 우선 사용해 사용자 역할을 반환합니다."""

    try:
        profile = getattr(user, "profile", None)
    except UserProfile.DoesNotExist:
        profile = None
    if profile is None:
        return UserProfile.Roles.VIEWER
    return profile.role or UserProfile.Roles.VIEWER


def _normalize_access_role(role: str | None) -> str | None:
    """접근 role 값을 정규화합니다."""

    normalized = (role or "").strip().lower()
    if normalized in AccessRole.values:
        return normalized
    return None


def _serialize_user_access(user_access: UserAccess) -> dict[str, object]:
    """사용자 접근 상태 행을 API 응답용 dict로 직렬화합니다."""

    user = user_access.user
    decided_by = user_access.decided_by
    payload = {
        "id": user_access.id,
        "scope": user_access.scope.key,
        "scopeName": user_access.scope.name,
        "status": user_access.status,
        "department": user_access.department,
        "requestedAt": user_access.requested_at.isoformat(),
        "decidedAt": user_access.decided_at.isoformat() if user_access.decided_at else None,
        "rejectionReason": user_access.reason,
        "user": {
            "id": user.id,
            "knoxId": getattr(user, "knox_id", None),
            "email": getattr(user, "email", None),
            "username": getattr(user, "username", None),
            "department": getattr(user, "department", None),
        },
        "decidedBy": {
            "id": decided_by.id,
            "knoxId": getattr(decided_by, "knox_id", None),
        } if decided_by else None,
    }
    if user_access.scope.scope_type != AccessScope.ScopeTypes.APP:
        payload["role"] = user_access.role
    return payload
