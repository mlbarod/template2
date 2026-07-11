# =============================================================================
# 모듈 설명: 포털/앱 접근 권한의 공통 경로 판정과 DRF permission을 제공합니다.
# - 주요 대상: PortalAccessRequiredPermission, 포털/앱 요청 단위 권한 payload 캐시
# - 불변 조건: 외부 token 전용 view의 명시적 permission override는 유지합니다.
# =============================================================================

"""포털과 앱 접근 권한을 Django middleware와 DRF에서 일관되게 검사합니다."""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission


PORTAL_ACCESS_API_PREFIX = "/api/v1/"
PORTAL_ACCESS_EXEMPT_PATH_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/health/",
    "/api/schema/",
    "/schema/",
    "/api/docs/",
    "/docs/",
    "/admin/",
    "/static/",
    "/media/",
    "/metrics/",
)
PORTAL_ACCESS_EXEMPT_PATHS = frozenset(
    {
        "/api/docs",
        "/api/schema",
        "/api/v1/auth",
        "/api/v1/health",
        "/api/v1/account/affiliation",
        "/api/v1/account/affiliation/reconfirm",
        "/api/v1/account/external-affiliations/sync",
        "/api/v1/account/line-sdwt-options",
        "/api/v1/account/portal-access",
        "/docs",
        "/metrics",
        "/schema",
    }
)

API_ROUTE_ACCESS_POLICIES = {
    "health": "public",
    "auth": "public",
    "activity": "portal",
    "line-dashboard": "app:line-dashboard",
    "l3_spider": "app:l3-spider",
    "pm_spider": "app:pm-spider",
    "assistant": "app:assistant",
    "observer": "app:observer",
    "emails": "app:emails",
    "fdc-trend": "app:fdc-trend",
    "data-movement": "token",
    "appstore": "app:appstore",
    "account": "portal",
    "voc": "app:voc",
}

APP_ACCESS_API_RULES = (
    ("/api/v1/activity/app-access-manual-commit", "access-stats"),
    ("/api/v1/activity/app-access-manual-preview", "access-stats"),
    ("/api/v1/activity/app-access-stats", "access-stats"),
    ("/api/v1/activity/app-access-sync-external", "access-stats"),
    ("/api/v1/activity/logs", "access-stats"),
)

_PORTAL_ACCESS_CACHE_ATTRIBUTE = "_portal_access_payload_cache"
_APP_ACCESS_CACHE_ATTRIBUTE = "_app_access_payload_cache"


class PortalAccessRequiredError(APIException):
    """포털 접근 승인이 없는 인증 요청에 일관된 403 응답을 제공합니다."""

    status_code = status.HTTP_403_FORBIDDEN
    default_code = "portal_access_required"

    def __init__(self, *, portal_access: dict[str, object]) -> None:
        """middleware 응답과 동일한 오류 payload를 보존합니다."""

        super().__init__(detail="portal_access_required", code=self.default_code)
        self.detail = {
            "error": "portal_access_required",
            "portalAccess": portal_access,
        }


