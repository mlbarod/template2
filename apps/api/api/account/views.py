# =============================================================================
# 모듈 설명: account 도메인 APIView를 제공합니다.
# - 주요 대상: 소속 변경/승인/재확인, 권한 부여, 외부 동기화
# - 불변 조건: 비즈니스 로직은 서비스/셀렉터로 위임합니다.
# =============================================================================

"""계정 도메인 APIView 모음.

- 주요 대상: 소속 변경, 개요 조회, 승인/목록, 외부 동기화, 권한 부여
- 주요 엔드포인트/클래스: AccountAffiliationView 등
- 가정/불변 조건: 모든 날짜는 UTC 기준으로 처리되며 입력이 없으면 KST로 해석함
"""
from __future__ import annotations

from datetime import timezone as dt_timezone
from typing import Optional
from zoneinfo import ZoneInfo

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import ensure_airflow_token, normalize_text, parse_json_body

from . import selectors, services
from .serializers import (
    AffiliationApprovalSerializer,
    AffiliationReconfirmResponseSerializer,
    ExternalAffiliationSyncSerializer,
)

# -----------------------------------------------------------------------------
# 시간대/페이지네이션 상수
# -----------------------------------------------------------------------------
KST = ZoneInfo("Asia/Seoul")          # 타임존 없는 datetime을 KST로 해석할 때 사용할 tzinfo
TIMEZONE_NAME = "Asia/Seoul"         # 서비스 레이어에 전달할 시간대 이름
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _parse_effective_from(value: Optional[str]):
    """effective_from 입력 문자열을 UTC timezone-aware datetime으로 변환합니다.

    입력:
    - value: ISO 형식 날짜 문자열

    반환:
    - datetime | None: UTC 기준 datetime 또는 None

    부작용:
    - 없음

    오류:
    - 없음(파싱 실패 시 None 반환)

    허용 예시:
    - 예시: "2025-12-28T10:30:00+09:00"
    - 예시: "2025-12-28T01:30:00Z"
    - "2025-12-28T10:30:00" (타임존 정보 없으면 KST로 간주)
    """
    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    if not value:
        return None

    # -----------------------------------------------------------------------------
    # 2) ISO 문자열 파싱
    # -----------------------------------------------------------------------------
    parsed = parse_datetime(str(value))
    if not parsed:
        return None

    # -----------------------------------------------------------------------------
    # 3) 타임존 정보 보정(KST 가정)
    # -----------------------------------------------------------------------------
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=KST)

    # -----------------------------------------------------------------------------
    # 4) UTC로 변환
    # -----------------------------------------------------------------------------
    return parsed.astimezone(dt_timezone.utc)


def _parse_int(value: object, default: int) -> int:
    """입력 값을 int로 파싱하며 실패 시 기본값을 반환합니다.

    입력:
    - value: 변환 대상 값
    - default: 기본값

    반환:
    - int: 파싱된 값 또는 기본값

    부작용:
    - 없음

    오류:
    - 없음
    """
    try:
        parsed = int(value)
        if parsed <= 0:
            return default
        return parsed
    except (TypeError, ValueError):
        return default


