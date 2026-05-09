# =============================================================================
# 모듈: 드론 API 뷰
# 주요 엔드포인트: DroneEarlyInformView, LineHistoryView, DroneSop*TriggerView
# 주요 가정: 외부 트리거는 Airflow 토큰으로 보호합니다.
# =============================================================================
"""Drone 조기 알림 설정 및 라인 대시보드 집계 엔드포인트.

조기 알림 설정은 DroneEarlyInform ORM 모델을 통해 처리하고,
라인 대시보드 집계/옵션 조회는 selectors에서 원시 SQL로 처리합니다.

# 엔드포인트 요약
- 예시 요청: GET    /api/v1/line-dashboard/early-inform?lineId=L1
- 예시 요청: POST   /api/v1/line-dashboard/early-inform { lineId, mainStep, customEndStep? }
- 예시 요청: PATCH  /api/v1/line-dashboard/early-inform { id, lineId?, mainStep?, customEndStep? }
- 예시 요청: DELETE /api/v1/line-dashboard/early-inform?id=123
- 예시 요청: GET    /api/v1/line-dashboard/jira-keys?userSdwtProd=SDWT_A
- 예시 요청: GET    /api/v1/line-dashboard/jira-user-sdwt-prods
- 예시 요청: POST   /api/v1/line-dashboard/jira-keys { userSdwtProd, jiraKey?, templateKey? }
- 예시 요청: POST   /api/v1/line-dashboard/sop/precheck
- 예시 요청: POST   /api/v1/line-dashboard/sop/trigger  { limit? }

# 응답(예시)
GET 예시:
{
  예시 "lineId": "L1",
  예시 "rowCount": 2,
  예시 "rows": [
    예시 { "id": 1, "lineId": "L1", "mainStep": "ETCH", "customEndStep": "ETCH-9" },
    예시 { "id": 2, "lineId": "L1", "mainStep": "PR",   "customEndStep": null }
  ]
}

POST/PATCH 예시:
예시 { "entry": { "id": 3, "lineId": "L1", "mainStep": "CMP", "customEndStep": null } }

DELETE 예시:
예시 { "success": true }

# 유의사항
- CSRF 예외(@csrf_exempt)를 적용했으므로, 외부 호출 노출 시 토큰/인증 등 별도 방어가 필수입니다.
- 값 길이 제한은 MAX_FIELD_LENGTH(예: 50) 기준으로 검증합니다.
- 중복키(ER_DUP_ENTRY/MySQL, 23505/PostgreSQL)는 409 Conflict(충돌)로 응답합니다.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services.activity_logging import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)
from api.common.services.request_helpers import (
    ensure_airflow_token,
    parse_json_body,
    parse_json_body_or_error_when_present,
)

from . import selectors, services
from .serializers import (
    DroneRequestValidationError,
    normalize_custom_end_step,
    normalize_line_id,
    normalize_main_step,
    normalize_target_text,
    normalize_updated_by,
    parse_limit_param,
    parse_optional_bool_field,
    parse_optional_comment,
    parse_optional_text_field,
    parse_positive_int,
    parse_required_channel,
    parse_user_id_list,
    serialize_early_inform_entry,
)
from .services.table_schema import DEFAULT_TABLE as TABLE_DEFAULT_TABLE, sanitize_identifier

logger = logging.getLogger(__name__)

def _ensure_authenticated(request: HttpRequest) -> JsonResponse | None:
    """인증 여부를 확인하고 실패 시 JsonResponse를 반환합니다.

    인자:
        요청: Django HttpRequest 객체.

    반환:
        인증 실패 시 JsonResponse, 성공 시 None.

    부작용:
        없음. 순수 검사입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 인증 확인
    # -----------------------------------------------------------------------------
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
    return None


def _json_error(message: str, status: int = 400) -> JsonResponse:
    """에러 응답(JsonResponse)을 구성합니다.

    인자:
        message: 에러 메시지.
        status: HTTP 상태 코드.

    반환:
        JsonResponse 객체.

    부작용:
        없음. 순수 응답 생성입니다.
    """

    return JsonResponse({"error": message}, status=status)


def _validation_error_response(exc: DroneRequestValidationError) -> JsonResponse:
    """요청 검증 예외를 JsonResponse로 변환합니다."""

    return JsonResponse({"error": str(exc)}, status=exc.status_code)


def _parse_json_body_or_error(request: HttpRequest) -> tuple[dict[str, Any], JsonResponse | None]:
    """JSON 바디를 파싱하고 실패 시 에러 응답을 반환합니다.

    인자:
        request: Django HttpRequest 객체.

    반환:
        (payload, error_response) 형태의 튜플.
        - 성공 시: (payload, None)
        - 실패 시: ({}, JsonResponse)

    부작용:
        없음. 순수 파싱입니다.
    """

    payload = parse_json_body(request)
    if not isinstance(payload, dict):
        return {}, _json_error("Invalid JSON body", status=400)
    return payload, None


def _resolve_knox_id(request: HttpRequest) -> str | None:
    """요청 사용자에서 knox_id를 추출합니다.

    인자:
        request: Django HttpRequest 객체.

    반환:
        knox_id 문자열 또는 None.

    부작용:
        없음. 순수 추출입니다.
    """

    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return getattr(user, "knox_id", None)
    return None


def _ensure_airflow_authenticated(request: HttpRequest) -> JsonResponse | None:
    """Airflow Bearer 토큰 인증을 수행합니다.

    인자:
        request: Django HttpRequest 객체.

    반환:
        인증 실패 시 JsonResponse, 성공 시 None.

    부작용:
        없음. 인증 검사만 수행합니다.
    """

    return ensure_airflow_token(request, require_bearer=True)


def _record_drone_sop_pipeline_activity(
    request: HttpRequest,
    *,
    summary: str,
    pipeline: str,
    limit: int | None = None,
) -> None:
    """Drone SOP 파이프라인 액티비티 로그 메타데이터를 기록합니다."""

    set_activity_summary(request, summary)
    metadata: dict[str, Any] = {
        "resource": "drone_sop",
        "pipeline": pipeline,
    }
    if limit is not None:
        metadata["limit"] = limit
    merge_activity_metadata(request, **metadata)


