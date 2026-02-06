# =============================================================================
# 모듈 설명: emails API 엔드포인트를 제공합니다.
# - 주요 뷰: EmailInboxListView, EmailDetailView, EmailMoveView, EmailHtmlView, EmailAssetView, EmailOutboxProcessTriggerView, EmailAssetOcrClaimView, EmailAssetOcrUpdateView
# - 불변 조건: 권한 검증 후 서비스/셀렉터에 위임하며 비즈니스 로직은 포함하지 않습니다.
# =============================================================================

from __future__ import annotations

import logging
from typing import Any, List, Optional

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from api.common.services import ensure_airflow_token, parse_json_body

from .permissions import (
    email_is_unassigned,
    extract_bearer_token,
    resolve_access_control,
    _resolve_sender_id_from_user,
    user_can_access_email,
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
    list_privileged_email_mailboxes,
    user_can_bulk_delete_emails,
)
from api.common.services import UNASSIGNED_USER_SDWT_PROD

from .serializers import (
    EmailAssetOcrClaimSerializer,
    EmailAssetOcrUpdateSerializer,
    serialize_email_detail,
    serialize_email_summary,
)
from .services import (
    bulk_delete_emails,
    build_email_filters,
    claim_email_asset_ocr_tasks,
    claim_unassigned_emails_for_user,
    delete_single_email,
    load_email_asset,
    load_email_html,
    move_emails_for_user,
    parse_mailbox_user_sdwt_prod,
    process_email_outbox_batch,
    run_pop3_ingest_from_env,
    SENT_MAILBOX_ID,
    update_email_asset_ocr_results,
)

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

    # -----------------------------------------------------------------------------
    # 1) 기대 토큰 준비
    # -----------------------------------------------------------------------------
    expected = (getattr(settings, "EMAIL_OCR_INTERNAL_TOKEN", "") or "").strip()
    if not expected:
        return JsonResponse({"error": "EMAIL_OCR_INTERNAL_TOKEN not configured"}, status=500)

    # -----------------------------------------------------------------------------
    # 2) 제공된 토큰 추출
    # -----------------------------------------------------------------------------
    provided = request.headers.get("X-Internal-Token") or request.META.get("HTTP_X_INTERNAL_TOKEN") or ""
    if not isinstance(provided, str):
        provided = ""

    # -----------------------------------------------------------------------------
    # 3) 비교 및 결과 반환
    # -----------------------------------------------------------------------------
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
    """공통 이메일 접근 검증을 수행하고, 문제 시 JsonResponse를 반환합니다.

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

    # -----------------------------------------------------------------------------
    # 1) 대상 메일 존재 확인
    # -----------------------------------------------------------------------------
    if email is None:
        return JsonResponse({"error": "Email not found"}, status=404)

    # -----------------------------------------------------------------------------
    # 2) UNASSIGNED 접근 제한 확인
    # -----------------------------------------------------------------------------
    if email_is_unassigned(email) and not user_can_view_unassigned(request.user):
        if not user_can_access_email(request.user, email, accessible):
            return JsonResponse({"error": "forbidden"}, status=403)

    # -----------------------------------------------------------------------------
    # 3) 일반 사용자 권한 범위 확인
    # -----------------------------------------------------------------------------
    if not is_privileged:
        if not accessible or not user_can_access_email(request.user, email, accessible):
            return JsonResponse({"error": "forbidden"}, status=403)

    # -----------------------------------------------------------------------------
    # 4) 접근 허용
    # -----------------------------------------------------------------------------
    return None


def _build_email_list_response(qs: Any, page: int, page_size: int) -> JsonResponse:
    """메일 목록 조회 결과를 페이지네이션 응답으로 구성합니다.

    입력:
        qs: Email QuerySet 또는 iterable.
        page: 요청 페이지 번호.
        page_size: 페이지 크기.
    반환:
        페이지네이션 정보가 포함된 JsonResponse.
    부작용:
        없음.
    오류:
        잘못된 페이지 요청은 마지막 페이지로 보정합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 페이지네이터 구성 및 페이지 선택
    # -----------------------------------------------------------------------------
    paginator = Paginator(qs, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    # -----------------------------------------------------------------------------
    # 2) 응답 payload 구성
    # -----------------------------------------------------------------------------
    results = [serialize_email_summary(email) for email in page_obj.object_list]

    return JsonResponse(
        {
            "results": results,
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        }
    )



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

        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        if not is_privileged and not accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 2) 필터 파싱 및 메일함 접근 검증
        # -----------------------------------------------------------------------------
        filters = build_email_filters(
            params=request.GET,
            default_page_size=DEFAULT_PAGE_SIZE,
            max_page_size=MAX_PAGE_SIZE,
        )
        mailbox_user_sdwt_prod = filters["mailbox_user_sdwt_prod"]
        can_view_unassigned = user_can_view_unassigned(request.user)
        if mailbox_user_sdwt_prod == SENT_MAILBOX_ID:
            return JsonResponse({"error": "use sent endpoint"}, status=400)
        if mailbox_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD and not can_view_unassigned:
            return JsonResponse({"error": "forbidden"}, status=403)
        if mailbox_user_sdwt_prod and not is_privileged:
            if mailbox_user_sdwt_prod not in accessible:
                return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) 조회 실행
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 4) 페이지네이션 응답 구성
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        is_authenticated, _is_privileged, _accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 금지 파라미터 검증
        # -----------------------------------------------------------------------------
        if "knox_id" in request.GET or "knoxId" in request.GET:
            return JsonResponse({"error": "knox_id query param is not allowed"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) sender_id 확인
        # -----------------------------------------------------------------------------
        sender_id = _resolve_sender_id_from_user(request.user)
        if not sender_id:
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 4) 필터 파싱 및 조회
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 5) 페이지네이션 응답 구성
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 특권 사용자 목록 구성
        # -----------------------------------------------------------------------------
        if is_privileged:
            results = list_privileged_email_mailboxes()
            if not user_can_view_unassigned(request.user):
                results = [
                    mailbox
                    for mailbox in results
                    if mailbox not in {UNASSIGNED_USER_SDWT_PROD, "rp-unclassified"}
                ]
            results = [SENT_MAILBOX_ID, *[mailbox for mailbox in results if mailbox != SENT_MAILBOX_ID]]
            return JsonResponse({"results": results})

        # -----------------------------------------------------------------------------
        # 3) 일반 사용자 목록 구성
        # -----------------------------------------------------------------------------
        if not accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        results = sorted(accessible)
        results = [SENT_MAILBOX_ID, *[mailbox for mailbox in results if mailbox != SENT_MAILBOX_ID]]
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

        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        if not is_privileged and not accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 2) 메일함 파라미터 검증
        # -----------------------------------------------------------------------------
        mailbox_user_sdwt_prod = parse_mailbox_user_sdwt_prod(request.GET)
        if not mailbox_user_sdwt_prod:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)
        if mailbox_user_sdwt_prod == SENT_MAILBOX_ID:
            return JsonResponse({"error": "sent mailbox has no members"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) UNASSIGNED/권한 검증
        # -----------------------------------------------------------------------------
        can_view_unassigned = user_can_view_unassigned(request.user)
        if mailbox_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD and not can_view_unassigned:
            return JsonResponse({"error": "forbidden"}, status=403)

        if not is_privileged and mailbox_user_sdwt_prod not in accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 4) 멤버 조회 및 응답
        # -----------------------------------------------------------------------------
        members = list_mailbox_members(mailbox_user_sdwt_prod=mailbox_user_sdwt_prod)
        return JsonResponse({"userSdwtProd": mailbox_user_sdwt_prod, "members": members})


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

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) sender_id 확인 및 카운트 조회
        # -----------------------------------------------------------------------------
        sender_id = _resolve_sender_id_from_user(user)
        if not sender_id:
            return JsonResponse({"error": "forbidden"}, status=403)
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

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 서비스 호출 및 예외 처리
        # -----------------------------------------------------------------------------
        try:
            payload = claim_unassigned_emails_for_user(user=user)
        except PermissionError:
            return JsonResponse({"error": "forbidden"}, status=403)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover  테스트 제외
            # 방어적 로깅
            logger.exception("Failed to claim UNASSIGNED emails for user_id=%s", getattr(user, "id", None))
            return JsonResponse({"error": "Failed to claim emails"}, status=500)

        # -----------------------------------------------------------------------------
        # 3) 응답 반환
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error

        # -----------------------------------------------------------------------------
        # 2) 상세 응답 반환
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error

        # -----------------------------------------------------------------------------
        # 2) 삭제 수행 및 예외 처리
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error

        # -----------------------------------------------------------------------------
        # 2) HTML 로드 및 응답
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error

        # -----------------------------------------------------------------------------
        # 2) 자산 조회
        # -----------------------------------------------------------------------------
        asset = get_email_asset_by_email_and_sequence(email_id=email_id, sequence=sequence)
        if asset is None:
            return JsonResponse({"error": "Email asset not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 3) MinIO 로드 및 응답
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        if not is_privileged and not accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 2) 요청 본문 파싱 및 id 정규화
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        email_ids = payload.get("email_ids") or payload.get("emailIds")
        if not isinstance(email_ids, list) or not email_ids:
            return JsonResponse({"error": "email_ids must be a non-empty list"}, status=400)

        normalized_ids: List[int] = []
        for raw in email_ids:
            try:
                normalized_ids.append(int(raw))
            except (TypeError, ValueError):
                return JsonResponse({"error": "email_ids must contain numeric values"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 권한 검증
        # -----------------------------------------------------------------------------
        if not is_privileged:
            sender_id = _resolve_sender_id_from_user(request.user)
            if not user_can_bulk_delete_emails(
                email_ids=normalized_ids,
                accessible_user_sdwt_prods=accessible,
                sender_id=sender_id,
            ):
                return JsonResponse({"error": "forbidden"}, status=403)
        else:
            if not user_can_view_unassigned(request.user) and contains_unassigned_emails(
                email_ids=normalized_ids
            ):
                return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 4) 삭제 수행 및 결과 반환
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 요청 본문 파싱 및 id 정규화
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        email_ids = payload.get("email_ids") or payload.get("emailIds")
        if not isinstance(email_ids, list) or not email_ids:
            return JsonResponse({"error": "email_ids must be a non-empty list"}, status=400)

        normalized_ids: List[int] = []
        for raw in email_ids:
            try:
                normalized_ids.append(int(raw))
            except (TypeError, ValueError):
                return JsonResponse({"error": "email_ids must contain numeric values"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 대상 메일함 검증
        # -----------------------------------------------------------------------------
        target_user_sdwt_prod = payload.get("to_user_sdwt_prod") or payload.get("toUserSdwtProd")
        if not isinstance(target_user_sdwt_prod, str) or not target_user_sdwt_prod.strip():
            return JsonResponse({"error": "to_user_sdwt_prod is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 4) 이동 처리 및 결과 반환
        # -----------------------------------------------------------------------------
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
            return JsonResponse({"error": "forbidden"}, status=403)
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

        # -----------------------------------------------------------------------------
        # 1) 토큰/인증 검증
        # -----------------------------------------------------------------------------
        expected_token = getattr(settings, "AIRFLOW_TRIGGER_TOKEN", "") or ""
        provided_token = extract_bearer_token(request)

        if expected_token:
            if provided_token != expected_token and not request.user.is_authenticated:
                return JsonResponse({"error": "Unauthorized"}, status=401)
        elif not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 수집 실행 및 결과 반환
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) Airflow 토큰 검증
        # -----------------------------------------------------------------------------
        auth_response = ensure_airflow_token(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) limit 파라미터 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request) or {}
        raw_limit = payload.get("limit")
        if raw_limit is None:
            raw_limit = request.GET.get("limit")

        limit = None
        if raw_limit is not None:
            try:
                limit = int(raw_limit)
            except (TypeError, ValueError):
                return JsonResponse({"error": "limit must be an integer"}, status=400)
            if limit <= 0:
                limit = None

        # -----------------------------------------------------------------------------
        # 3) 처리 실행 및 결과 반환
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 내부 토큰 검증
        # -----------------------------------------------------------------------------
        auth_response = _ensure_internal_token(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 요청 본문 파싱 및 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            if not request.body:
                payload = {}
            else:
                return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = EmailAssetOcrClaimSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        # -----------------------------------------------------------------------------
        # 3) 기본값 준비
        # -----------------------------------------------------------------------------
        default_limit = getattr(settings, "EMAIL_OCR_CLAIM_LIMIT", 50) or 50
        default_lease_seconds = getattr(settings, "EMAIL_OCR_LEASE_SECONDS", 1800) or 1800
        max_attempts = getattr(settings, "EMAIL_OCR_MAX_ATTEMPTS", 3) or 3

        limit = serializer.validated_data.get("limit") or default_limit
        lease_seconds = serializer.validated_data.get("lease_seconds") or default_lease_seconds
        worker_id = serializer.validated_data.get("worker_id")

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 결과 반환
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 1) 내부 토큰 검증
        # -----------------------------------------------------------------------------
        auth_response = _ensure_internal_token(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 요청 본문 파싱 및 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = EmailAssetOcrUpdateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 결과 반환
        # -----------------------------------------------------------------------------
        max_attempts = getattr(settings, "EMAIL_OCR_MAX_ATTEMPTS", 3) or 3
        results = serializer.validated_data.get("results") or []
        result = update_email_asset_ocr_results(results=results, max_attempts=max_attempts)
        return JsonResponse(result)
