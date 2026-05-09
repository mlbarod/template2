# =============================================================================
# 모듈 설명: emails API 엔드포인트를 제공합니다.
# - 주요 뷰: EmailInboxListView, EmailDetailView, EmailMoveView, EmailHtmlView, EmailAssetView, EmailOutboxProcessTriggerView, EmailAssetOcrClaimView, EmailAssetOcrUpdateView
# - 불변 조건: 권한 검증 후 서비스/셀렉터에 위임하며 비즈니스 로직은 포함하지 않습니다.
# =============================================================================

from __future__ import annotations

import logging
from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from api.common.services import (
    UNASSIGNED_USER_SDWT_PROD,
    ensure_airflow_token,
    parse_json_body,
    parse_json_body_or_error_when_present,
)

from .permissions import (
    extract_bearer_token,
    resolve_access_control,
    resolve_email_access_denial,
    _resolve_sender_id_from_user,
    user_can_access_mailbox,
    user_can_view_unassigned,
)
from .selectors import (
    contains_unassigned_emails,
    count_unassigned_emails_for_sender_id,
    get_email_asset_by_email_and_sequence,
    get_email_by_id,
    get_filtered_emails,
    get_sent_emails,
    list_mailbox_members,
    user_can_bulk_delete_emails,
)

from .serializers import (
    EmailAssetOcrClaimSerializer,
    EmailAssetOcrUpdateSerializer,
    EmailRequestValidationError,
    parse_email_id_list,
    parse_optional_positive_limit,
    serialize_email_detail,
    serialize_email_page,
)
from .services import (
    bulk_delete_emails,
    build_email_filters,
    claim_email_asset_ocr_tasks,
    claim_unassigned_emails_for_user,
    delete_single_email,
    get_mailbox_access_summary_for_user,
    load_email_asset,
    load_email_html,
    move_emails_for_user,
    parse_mailbox_user_sdwt_prod,
    process_email_outbox_batch,
    run_pop3_ingest_from_env,
    SENT_MAILBOX_ID,
    update_email_asset_ocr_results,
)
from .services.mailbox import list_mailboxes_for_user_access

# =============================================================================
# 로깅
# =============================================================================
logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _ensure_internal_token(request: HttpRequest) -> JsonResponse | None:
    """내부 OCR 토큰을 검증하고 실패 시 JsonResponse를 반환합니다.

    입력:
        요청: Django HttpRequest.
    반환:
        JsonResponse | None: 오류 시 JsonResponse, 정상 시 None.
    부작용:
        없음.
    오류:
        - 500: 설정에 토큰이 없을 때
        - 401: 제공된 토큰이 기대값과 다를 때
    """
    expected = (getattr(settings, "EMAIL_OCR_INTERNAL_TOKEN", "") or "").strip()
    if not expected:
        return JsonResponse({"error": "EMAIL_OCR_INTERNAL_TOKEN not configured"}, status=500)
    provided = request.headers.get("X-Internal-Token") or request.META.get("HTTP_X_INTERNAL_TOKEN") or ""
    if not isinstance(provided, str):
        provided = ""
    if provided.strip() != expected:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


def _check_email_access(
    *,
    request: HttpRequest,
    email: Any,
    is_privileged: bool,
    accessible: Optional[set[str]],
) -> Optional[JsonResponse]:
    """공통 이메일 접근 검증 결과를 HTTP 에러 응답으로 변환합니다.

    입력:
        요청: Django HttpRequest.
        email: Email 인스턴스 또는 None.
        is_privileged: 특권 사용자 여부.
        accessible: 접근 가능한 user_sdwt_prod 집합.
    반환:
        에러 응답(JsonResponse) 또는 None(접근 허용).
    부작용:
        없음.
    오류:
        없음(에러는 JsonResponse로 반환).
    """
    denial = resolve_email_access_denial(
        user=request.user,
        email=email,
        is_privileged=is_privileged,
        accessible=accessible,
    )
    if denial == "not_found":
        return JsonResponse({"error": "Email not found"}, status=404)
    if denial == "forbidden":
        return JsonResponse({"error": "forbidden"}, status=403)
    return None