def _internal_server_error_response(
    *,
    log_message: str,
    error_message: str,
) -> JsonResponse:
    """공통 500 응답을 생성하고 예외 로그를 기록합니다."""

    logger.exception(log_message)
    return JsonResponse({"error": error_message}, status=500)


def _record_activity_state_and_respond(
    request: HttpRequest,
    *,
    activity_state: dict[str, Any],
    response_payload: dict[str, Any],
    status: int = 200,
) -> JsonResponse:
    """액티비티 상태를 기록하고 JSON 응답을 반환합니다."""

    set_activity_new_state(request, activity_state)
    return JsonResponse(response_payload, status=status)


def _respond_precheck_has_candidates(
    request: HttpRequest,
    *,
    has_candidates: bool,
) -> JsonResponse:
    """사전 확인(precheck) 응답을 구성합니다."""

    response_payload: dict[str, Any] = {"hasCandidates": has_candidates}
    activity_state: dict[str, Any] = {"has_candidates": has_candidates}

    return _record_activity_state_and_respond(
        request,
        activity_state=activity_state,
        response_payload=response_payload,
    )


def _respond_pop3_ingest_result(request: HttpRequest, *, result: Any) -> JsonResponse:
    """POP3 수집 트리거 응답을 구성합니다."""

    return _record_activity_state_and_respond(
        request,
        activity_state={
            "matched": result.matched_mails,
            "upserted": result.upserted_rows,
            "deleted": result.deleted_mails,
            "pruned": result.pruned_rows,
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
        },
        response_payload={
            "matched": result.matched_mails,
            "upserted": result.upserted_rows,
            "deleted": result.deleted_mails,
            "pruned": result.pruned_rows,
            "skipped": result.skipped,
            "skipReason": result.skip_reason,
        },
    )


def _respond_pipeline_trigger_result(
    request: HttpRequest,
    *,
    result: Any,
) -> JsonResponse:
    """통합 Drone SOP 파이프라인 트리거 응답을 구성합니다."""

    response_payload: dict[str, Any] = {
        "candidates": result.candidates,
        "jiraCreated": result.jira_created,
        "jiraUpdated": result.jira_updated_rows,
        "messengerSent": result.messenger_sent,
        "mailSent": result.mail_sent,
        "skipped": result.skipped,
        "skipReason": result.skip_reason,
    }
    activity_state: dict[str, Any] = {
        "candidates": result.candidates,
        "jira_created": result.jira_created,
        "jira_updated_rows": result.jira_updated_rows,
        "messenger_sent": result.messenger_sent,
        "mail_sent": result.mail_sent,
        "skipped": result.skipped,
        "skip_reason": result.skip_reason,
    }
    return _record_activity_state_and_respond(
        request,
        activity_state=activity_state,
        response_payload=response_payload,
    )


class DroneAirflowTriggerView(APIView):
    """Airflow Bearer 토큰 인증이 필요한 트리거 뷰 베이스 클래스."""

    permission_classes: tuple = ()

    @staticmethod
    def _authorize_airflow(request: HttpRequest) -> JsonResponse | None:
        """Airflow 토큰 인증을 확인합니다."""

        return _ensure_airflow_authenticated(request)

    def _execute_airflow_pipeline(
        self,
        request: HttpRequest,
        *,
        summary: str,
        pipeline: str,
        on_success: Callable[[], JsonResponse],
        log_message: str,
        error_message: str,
        limit: int | None = None,
        authorize: bool = True,
    ) -> JsonResponse:
        """Airflow 트리거 공통 실행 흐름(인증/로그/예외)을 처리합니다."""

        if authorize:
            auth_response = self._authorize_airflow(request)
            if auth_response is not None:
                return auth_response

        _record_drone_sop_pipeline_activity(
            request,
            summary=summary,
            pipeline=pipeline,
            limit=limit,
        )

        try:
            return on_success()
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message=log_message,
                error_message=error_message,
            )


class DroneAuthenticatedView(APIView):
    """로그인 사용자 인증이 필요한 뷰 베이스 클래스."""

    @staticmethod
    def _authorize_user(request: HttpRequest) -> JsonResponse | None:
        """사용자 인증을 확인합니다."""

        return _ensure_authenticated(request)

    @staticmethod
    def _execute_user_action(
        *,
        on_success: Callable[[], JsonResponse],
        log_message: str,
        error_message: str,
    ) -> JsonResponse:
        """사용자 액션 공통 실행 흐름(ValueError/예외)을 처리합니다."""

        try:
            return on_success()
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message=log_message,
                error_message=error_message,
            )


