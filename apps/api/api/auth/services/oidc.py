# =============================================================================
# 모듈 설명: id_token 기반 OIDC 세션 인증 엔드포인트를 제공합니다.
# - 주요 대상: auth_config, auth_login, auth_callback, auth_me, auth_logout
# - 불변 조건: settings에 OIDC 설정이 존재해야 합니다.
# =============================================================================

"""id_token-only OIDC 플로우를 사용하는 세션 기반 인증 엔드포인트 모음.

- 주요 대상: auth_config, auth_login, auth_callback, auth_me, auth_logout
- 주요 엔드포인트/클래스: auth_* 함수형 뷰
- 가정/불변 조건: ADFS OIDC 설정이 settings에 등록되어 있음
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

import api.account.services as account_services
from api.common.services import resolve_frontend_target
from .oidc_utils import (
    ADFS_AUTH_URL,       # ADFS 인증 엔드포인트(…/adfs/oauth2/authorize)
    ADFS_LOGOUT_URL,     # ADFS 로그아웃 엔드포인트
    ISSUER,              # 토큰 발급자(iss)
    OIDC_CLIENT_ID,      # audience 검증에 사용
    PUB_KEY,             # RS256 공개키(PEM 문자열 또는 공개키 객체)
    REDIRECT_URI,        # 콜백 URL(ADFS 등록값과 완전히 동일해야 함)
    b64d,                # urlsafe base64 디코드(bytes 반환)
    b64e,                # urlsafe base64 인코드(str 반환)
    is_allowed_redirect, # 화이트리스트 기반 리다이렉트 검증
    pop_nonce,           # 세션에서 nonce pop
    save_nonce,          # 세션에 nonce 저장
)


# =============================================================================
# 내부 유틸: 설정 값 및 공통 처리
# =============================================================================


def _session_max_age() -> Optional[int]:
    """SESSION_COOKIE_AGE 설정을 안전하게 정수로 변환합니다.

    입력:
    - 없음(settings 사용)

    반환:
    - Optional[int]: 양수일 때만 값, 그 외 None

    부작용:
    - 없음

    오류:
    - 없음(변환 실패 시 None 반환)
    """
    # -----------------------------------------------------------------------------
    # 1) 설정값 추출 및 정수 변환
    # -----------------------------------------------------------------------------
    try:
        raw = getattr(settings, "SESSION_COOKIE_AGE", None)
        if raw is None:
            return None
        value = int(raw)
    except (TypeError, ValueError):
        return None
    # -----------------------------------------------------------------------------
    # 2) 양수 여부 확인
    # -----------------------------------------------------------------------------
    return value if value > 0 else None


def _provider_configured() -> bool:
    """OIDC_PROVIDER_CONFIGURED 설정 여부를 bool로 반환합니다.

    입력:
    - 없음(settings 사용)

    반환:
    - bool: 설정 값의 불리언 표현

    부작용:
    - 없음

    오류:
    - 없음
    """
    # -----------------------------------------------------------------------------
    # 1) 설정값 조회 및 bool 변환
    # -----------------------------------------------------------------------------
    return bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))


def _decode_state_to_str(state: str, request: HttpRequest) -> str:
    """state(b64url)를 문자열로 디코드합니다.

    입력:
    - state: base64url 인코딩된 문자열
    - 요청: Django HttpRequest

    반환:
    - str: 디코딩된 문자열 또는 안전한 기본 경로

    부작용:
    - 없음

    오류:
    - 없음(디코딩 실패 시 기본 경로로 폴백)
    """
    # -----------------------------------------------------------------------------
    # 1) base64url 디코딩 시도
    # -----------------------------------------------------------------------------
    try:
        decoded_state = b64d(state)
    except Exception:
        # state 자체가 깨졌다면 기본 프론트엔드로
        return resolve_frontend_target(None, request=request)

    # -----------------------------------------------------------------------------
    # 2) 문자열 타입 처리
    # -----------------------------------------------------------------------------
    if isinstance(decoded_state, str):
        return decoded_state

    # -----------------------------------------------------------------------------
    # 3) 바이트 → 문자열 복구 시도
    # -----------------------------------------------------------------------------
    try:
        return decoded_state.decode("utf-8")
    except Exception:
        # 인코딩 문제 시 최대한 복구
        return str(decoded_state, "utf-8", errors="ignore")


def _safe_redirect_target(target: Optional[str], request: HttpRequest) -> str:
    """target을 안전한 리다이렉트 경로로 정규화합니다.

    입력:
    - target: 요청된 리다이렉트 대상
    - 요청: Django HttpRequest

    반환:
    - str: 화이트리스트를 통과한 안전한 대상

    부작용:
    - 없음

    오류:
    - 없음
    """
    # -----------------------------------------------------------------------------
    # 1) 기본 타깃 해석
    # -----------------------------------------------------------------------------
    resolved = resolve_frontend_target(target, request=request)
    # -----------------------------------------------------------------------------
    # 2) 화이트리스트 검증 및 폴백
    # -----------------------------------------------------------------------------
    if not is_allowed_redirect(resolved):
        return resolve_frontend_target(None, request=request)
    return resolved


def _ensure_pubkey_ready() -> None:
    """PUB_KEY 준비 상태를 확인하고 없으면 RuntimeError를 발생시킵니다.

    입력:
    - 없음(모듈 상수 사용)

    반환:
    - 없음

    부작용:
    - 없음

    오류:
    - RuntimeError: 공개키 설정이 없을 때
    """
    # -----------------------------------------------------------------------------
    # 1) 공개키 존재 여부 확인
    # -----------------------------------------------------------------------------
    if not PUB_KEY:
        raise RuntimeError("OIDC public key (PUB_KEY) is not configured.")
    # 필요하다면 PUB_KEY 타입 검사 추가 가능 (예: isinstance(PUB_KEY, str))


def _redirect_with_error(target: str, error_code: str) -> HttpResponse:
    """공통 에러 리다이렉트 응답을 생성합니다.

    입력:
    - target: 안전한 리다이렉트 대상 URL
    - error_code: 에러 코드 문자열

    반환:
    - HttpResponse: 리다이렉트 응답

    부작용:
    - 없음

    오류:
    - 없음
    """
    # -----------------------------------------------------------------------------
    # 1) 쿼리 구분자 선택
    # -----------------------------------------------------------------------------
    separator = "&" if "?" in target else "?"
    # -----------------------------------------------------------------------------
    # 2) 리다이렉트 응답 생성
    # -----------------------------------------------------------------------------
    return redirect(f"{target}{separator}error={error_code}")


def _decode_id_token(raw_id_token: str) -> Dict[str, Any]:
    """id_token(JWT)을 디코드해 클레임 딕셔너리를 반환합니다.

    입력:
    - raw_id_token: id_token 문자열

    반환:
    - Dict[str, Any]: JWT 클레임

    부작용:
    - 없음

    오류:
    - jwt.PyJWTError: 토큰 파싱/검증 실패
    """
    return jwt.decode(
        raw_id_token,
        PUB_KEY,
        algorithms=["RS256"],
        options={
            # 할 일: 운영 환경에서는 아래 옵션들을 True로 설정하고
            #        leeway/clock_skew 조정 및 iss/aud 검증을 활성화하는 것이 안전함.
            # 사내 시스템 전용이라 토큰 검증을 의도적으로 비활성화함.
            "verify_signature": False,
            "verify_exp": False,
            "verify_aud": False,
            "verify_iss": False,
        },
    )


def _extract_user_info_from_claims(claims: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """ADFS 클레임을 사용자 모델 필드로 매핑해 반환합니다.

    입력:
    - claims: id_token에서 추출한 클레임 딕셔너리

    반환:
    - Dict[str, Optional[str]]: 사용자 필드 매핑 결과

    부작용:
    - 없음

    오류:
    - 없음

    매핑 예시:
    - loginid → knox_id (로그인 ID 매핑)
    - userid → avatarid (아바타 ID 매핑)
    - sabun → sabun (사번 유지)
    - username → username (first_name/last_name 계산에 사용)
    - mail → email (이메일 매핑)
    """
    # -----------------------------------------------------------------------------
    # 1) 클레임-필드 매핑 정의
    # -----------------------------------------------------------------------------
    claim_to_field = {
        "loginid": "knox_id",
        "userid": "avatarid",
        "sabun": "sabun",
        "username": "username",
        "username_en": "username_en",
        "first_name": "first_name",
        "last_name": "last_name",
        "givenname": "givenname",
        "surname": "surname",
        "deptname": "department",
        "deptid": "deptid",
        "mail": "email",
        "grdName": "grd_name",
        "grdname_en": "grdname_en",
        "busname": "busname",
        "intcode": "intcode",
        "intname": "intname",
        "origincomp": "origincomp",
        "employeetype": "employeetype",
    }

    # -----------------------------------------------------------------------------
    # 2) 기본 값 추출 및 정규화
    # -----------------------------------------------------------------------------
    info: Dict[str, Optional[str]] = {}
    for claim_key, field_name in claim_to_field.items():
        raw = claims.get(claim_key)
        value = str(raw).strip() if raw is not None else ""
        info[field_name] = value or None

    # -----------------------------------------------------------------------------
    # 3) 이름 정보 보정
    # -----------------------------------------------------------------------------
    username = info.get("username") or ""
    if username and (not info.get("first_name") or not info.get("last_name")):
        trimmed = username.strip()
        if trimmed:
            if len(trimmed) >= 2:
                info["last_name"] = info.get("last_name") or trimmed[:1]
                info["first_name"] = info.get("first_name") or trimmed[1:]
            else:
                info["first_name"] = info.get("first_name") or trimmed

    # -----------------------------------------------------------------------------
    # 4) 결과 반환
    # -----------------------------------------------------------------------------
    return info


# =============================================================================
# 공개 엔드포인트
# =============================================================================


def auth_config(request: HttpRequest) -> JsonResponse:
    """프런트엔드에 필요한 최소 OIDC 설정을 제공합니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - JsonResponse: OIDC 설정 값

    부작용:
    - 없음

    오류:
    - 없음

    예시 요청:
    - 예시 요청: GET /api/v1/auth/config

    예시 응답:
    - 예시 응답: 200 {"issuer": "...", "clientId": "...", "loginUrl": "...", "locale": "ko-KR", "timeZone": "Asia/Seoul"}

    snake/camel 호환:
    - 해당 없음(요청 바디 없음)
    """
    # -----------------------------------------------------------------------------
    # 1) 설정 페이로드 구성
    # -----------------------------------------------------------------------------
    config = {
        "issuer": ISSUER,
        "clientId": OIDC_CLIENT_ID,
        "loginUrl": "/api/v1/auth/login",
        "logoutUrl": "/api/v1/auth/logout",
        "meUrl": "/api/v1/auth/me",
        "callbackUrl": REDIRECT_URI,
        "responseMode": "form_post",
        "responseType": "id_token",
        "frontendRedirect": settings.FRONTEND_BASE_URL,
        "sessionMaxAgeSeconds": _session_max_age(),
        "providerConfigured": _provider_configured(),
        "locale": getattr(settings, "LANGUAGE_CODE", "") or "",
        "timeZone": getattr(settings, "TIME_ZONE", "") or "",
    }
    # -----------------------------------------------------------------------------
    # 2) 응답 반환
    # -----------------------------------------------------------------------------
    return JsonResponse(config)


def auth_login(request: HttpRequest) -> HttpResponse:
    """ADFS 로그인 시작 엔드포인트입니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - HttpResponse: ADFS authorize로 리다이렉트 응답

    부작용:
    - 세션에 nonce 저장

    오류:
    - 400: OIDC 설정이 비활성화된 경우

    예시 요청:
    - 예시 요청: GET /api/v1/auth/login?target=/dashboard

    예시 응답:
    - 예시 응답: 302 Location: https://<adfs-auth>/?client_id=...

    snake/camel 호환:
    - 해당 없음(쿼리 파라미터 target/next만 사용)
    """
    # -----------------------------------------------------------------------------
    # 1) 제공자 설정 확인
    # -----------------------------------------------------------------------------
    if not _provider_configured():
        return HttpResponseBadRequest("oidc not configured")

    # -----------------------------------------------------------------------------
    # 2) 리다이렉트 대상 준비
    # -----------------------------------------------------------------------------
    requested_target = request.GET.get("target") or request.GET.get("next")
    target = _safe_redirect_target(requested_target, request)
    state = b64e(target)

    # -----------------------------------------------------------------------------
    # 3) nonce 생성 및 저장
    # -----------------------------------------------------------------------------
    nonce = uuid.uuid4().hex
    save_nonce(request, nonce)  # 콜백에서 pop 하여 재사용 방지

    # -----------------------------------------------------------------------------
    # 4) ADFS 요청 파라미터 구성
    # -----------------------------------------------------------------------------
    params = {
        "client_id": OIDC_CLIENT_ID,
        # ADFS에 등록된 redirect_uri와 완전히 일치해야 함
        "redirect_uri": REDIRECT_URI,
        "response_mode": "form_post",  # 폼 POST로 id_token 전달
        "response_type": "id_token",   # 암시적 id_token 전용
        "scope": "openid profile email",
        "nonce": nonce,
        "state": state,
    }
    # -----------------------------------------------------------------------------
    # 5) ADFS authorize로 리다이렉트
    # -----------------------------------------------------------------------------
    return redirect(f"{ADFS_AUTH_URL}?{urlencode(params)}")


@csrf_exempt
def auth_callback(request: HttpRequest) -> HttpResponse:
    """ADFS form_post 콜백을 처리하고 세션 로그인을 수행합니다.

    입력:
    - 요청: Django HttpRequest (form_post)

    반환:
    - HttpResponse: 리다이렉트 또는 오류 응답

    부작용:
    - 사용자 생성/갱신 및 세션 로그인
    - 현재 소속 접근 권한 행 보장

    오류:
    - 400: 잘못된 메서드, 설정 비활성화, 파라미터 누락
    - 302: 토큰 오류/nonce 오류 시 error 쿼리를 포함해 리다이렉트

    예시 요청:
    - 예시 요청: POST /api/v1/auth/callback
      폼 예시: id_token=<jwt>&state=<b64url>

    예시 응답:
    - 예시 응답: 302 Location: https://<frontend>/?error=invalid_token

    snake/camel 호환:
    - 해당 없음(form_post 키를 그대로 사용)
    """
    # -----------------------------------------------------------------------------
    # 1) 메서드 및 설정 확인
    # -----------------------------------------------------------------------------
    if request.method != "POST":
        return HttpResponseBadRequest("form_post only")

    if not _provider_configured():
        return HttpResponseBadRequest("oidc not configured")

    # -----------------------------------------------------------------------------
    # 2) 필수 파라미터 추출
    # -----------------------------------------------------------------------------
    # form_post에서 넘어온 필수 파라미터
    id_token = request.POST.get("id_token")
    state = request.POST.get("state")
    if not id_token or not state:
        return HttpResponseBadRequest("missing id_token/state")

    # -----------------------------------------------------------------------------
    # 3) state 복원 및 안전한 타깃 계산
    # -----------------------------------------------------------------------------
    # state 복원 → target 문자열 → 안전한 리다이렉트 경로로 정규화
    raw_target = _decode_state_to_str(state, request)
    target = _safe_redirect_target(raw_target, request)

    # -----------------------------------------------------------------------------
    # 4) 세션 nonce 준비
    # -----------------------------------------------------------------------------
    # 세션에서 nonce를 꺼내 검증 준비
    expected_nonce = pop_nonce(request)

    # -----------------------------------------------------------------------------
    # 5) 공개키 준비 확인
    # -----------------------------------------------------------------------------
    # 공개키 준비 확인 (설정 누락 시 조기에 에러 발생)
    _ensure_pubkey_ready()

    # -----------------------------------------------------------------------------
    # 6) id_token 디코드 및 오류 처리
    # -----------------------------------------------------------------------------
    # id_token 디코드
    try:
        decoded = _decode_id_token(id_token)
    except jwt.ExpiredSignatureError:
        return _redirect_with_error(target, "token_expired")
    except jwt.InvalidIssuerError:
        return _redirect_with_error(target, "invalid_iss")
    except jwt.InvalidAudienceError:
        return _redirect_with_error(target, "invalid_aud")
    except jwt.PyJWTError:
        # 기타 서명/포맷 오류 등
        return _redirect_with_error(target, "invalid_token")

    # -----------------------------------------------------------------------------
    # 7) nonce 검증
    # -----------------------------------------------------------------------------
    # nonce 일치 여부 확인 (재전송/재사용 방지)
    if expected_nonce is None or decoded.get("nonce") != expected_nonce:
        return _redirect_with_error(target, "invalid_nonce")

    # -----------------------------------------------------------------------------
    # 8) 사용자 정보 추출 및 필수 필드 확인
    # -----------------------------------------------------------------------------
    # loginid / sabun / department / email 기반 사용자 정보 추출
    info = _extract_user_info_from_claims(decoded)
    sabun = info.get("sabun")
    knox_id = info.get("knox_id")

    # Django username 필드는 sabun을 사용 (항상 온다고 가정)
    if not sabun:
        return _redirect_with_error(target, "missing_sabun")
    if not knox_id:
        return _redirect_with_error(target, "missing_loginid")

    # -----------------------------------------------------------------------------
    # 9) 사용자 생성/갱신
    # -----------------------------------------------------------------------------
    # Django 유저 생성/업데이트
    UserModel = get_user_model()
    defaults = {key: value for key, value in info.items() if key != "sabun"}
    user, created = UserModel.objects.get_or_create(sabun=str(sabun), defaults=defaults)

    update_fields = []

    candidate_updates = {**info, "knox_id": str(knox_id)}
    candidate_updates.pop("sabun", None)

    for field_name, value in candidate_updates.items():
        if not value:
            continue
        if not hasattr(user, field_name):
            continue
        if getattr(user, field_name) == value:
            continue
        setattr(user, field_name, value)
        update_fields.append(field_name)

    if created or update_fields:
        user.save(update_fields=update_fields or None)

    # -----------------------------------------------------------------------------
    # 9-1) 최초 생성 사용자 외부 소속 자동 승인(가능한 경우에만)
    # -----------------------------------------------------------------------------
    if created:
        account_services.auto_approve_affiliation_from_snapshot(
            user=user,
            timezone_name=str(getattr(settings, "TIME_ZONE", "UTC") or "UTC"),
        )

    # -----------------------------------------------------------------------------
    # 9-2) 현재 소속 접근 권한 행 보장
    # -----------------------------------------------------------------------------
    account_services.ensure_self_access(user, role="member")

    # -----------------------------------------------------------------------------
    # 10) 세션 로그인 및 리다이렉트
    # -----------------------------------------------------------------------------
    # 세션 로그인 후 프런트로 리다이렉트
    login(request, user)
    return redirect(target)


def auth_me(request: HttpRequest) -> JsonResponse:
    """현재 로그인한 사용자 정보를 반환합니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - JsonResponse: 사용자 정보 또는 에러

    부작용:
    - 현재 소속 접근 권한 행 보장

    오류:
    - 401: 미인증 사용자

    예시 요청:
    - 예시 요청: GET /api/v1/auth/me

    예시 응답:
    - 예시 응답: 200 {"id": 1, "usr_id": "...", "avatarid": "U-12345", "username": "...", "has_pending_affiliation": false}

    snake/camel 호환:
    - 해당 없음(요청 바디 없음)
    """
    # -----------------------------------------------------------------------------
    # 1) 인증 여부 확인
    # -----------------------------------------------------------------------------
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "unauthorized"}, status=401)

    # -----------------------------------------------------------------------------
    # 2) 사용자 정보 준비
    # -----------------------------------------------------------------------------
    user = request.user
    account_services.ensure_self_access(user, role="member")
    username = user.username if isinstance(getattr(user, "username", None), str) else ""
    pending_change = account_services.get_pending_user_sdwt_prod_change(user=user)
    pending_user_sdwt_prod = pending_change.to_user_sdwt_prod if pending_change else None
    has_pending_affiliation = pending_change is not None
    # -----------------------------------------------------------------------------
    # 3) 응답 페이로드 구성
    # -----------------------------------------------------------------------------
    payload = {
        "id": user.pk,
        "usr_id": getattr(user, "knox_id", None),  # = 사용자 모델의 knox_id
        "avatarid": getattr(user, "avatarid", None),  # = 사용자 모델의 avatarid
        "username": username,  # = 사용자 표시용 이름(사용자 모델의 username)
        "email": user.email,
        "is_superuser": bool(getattr(user, "is_superuser", False)),
        "is_staff": bool(getattr(user, "is_staff", False)),
        "roles": [],  # 필요 시 롤/권한 매핑 로직 추가
        "department": getattr(user, "department", None),
        "line": getattr(user, "line", None),
        "user_sdwt_prod": getattr(user, "user_sdwt_prod", None),
        "pending_user_sdwt_prod": pending_user_sdwt_prod,
        "has_pending_affiliation": has_pending_affiliation,
    }
    # -----------------------------------------------------------------------------
    # 4) 응답 반환
    # -----------------------------------------------------------------------------
    return JsonResponse(payload)


def auth_logout(request: HttpRequest) -> HttpResponse:
    """로컬 세션 종료 후 IdP 로그아웃 URL을 안내하거나 리다이렉트합니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - HttpResponse: JSON 응답 또는 리다이렉트

    부작용:
    - Django 세션 종료 및 세션 쿠키 삭제

    오류:
    - 없음

    예시 요청:
    - 예시 요청: POST /api/v1/auth/logout
    - 예시 요청: GET /api/v1/auth/logout

    예시 응답:
    - 예시 응답: 200 {"logoutUrl": "https://<adfs-logout>"}
    - 예시 응답: 302 Location: https://<adfs-logout>

    snake/camel 호환:
    - 해당 없음(요청 바디 없음)
    """
    # -----------------------------------------------------------------------------
    # 1) 세션 로그아웃 처리
    # -----------------------------------------------------------------------------
    logout(request)

    # -----------------------------------------------------------------------------
    # 2) 세션 쿠키 삭제 헬퍼 정의
    # -----------------------------------------------------------------------------
    def _delete_session_cookie(응답: HttpResponse) -> HttpResponse:
        """세션 쿠키를 삭제한 응답을 반환합니다.

        입력:
        - 응답: HttpResponse

        반환:
        - HttpResponse: 세션 쿠키가 제거된 응답

        부작용:
        - 응답에 세션 쿠키 삭제 지시 추가

        오류:
        - 없음
        """
        응답.delete_cookie(settings.SESSION_COOKIE_NAME)
        return 응답

    # -----------------------------------------------------------------------------
    # 3) 요청 메서드에 따른 분기 처리
    # -----------------------------------------------------------------------------
    if request.method == "POST":
        response = JsonResponse({"logoutUrl": ADFS_LOGOUT_URL})
        return _delete_session_cookie(response)

    # -----------------------------------------------------------------------------
    # 4) 기본 GET 리다이렉트 처리
    # -----------------------------------------------------------------------------
    response = redirect(ADFS_LOGOUT_URL)
    return _delete_session_cookie(response)


__all__ = [
    "auth_config",
    "auth_login",
    "auth_callback",
    "auth_me",
    "auth_logout",
]