# =============================================================================
# 1) 사용자: 내 소속 확인/변경 신청
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationView(APIView):
    """현재 사용자의 user_sdwt_prod 소속 변경을 신청합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """로그인 사용자 기준 소속 개요 데이터를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 소속 개요 데이터

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/affiliation

        예시 응답:
        - 예시 응답: 200 {"currentUserSdwtProd": "...", "accessibleUserSdwtProds": [...]}

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload = services.get_affiliation_overview(user=user, timezone_name=TIMEZONE_NAME)
        return JsonResponse(payload)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """소속 변경 요청을 생성합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 변경 요청 결과

        부작용:
        - 변경 요청 생성(서비스 레이어)

        오류:
        - 400: 입력 오류
        - 401: 미인증

        예시 요청:
        - 예시 요청: POST /api/v1/account/affiliation
          요청 바디 예시: {"user_sdwt_prod":"SDWT_A","effective_from":"2025-12-28T10:00:00+09:00"}

        snake/camel 호환:
        - user_sdwt_prod / userSdwtProd (키 매핑)
        - effective_from / effectiveFrom (키 매핑)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) user_sdwt_prod 추출(호환 키 포함)
        # -----------------------------------------------------------------------------
        new_value = normalize_text(payload.get("user_sdwt_prod"))
        if not new_value:
            new_value = normalize_text(payload.get("userSdwtProd"))
        if not new_value:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 4) 소속 옵션 유효성 검증
        # -----------------------------------------------------------------------------
        option = selectors.get_affiliation_option_by_user_sdwt_prod(user_sdwt_prod=new_value)
        if option is None:
            return JsonResponse({"error": "Invalid user_sdwt_prod"}, status=400)

        # -----------------------------------------------------------------------------
        # 5) effective_from 파싱
        # -----------------------------------------------------------------------------
        effective_from_raw = payload.get("effective_from") or payload.get("effectiveFrom")
        effective_from = _parse_effective_from(effective_from_raw)
        if effective_from_raw and effective_from is None:
            return JsonResponse({"error": "Invalid effective_from"}, status=400)

        # -----------------------------------------------------------------------------
        # 6) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        response_payload, status_code = services.request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod=new_value,
            effective_from=effective_from,
            timezone_name=TIMEZONE_NAME,
        )
        return JsonResponse(response_payload, status=status_code)


# =============================================================================
# 2) 사용자: 계정 화면 한 번에 로딩할 개요
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountOverviewView(APIView):
    """계정 화면에서 필요한 데이터를 한번에 제공합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """계정 화면 구성에 필요한 데이터를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 계정 개요 데이터

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/overview

        예시 응답:
        - 예시 응답: 200 {"user": {...}, "affiliationHistory": [...], "manageableGroups": [...]}

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload = services.get_account_overview(user=user, timezone_name=TIMEZONE_NAME)
        return JsonResponse(payload)


# =============================================================================
# 3) 관리자(그룹 매니저/슈퍼유저): 소속 변경 요청 승인/거절
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationApprovalView(APIView):
    """해당 소속 관리자(그룹 매니저)/슈퍼유저가 소속 변경 요청을 승인한다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """소속 변경 요청을 승인/거절합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 승인/거절 결과

        부작용:
        - 변경 요청 승인/거절 처리

        오류:
        - 400: 입력 오류
        - 401: 미인증

        예시 요청:
        - 예시 요청: POST /api/v1/account/affiliation/approve
          요청 바디 예시: {"changeId":123,"decision":"approve"}
          요청 바디 예시: {"changeId":123,"decision":"reject","rejectionReason":"소속 정보 불일치"}

        snake/camel 호환:
        - rejection_reason / rejectionReason (키 매핑)
        - changeId (레거시 id 보정 지원)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 하위 호환 키 보정
        # -----------------------------------------------------------------------------
        if "changeId" not in payload and "id" in payload:
            payload = {**payload, "changeId": payload.get("id")}
        if "rejectionReason" not in payload and "rejection_reason" in payload:
            payload = {**payload, "rejectionReason": payload.get("rejection_reason")}

        # -----------------------------------------------------------------------------
        # 4) 입력 검증
        # -----------------------------------------------------------------------------
        serializer = AffiliationApprovalSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        change_id = serializer.validated_data["changeId"]
        decision = (serializer.validated_data.get("decision") or "approve").lower()
        rejection_reason = (serializer.validated_data.get("rejectionReason") or "").strip() or None

        # -----------------------------------------------------------------------------
        # 5) 의사결정에 따른 서비스 호출
        # -----------------------------------------------------------------------------
        if decision == "reject":
            response_payload, status_code = services.reject_affiliation_change(
                approver=user,
                change_id=change_id,
                rejection_reason=rejection_reason,
            )
        else:
            response_payload, status_code = services.approve_affiliation_change(
                approver=user,
                change_id=change_id,
            )
        return JsonResponse(response_payload, status=status_code)


# =============================================================================
# 4) 관리자/사용자: 소속 변경 요청 목록 조회 (검색/필터/페이지네이션)
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationRequestListView(APIView):
    """소속 변경 요청 목록을 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """소속 변경 요청 목록을 검색/필터링하여 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 변경 요청 목록 및 페이지 정보

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/affiliation/requests?status=pending&q=kim&userSdwtProd=SDWT_A&page=2&pageSize=50

        snake/camel 호환:
        - user_sdwt_prod / userSdwtProd (키 매핑)
        - page_size / pageSize (키 매핑)

        기타 호환:
        - q / search (검색 키)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 상태/검색/그룹 필터 추출
        # -----------------------------------------------------------------------------
        status = (request.GET.get("status") or "pending").strip()

        search = (request.GET.get("q") or request.GET.get("search") or "").strip()

        user_sdwt_prod = (
            request.GET.get("user_sdwt_prod")
            or request.GET.get("userSdwtProd")
            or ""
        ).strip()

        # -----------------------------------------------------------------------------
        # 3) 페이지네이션 파라미터 보정
        # -----------------------------------------------------------------------------
        page = _parse_int(request.GET.get("page"), 1)
        page_size = min(
            _parse_int(
                request.GET.get("page_size") or request.GET.get("pageSize"),
                DEFAULT_PAGE_SIZE,
            ),
            MAX_PAGE_SIZE,
        )

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload, status_code = services.get_affiliation_change_requests(
            user=user,
            status=status if status and status.lower() != "all" else None,
            search=search or None,
            user_sdwt_prod=user_sdwt_prod or None,
            page=page,
            page_size=page_size,
        )
        return JsonResponse(payload, status=status_code)


# =============================================================================
# 5) 사용자: 외부 예측 소속 변경 시 "재확인" 상태 조회/응답
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationReconfirmView(APIView):
    """외부 예측 소속 변경 시 사용자 재확인 여부를 조회/응답합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """재확인 대상 여부와 관련 정보를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 재확인 상태 정보

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/affiliation/reconfirm

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload = services.get_affiliation_reconfirm_status(user=user)
        return JsonResponse(payload)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """사용자가 재확인 응답을 제출합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 처리 결과

        부작용:
        - 자동 승인 선택 시 소속 변경이 즉시 적용됨
        - 예측값 불일치 또는 예측 없음 선택 시 승인 대기 요청이 생성됨
        - 기존 유지/자동 승인/승인 대기 생성 성공 시 재확인 플래그가 해제됨

        오류:
        - 400: 입력 오류
        - 401: 미인증
        - 409: 재확인 대상 아님

        예시 요청:
        - 예시 요청: POST /api/v1/account/affiliation/reconfirm
          요청 바디 예시(변경 적용): {"accepted": true, "user_sdwt_prod": "G1"}
        - 예시 요청: POST /api/v1/account/affiliation/reconfirm
          요청 바디 예시(승인 대기): {"accepted": true, "user_sdwt_prod": "G2"}
        - 예시 요청: POST /api/v1/account/affiliation/reconfirm
          요청 바디 예시(기존 유지): {"accepted": false}

        snake/camel 호환:
        - 해당 없음(요청 바디는 snake_case만 허용)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 입력 검증
        # -----------------------------------------------------------------------------
        serializer = AffiliationReconfirmResponseSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        validated = serializer.validated_data
        response_payload, status_code = services.submit_affiliation_reconfirm_response(
            user=user,
            accepted=validated["accepted"],
            department=validated.get("department"),
            line=validated.get("line"),
            user_sdwt_prod=validated.get("user_sdwt_prod"),
            timezone_name=TIMEZONE_NAME,
        )
        return JsonResponse(response_payload, status=status_code)


