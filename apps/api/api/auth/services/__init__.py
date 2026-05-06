# =============================================================================
# 모듈 설명: auth 도메인 서비스의 공개 파사드를 제공합니다.
# - 주요 대상: OIDC 인증 플로우, 인증 클래스
# - 불변 조건: 외부 모듈은 이 파사드를 통해 auth 서비스를 사용합니다.
# =============================================================================

"""auth 서비스 공개 파사드.

- 주요 대상: auth_* 엔드포인트 로직, CsrfExemptSessionAuthentication
- 주요 엔드포인트/클래스: auth_config/auth_login/auth_callback/auth_me/auth_logout
- 가정/불변 조건: OIDC 설정은 settings/env에서 주입됨
"""
from __future__ import annotations

from .authentication import CsrfExemptSessionAuthentication
from .oidc import (
    auth_callback,
    auth_config,
    auth_login,
    auth_logout,
    auth_me,
)

__all__ = [
    "CsrfExemptSessionAuthentication",
    "auth_callback",
    "auth_config",
    "auth_login",
    "auth_logout",
    "auth_me",
]