class PortalAuthenticationRequiredError(APIException):
    """보호 API의 익명 요청에 기존 401 응답 계약을 유지합니다."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "not_authenticated"
    default_detail = "Authentication credentials were not provided."

    def __init__(self) -> None:
        """account view의 기존 익명 오류 payload와 같은 형태를 반환합니다."""

        super().__init__(detail={"error": "unauthorized"}, code=self.default_code)


class AppAccessRequiredError(APIException):
    """앱 접근 권한이 없는 인증 요청에 일관된 403 응답을 제공합니다."""

    status_code = status.HTTP_403_FORBIDDEN
    default_code = "app_access_required"

    def __init__(self, *, scope_key: str, app_access: dict[str, object]) -> None:
        """차단된 앱 scope와 최종 권한 payload를 응답에 포함합니다."""

        super().__init__(detail="app_access_required", code=self.default_code)
        self.detail = {
            "error": "app_access_required",
            "scope": scope_key,
            "appAccess": app_access,
        }


def _normalize_path(path: str) -> str:
    """경로 끝의 슬래시를 제거해 예외 경로 비교를 일관되게 만듭니다."""

    if not path or path == "/":
        return path
    return path.rstrip("/")


def is_portal_access_exempt_path(path: str) -> bool:
    """포털 접근 검사 예외 경로인지 반환합니다."""

    normalized_path = _normalize_path(path)
    if normalized_path in PORTAL_ACCESS_EXEMPT_PATHS:
        return True
    if any(
        normalized_path.startswith(prefix)
        for prefix in PORTAL_ACCESS_EXEMPT_PATH_PREFIXES
    ):
        return True
    return resolve_api_route_access_policy(normalized_path) in {"public", "token"}


def is_portal_access_protected_path(path: str) -> bool:
    """포털 접근 승인이 필요한 API 경로인지 반환합니다."""

    normalized_path = _normalize_path(path)
    return normalized_path.startswith(PORTAL_ACCESS_API_PREFIX) and not is_portal_access_exempt_path(
        normalized_path
    )


def resolve_api_route_access_policy(path: str) -> str | None:
    """API 경로에 선언된 public/token/portal/app 접근 정책을 반환합니다."""

    normalized_path = _normalize_path(path)
    for prefix, scope_key in APP_ACCESS_API_RULES:
        if normalized_path == prefix or normalized_path.startswith(f"{prefix}/"):
            return f"app:{scope_key}"

    if not normalized_path.startswith(PORTAL_ACCESS_API_PREFIX):
        return None
    relative_path = normalized_path.removeprefix(PORTAL_ACCESS_API_PREFIX).strip("/")
    if not relative_path:
        return None
    root_route = relative_path.split("/", maxsplit=1)[0]
    return API_ROUTE_ACCESS_POLICIES.get(root_route)


def resolve_app_access_scope_for_path(path: str) -> str | None:
    """API 경로에 대응하는 앱 scope key를 반환합니다."""

    policy = resolve_api_route_access_policy(path)
    if not policy or not policy.startswith("app:"):
        return None
    return policy.removeprefix("app:")


def _get_base_request(request: Any) -> Any:
    """DRF Request이면 내부 Django HttpRequest를 반환합니다."""

    return getattr(request, "_request", request)


def get_request_portal_access_payload(*, request: Any, user: Any) -> dict[str, object]:
    """같은 요청에서는 사용자별 포털 권한 payload를 한 번만 조회합니다."""

    base_request = _get_base_request(request)
    user_id = getattr(user, "pk", None)
    cached = getattr(base_request, _PORTAL_ACCESS_CACHE_ATTRIBUTE, None)
    if isinstance(cached, tuple) and len(cached) == 2 and cached[0] == user_id:
        payload = cached[1]
        if isinstance(payload, dict):
            return payload

    # account 도메인 import는 Django 초기화 순환을 피하기 위해 요청 시점에 수행합니다.
    from api.account import services as account_services

    payload = account_services.get_portal_access_payload(user=user)
    setattr(base_request, _PORTAL_ACCESS_CACHE_ATTRIBUTE, (user_id, payload))
    return payload


def get_request_app_access_payload(
    *,
    request: Any,
    user: Any,
    scope_key: str,
) -> dict[str, object]:
    """같은 요청에서는 사용자와 앱 scope별 권한 payload를 한 번만 조회합니다."""

    base_request = _get_base_request(request)
    user_id = getattr(user, "pk", None)
    cached = getattr(base_request, _APP_ACCESS_CACHE_ATTRIBUTE, None)
    if not isinstance(cached, dict):
        cached = {}
        setattr(base_request, _APP_ACCESS_CACHE_ATTRIBUTE, cached)

    cache_key = (user_id, scope_key)
    payload = cached.get(cache_key)
    if isinstance(payload, dict):
        return payload

    # account 도메인 import는 Django 초기화 순환을 피하기 위해 요청 시점에 수행합니다.
    from api.account import services as account_services

    payload = account_services.get_access_payload(user=user, scope_key=scope_key)
    cached[cache_key] = payload
    return payload


def require_request_app_access(*, request: Any, user: Any) -> dict[str, object] | None:
    """현재 API 경로에 앱 scope가 연결되어 있으면 접근 상태를 검사합니다."""

    path = getattr(request, "path", "") or ""
    scope_key = resolve_app_access_scope_for_path(path)
    if scope_key is None:
        return None
    if not user or not getattr(user, "is_authenticated", False):
        raise PortalAuthenticationRequiredError()

    app_access = get_request_app_access_payload(
        request=request,
        user=user,
        scope_key=scope_key,
    )
    if not app_access.get("allowed"):
        raise AppAccessRequiredError(scope_key=scope_key, app_access=app_access)
    return app_access


def require_request_portal_access(*, request: Any, user: Any) -> dict[str, object] | None:
    """보호 경로의 인증 및 포털 접근 상태를 검사합니다."""

    path = getattr(request, "path", "") or ""
    if not is_portal_access_protected_path(path):
        return None
    if not user or not getattr(user, "is_authenticated", False):
        raise PortalAuthenticationRequiredError()

    portal_access = get_request_portal_access_payload(request=request, user=user)
    if not portal_access.get("allowed"):
        raise PortalAccessRequiredError(portal_access=portal_access)
    require_request_app_access(request=request, user=user)
    return portal_access


class PortalAccessRequiredPermission(BasePermission):
    """기본 DRF view의 익명 및 미승인 포털 요청을 차단합니다."""

    def has_permission(self, request: Any, view: Any) -> bool:
        """공통 포털 접근 검사를 통과한 요청만 허용합니다."""

        require_request_portal_access(request=request, user=getattr(request, "user", None))
        return True


__all__ = [
    "API_ROUTE_ACCESS_POLICIES",
    "PORTAL_ACCESS_API_PREFIX",
    "PORTAL_ACCESS_EXEMPT_PATH_PREFIXES",
    "PORTAL_ACCESS_EXEMPT_PATHS",
    "APP_ACCESS_API_RULES",
    "AppAccessRequiredError",
    "PortalAccessRequiredError",
    "PortalAuthenticationRequiredError",
    "PortalAccessRequiredPermission",
    "get_request_portal_access_payload",
    "get_request_app_access_payload",
    "is_portal_access_exempt_path",
    "is_portal_access_protected_path",
    "require_request_portal_access",
    "require_request_app_access",
    "resolve_api_route_access_policy",
    "resolve_app_access_scope_for_path",
]