@method_decorator(csrf_exempt, name="dispatch")
class DroneEarlyInformView(DroneAuthenticatedView):
    """drone_early_inform 테이블 CRUD(생성/조회/수정/삭제) 엔드포인트입니다.

    - GET: lineId로 행 목록 조회(정렬: main_step ASC, id ASC)
    - POST: 신규 행 추가(중복 main_step 방지 가정)
    - PATCH: 부분 업데이트(id 필수)
    - DELETE: 행 삭제(id 쿼리 파라미터)
    """

    # 한 곳에서만 테이블명을 관리해 실수 방지
    TABLE_NAME = "drone_early_inform"

    # --------------------------------------------------------------------- #
    # 조회
    # --------------------------------------------------------------------- #
    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """lineId로 행 목록을 가져옵니다.

        요청 예시:
            예시 요청: GET /api/v1/line-dashboard/early-inform?lineId=L1

        반환:
            예시 응답: 200 {"lineId": "...", "rowCount": 1, "rows": [...], "userSdwt": [...]}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            400: lineId 누락/형식 오류
            401: 비인증
            500: 서버 오류

        snake_case/camelCase 호환:
            query 파라미터는 lineId만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 파라미터 검증
        # -----------------------------------------------------------------------------
        line_id = normalize_line_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        try:
            normalized_rows = [
                serialize_early_inform_entry(entry)
                for entry in selectors.list_early_inform_entries(line_id=line_id)
            ]
            user_sdwt_values = selectors.list_user_sdwt_prod_values_for_line(line_id=line_id)
            return JsonResponse(
                {
                    "lineId": line_id,
                    "rowCount": len(normalized_rows),
                    "rows": normalized_rows,
                    "userSdwt": user_sdwt_values,
                }
            )
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load drone_early_inform rows",
                error_message="Failed to load settings",
            )

    # --------------------------------------------------------------------- #
    # 생성
    # --------------------------------------------------------------------- #
    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """신규 행을 생성합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/early-inform
            예시 바디: {"lineId":"L1","mainStep":"STEP1","customEndStep":"STEP2"}

        반환:
            예시 응답: 201 {"entry": {...}}

        부작용:
            DroneEarlyInform 레코드가 생성됩니다.

        오류:
            400: JSON/필드 검증 오류
            401: 비인증
            409: 중복 키
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 camelCase(lineId/mainStep/customEndStep)만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱
        # -----------------------------------------------------------------------------
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 3) 필수/선택 필드 검증
        # -----------------------------------------------------------------------------
        line_id = normalize_line_id(payload.get("lineId"))
        main_step = normalize_main_step(payload.get("mainStep"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)
        if not main_step:
            return JsonResponse({"error": "mainStep is required"}, status=400)

        try:
            custom_end_step = normalize_custom_end_step(payload.get("customEndStep"))
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        # -----------------------------------------------------------------------------
        # 4) updated_by 계산
        # -----------------------------------------------------------------------------
        updated_by = self._resolve_updated_by(request)

        # -----------------------------------------------------------------------------
        # 5) 서비스 호출 및 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        try:
            entry = services.create_early_inform_entry(
                line_id=line_id,
                main_step=main_step,
                custom_end_step=custom_end_step,
                updated_by=updated_by,
            )
            entry_payload = serialize_early_inform_entry(entry)

            set_activity_summary(request, "Create drone_early_inform entry")
            set_activity_new_state(request, entry_payload)
            merge_activity_metadata(
                request,
                resource=self.TABLE_NAME,
                entryId=entry_payload["id"],
            )
            return JsonResponse({"entry": entry_payload}, status=201)

        except services.DroneEarlyInformDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to create drone_early_inform row",
                error_message="Failed to create entry",
            )

    # --------------------------------------------------------------------- #
    # 수정(부분)
    # --------------------------------------------------------------------- #
    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """id로 지정된 행을 부분 업데이트합니다.

        요청 예시:
            예시 요청: PATCH /api/v1/line-dashboard/early-inform
            예시 바디: {"id": 123, "customEndStep": "STEP2"}

        반환:
            예시 응답: 200 {"entry": {...}}

        부작용:
            DroneEarlyInform 레코드가 수정됩니다.

        오류:
            400: JSON/필드 검증 오류
            401: 비인증
            404: 대상 없음
            409: 중복 키
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 camelCase(lineId/mainStep/customEndStep)만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱
        # -----------------------------------------------------------------------------
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 3) id 검증
        # -----------------------------------------------------------------------------
        try:
            entry_id = parse_positive_int(payload.get("id"))
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        # -----------------------------------------------------------------------------
        # 4) 액티비티 로그 및 업데이트 필드 수집
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Update drone_early_inform entry #{entry_id}")
        merge_activity_metadata(request, resource=self.TABLE_NAME, entryId=entry_id)

        updates: dict[str, Any] = {}
        updated_by = self._resolve_updated_by(request)

        if "lineId" in payload:
            line_id = normalize_line_id(payload.get("lineId"))
            if not line_id:
                return JsonResponse({"error": "lineId is required"}, status=400)
            updates["line_id"] = line_id

        if "mainStep" in payload:
            main_step = normalize_main_step(payload.get("mainStep"))
            if not main_step:
                return JsonResponse({"error": "mainStep is required"}, status=400)
            updates["main_step"] = main_step

        if "customEndStep" in payload:
            try:
                normalized = normalize_custom_end_step(payload.get("customEndStep"))
            except DroneRequestValidationError as exc:
                return _validation_error_response(exc)
            updates["custom_end_step"] = normalized

        if not updates:
            return JsonResponse({"error": "No valid fields to update"}, status=400)

        # -----------------------------------------------------------------------------
        # 5) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            result = services.update_early_inform_entry(
                entry_id=entry_id,
                updates=updates,
                updated_by=updated_by,
            )
            set_activity_previous_state(request, serialize_early_inform_entry(result.previous_entry))
            entry_payload = serialize_early_inform_entry(result.entry)
            set_activity_new_state(request, entry_payload)
            return JsonResponse({"entry": entry_payload})

        except services.DroneEarlyInformNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except services.DroneEarlyInformDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to update drone_early_inform row",
                error_message="Failed to update entry",
            )

    # --------------------------------------------------------------------- #
    # 삭제
    # --------------------------------------------------------------------- #
    def delete(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """id로 지정된 행을 삭제합니다.

        요청 예시:
            예시 요청: DELETE /api/v1/line-dashboard/early-inform?id=123

        반환:
            예시 응답: 200 {"success": true}

        부작용:
            DroneEarlyInform 레코드가 삭제됩니다.

        오류:
            400: id 검증 오류
            401: 비인증
            404: 대상 없음
            500: 서버 오류

        snake_case/camelCase 호환:
            query 파라미터는 id만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) id 검증
        # -----------------------------------------------------------------------------
        try:
            entry_id = parse_positive_int(request.GET.get("id"))
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        # -----------------------------------------------------------------------------
        # 3) 액티비티 로그 및 삭제 수행
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Delete drone_early_inform entry #{entry_id}")
        merge_activity_metadata(request, resource=self.TABLE_NAME, entryId=entry_id)

        try:
            deleted_entry = services.delete_early_inform_entry(entry_id=entry_id)
            set_activity_previous_state(request, serialize_early_inform_entry(deleted_entry))

            set_activity_new_state(request, {"deleted": True})
            return JsonResponse({"success": True})

        except services.DroneEarlyInformNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to delete drone_early_inform row",
                error_message="Failed to delete entry",
            )

    # --------------------------------------------------------------------- #
    # 검증/정규화 유틸
    # --------------------------------------------------------------------- #
    @classmethod
    def _resolve_updated_by(cls, request: HttpRequest) -> str | None:
        """요청 사용자 기반 updated_by 값을 정규화합니다."""

        knox_id = _resolve_knox_id(request)
        return normalize_updated_by(knox_id or "system")


