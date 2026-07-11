# =============================================================================
# 모듈 설명: 활동 로그 기록/knox_id/포털 접근 검증 미들웨어를 제공합니다.
# - 주요 클래스: ActivityLoggingMiddleware, KnoxIdRequiredMiddleware, AccessRequiredMiddleware
# - 불변 조건: 활동 로그 저장은 activity 서비스 파사드를 통해 수행합니다.
# =============================================================================

"""활동 로그 기록과 knox_id 검증을 담당하는 공용 미들웨어 모음.

- 주요 대상: ActivityLoggingMiddleware, KnoxIdRequiredMiddleware
- 주요 엔드포인트/클래스: ActivityLoggingMiddleware, KnoxIdRequiredMiddleware
- 가정/불변 조건: 활동 로그 저장은 activity 서비스 파사드를 통해 수행됨
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, Iterable, Mapping, Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin  # Django 미들웨어 호환성 클래스

from api.common.permissions import (
    get_request_app_access_payload,
    get_request_portal_access_payload,
    is_portal_access_protected_path,
    resolve_app_access_scope_for_path,
)

from .request_helpers import _load_json_bytes

# 현재 파일의 로거(logger) 설정
logger = logging.getLogger(__name__)


class ActivityLoggingMiddleware(MiddlewareMixin):
    """사용자 요청/응답을 감시하고 ActivityLog에 기록하는 미들웨어.

    주요 동작:
    - 인증된 사용자 요청만 기록(비로그인 사용자는 user=None)
    - 관리자/시스템 경로는 기록하지 않음
    - 요청 경로, 메서드, 응답 코드, 쿼리 파라미터 등을 저장
    """

    TRACKED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def process_request(self, request: HttpRequest) -> None:
        """요청 단위 컨텍스트를 초기화하고 요청 페이로드를 스냅샷합니다.

        입력:
        - 요청: Django HttpRequest

        반환:
        - 없음

        부작용:
        - request에 `_activity_log_context`를 생성/갱신

        오류:
        - 없음
        """

        # -----------------------------------------------------------------------------
        # 1) 요청 컨텍스트 확보
        # -----------------------------------------------------------------------------
        context = getattr(request, "_activity_log_context", None)
        if context is None:
            context = {}
            setattr(request, "_activity_log_context", context)

        # -----------------------------------------------------------------------------
        # 2) 추적 대상 메서드의 요청 본문 스냅샷 저장
        # -----------------------------------------------------------------------------
        if request.method in self.TRACKED_METHODS:
            context["request_payload"] = self._extract_request_payload(request)

    def process_response(self, request: HttpRequest, response: HttpResponse):
        """응답 생성 후 호출되어 활동 로그를 기록합니다.

        입력:
        - 요청: Django HttpRequest
        - 응답: Django HttpResponse

        반환:
        - HttpResponse: 원본 응답 객체

        부작용:
        - ActivityLog에 DB 쓰기 발생 가능

        오류:
        - 로그 기록 중 오류는 삼키고 응답을 그대로 반환
        """
        # -----------------------------------------------------------------------------
        # 1) 로그 기록 시도(실패해도 응답 흐름 유지)
        # -----------------------------------------------------------------------------
        try:
            # 실제 로그 생성 함수 호출
            self._record(request, response)
        except Exception:  # 테스트 제외(커버리지): pragma: no cover
            # 로그 저장에 실패하더라도 서비스 중단 없이 에러만 기록
            logger.exception("Failed to record activity log")

        # -----------------------------------------------------------------------------
        # 2) 원본 응답 반환
        # -----------------------------------------------------------------------------
        # 원래의 응답 객체를 그대로 반환
        return response

    def _record(self, request: HttpRequest, response: HttpResponse) -> None:
        """ActivityLog 테이블에 로그 레코드를 생성합니다.

        입력:
        - 요청: Django HttpRequest
        - 응답: Django HttpResponse

        반환:
        - 없음

        부작용:
        - ActivityLog 테이블에 DB 쓰기 수행

        오류:
        - 없음(상위 호출에서 예외 처리)
        """
        # -----------------------------------------------------------------------------
        # 1) 기록 제외 조건 검사
        # -----------------------------------------------------------------------------
        # CORS preflight 요청(OPTIONS)은 무시
        if request.method == "OPTIONS":
            return

        # 요청 경로 추출 (없을 경우 안전하게 빈 문자열)
        path = getattr(request, "path", "") or ""

        # admin 페이지나 Django 내부 경로는 기록하지 않음
        if path.startswith("/admin/") or path.startswith("/__"):
            return

        # -----------------------------------------------------------------------------
        # 2) 인증 사용자 판별
        # -----------------------------------------------------------------------------
        user = getattr(request, "user", None)
        if user is not None and not getattr(user, "is_authenticated", False):
            user = None

        # -----------------------------------------------------------------------------
        # 3) 기본 메타데이터 구성
        # -----------------------------------------------------------------------------
        context: Dict[str, Any] = getattr(request, "_activity_log_context", {})

        metadata: Dict[str, Any] = {
            # GET 파라미터를 dict로 변환해 저장
            "query": request.GET.dict() if hasattr(request, "GET") else {},
            "result": "ok" if getattr(response, "status_code", 200) < 400 else "fail",
        }

        extra_metadata: Mapping[str, Any] = context.get("extra_metadata") or {}
        metadata.update(extra_metadata)

        # -----------------------------------------------------------------------------
        # 4) 변경/오류 정보 구성
        # -----------------------------------------------------------------------------
        if metadata["result"] == "ok" and request.method in self.TRACKED_METHODS:
            before = context.get("before")
            after = context.get("after")
            change_set = context.get("changes")
            if not change_set:
                change_set = self._compute_diff(before, after)
            normalized_changes = self._normalize_change_set(change_set)
            if normalized_changes:
                metadata["changes"] = normalized_changes
        elif metadata["result"] == "fail":
            error_payload = self._extract_response_payload(response)
            if error_payload is not None:
                try:
                    metadata["error"] = json.dumps(error_payload, ensure_ascii=False)
                except TypeError:
                    metadata["error"] = str(error_payload)
            else:
                status_text = getattr(response, "reason_phrase", None)
                if status_text:
                    metadata["error"] = status_text

        # -----------------------------------------------------------------------------
        # 5) activity 서비스 파사드를 통한 로그 생성
        # -----------------------------------------------------------------------------
        from api.activity import services as activity_services

        activity_services.record_activity_log(
            user=user,
            action=context.get("summary")
            or (
                request.resolver_match.view_name
                if getattr(request, "resolver_match", None)
                else ""
            ),
            path=path,
            method=getattr(request, "method", "GET"),
            status_code=getattr(response, "status_code", 200),
            metadata=metadata,
        )

    def _extract_request_payload(self, request: HttpRequest) -> Optional[Any]:
        """요청 본문을 JSON으로 파싱하거나 텍스트로 스냅샷합니다.

        입력:
        - 요청: Django HttpRequest

        반환:
        - Optional[Any]: JSON 객체 또는 텍스트, 실패 시 None

        부작용:
        - 없음

        오류:
        - 없음(읽기/파싱 실패 시 None)
        """

        # -----------------------------------------------------------------------------
        # 1) 요청 바디 읽기
        # -----------------------------------------------------------------------------
        try:
            body = request.body
        except Exception:  # 최선 처리(커버리지 제외): pragma: no cover
            return None

        # -----------------------------------------------------------------------------
        # 2) 빈 바디 처리
        # -----------------------------------------------------------------------------
        if not body:
            return None

        # -----------------------------------------------------------------------------
        # 3) JSON 파싱 시도
        # -----------------------------------------------------------------------------
        encoding = request.encoding or "utf-8"
        parsed, payload = _load_json_bytes(body, encoding=encoding)
        if parsed:
            return payload

        # -----------------------------------------------------------------------------
        # 4) 텍스트 폴백 처리
        # -----------------------------------------------------------------------------
        try:
            return body.decode(encoding, errors="replace")
        except Exception:
            return None

    def _extract_response_payload(self, response: HttpResponse) -> Optional[Any]:
        """응답 본문을 JSON으로 파싱합니다.

        입력:
        - 응답: Django HttpResponse

        반환:
        - Optional[Any]: JSON 객체 또는 None

        부작용:
        - 없음

        오류:
        - 없음(읽기/파싱 실패 시 None)
        """

        # -----------------------------------------------------------------------------
        # 1) 응답 콘텐츠 존재 여부 확인
        # -----------------------------------------------------------------------------
        if not hasattr(response, "content"):
            return None

        # -----------------------------------------------------------------------------
        # 2) 응답 콘텐츠 읽기
        # -----------------------------------------------------------------------------
        try:
            content = response.content
        except Exception:  # 최선 처리(커버리지 제외): pragma: no cover
            return None

        # -----------------------------------------------------------------------------
        # 3) 빈 콘텐츠 처리
        # -----------------------------------------------------------------------------
        if not content:
            return None

        # -----------------------------------------------------------------------------
        # 4) JSON 파싱
        # -----------------------------------------------------------------------------
        parsed, payload = _load_json_bytes(content, encoding=response.charset or "utf-8")
        return payload if parsed else None

    def _compute_diff(
        self, before: Optional[Any], after: Optional[Any]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """딕셔너리 기반 변경 사항을 계산합니다.

        입력:
        - before: 변경 전 상태
        - after: 변경 후 상태

        반환:
        - Optional[Dict[str, Dict[str, Any]]]: 변경 셋 또는 None

        부작용:
        - 없음

        오류:
        - 없음
        """

        # -----------------------------------------------------------------------------
        # 1) 입력 타입 검증
        # -----------------------------------------------------------------------------
        if not isinstance(after, Mapping):
            return None

        # -----------------------------------------------------------------------------
        # 2) before 미존재 처리
        # -----------------------------------------------------------------------------
        if not isinstance(before, Mapping):
            return {key: {"old": None, "new": value} for key, value in after.items()} or None

        # -----------------------------------------------------------------------------
        # 3) 변경 사항 비교
        # -----------------------------------------------------------------------------
        diff: Dict[str, Dict[str, Any]] = {}
        keys: Iterable[str] = set(before.keys()) | set(after.keys())
        for key in keys:
            old_value = before.get(key)
            new_value = after.get(key)
            if old_value != new_value:
                diff[key] = {"old": old_value, "new": new_value}

        # -----------------------------------------------------------------------------
        # 4) 결과 반환
        # -----------------------------------------------------------------------------
        return diff or None

    def _normalize_change_set(
        self, changes: Optional[Any]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """변경 사항을 {old, new} 구조로 정규화합니다.

        입력:
        - changes: 변경 셋 후보 값

        반환:
        - Optional[Dict[str, Dict[str, Any]]]: 정규화된 변경 셋

        부작용:
        - 없음

        오류:
        - 없음
        """

        # -----------------------------------------------------------------------------
        # 1) 입력 타입 검증
        # -----------------------------------------------------------------------------
        if not isinstance(changes, Mapping):
            return None

        # -----------------------------------------------------------------------------
        # 2) 필드별 정규화
        # -----------------------------------------------------------------------------
        normalized: Dict[str, Dict[str, Any]] = {}
        for field, payload in changes.items():
            if isinstance(payload, Mapping):
                old_value = payload.get("old", payload.get("from"))
                new_value = payload.get("new", payload.get("to"))
            else:
                old_value = None
                new_value = payload

            if old_value is None and new_value is None:
                continue

            normalized[field] = {
                "old": self._sanitize_json_value(old_value),
                "new": self._sanitize_json_value(new_value),
            }

        # -----------------------------------------------------------------------------
        # 3) 결과 반환
        # -----------------------------------------------------------------------------
        return normalized or None

    def _sanitize_json_value(self, value: Any) -> Any:
        """ActivityLog 메타데이터 저장을 위해 JSON 직렬화 가능한 값으로 변환합니다.

        입력:
        - value: 정규화 대상 값

        반환:
        - Any: JSON 직렬화 가능한 값

        부작용:
        - 없음

        오류:
        - 없음
        """

        # -----------------------------------------------------------------------------
        # 1) 타입별 변환
        # -----------------------------------------------------------------------------
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except Exception:
                return value.decode("utf-8", errors="replace")
        if isinstance(value, Mapping):
            return {k: self._sanitize_json_value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._sanitize_json_value(v) for v in value]

        # -----------------------------------------------------------------------------
        # 2) JSON 직렬화 가능 여부 확인
        # -----------------------------------------------------------------------------
        # json.dumps 가능 여부를 검사하여 불가능하면 문자열로 변환
        try:
            json.dumps(value)
            return value
        except TypeError:
            return str(value)


class KnoxIdRequiredMiddleware(MiddlewareMixin):
    """인증 사용자가 knox_id를 갖도록 보장하는 미들웨어.

    제외 경로는 EXEMPT_PATHS/EXEMPT_PATH_PREFIXES로 관리합니다.
    """

    EXEMPT_PATH_PREFIXES = (
        "/auth/",
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
        "/webhooks/",
    )
    EXEMPT_PATHS = {
        "/admin",
        "/api/docs",
        "/api/schema",
        "/api/v1/auth",
        "/api/v1/health",
        "/auth",
        "/docs",
        "/metrics",
        "/schema",
        "/static",
        "/media",
    }

    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        """knox_id 누락 여부를 검사하고 필요한 경우 403을 반환합니다.

        입력:
        - 요청: Django HttpRequest

        반환:
        - HttpResponse | None: 차단 시 JsonResponse, 통과 시 None

        부작용:
        - 없음

        오류:
        - 403: 인증 사용자이지만 knox_id가 없을 때
        """
        # -----------------------------------------------------------------------------
        # 1) 예외 경로 검사
        # -----------------------------------------------------------------------------
        path = getattr(request, "path", "") or ""
        if self._is_exempt_path(path):
            return None

        # -----------------------------------------------------------------------------
        # 2) 사용자 인증 상태 확인
        # -----------------------------------------------------------------------------
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None

        # -----------------------------------------------------------------------------
        # 3) knox_id 유효성 검사
        # -----------------------------------------------------------------------------
        knox_id = getattr(user, "knox_id", None)
        if not isinstance(knox_id, str) or not knox_id.strip():
            return JsonResponse({"error": "knox_id is required"}, status=403)

        return None

    def _is_exempt_path(self, path: str) -> bool:
        """knox_id 검사를 제외할 경로인지 판별합니다.

        입력:
        - path: 요청 경로

        반환:
        - bool: 제외 대상 여부

        부작용:
        - 없음

        오류:
        - 없음
        """
        # -----------------------------------------------------------------------------
        # 1) 빈 경로 처리
        # -----------------------------------------------------------------------------
        if not path:
            return False
        # -----------------------------------------------------------------------------
        # 2) 정확 경로 매칭
        # -----------------------------------------------------------------------------
        if path in self.EXEMPT_PATHS:
            return True
        # -----------------------------------------------------------------------------
        # 3) 프리픽스 매칭
        # -----------------------------------------------------------------------------
        return any(path.startswith(prefix) for prefix in self.EXEMPT_PATH_PREFIXES)


class AccessRequiredMiddleware(MiddlewareMixin):
    """인증 사용자의 portal/app scope 접근 상태를 API 레벨에서 검사합니다."""

    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        """포털과 앱 접근 승인 상태를 검사하고 차단 시 403을 반환합니다.

        입력:
        - 요청: Django HttpRequest

        반환:
        - HttpResponse | None: 차단 시 JsonResponse, 통과 시 None

        부작용:
        - 없음

        오류:
        - 403: 인증 사용자이지만 포털 접근이 허용되지 않을 때
        """

        path = getattr(request, "path", "") or ""
        if not is_portal_access_protected_path(path):
            return None

        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None

        portal_access = get_request_portal_access_payload(request=request, user=user)
        if not portal_access.get("allowed"):
            return JsonResponse(
                {
                    "error": "portal_access_required",
                    "portalAccess": portal_access,
                },
                status=403,
            )

        scope_key = resolve_app_access_scope_for_path(path)
        if scope_key is None:
            return None

        app_access = get_request_app_access_payload(
            request=request,
            user=user,
            scope_key=scope_key,
        )
        if app_access.get("allowed"):
            return None

        return JsonResponse(
            {
                "error": "app_access_required",
                "scope": scope_key,
                "appAccess": app_access,
            },
            status=403,
        )