def _build_email_list_response(qs: Any, page: int, page_size: int) -> JsonResponse:
    """메일 목록 직렬화 결과를 JsonResponse로 감쌉니다.

    입력:
        qs: Email QuerySet 또는 iterable.
        page: 요청 페이지 번호.
        page_size: 페이지 크기.
    반환:
        페이지네이션 정보가 포함된 JsonResponse.
    부작용:
        없음.
    오류:
        없음.
    """
    return JsonResponse(serialize_email_page(qs, page=page, page_size=page_size))


def _error_response(message: str, *, status: int) -> JsonResponse:
    """공통 에러 응답을 생성합니다."""

    return JsonResponse({"error": message}, status=status)


def _validation_error_response(exc: EmailRequestValidationError) -> JsonResponse:
    """요청 검증 예외를 JsonResponse로 변환합니다."""

    return _error_response(str(exc), status=exc.status_code)


def _ensure_authenticated_user(request: HttpRequest) -> JsonResponse | None:
    """요청 사용자의 로그인 여부를 확인합니다."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return _error_response("unauthorized", status=401)
    return None


def _resolve_email_access_control(
    request: HttpRequest,
) -> tuple[bool, set[str] | None, JsonResponse | None]:
    """이메일 접근 컨텍스트를 계산하고 미인증 응답을 함께 반환합니다."""

    is_authenticated, is_privileged, accessible = resolve_access_control(request)
    if not is_authenticated:
        return is_privileged, accessible, _error_response("unauthorized", status=401)
    return is_privileged, accessible, None


def _parse_required_json_body(request: HttpRequest) -> tuple[dict[str, Any], JsonResponse | None]:
    """필수 JSON 본문을 dict로 파싱합니다."""

    payload = parse_json_body(request)
    if not isinstance(payload, dict):
        return {}, _error_response("Invalid JSON body", status=400)
    return payload, None


def _parse_optional_json_body(request: HttpRequest) -> tuple[dict[str, Any], JsonResponse | None]:
    """비어 있는 본문을 허용하는 JSON 본문을 dict로 파싱합니다."""

    payload = parse_json_body(request)
    if payload is None:
        if not request.body:
            return {}, None
        return {}, _error_response("Invalid JSON body", status=400)
    if not isinstance(payload, dict):
        return {}, _error_response("Invalid JSON body", status=400)
    return payload, None


@method_decorator(csrf_exempt, name="dispatch")
class EmailInboxListView(APIView):
    """메일함(user_sdwt_prod) 기준 메일 리스트 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """메일함 메일 리스트를 조회합니다.

        입력:
            쿼리:
                - user_sdwt_prod 또는 userSdwtProd: 메일함 식별자(옵션)
                - q: 검색어(제목/본문/발신자/참여자)
                - sender: 발신자 필터
                - recipient: 수신자 필터(To/Cc)
                - date_from/date_to: 수신 기간 필터(ISO, 기본 타임존 기준 날짜/시간)
                - page/page_size: 페이지네이션
        반환:
            예시 응답: {"results": [...], "page": int, "pageSize": int, "total": int, "totalPages": int}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 400: 보낸메일함 접근/UNASSIGNED 접근 오류
        예시 요청:
            예시 요청: GET /api/v1/emails/inbox/?user_sdwt_prod=group-a&q=report&page=1&page_size=20
        snake/camel 호환:
            user_sdwt_prod <-> userSdwtProd만 지원합니다(그 외는 snake_case 사용).
        날짜 해석:
            - 타임존 없는 값은 Django 기본 타임존(TIME_ZONE)으로 해석 후 UTC로 변환합니다.
            - 날짜만 입력 시 date_from=해당 날짜 00:00:00, date_to=해당 날짜 23:59:59.999999로 처리됩니다.
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error

        if not is_privileged and not accessible:
            return _error_response("forbidden", status=403)
        filters = build_email_filters(
            params=request.GET,
            default_page_size=DEFAULT_PAGE_SIZE,
            max_page_size=MAX_PAGE_SIZE,
        )
        mailbox_user_sdwt_prod = filters["mailbox_user_sdwt_prod"]
        if mailbox_user_sdwt_prod == SENT_MAILBOX_ID:
            return _error_response("use sent endpoint", status=400)
        if not user_can_access_mailbox(
            user=request.user,
            mailbox_user_sdwt_prod=mailbox_user_sdwt_prod,
            is_privileged=is_privileged,
            accessible=accessible,
        ):
            return _error_response("forbidden", status=403)
        can_view_unassigned = user_can_view_unassigned(request.user)
        qs = get_filtered_emails(
            accessible_user_sdwt_prods=accessible,
            is_privileged=is_privileged,
            can_view_unassigned=can_view_unassigned,
            mailbox_user_sdwt_prod=mailbox_user_sdwt_prod,
            search=filters["search"],
            sender=filters["sender"],
            recipient=filters["recipient"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
        )
        page = filters["page"]
        page_size = filters["page_size"]

        return _build_email_list_response(qs, page, page_size)


@method_decorator(csrf_exempt, name="dispatch")
class EmailSentListView(APIView):
    """보낸 메일(sender_id) 기준 리스트 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """발신자(sender_id) 기준 보낸메일 리스트를 조회합니다.

        입력:
            쿼리:
                - q/sender/recipient/date_from/date_to/page/page_size (검색/기간/페이지, 기본 타임존 기준 날짜/시간)
        반환:
            예시 응답: {"results": [...], "page": int, "pageSize": int, "total": int, "totalPages": int}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: sender_id 미확인
            - 400: knox_id/knoxId 파라미터 사용 금지
        예시 요청:
            예시 요청: GET /api/v1/emails/sent/?q=report&page=1&page_size=20
        snake/camel 호환:
            지원하지 않습니다(특히 knox_id/knoxId 파라미터는 허용하지 않음).
        날짜 해석:
            - 타임존 없는 값은 Django 기본 타임존(TIME_ZONE)으로 해석 후 UTC로 변환합니다.
            - 날짜만 입력 시 date_from=해당 날짜 00:00:00, date_to=해당 날짜 23:59:59.999999로 처리됩니다.
        """
        _is_privileged, _accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        if "knox_id" in request.GET or "knoxId" in request.GET:
            return _error_response("knox_id query param is not allowed", status=400)
        sender_id = _resolve_sender_id_from_user(request.user)
        if not sender_id:
            return _error_response("forbidden", status=403)
        filters = build_email_filters(
            params=request.GET,
            default_page_size=DEFAULT_PAGE_SIZE,
            max_page_size=MAX_PAGE_SIZE,
        )

        qs = get_sent_emails(
            sender_id=sender_id,
            search=filters["search"],
            sender=filters["sender"],
            recipient=filters["recipient"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
        )
        page = filters["page"]
        page_size = filters["page_size"]

        return _build_email_list_response(qs, page, page_size)


@method_decorator(csrf_exempt, name="dispatch")
class EmailMailboxListView(APIView):
    """현재 사용자가 접근 가능한 메일함(user_sdwt_prod) 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """사용자가 접근 가능한 메일함 목록을 반환합니다.

        입력:
            쿼리: 없음.
        반환:
            예시 응답: {"results": ["__sent__", "group-a", ...]}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음(일반 사용자 + 접근 집합 없음)
        예시 요청:
            예시 요청: GET /api/v1/emails/mailboxes/
        snake/camel 호환:
            해당 없음(쿼리 파라미터 없음).
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        if not is_privileged and not accessible:
            return _error_response("forbidden", status=403)

        results = list_mailboxes_for_user_access(
            user=request.user,
            is_privileged=is_privileged,
            accessible_user_sdwt_prods=accessible,
        )
        return JsonResponse({"results": results})


@method_decorator(csrf_exempt, name="dispatch")
class EmailMailboxMembersView(APIView):
    """메일함(user_sdwt_prod)에 접근 가능한 멤버 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """메일함 멤버 목록을 반환합니다.

        입력:
            쿼리:
                - user_sdwt_prod 또는 userSdwtProd: 대상 메일함 식별자
        반환:
            예시 응답: {"userSdwtProd": "...", "members": [...]}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 400: 메일함 값 누락/보낸메일함 요청
        예시 요청:
            예시 요청: GET /api/v1/emails/mailboxes/members/?userSdwtProd=group-a
        snake/camel 호환:
            user_sdwt_prod <-> userSdwtProd 지원.
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error

        if not is_privileged and not accessible:
            return _error_response("forbidden", status=403)
        mailbox_user_sdwt_prod = parse_mailbox_user_sdwt_prod(request.GET)
        if not mailbox_user_sdwt_prod:
            return _error_response("user_sdwt_prod is required", status=400)
        if mailbox_user_sdwt_prod == SENT_MAILBOX_ID:
            return _error_response("sent mailbox has no members", status=400)
        if not user_can_access_mailbox(
            user=request.user,
            mailbox_user_sdwt_prod=mailbox_user_sdwt_prod,
            is_privileged=is_privileged,
            accessible=accessible,
        ):
            return _error_response("forbidden", status=403)
        members = list_mailbox_members(mailbox_user_sdwt_prod=mailbox_user_sdwt_prod)
        return JsonResponse({"userSdwtProd": mailbox_user_sdwt_prod, "members": members})


@method_decorator(csrf_exempt, name="dispatch")
class EmailMailboxSummaryView(APIView):
    """현재 사용자의 메일함 접근 요약을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """메일함별 멤버/권한/메일 수 요약을 반환합니다.

        입력:
            요청: Django HttpRequest.
        반환:
            JsonResponse: {"results": [...]} 형태의 메일함 요약.
        부작용:
            없음.
        오류:
            - 401: 인증 실패
        """

        auth_error = _ensure_authenticated_user(request)
        if auth_error is not None:
            return auth_error

        results = get_mailbox_access_summary_for_user(user=request.user)
        return JsonResponse({"results": results})


@method_decorator(csrf_exempt, name="dispatch")
class EmailUnassignedSummaryView(APIView):
    """현재 사용자(sender_id=knox_id)의 UNASSIGNED 메일 개수를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자 기준 UNASSIGNED 메일 개수를 반환합니다.

        입력:
            쿼리: 없음.
        반환:
            예시 응답: {"mailbox": "UNASSIGNED", "count": int}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: sender_id 미확인
        예시 요청:
            예시 요청: GET /api/v1/emails/unassigned/
        snake/camel 호환:
            해당 없음(쿼리 파라미터 없음).
        """
        auth_error = _ensure_authenticated_user(request)
        if auth_error is not None:
            return auth_error
        user = request.user
        sender_id = _resolve_sender_id_from_user(user)
        if not sender_id:
            return _error_response("forbidden", status=403)
        count = count_unassigned_emails_for_sender_id(sender_id=sender_id)
        return JsonResponse({"mailbox": UNASSIGNED_USER_SDWT_PROD, "count": count})


@method_decorator(csrf_exempt, name="dispatch")
class EmailUnassignedClaimView(APIView):
    """현재 사용자(sender_id=knox_id)의 UNASSIGNED 메일을 현재 user_sdwt_prod로 귀속(옮김)합니다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자의 UNASSIGNED 메일을 자신의 메일함으로 이동합니다.

        입력:
            바디: 없음(JSON 본문 불필요).
        반환:
            예시 응답: {"moved": int, "ragRegistered": int, "ragFailed": int, "ragMissing": int}
        부작용:
            Email.user_sdwt_prod 업데이트 및 RAG 인덱싱 큐 적재.
        오류:
            - 401: 인증 실패
            - 403: knox_id 미설정
            - 400: user_sdwt_prod 미설정/UNASSIGNED
            - 500: 기타 서버 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/unassigned/claim/
        snake/camel 호환:
            해당 없음(요청 본문 없음).
        """
        auth_error = _ensure_authenticated_user(request)
        if auth_error is not None:
            return auth_error
        user = request.user
        try:
            payload = claim_unassigned_emails_for_user(user=user)
        except PermissionError:
            return _error_response("forbidden", status=403)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover  테스트 제외
            # 방어적 로깅
            logger.exception("Failed to claim UNASSIGNED emails for user_id=%s", getattr(user, "id", None))
            return JsonResponse({"error": "Failed to claim emails"}, status=500)
        return JsonResponse(payload)


@method_decorator(csrf_exempt, name="dispatch")
class EmailDetailView(APIView):
    """단일 메일 상세 조회 (텍스트)."""

    def get(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """단일 메일 상세 정보를 조회합니다.

        입력:
            경로:
                - email_id: 메일 PK
        반환:
            Email 상세 JSON (camelCase 키).
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 404: 메일 없음
        예시 요청:
            예시 요청: GET /api/v1/emails/123/
        snake/camel 호환:
            해당 없음(경로 파라미터만 사용).
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error
        return JsonResponse(serialize_email_detail(email))

    def delete(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """단일 메일을 삭제합니다(RAG 삭제는 Outbox 처리).

        입력:
            경로:
                - email_id: 메일 PK
        반환:
            예시 응답: {"status": "ok"}
        부작용:
            Email 삭제 및 RAG 삭제 Outbox 적재.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 404: 메일 없음
            - 500: 기타 서버 오류
        예시 요청:
            예시 요청: DELETE /api/v1/emails/123/
        snake/camel 호환:
            해당 없음(경로 파라미터만 사용).
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error
        try:
            delete_single_email(email_id)
            return JsonResponse({"status": "ok"})
        except NotFound as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except Exception:  # pragma: no cover  테스트 제외
            # 방어적 로깅
            logger.exception("Failed to delete email id=%s", email_id)
            return JsonResponse({"error": "Failed to delete email"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailHtmlView(APIView):
    """MinIO 저장된 HTML 본문을 반환합니다."""

    def get(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> HttpResponse:
        """MinIO에 저장된 HTML 본문을 반환합니다.

        입력:
            경로:
                - email_id: 메일 PK
        반환:
            HTML 본문(HttpResponse) 또는 204 응답.
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 404: 메일 없음
            - 500: HTML 로드 실패
        예시 요청:
            예시 요청: GET /api/v1/emails/123/html/
        snake/camel 호환:
            해당 없음(경로 파라미터만 사용).
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error
        try:
            html_bytes = load_email_html(email=email)
        except Exception:  # pragma: no cover  테스트 제외
            logger.exception("Failed to load email HTML (id=%s)", email_id)
            return JsonResponse({"error": "Failed to load HTML body"}, status=500)

        if not html_bytes:
            return HttpResponse("", status=204)

        response = HttpResponse(html_bytes, content_type="text/html; charset=utf-8")
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=300"
        return response


@method_decorator(csrf_exempt, name="dispatch")
class EmailAssetView(APIView):
    """MinIO에 저장된 이메일 이미지 자산을 반환합니다."""

    def get(
        self,
        request: HttpRequest,
        email_id: int,
        sequence: int,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse:
        """이메일 이미지 자산을 반환합니다.

        입력:
            경로:
                - email_id: 메일 PK
                - sequence: 이미지 순번
        반환:
            이미지(HttpResponse) 또는 404 응답.
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 404: 메일/자산/오브젝트 없음
            - 500: 자산 로드 실패
        예시 요청:
            예시 요청: GET /api/v1/emails/123/assets/1/
        snake/camel 호환:
            해당 없음(경로 파라미터만 사용).
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error
        asset = get_email_asset_by_email_and_sequence(email_id=email_id, sequence=sequence)
        if asset is None:
            return JsonResponse({"error": "Email asset not found"}, status=404)
        try:
            asset_bytes = load_email_asset(asset=asset)
        except Exception:  # pragma: no cover  테스트 제외
            logger.exception("Failed to load email asset (email_id=%s sequence=%s)", email_id, sequence)
            return JsonResponse({"error": "Failed to load email asset"}, status=500)

        if not asset_bytes:
            return JsonResponse({"error": "Email asset not found"}, status=404)

        content_type = asset.content_type or "application/octet-stream"
        response = HttpResponse(asset_bytes, content_type=content_type)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=3600"
        return response


@method_decorator(csrf_exempt, name="dispatch")
class EmailBulkDeleteView(APIView):
    """여러 메일 삭제 (모두 성공 시 반영)."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """여러 메일을 일괄 삭제합니다.

        입력:
            바디 예시(JSON):
                - email_ids 또는 emailIds: 삭제할 Email id 목록
        반환:
            예시 응답: {"deleted": int}
        부작용:
            Email 삭제 및 RAG 삭제 Outbox 적재.
        오류:
            - 401: 인증 실패
            - 403: 권한 부족/UNASSIGNED 삭제 금지
            - 400: 잘못된 JSON/파라미터
            - 404: 대상 메일 없음
            - 500: 기타 서버 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/bulk-delete/
            예시 바디: {"email_ids":[1,2,3]}
        snake/camel 호환:
            email_ids <-> emailIds 지원.
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        if not is_privileged and not accessible:
            return _error_response("forbidden", status=403)
        payload, payload_error = _parse_required_json_body(request)
        if payload_error is not None:
            return payload_error
        try:
            normalized_ids = parse_email_id_list(payload)
        except EmailRequestValidationError as exc:
            return _validation_error_response(exc)
        if not is_privileged:
            sender_id = _resolve_sender_id_from_user(request.user)
            if not user_can_bulk_delete_emails(
                email_ids=normalized_ids,
                accessible_user_sdwt_prods=accessible,
                sender_id=sender_id,
            ):
                return _error_response("forbidden", status=403)
        else:
            if not user_can_view_unassigned(request.user) and contains_unassigned_emails(
                email_ids=normalized_ids
            ):
                return _error_response("forbidden", status=403)
        try:
            deleted_count = bulk_delete_emails(normalized_ids)
            return JsonResponse({"deleted": deleted_count})
        except NotFound as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except Exception:  # pragma: no cover  테스트 제외
            # 방어적 로깅
            logger.exception("Failed to bulk delete emails")
            return JsonResponse({"error": "Failed to delete emails"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailMoveView(APIView):
    """메일 이동 (user_sdwt_prod 변경 + RAG 재등록)."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """메일함을 다른 user_sdwt_prod로 이동합니다.

        입력:
            바디 예시(JSON):
                - email_ids 또는 emailIds: 이동할 Email id 목록
                - to_user_sdwt_prod 또는 toUserSdwtProd: 대상 메일함
        반환:
            예시 응답: {"moved": int, "ragRegistered": int, "ragFailed": int, "ragMissing": int}
        부작용:
            Email.user_sdwt_prod 업데이트 및 RAG 인덱싱 큐 적재.
        오류:
            - 401: 인증 실패
            - 403: 권한 부족
            - 400: 잘못된 입력
            - 500: 기타 서버 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/move/
            예시 바디: {"emailIds":[1,2], "toUserSdwtProd":"group-b"}
        snake/camel 호환:
            email_ids <-> emailIds, to_user_sdwt_prod <-> toUserSdwtProd 지원.
        """
        auth_error = _ensure_authenticated_user(request)
        if auth_error is not None:
            return auth_error
        user = request.user
        payload, payload_error = _parse_required_json_body(request)
        if payload_error is not None:
            return payload_error
        try:
            normalized_ids = parse_email_id_list(payload)
        except EmailRequestValidationError as exc:
            return _validation_error_response(exc)
        target_user_sdwt_prod = payload.get("to_user_sdwt_prod") or payload.get("toUserSdwtProd")
        if not isinstance(target_user_sdwt_prod, str) or not target_user_sdwt_prod.strip():
            return _error_response("to_user_sdwt_prod is required", status=400)
        try:
            result = move_emails_for_user(
                user=user,
                email_ids=normalized_ids,
                to_user_sdwt_prod=target_user_sdwt_prod,
            )
            return JsonResponse(result)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except PermissionError:
            return _error_response("forbidden", status=403)
        except Exception:  # pragma: no cover  테스트 제외
            # 방어적 로깅
            logger.exception("Failed to move emails")
            return JsonResponse({"error": "Failed to move emails"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailIngestTriggerView(APIView):
    """POP3 메일 수집을 백엔드에서 실행하도록 트리거."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """POP3 메일 수집을 트리거합니다.

        입력:
            바디: 없음.
            헤더 예시:
                - Authorization: Bearer <token> (AIRFLOW_TRIGGER_TOKEN 사용 시)
        반환:
            예시 응답: {"deleted": int, "reindexed": int}
        부작용:
            POP3 수집 및 Email 저장 수행.
        오류:
            - 401: 토큰/인증 실패
            - 400: 환경변수 누락 등 설정 오류
            - 500: 수집 실패
        예시 요청:
            예시 요청: POST /api/v1/emails/ingest/
        snake/camel 호환:
            해당 없음(요청 본문 없음).
        """
        expected_token = getattr(settings, "AIRFLOW_TRIGGER_TOKEN", "") or ""
        provided_token = extract_bearer_token(request)

        if expected_token:
            if provided_token != expected_token and not request.user.is_authenticated:
                return JsonResponse({"error": "Unauthorized"}, status=401)
        elif not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        try:
            result = run_pop3_ingest_from_env() or {}
            return JsonResponse({"deleted": result.get("deleted", 0), "reindexed": result.get("reindexed", 0)})
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:
            logger.exception("Failed to trigger POP3 ingest")
            return JsonResponse({"error": "POP3 ingest failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailOutboxProcessTriggerView(APIView):
    """RAG Outbox 대기 항목 처리를 트리거합니다."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """Outbox 대기 항목 처리를 수행합니다.

        입력:
            바디 예시(JSON, 옵션):
                - limit: 처리 건수 제한
            쿼리(옵션):
                - limit: 처리 건수 제한
        반환:
            예시 응답: {"processed": int, "succeeded": int, "failed": int}
        부작용:
            Outbox 상태 업데이트 및 RAG 호출.
        오류:
            - 401: Airflow 트리거 토큰 인증 실패
            - 400: limit 파라미터 오류
            - 500: 처리 실패
        예시 요청:
            예시 요청: POST /api/v1/emails/outbox/process/
            예시 바디: {"limit": 50}
        snake/camel 호환:
            해당 없음(limit 키만 사용).
        """
        auth_response = ensure_airflow_token(request)
        if auth_response is not None:
            return auth_response
        content_type = request.META.get("CONTENT_TYPE", "")
        if content_type.startswith("application/json"):
            payload, payload_error = parse_json_body_or_error_when_present(request)
            if payload_error is not None:
                return payload_error
        else:
            payload = {}
        try:
            limit = parse_optional_positive_limit(
                body_value=payload.get("limit"),
                query_value=request.GET.get("limit"),
            )
        except EmailRequestValidationError as exc:
            return _validation_error_response(exc)
        try:
            if limit is None:
                result = process_email_outbox_batch()
            else:
                result = process_email_outbox_batch(limit=limit)
            return JsonResponse(result)
        except Exception:
            logger.exception("Failed to process email outbox")
            return JsonResponse({"error": "Email outbox processing failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailAssetOcrClaimView(APIView):
    """OCR 작업 클레임을 제공합니다."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """OCR 작업을 클레임합니다.

        입력:
            헤더:
                - X-Internal-Token: 내부 OCR 인증 토큰
            바디 예시(JSON):
                - limit: 최대 클레임 개수(옵션)
                - lease_seconds: 잠금 유지 시간(초, 옵션)
                - worker_id: 작업자 식별자(옵션)
        반환:
            예시 응답: {"tasks":[{"asset_id":1,"email_id":10,"sequence":1,"source_type":"CID","object_key":"...","bucket":"...","external_url":null,"content_type":"image/png","size_bytes":1234,"lock_token":"...","lock_expires_at":"...","attempt_count":1}]}
        부작용:
            EmailAsset 락 및 상태 갱신.
        오류:
            - 401: 내부 토큰 인증 실패
            - 400: 요청 본문 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/assets/ocr/claim/
            예시 바디: {"limit":50,"lease_seconds":1800,"worker_id":"gpu-01"}
        snake/camel 호환:
            snake_case만 사용합니다.
        """
        auth_response = _ensure_internal_token(request)
        if auth_response is not None:
            return auth_response
        payload, payload_error = _parse_optional_json_body(request)
        if payload_error is not None:
            return payload_error

        serializer = EmailAssetOcrClaimSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)
        default_limit = getattr(settings, "EMAIL_OCR_CLAIM_LIMIT", 50) or 50
        default_lease_seconds = getattr(settings, "EMAIL_OCR_LEASE_SECONDS", 1800) or 1800
        max_attempts = getattr(settings, "EMAIL_OCR_MAX_ATTEMPTS", 3) or 3

        limit = serializer.validated_data.get("limit") or default_limit
        lease_seconds = serializer.validated_data.get("lease_seconds") or default_lease_seconds
        worker_id = serializer.validated_data.get("worker_id")
        tasks = claim_email_asset_ocr_tasks(
            limit=limit,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
            worker_id=worker_id,
        )
        return JsonResponse({"tasks": tasks})


@method_decorator(csrf_exempt, name="dispatch")
class EmailAssetOcrUpdateView(APIView):
    """OCR 결과를 EmailAsset에 반영하고 RAG 재인덱싱을 요청합니다."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """OCR 결과 업데이트를 처리합니다.

        입력:
            헤더:
                - X-Internal-Token: 내부 OCR 인증 토큰
            바디 예시(JSON):
                - results: OCR 결과 목록
                    - asset_id: EmailAsset 기본 키
                    - lock_token: 클레임 시 받은 토큰
                    - status: DONE | FAILED 상태
                    - text: OCR 텍스트(옵션)
                    - error_code: 실패 코드(옵션)
                    - error_message: 실패 사유(옵션)
                    - ocr_model: 사용 모델(옵션)
                    - ocr_duration_ms: 처리 시간(ms, 옵션)
                    - processed_at: 처리 완료 시각(옵션, ISO)
        반환:
            예시 응답: {"updated": int, "rejected": int, "ragQueued": int, "ragFailed": int, "ragSkipped": int}
        부작용:
            EmailAsset 업데이트 및 RAG Outbox 적재.
        오류:
            - 401: 내부 토큰 인증 실패
            - 400: 요청 본문 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/assets/ocr/update/
            예시 바디: {"results":[{"asset_id":1,"lock_token":"token","status":"DONE","text":"..."}]}
        snake/camel 호환:
            snake_case만 사용합니다.
        """
        auth_response = _ensure_internal_token(request)
        if auth_response is not None:
            return auth_response
        payload, payload_error = _parse_required_json_body(request)
        if payload_error is not None:
            return payload_error

        serializer = EmailAssetOcrUpdateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)
        max_attempts = getattr(settings, "EMAIL_OCR_MAX_ATTEMPTS", 3) or 3
        results = serializer.validated_data.get("results") or []
        result = update_email_asset_ocr_results(results=results, max_attempts=max_attempts)
        return JsonResponse(result)