# =============================================================================
# 6) Airflow(또는 외부 배치): 외부 예측 소속 스냅샷 동기화 엔드포인트
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountExternalAffiliationSyncView(APIView):
    """외부 DB 예측 소속 스냅샷을 동기화합니다 (Airflow 토큰 인증)."""

    # DRF의 기본 권한(permission, 예: IsAuthenticated)을 끄고,
    # 아래 ensure_airflow_token으로 별도 인증을 적용하려는 의도입니다.
    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """Airflow 토큰 인증 후 외부 소속 스냅샷을 동기화합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 동기화 결과

        부작용:
        - 외부 소속 스냅샷 업데이트

        오류:
        - 400: 입력 오류
        - 401/403: 토큰 인증 실패

        예시 요청:
        - 예시 요청: POST /api/v1/account/external-affiliations/sync
          헤더 예시: Authorization: Bearer <token>
          요청 바디 예시: {"records":[{"knox_id":"K1","department":"Dept","user_sdwt_prod":"G1","source_updated_at":"2025-01-01T00:00:00Z"}]}

        snake/camel 호환:
        - 해당 없음(요청 바디는 snake_case만 허용)
        """
        # -----------------------------------------------------------------------------
        # 1) Airflow 토큰 검증
        # -----------------------------------------------------------------------------
        auth_response = ensure_airflow_token(request, require_bearer=True)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 입력 검증
        # -----------------------------------------------------------------------------
        serializer = ExternalAffiliationSyncSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        records = serializer.validated_data.get("records") or []
        result = services.sync_external_affiliations(records=records)
        return JsonResponse(result)