@method_decorator(csrf_exempt, name="dispatch")
class DroneNotificationTargetView(DroneAuthenticatedView):
    """라인별 Drone SOP 알림 target 조회/생성 엔드포인트입니다."""

    @staticmethod
    def _serialize_target(target: Any, *, fallback_line_id: str) -> dict[str, object]:
        """DroneSopUserSdwtChannel row를 API 응답 형태로 변환합니다."""

        return {
            "lineId": getattr(target, "line_id", None) or fallback_line_id,
            "targetUserSdwtProd": getattr(target, "target_user_sdwt_prod", None) or "",
            "source": getattr(target, "source", None) or "custom",
            "isConfigured": True,
            "jiraKey": getattr(target, "jira_key", None) or None,
            "jiraEnabled": bool(getattr(target, "jira_enabled", True)),
            "messengerEnabled": bool(getattr(target, "messenger_enabled", True)),
            "mailEnabled": bool(getattr(target, "mail_enabled", True)),
        }

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인별 알림 target 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: target 목록

        부작용:
        - 없음(읽기 전용)

        오류:
        - 400: lineId 누락
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/notification-targets?lineId=L1

        snake/camel 호환:
        - 요청 쿼리는 lineId(camelCase)만 지원합니다.
        """

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        line_id = normalize_line_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        targets = selectors.list_drone_sop_notification_targets_for_line(line_id=line_id)
        mapping_options = selectors.list_drone_sop_mapping_option_values_for_line(line_id=line_id)
        return JsonResponse(
            {
                "lineId": line_id,
                "targets": targets,
                "targetUserSdwtProds": [row["targetUserSdwtProd"] for row in targets],
                "mappingOptions": mapping_options,
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인별 알림 target을 생성합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 생성/조회된 target

        부작용:
        - DroneSopUserSdwtChannel target row 생성 또는 재활성화

        오류:
        - 400: 입력 오류
        - 401: 미인증
        - 403: 권한 없음

        예시 요청:
        - 예시 요청: POST /api/v1/line-dashboard/notification-targets
          요청 바디 예시: {"lineId":"L1","targetUserSdwtProd":"L1_NIGHT_SHIFT"}

        snake/camel 호환:
        - 요청 본문은 lineId/targetUserSdwtProd(camelCase)만 지원합니다.
        """

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        if not selectors.user_can_manage_drone_sop_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        line_id = normalize_line_id(payload.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)
        target_user_sdwt_prod = normalize_target_text(payload.get("targetUserSdwtProd"))
        if not target_user_sdwt_prod:
            return JsonResponse({"error": "targetUserSdwtProd is required"}, status=400)
        existing_targets = selectors.list_drone_sop_notification_targets_for_line(line_id=line_id)
        if any(
            str(row.get("targetUserSdwtProd") or "").casefold() == target_user_sdwt_prod.casefold()
            for row in existing_targets
        ):
            return JsonResponse({"error": "notification target already exists"}, status=409)

        try:
            target, updated = services.ensure_drone_sop_notification_target(
                line_id=line_id,
                target_user_sdwt_prod=target_user_sdwt_prod,
                actor=request.user,
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        return JsonResponse(
            {
                "lineId": line_id,
                "target": self._serialize_target(target, fallback_line_id=line_id),
                "updated": updated,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneNotificationTargetMappingView(DroneAuthenticatedView):
    """라인별 Drone SOP 알림 target 지정 조합 생성 엔드포인트입니다."""

    @staticmethod
    def _find_response_target(*, line_id: str, target_user_sdwt_prod: str) -> dict[str, object]:
        """갱신 후 target 목록에서 응답 대상 target을 찾습니다."""

        targets = selectors.list_drone_sop_notification_targets_for_line(line_id=line_id)
        normalized_target = target_user_sdwt_prod.casefold()
        for target in targets:
            if str(target.get("targetUserSdwtProd") or "").casefold() == normalized_target:
                return target
        return {
            "lineId": line_id,
            "targetUserSdwtProd": target_user_sdwt_prod,
            "source": "custom",
            "isConfigured": True,
            "jiraKey": None,
            "jiraEnabled": True,
            "messengerEnabled": True,
            "mailEnabled": True,
            "mappings": [],
        }

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """알림 target에 sdwt_prod/user_sdwt_prod 지정 조합을 추가합니다.

        예시 요청:
        - POST /api/v1/line-dashboard/notification-target-mappings
          {"lineId":"L1","targetUserSdwtProd":"TARGET_A","sdwtProd":"SDWT_A","userSdwtProd":"USR_A"}
        """

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        if not selectors.user_can_manage_drone_sop_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        line_id = normalize_line_id(payload.get("lineId"))
        target_user_sdwt_prod = normalize_target_text(payload.get("targetUserSdwtProd"))
        sdwt_prod = normalize_target_text(payload.get("sdwtProd"))
        user_sdwt_prod = normalize_target_text(payload.get("userSdwtProd"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)
        if not target_user_sdwt_prod:
            return JsonResponse({"error": "targetUserSdwtProd is required"}, status=400)
        if not sdwt_prod:
            return JsonResponse({"error": "sdwtProd is required"}, status=400)
        if not user_sdwt_prod:
            return JsonResponse({"error": "userSdwtProd is required"}, status=400)

        try:
            mapping = services.create_drone_sop_target_mapping(
                line_id=line_id,
                target_user_sdwt_prod=target_user_sdwt_prod,
                sdwt_prod=sdwt_prod,
                user_sdwt_prod=user_sdwt_prod,
                actor=request.user,
            )
        except services.DroneSopTargetMappingDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        target = self._find_response_target(
            line_id=line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
        )
        return JsonResponse(
            {
                "lineId": line_id,
                "target": target,
                "mapping": {
                    "sdwtProd": mapping.sdwt_prod or "",
                    "userSdwtProd": mapping.user_sdwt_prod or "",
                },
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneJiraKeyView(DroneAuthenticatedView):
    """target_user_sdwt_prod 단위 Jira 템플릿/프로젝트 키 조회/갱신 엔드포인트입니다."""

    MAX_PROJECT_KEY_LENGTH = 64
    MAX_TEMPLATE_KEY_LENGTH = 50
    MAX_NEEDTOSEND_KEYWORD_LENGTH = 64

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """userSdwtProd에 해당하는 Jira 키/템플릿 키를 조회합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: Jira 키/템플릿 키 정보

        부작용:
        - 없음(읽기 전용)

        오류:
        - 400: userSdwtProd 누락
        - 401: 미인증
        - 404: userSdwtProd 없음

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/jira-keys?userSdwtProd=SDWT_A

        snake/camel 호환:
        - 요청 쿼리는 userSdwtProd(camelCase)만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) targetUserSdwtProd 검증
        # -----------------------------------------------------------------------------
        target_user_sdwt_prod = normalize_target_text(
            request.GET.get("targetUserSdwtProd") or request.GET.get("userSdwtProd")
        )
        if not target_user_sdwt_prod:
            return JsonResponse({"error": "userSdwtProd is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 4) Jira 키 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        entry = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(
            target_user_sdwt_prod=target_user_sdwt_prod
        )
        jira_key = entry.jira_key if entry and entry.jira_key else None
        template_key = entry.jira_template_key if entry and entry.jira_template_key else None
        return JsonResponse(
            {
                "userSdwtProd": target_user_sdwt_prod,
                "targetUserSdwtProd": target_user_sdwt_prod,
                "lineId": entry.line_id if entry else "",
                "jiraKey": jira_key,
                "templateKey": template_key,
                "jiraEnabled": bool(entry.jira_enabled) if entry else True,
                "messengerEnabled": bool(entry.messenger_enabled) if entry else True,
                "mailEnabled": bool(entry.mail_enabled) if entry else True,
                "needtosendCommentLastAt": entry.needtosend_comment_last_at if entry else None,
                "needtosendEnabled": bool(entry.needtosend_enabled) if entry else False,
                "needtosendIgnoreSampleType": bool(entry.needtosend_ignore_sample_type) if entry else False,
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """슈퍼유저가 userSdwtProd에 대한 Jira 키/템플릿 키를 갱신합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 갱신 결과

        부작용:
        - Jira 키/템플릿 키 갱신

        오류:
        - 400: 입력 오류
        - 401: 미인증
        - 403: 권한 없음
        - 403: 권한 없음
        - 404: userSdwtProd 없음

        예시 요청:
        - 예시 요청: POST /api/v1/line-dashboard/jira-keys
          요청 바디 예시: {"userSdwtProd":"SDWT_A","jiraKey":"ABC","templateKey":"common"}

        snake/camel 호환:
        - 요청 본문은 userSdwtProd/jiraKey/templateKey(camelCase)만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        if not getattr(request.user, "is_superuser", False):
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 3) targetUserSdwtProd 추출 및 검증
        # -----------------------------------------------------------------------------
        target_user_sdwt_prod = normalize_target_text(
            payload.get("targetUserSdwtProd") or payload.get("userSdwtProd")
        )
        if not target_user_sdwt_prod:
            return JsonResponse({"error": "userSdwtProd is required"}, status=400)
        line_id = normalize_line_id(payload.get("lineId"))

        # -----------------------------------------------------------------------------
        # 5) jiraKey/templateKey 추출 및 길이 검증
        # -----------------------------------------------------------------------------
        try:
            jira_key_provided, jira_key = parse_optional_text_field(
                payload,
                field_name="jiraKey",
                max_length=self.MAX_PROJECT_KEY_LENGTH,
            )
            template_key_provided, template_key = parse_optional_text_field(
                payload,
                field_name="templateKey",
                max_length=self.MAX_TEMPLATE_KEY_LENGTH,
            )
            jira_enabled_provided, jira_enabled = parse_optional_bool_field(
                payload,
                field_name="jiraEnabled",
            )
            messenger_enabled_provided, messenger_enabled = parse_optional_bool_field(
                payload,
                field_name="messengerEnabled",
            )
            mail_enabled_provided, mail_enabled = parse_optional_bool_field(
                payload,
                field_name="mailEnabled",
            )
            needtosend_comment_provided, needtosend_comment_last_at = parse_optional_text_field(
                payload,
                field_name="needtosendCommentLastAt",
                max_length=self.MAX_NEEDTOSEND_KEYWORD_LENGTH,
            )
            needtosend_enabled_provided, needtosend_enabled = parse_optional_bool_field(
                payload,
                field_name="needtosendEnabled",
            )
            needtosend_ignore_sample_type_provided, needtosend_ignore_sample_type = parse_optional_bool_field(
                payload,
                field_name="needtosendIgnoreSampleType",
            )
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        if not (
            jira_key_provided
            or template_key_provided
            or jira_enabled_provided
            or messenger_enabled_provided
            or mail_enabled_provided
            or needtosend_comment_provided
            or needtosend_enabled_provided
            or needtosend_ignore_sample_type_provided
        ):
            return JsonResponse({"error": "jiraKey or templateKey is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 6) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload_kwargs: dict[str, object] = {"target_user_sdwt_prod": target_user_sdwt_prod}
        if line_id:
            payload_kwargs["line_id"] = line_id
            payload_kwargs["actor"] = request.user
        if jira_key_provided:
            payload_kwargs["jira_key"] = jira_key
        if template_key_provided:
            payload_kwargs["jira_template_key"] = template_key
        if jira_enabled_provided:
            payload_kwargs["jira_enabled"] = jira_enabled
        if messenger_enabled_provided:
            payload_kwargs["messenger_enabled"] = messenger_enabled
        if mail_enabled_provided:
            payload_kwargs["mail_enabled"] = mail_enabled
        if needtosend_comment_provided:
            payload_kwargs["needtosend_comment_last_at"] = needtosend_comment_last_at
        if needtosend_enabled_provided:
            payload_kwargs["needtosend_enabled"] = needtosend_enabled
        if needtosend_ignore_sample_type_provided:
            payload_kwargs["needtosend_ignore_sample_type"] = needtosend_ignore_sample_type

        try:
            template, updated = services.upsert_drone_sop_user_sdwt_channel(**payload_kwargs)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse(
            {
                "userSdwtProd": target_user_sdwt_prod,
                "targetUserSdwtProd": target_user_sdwt_prod,
                "lineId": template.line_id or line_id,
                "jiraKey": template.jira_key,
                "templateKey": template.jira_template_key,
                "jiraEnabled": template.jira_enabled,
                "messengerEnabled": template.messenger_enabled,
                "mailEnabled": template.mail_enabled,
                "needtosendCommentLastAt": template.needtosend_comment_last_at,
                "needtosendEnabled": template.needtosend_enabled,
                "needtosendIgnoreSampleType": template.needtosend_ignore_sample_type,
                "updated": updated,
            }
        )


class JiraUserSdwtProdListView(DroneAuthenticatedView):
    """채널 설정에 등록된 target_user_sdwt_prod 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """채널 설정에 등록된 target_user_sdwt_prod 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: {"userSdwtProds": ["..."]}

        부작용:
        - 없음(읽기 전용)

        오류:
        - 401: 미인증
        - 500: 서버 오류

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/jira-user-sdwt-prods

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 목록 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        try:
            target_user_sdwt_prods = selectors.list_drone_sop_jira_target_user_sdwt_prods()
            return JsonResponse({"userSdwtProds": target_user_sdwt_prods})
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load Jira user SDWT prods",
                error_message="Failed to load Jira user SDWT prods",
            )


@method_decorator(csrf_exempt, name="dispatch")
class DroneNotificationRecipientView(DroneAuthenticatedView):
    """Drone SOP 채널별 수신인 조회/교체 엔드포인트입니다.

    커스텀 targetUserSdwtProd는 허용하지만 lineId는 기존 라인 안에서만 허용합니다.
    """

    @classmethod
    def _validate_line_id(cls, raw_value: Any) -> tuple[str, JsonResponse | None]:
        """lineId 필수 여부를 검증합니다."""

        line_id = normalize_line_id(raw_value)
        if not line_id:
            return "", JsonResponse({"error": "lineId is required"}, status=400)
        return line_id, None

    @classmethod
    def _validate_target(cls, raw_value: Any) -> tuple[str, JsonResponse | None]:
        """targetUserSdwtProd 필수 여부를 검증합니다."""

        target_user_sdwt_prod = normalize_target_text(raw_value)
        if not target_user_sdwt_prod:
            return "", JsonResponse({"error": "targetUserSdwtProd is required"}, status=400)
        return target_user_sdwt_prod, None

    @staticmethod
    def _validate_channel(raw_value: Any) -> tuple[str, JsonResponse | None]:
        """채널 값을 mail/messenger 중 하나로 검증합니다."""

        try:
            channel = services.normalize_recipient_channel(raw_value)
        except ValueError as exc:
            return "", JsonResponse({"error": str(exc)}, status=400)
        return channel, None

    @staticmethod
    def _can_update_recipients(*, user: Any) -> bool:
        """수신인 설정 변경 권한을 확인합니다."""

        return selectors.user_can_manage_drone_sop_recipients(user=user)

    @staticmethod
    def _validate_target_line_context(*, line_id: str, target_user_sdwt_prod: str) -> JsonResponse | None:
        """target이 이미 다른 line에 소속되어 있으면 요청을 거부합니다."""

        target = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(
            target_user_sdwt_prod=target_user_sdwt_prod
        )
        target_line_id = getattr(target, "line_id", "") if target else ""
        if target_line_id and target_line_id.casefold() != line_id.casefold():
            return JsonResponse({"error": "targetUserSdwtProd already belongs to another line"}, status=400)
        return None

    @staticmethod
    def _resolve_target_line_id(*, line_id: str, target_user_sdwt_prod: str) -> str:
        """기존 target이 있으면 저장된 line_id를 우선 사용합니다."""

        target = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(
            target_user_sdwt_prod=target_user_sdwt_prod
        )
        target_line_id = getattr(target, "line_id", "") if target else ""
        return target_line_id or line_id

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """target/channel 수신인 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 수신인 목록

        부작용:
        - 없음(읽기 전용)

        오류:
        - 400: 입력 오류
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/notification-recipients?lineId=L1&targetUserSdwtProd=ETCH_A&channel=mail

        snake/camel 호환:
        - 요청 쿼리는 lineId/targetUserSdwtProd/channel(camelCase)만 지원합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) line/target/channel 검증
        # -----------------------------------------------------------------------------
        line_id, line_error = self._validate_line_id(request.GET.get("lineId"))
        if line_error is not None:
            return line_error
        target_user_sdwt_prod, target_error = self._validate_target(request.GET.get("targetUserSdwtProd"))
        if target_error is not None:
            return target_error
        channel, channel_error = self._validate_channel(request.GET.get("channel") or "mail")
        if channel_error is not None:
            return channel_error
        resolved_line_id = self._resolve_target_line_id(
            line_id=line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
        )

        if not self._can_update_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) 수신인 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        recipients = selectors.list_drone_sop_channel_recipients(
            line_id=resolved_line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
            channel=channel,
        )
        return JsonResponse(
            {
                "lineId": resolved_line_id,
                "targetUserSdwtProd": target_user_sdwt_prod,
                "channel": channel,
                "recipients": recipients,
            }
        )

    def put(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """target/channel 수신인 목록을 최종 userIds 스냅샷으로 교체합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 갱신된 수신인 목록

        부작용:
        - 수신인 생성/재활성화/비활성화

        오류:
        - 400: 입력 오류
        - 401: 미인증
        - 403: 권한 없음

        예시 요청:
        - 예시 요청: PUT /api/v1/line-dashboard/notification-recipients
          요청 바디 예시: {"lineId":"L1","targetUserSdwtProd":"ETCH_A","channel":"mail","userIds":[1,2,3]}

        snake/camel 호환:
        - 요청 본문은 lineId/targetUserSdwtProd/channel/userIds(camelCase)만 지원합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 및 JSON 파싱
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 2) line/target/channel/userIds 검증
        # -----------------------------------------------------------------------------
        line_id, line_error = self._validate_line_id(payload.get("lineId"))
        if line_error is not None:
            return line_error
        target_user_sdwt_prod, target_error = self._validate_target(payload.get("targetUserSdwtProd"))
        if target_error is not None:
            return target_error
        channel, channel_error = self._validate_channel(payload.get("channel") or "mail")
        if channel_error is not None:
            return channel_error
        target_line_error = self._validate_target_line_context(
            line_id=line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
        )
        if target_line_error is not None:
            return target_line_error
        try:
            user_ids = parse_user_id_list(payload.get("userIds"))
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        if not self._can_update_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        try:
            result = services.replace_drone_sop_channel_recipients(
                line_id=line_id,
                target_user_sdwt_prod=target_user_sdwt_prod,
                channel=channel,
                user_ids=user_ids,
                actor=request.user,
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse(result)


@method_decorator(csrf_exempt, name="dispatch")
class DroneNotificationRecipientPermissionView(DroneAuthenticatedView):
    """Drone SOP 수신인 설정 권한 컨텍스트 조회 엔드포인트입니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자의 Drone SOP 수신인 설정 권한을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 운영자 여부와 관리 가능한 User SDWT 목록

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/notification-recipient-permissions

        snake/camel 호환:
        - 요청 바디 없음
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) Drone 앱 권한 컨텍스트 반환
        # -----------------------------------------------------------------------------
        return JsonResponse(selectors.get_drone_sop_permission_context(user=request.user))


class LineHistoryView(APIView):
    """라인 대시보드 차트용 시간 단위 합계/분해 집계 제공."""

    DEFAULT_RANGE_DAYS = 14

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인 대시보드 히스토리 집계를 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/line-dashboard/history?lineId=L1&rangeDays=14

        반환:
            예시 응답: 200 {"table": "...", "from": "...", "to": "...", "totals": [...], "breakdowns": {...}}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            400: 파라미터 검증 오류
            500: 서버 오류

        snake_case/camelCase 호환:
            query 파라미터는 lineId/rangeDays 등 camelCase만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 집계 payload 구성
        # -----------------------------------------------------------------------------
        try:
            payload = selectors.get_line_history_payload(
                table_param=request.GET.get("table"),
                line_id_param=request.GET.get("lineId"),
                from_param=request.GET.get("from"),
                to_param=request.GET.get("to"),
                range_days_param=request.GET.get("rangeDays"),
                default_range_days=self.DEFAULT_RANGE_DAYS,
            )
            return JsonResponse(payload)
        except (ValueError, LookupError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load history data",
                error_message="Failed to load history data",
            )


class LineIdListView(APIView):
    """사이드바 필터용 line_id 고유값 목록 반환."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """line_id 고유값 목록을 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/line-dashboard/line-ids

        반환:
            예시 응답: 200 {"lineIds": ["L1", "L2"]}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            500: 서버 오류

        snake_case/camelCase 호환:
            입력 파라미터는 없습니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 목록 조회
        # -----------------------------------------------------------------------------
        try:
            return JsonResponse({"lineIds": selectors.list_distinct_line_ids()})
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load distinct line ids",
                error_message="Failed to load line options",
            )


class DroneTablesView(APIView):
    """라인 대시보드 테이블 조회 엔드포인트입니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """테이블 목록 조회 결과를 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/line-dashboard/tables?table=drone_sop&lineId=L1

        반환:
            예시 응답: 200 {"table":"drone_sop","rowCount":1,"rows":[...]}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            404: 테이블 없음
            400: 입력 오류(컬럼/날짜 등)
            500: 내부 오류
        """

        try:
            payload = services.get_table_list_payload(params=request.GET)
            return JsonResponse(payload)
        except services.TableNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except (ValueError, LookupError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load drone tables data",
                error_message="Failed to load table data",
            )


@method_decorator(csrf_exempt, name="dispatch")
class DroneTableUpdateView(APIView):
    """라인 대시보드 테이블 단건 수정 엔드포인트입니다."""

    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """테이블 레코드를 부분 업데이트합니다.

        요청 예시:
            예시 요청: PATCH /api/v1/line-dashboard/tables/update
            예시 바디: {"table":"drone_sop","id":123,"updates":{"status":"DONE"}}

        반환:
            예시 응답: 200 {"success": true}

        부작용:
            대상 테이블 레코드가 업데이트됩니다.

        오류:
            400: 입력 오류/JSON 파싱 실패
            404: 테이블/레코드 없음
            500: 내부 오류
        """

        payload = parse_json_body(request)
        if not isinstance(payload, dict):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        table_name = sanitize_identifier(payload.get("table"), TABLE_DEFAULT_TABLE)
        if not table_name:
            return JsonResponse({"error": "Invalid table name"}, status=400)

        record_id = payload.get("id")
        if record_id in (None, ""):
            return JsonResponse({"error": "Record id is required"}, status=400)

        set_activity_summary(request, f"Update {table_name} record #{record_id}")
        merge_activity_metadata(request, resource=table_name, entryId=record_id)

        try:
            result = services.update_table_record(payload=payload)
        except services.TableNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except services.TableRecordNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to update drone table record",
                error_message="Failed to update record",
            )

        if result.previous_row is not None:
            set_activity_previous_state(request, result.previous_row)
        if result.updated_row is not None:
            set_activity_new_state(request, result.updated_row)

        return JsonResponse({"success": True})


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopInstantInformView(DroneAuthenticatedView):
    """라인 대시보드에서 호출하는 Drone SOP 단건 즉시인폼 체크 요청."""

    permission_classes: tuple = ()

    @staticmethod
    def _resolve_status(result: services.DroneSopInstantInformResult) -> str:
        """즉시 인폼 결과를 상태 문자열로 변환합니다."""

        return "already_informed" if result.already_informed else "queued"

    def post(self, request: HttpRequest, sop_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """Drone SOP 단건 즉시인폼 체크 요청을 처리합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/123/instant-inform
            예시 바디: {"comment":"추가 코멘트"}

        반환:
            예시 응답: 200 {"status": "queued", "queued": true, "alreadyInformed": false, "updated": {...}}

        부작용:
            즉시인폼 체크는 배치 실행 시 Jira 생성으로 이어집니다.

        오류:
            400: 입력 검증 오류
            401: 비인증
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 comment만 사용하며 camelCase만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱 및 comment 검증
        # -----------------------------------------------------------------------------
        payload, payload_error = parse_json_body_or_error_when_present(request)
        if payload_error is not None:
            return payload_error
        try:
            comment = parse_optional_comment(payload)
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        # -----------------------------------------------------------------------------
        # 3) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Instant inform drone_sop #{sop_id}")
        merge_activity_metadata(request, resource="drone_sop", action="instant_inform", sop_id=sop_id)
        if comment is not None:
            merge_activity_metadata(request, comment_length=len(comment))

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        def _run() -> JsonResponse:
            result = services.enqueue_drone_sop_jira_instant_inform(sop_id=sop_id, comment=comment)
            status = self._resolve_status(result)

            set_activity_new_state(
                request,
                {
                    "status": status,
                    "already_informed": result.already_informed,
                    "queued": result.queued,
                    "jira_key": result.jira_key,
                },
            )

            payload = {
                "status": status,
                "alreadyInformed": result.already_informed,
                "queued": result.queued,
                "jiraKey": result.jira_key,
                "updated": result.updated_fields,
            }
            return JsonResponse(payload, status=200)

        return self._execute_user_action(
            on_success=_run,
            log_message="Drone SOP instant inform failed",
            error_message="Drone SOP instant inform failed",
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopRetryChannelView(DroneAuthenticatedView):
    """라인 대시보드에서 호출하는 Drone SOP 단건 채널 재시도 요청."""

    permission_classes: tuple = ()

    @staticmethod
    def _resolve_status(result: services.DroneSopRetryChannelResult) -> str:
        """채널 재시도 결과를 상태 문자열로 변환합니다."""

        if result.queued:
            return "queued"
        if result.already_sent:
            return "already_sent"
        return "already_pending"

    def post(self, request: HttpRequest, sop_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """Drone SOP 단건 채널 재시도 요청을 처리합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/123/retry-channel
            예시 바디: {"channel":"jira"}

        반환:
            예시 응답: 200 {"status":"queued","channel":"jira","updated":{...}}

        부작용:
            실패 채널(send_*=-1)이면 해당 채널을 대기(0)로 되돌립니다.

        오류:
            400: 입력 검증 오류
            401: 비인증
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 channel만 사용하며 camelCase만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱 및 channel 검증
        # -----------------------------------------------------------------------------
        payload, payload_error = _parse_json_body_or_error(request)
        if payload_error is not None:
            return payload_error
        try:
            channel = parse_required_channel(payload)
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        # -----------------------------------------------------------------------------
        # 3) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Retry drone_sop #{sop_id} channel={channel}")
        merge_activity_metadata(request, resource="drone_sop", action="retry_channel", sop_id=sop_id, channel=channel)

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        def _run() -> JsonResponse:
            result = services.retry_drone_sop_channel(sop_id=sop_id, channel=channel)
            status = self._resolve_status(result)

            set_activity_new_state(
                request,
                {
                    "status": status,
                    "channel": result.channel,
                    "queued": result.queued,
                    "already_pending": result.already_pending,
                    "already_sent": result.already_sent,
                },
            )

            response_payload = {
                "status": status,
                "channel": result.channel,
                "queued": result.queued,
                "alreadyPending": result.already_pending,
                "alreadySent": result.already_sent,
                "updated": result.updated_fields,
            }
            return JsonResponse(response_payload, status=200)

        return self._execute_user_action(
            on_success=_run,
            log_message="Drone SOP retry-channel failed",
            error_message="Drone SOP retry-channel failed",
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopPop3IngestTriggerView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 Drone SOP POP3 수집 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """POP3 수집 트리거를 실행합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/ingest/pop3/trigger
            헤더 예시: Authorization: Bearer <token>

        반환:
            예시 응답: 200 {"matched": 1, "upserted": 1, "deleted": 0, "pruned": 0, "skipped": false}

        부작용:
            POP3 수집 및 DB upsert가 발생합니다.

        오류:
            401: 토큰 인증 실패
            400: 입력 검증 오류
            500: 서버 오류

        snake_case/camelCase 호환:
            입력 파라미터는 없습니다.
        """
        return self._execute_airflow_pipeline(
            request,
            summary="Trigger drone_sop POP3 ingest",
            pipeline="pop3_ingest",
            on_success=lambda: _respond_pop3_ingest_result(
                request,
                result=services.run_drone_sop_pop3_ingest_from_env(),
            ),
            log_message="Failed to trigger drone SOP POP3 ingest",
            error_message="Drone SOP POP3 ingest failed",
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopPipelinePrecheckView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 통합 Drone SOP 파이프라인 precheck 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """통합 파이프라인 전송 대상 존재 여부를 반환합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/precheck
            헤더 예시: Authorization: Bearer <token>

        반환:
            예시 응답: 200 {"hasCandidates": true}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            401: 토큰 인증 실패
            500: 서버 오류

        snake_case/camelCase 호환:
            입력 파라미터는 없습니다.
        """
        return self._execute_airflow_pipeline(
            request,
            summary="Precheck drone_sop pipeline candidates",
            pipeline="pipeline_precheck",
            on_success=lambda: _respond_precheck_has_candidates(
                request,
                has_candidates=services.has_drone_sop_pipeline_candidates(),
            ),
            log_message="Failed to precheck drone SOP pipeline candidates",
            error_message="Drone SOP pipeline precheck failed",
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopPipelineTriggerView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 통합 Drone SOP 파이프라인 실행 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """통합 Drone SOP 파이프라인 실행을 처리합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/trigger
            헤더 예시: Authorization: Bearer <token>
            예시 바디: {"limit":100}

        반환:
            예시 응답: 200 {"candidates": 10, "jiraCreated": 9, "messengerSent": 9, "mailSent": 9}

        부작용:
            Jira/메신저/메일 전송 및 drone_sop 업데이트가 발생합니다.

        오류:
            401: 토큰 인증 실패
            400: limit 검증 오류
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 limit만 사용하며 camelCase만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) Airflow 토큰 검증
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_airflow(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) limit 파라미터 파싱
        # -----------------------------------------------------------------------------
        payload, payload_error = parse_json_body_or_error_when_present(request)
        if payload_error is not None:
            return payload_error
        try:
            limit = parse_limit_param(body_value=payload.get("limit"), query_value=request.GET.get("limit"))
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        return self._execute_airflow_pipeline(
            request,
            summary="Trigger drone_sop pipeline create",
            pipeline="pipeline_create",
            limit=limit,
            authorize=False,
            on_success=lambda: _respond_pipeline_trigger_result(
                request,
                result=services.run_drone_sop_pipeline_from_env(limit=limit),
            ),
            log_message="Failed to trigger drone SOP pipeline create",
            error_message="Drone SOP pipeline create failed",
        )


__all__ = [
    "DroneEarlyInformView",
    "DroneSopInstantInformView",
    "DroneSopPipelinePrecheckView",
    "DroneSopPipelineTriggerView",
    "DroneSopPop3IngestTriggerView",
    "DroneTableUpdateView",
    "DroneTablesView",
    "LineHistoryView",
    "LineIdListView",
]
