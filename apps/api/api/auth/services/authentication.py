# =============================================================================
# 모듈 설명: API 인증 헬퍼를 제공합니다.
# - 주요 클래스: CsrfExemptSessionAuthentication, PortalAccessBasicAuthentication
# - 불변 조건: 사내망 환경에서 세션 쿠키 인증을 사용합니다.
# =============================================================================

"""API 서비스용 인증 헬퍼 모듈.

- 주요 대상: CsrfExemptSessionAuthentication, PortalAccessBasicAuthentication
- 주요 엔드포인트/클래스: 세션 인증, 포털 접근 검사가 포함된 Basic 인증
- 가정/불변 조건: 사내망 환경에서 세션 쿠키 기반 인증을 사용함
"""

from __future__ import annotations  # 미래 버전 호환 (타입 주석 등에서 문자열 참조 가능)

from typing import Any

from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.exceptions import PermissionDenied

from api.common.permissions import require_request_portal_access


def _is_knox_id_exempt_path(path: str) -> bool:
    """KnoxIdRequiredMiddleware와 같은 예외 경로 정책을 적용합니다."""

    # 인증 모듈 초기화 시 공용 middleware를 다시 불러오는 순환을 피합니다.
    from api.common.services.middleware import KnoxIdRequiredMiddleware

    if not path:
        return False
    if path in KnoxIdRequiredMiddleware.EXEMPT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in KnoxIdRequiredMiddleware.EXEMPT_PATH_PREFIXES)


def _require_basic_user_knox_id(*, request: Any, user: Any) -> None:
    """Basic 인증 사용자의 필수 knox_id를 검사합니다."""

    path = getattr(request, "path", "") or ""
    if _is_knox_id_exempt_path(path):
        return

    knox_id = getattr(user, "knox_id", None)
    if not isinstance(knox_id, str) or not knox_id.strip():
        raise PermissionDenied({"error": "knox_id is required"})


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """CSRF 검사를 생략하는 SessionAuthentication 커스텀 클래스입니다.

    역할:
    - 세션 쿠키 인증은 유지하면서 CSRF 검사를 우회합니다.
    - 사내망 전용 환경에서 프론트엔드 요청 편의를 높입니다.
    """

    def enforce_csrf(self, request):
        """CSRF 검사 단계를 오버라이드하여 검사를 생략합니다.

        입력:
        - 요청: Django HttpRequest

        반환:
        - None: 항상 통과

        부작용:
        - CSRF 검사가 수행되지 않음

        오류:
        - 없음
        """

        return None  # CSRF 검사를 수행하지 않음


class PortalAccessBasicAuthentication(BasicAuthentication):
    """Basic 인증 성공 직후 포털 접근 승인 상태를 검사합니다."""

    def authenticate(self, request: Any) -> tuple[Any, Any] | None:
        """Basic 사용자 인증 후 보호 경로의 포털 접근 권한을 강제합니다."""

        result = super().authenticate(request)
        if result is None:
            return None

        user, _auth = result
        _require_basic_user_knox_id(request=request, user=user)
        require_request_portal_access(request=request, user=user)
        return result


# 이 모듈에서 외부로 노출할 심볼을 명시
__all__ = ["CsrfExemptSessionAuthentication", "PortalAccessBasicAuthentication"]