# =============================================================================
# 7) 그룹 접근 권한 부여/회수
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountGrantView(APIView):
    """user_sdwt_prod 그룹 접근 권한 부여/회수."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """특정 유저에게 그룹 권한을 grant/revoke 합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 권한 변경 결과

        부작용:
        - 접근 권한 부여/회수

        오류:
        - 400: 입력 오류
        - 401: 미인증
        - 404: 대상 사용자 없음

        예시 요청:
        - 예시 요청: POST /api/v1/account/access/grants
          요청 바디 예시: {"user_sdwt_prod":"SDWT_A","userId":123,"action":"grant","role":"manager"}

        snake/camel 호환:
        - user_sdwt_prod / userSdwtProd (키 매핑)
        - userId / user_id (키 매핑)
        - role / accessRole (키 매핑)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 대상 그룹/사용자 추출
        # -----------------------------------------------------------------------------
        target_group = (payload.get("user_sdwt_prod") or payload.get("userSdwtProd") or "").strip()
        if not target_group:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)

        target_user = services.resolve_target_user(
            target_id=payload.get("userId") or payload.get("user_id"),
            target_knox_id=payload.get("knox_id"),
        )
        if not target_user:
            return JsonResponse({"error": "Target user not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 4) 액션/역할 정규화
        # -----------------------------------------------------------------------------
        action = (payload.get("action") or "grant").lower()
        role = (payload.get("role") or payload.get("accessRole") or "").strip().lower()
        if action != "revoke":
            if not role:
                return JsonResponse({"error": "role is required"}, status=400)
            if role not in {"viewer", "member", "manager"}:
                return JsonResponse({"error": "Invalid role"}, status=400)

        # -----------------------------------------------------------------------------
        # 5) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        response_payload, status_code = services.grant_or_revoke_access(
            grantor=user,
            target_group=target_group,
            target_user=target_user,
            action=action,
            role=role or None,
        )
        return JsonResponse(response_payload, status=status_code)


# =============================================================================
# 9) 내가 관리 가능한 그룹 + 멤버 목록 조회
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountGrantListView(APIView):
    """요청 사용자가 관리할 수 있는 user_sdwt_prod 그룹 멤버 목록 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """관리 가능한 그룹과 해당 멤버 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 그룹/멤버 목록

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/access/manageable

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload = services.get_manageable_groups_with_members(user=user)
        return JsonResponse(payload)


# =============================================================================
# 10) 소속 멤버 목록 조회
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationMembersView(APIView):
    """접근 가능한 소속의 사용자 멤버 목록을 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """소속 멤버 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 소속 멤버 목록

        부작용:
        - 없음

        오류:
        - 400: 소속 식별자 누락
        - 401: 미인증
        - 403: 접근 권한 없음

        예시 요청:
        - 예시 요청: GET /api/v1/account/affiliation/members?user_sdwt_prod=SDWT_A

        snake/camel 호환:
        - user_sdwt_prod / userSdwtProd (쿼리 키 매핑)
        """

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        user_sdwt_prod = (
            request.GET.get("user_sdwt_prod")
            or request.GET.get("userSdwtProd")
            or selectors.get_current_user_sdwt_prod(user=user)
            or ""
        ).strip()
        payload, status_code = services.get_affiliation_members(
            user=user,
            user_sdwt_prod=user_sdwt_prod,
        )
        return JsonResponse(payload, status=status_code)


# =============================================================================
# 11) 사용자 pool 조회
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class AccountUserPoolView(APIView):
    """수신인 선택 UI에서 사용할 account_user 기반 사용자 pool 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """활성 사용자 검색 결과와 user_sdwt_prod 옵션을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 사용자 옵션 및 소속 옵션

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/users?search=kim
        - 예시 요청: GET /api/v1/account/users?userSdwtProd=PHOTO_B

        snake/camel 호환:
        - user_sdwt_prod / userSdwtProd (쿼리 키 매핑)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 쿼리 파라미터 정규화
        # -----------------------------------------------------------------------------
        search = normalize_text(request.GET.get("search"))
        user_sdwt_prod = normalize_text(request.GET.get("user_sdwt_prod"))
        if not user_sdwt_prod:
            user_sdwt_prod = normalize_text(request.GET.get("userSdwtProd"))
        contact_field = normalize_text(request.GET.get("contactField"))
        if contact_field and contact_field not in {"email", "knox_id"}:
            return JsonResponse({"error": "contactField must be email or knox_id"}, status=400)
        raw_limit = normalize_text(request.GET.get("limit"))
        limit = None if raw_limit == "all" and user_sdwt_prod else min(_parse_int(raw_limit, 50), 500)

        # -----------------------------------------------------------------------------
        # 3) 사용자 pool 및 소속 옵션 조회
        # -----------------------------------------------------------------------------
        results = selectors.list_active_user_pool(
            search=search,
            user_sdwt_prod=user_sdwt_prod,
            contact_field=contact_field,
            limit=limit,
        )
        user_sdwt_prods = selectors.list_distinct_active_user_sdwt_prod_values()
        return JsonResponse(
            {
                "results": results,
                "userSdwtProds": user_sdwt_prods,
            }
        )


# =============================================================================
# 12) line/user_sdwt_prod 선택 옵션 조회 (DB에 존재하는 조합만)
# =============================================================================
@method_decorator(csrf_exempt, name="dispatch")
class LineSdwtOptionsView(APIView):
    """사용자가 선택할 수 있는 line/user_sdwt_prod 조합을 DB 값으로 한정해 제공."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """선택 가능한 line/user_sdwt_prod 조합을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 옵션 페이로드

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/account/line-sdwt-options

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 옵션 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        pairs = selectors.list_line_sdwt_pairs()
        payload = services.get_line_sdwt_options_payload(pairs=pairs)
        return JsonResponse(payload)
