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
- 예시 요청: POST   /api/v1/line-dashboard/sop/jira/precheck

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
from typing import Any, Optional

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import MAX_FIELD_LENGTH
from api.common.services import ensure_airflow_token, parse_json_body

from api.common.services import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)

from . import selectors, services
from .serializers import serialize_early_inform_entry

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


def _parse_json_body_or_empty(request: HttpRequest) -> dict[str, Any]:
    """JSON 바디를 파싱하고 실패 시 빈 dict를 반환합니다.

    인자:
        request: Django HttpRequest 객체.

    반환:
        payload dict(실패 시 빈 dict).

    부작용:
        없음. 순수 파싱입니다.
    """

    payload = parse_json_body(request)
    return payload if isinstance(payload, dict) else {}


def _parse_limit_param(request: HttpRequest) -> tuple[int | None, JsonResponse | None]:
    """limit 파라미터를 파싱합니다.

    우선순위:
        1) JSON 바디의 limit
        2) query parameter의 limit

    인자:
        request: Django HttpRequest 객체.

    반환:
        (limit, error_response) 튜플.

    부작용:
        없음. 순수 파싱입니다.
    """

    payload = _parse_json_body_or_empty(request)
    raw_limit = payload.get("limit")
    if raw_limit is None:
        raw_limit = request.GET.get("limit")

    if raw_limit is None:
        return None, None

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return None, _json_error("limit must be an integer", status=400)

    if limit <= 0:
        return None, None

    return limit, None


def _parse_positive_int_or_error(
    value: Any,
    *,
    error_message: str = "A valid id is required",
) -> tuple[int | None, JsonResponse | None]:
    """양의 정수 값을 파싱하고 실패 시 에러 응답을 반환합니다.

    인자:
        value: 원본 입력 값.
        error_message: 파싱 실패 시 사용할 에러 메시지.

    반환:
        (parsed_value, error_response) 튜플.

    부작용:
        없음. 순수 파싱입니다.
    """

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, _json_error(error_message, status=400)
    if parsed <= 0:
        return None, _json_error(error_message, status=400)
    return parsed, None


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


def _respond_precheck_has_candidates(request: HttpRequest, *, has_candidates: bool) -> JsonResponse:
    """사전 확인(precheck) 응답을 구성합니다."""

    return _record_activity_state_and_respond(
        request,
        activity_state={"has_candidates": has_candidates},
        response_payload={"hasCandidates": has_candidates},
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


def _respond_jira_trigger_result(request: HttpRequest, *, result: Any) -> JsonResponse:
    """Jira 생성 트리거 응답을 구성합니다."""

    return _record_activity_state_and_respond(
        request,
        activity_state={
            "candidates": result.candidates,
            "created": result.created,
            "updated_rows": result.updated_rows,
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
        },
        response_payload={
            "candidates": result.candidates,
            "created": result.created,
            "updated": result.updated_rows,
            "skipped": result.skipped,
            "skipReason": result.skip_reason,
        },
    )


def _respond_inform_trigger_result(request: HttpRequest, *, result: Any) -> JsonResponse:
    """멀티 채널 전송 트리거 응답을 구성합니다."""

    return _record_activity_state_and_respond(
        request,
        activity_state={
            "candidates": result.candidates,
            "jira_created": result.jira_created,
            "jira_updated_rows": result.jira_updated_rows,
            "messenger_sent": result.messenger_sent,
            "mail_sent": result.mail_sent,
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
        },
        response_payload={
            "candidates": result.candidates,
            "jiraCreated": result.jira_created,
            "jiraUpdated": result.jira_updated_rows,
            "messengerSent": result.messenger_sent,
            "mailSent": result.mail_sent,
            "skipped": result.skipped,
            "skipReason": result.skip_reason,
        },
    )


class DroneAirflowTriggerView(APIView):
    """Airflow Bearer 토큰 인증이 필요한 트리거 뷰 베이스 클래스."""

    permission_classes: tuple = ()

    @staticmethod
    def _authorize_airflow(request: HttpRequest) -> JsonResponse | None:
        """Airflow 토큰 인증을 확인합니다."""

        return _ensure_airflow_authenticated(request)


class DroneAuthenticatedView(APIView):
    """로그인 사용자 인증이 필요한 뷰 베이스 클래스."""

    @staticmethod
    def _authorize_user(request: HttpRequest) -> JsonResponse | None:
        """사용자 인증을 확인합니다."""

        return _ensure_authenticated(request)


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
        line_id = self._sanitize_line_id(request.GET.get("lineId"))
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
            logger.exception("Failed to load drone_early_inform rows")
            return JsonResponse({"error": "Failed to load settings"}, status=500)

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
        line_id = self._sanitize_line_id(payload.get("lineId"))
        main_step = self._sanitize_main_step(payload.get("mainStep"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)
        if not main_step:
            return JsonResponse({"error": "mainStep is required"}, status=400)

        try:
            custom_end_step = self._normalize_custom_end_step(payload.get("customEndStep"))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        # -----------------------------------------------------------------------------
        # 4) updated_by 계산
        # -----------------------------------------------------------------------------
        knox_id = _resolve_knox_id(request)
        updated_by = self._sanitize_updated_by(knox_id or "system")

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
            logger.exception("Failed to create drone_early_inform row")
            return JsonResponse({"error": "Failed to create entry"}, status=500)

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
        entry_id, entry_id_error = _parse_positive_int_or_error(payload.get("id"))
        if entry_id_error is not None:
            return entry_id_error

        # -----------------------------------------------------------------------------
        # 4) 액티비티 로그 및 업데이트 필드 수집
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Update drone_early_inform entry #{entry_id}")
        merge_activity_metadata(request, resource=self.TABLE_NAME, entryId=entry_id)

        updates: dict[str, Any] = {}
        knox_id = _resolve_knox_id(request)
        updated_by = self._sanitize_updated_by(knox_id or "system")

        if "lineId" in payload:
            line_id = self._sanitize_line_id(payload.get("lineId"))
            if not line_id:
                return JsonResponse({"error": "lineId is required"}, status=400)
            updates["line_id"] = line_id

        if "mainStep" in payload:
            main_step = self._sanitize_main_step(payload.get("mainStep"))
            if not main_step:
                return JsonResponse({"error": "mainStep is required"}, status=400)
            updates["main_step"] = main_step

        if "customEndStep" in payload:
            try:
                normalized = self._normalize_custom_end_step(payload.get("customEndStep"))
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
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
            logger.exception("Failed to update drone_early_inform row")
            return JsonResponse({"error": "Failed to update entry"}, status=500)

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
        entry_id, entry_id_error = _parse_positive_int_or_error(request.GET.get("id"))
        if entry_id_error is not None:
            return entry_id_error

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
            logger.exception("Failed to delete drone_early_inform row")
            return JsonResponse({"error": "Failed to delete entry"}, status=500)

    # --------------------------------------------------------------------- #
    # 검증/정규화 유틸
    # --------------------------------------------------------------------- #
    @staticmethod
    def _sanitize_short_text(
        value: Any,
        *,
        allow_non_str: bool = False,
    ) -> Optional[str]:
        """짧은 문자열 필드를 정규화합니다.

        인자:
            value: 원본 입력 값.
            allow_non_str: 문자열이 아닐 때 str 변환 허용 여부.

        반환:
            정규화된 문자열 또는 None.

        부작용:
            없음. 순수 검증입니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 타입/길이 검증
        # -----------------------------------------------------------------------------
        if isinstance(value, str):
            trimmed = value.strip()
        elif value is None:
            trimmed = ""
        elif allow_non_str:
            trimmed = str(value).strip()
        else:
            return None
        if not trimmed:
            return None
        return trimmed if len(trimmed) <= MAX_FIELD_LENGTH else None

    @staticmethod
    def _sanitize_line_id(value: Any) -> Optional[str]:
        """lineId 값을 정규화합니다."""

        return DroneEarlyInformView._sanitize_short_text(value, allow_non_str=False)

    @staticmethod
    def _sanitize_main_step(value: Any) -> Optional[str]:
        """mainStep 값을 정규화합니다.

        인자:
            value: 원본 입력 값.

        반환:
            정규화된 문자열 또는 None.

        부작용:
            없음. 순수 검증입니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 문자열화 및 공백 제거
        # -----------------------------------------------------------------------------
        return DroneEarlyInformView._sanitize_short_text(value, allow_non_str=True)

    @staticmethod
    def _normalize_custom_end_step(value: Any) -> Optional[str]:
        """customEndStep 값을 정규화합니다.

        인자:
            value: 원본 입력 값.

        반환:
            정규화된 문자열 또는 None.

        부작용:
            없음. 순수 검증입니다.

        오류:
            길이 제한 초과 시 ValueError를 발생시킵니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 문자열화 및 빈값 처리
        # -----------------------------------------------------------------------------
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
        else:
            trimmed = str(value).strip()
        if not trimmed:
            return None
        # -----------------------------------------------------------------------------
        # 2) 길이 제한 검증
        # -----------------------------------------------------------------------------
        if len(trimmed) > MAX_FIELD_LENGTH:
            raise ValueError("customEndStep must be 50 characters or fewer")
        return trimmed

    @staticmethod
    def _sanitize_updated_by(value: Any) -> Optional[str]:
        """updated_by 값을 정규화합니다.

        인자:
            value: 원본 입력 값.

        반환:
            정규화된 문자열 또는 None.

        부작용:
            없음. 순수 검증입니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 타입/길이 검증
        # -----------------------------------------------------------------------------
        return DroneEarlyInformView._sanitize_short_text(value, allow_non_str=False)


@method_decorator(csrf_exempt, name="dispatch")
class DroneJiraKeyView(DroneAuthenticatedView):
    """user_sdwt_prod 단위 Jira 템플릿/프로젝트 키 조회/갱신 엔드포인트입니다."""

    MAX_PROJECT_KEY_LENGTH = 64
    MAX_TEMPLATE_KEY_LENGTH = 50

    @staticmethod
    def _ensure_valid_target_user_sdwt_prod(target_user_sdwt_prod: str) -> JsonResponse | None:
        """target_user_sdwt_prod 유효성(필수/존재)을 확인합니다."""

        if not target_user_sdwt_prod:
            return JsonResponse({"error": "userSdwtProd is required"}, status=400)
        if not selectors.affiliation_exists_for_user_sdwt_prod(user_sdwt_prod=target_user_sdwt_prod):
            return JsonResponse({"error": "userSdwtProd not found"}, status=404)
        return None

    @staticmethod
    def _extract_payload_alias(
        payload: dict[str, Any],
        *,
        camel_key: str,
        snake_key: str,
    ) -> tuple[bool, Any]:
        """camel/snake 키 우선순위로 값을 추출합니다.

        반환:
            (provided, raw_value) 튜플.
            camel_key가 있으면 camel 우선, 없으면 snake를 사용합니다.
        """

        if camel_key in payload:
            return True, payload.get(camel_key)
        if snake_key in payload:
            return True, payload.get(snake_key)
        return False, None

    @staticmethod
    def _resolve_target_user_sdwt_prod_for_get(request: HttpRequest) -> str:
        """GET 쿼리에서 userSdwtProd/user_sdwt_prod를 읽어 정규화합니다."""

        raw_camel = request.GET.get("userSdwtProd")
        if isinstance(raw_camel, str) and raw_camel.strip():
            return raw_camel.strip()

        raw_snake = request.GET.get("user_sdwt_prod")
        if isinstance(raw_snake, str):
            return raw_snake.strip()
        return ""

    @staticmethod
    def _resolve_target_user_sdwt_prod_for_post(payload: dict[str, Any]) -> str:
        """POST 본문에서 userSdwtProd/user_sdwt_prod를 읽어 정규화합니다."""

        provided, raw_value = DroneJiraKeyView._extract_payload_alias(
            payload,
            camel_key="userSdwtProd",
            snake_key="user_sdwt_prod",
        )
        if not provided:
            return ""
        return raw_value.strip() if isinstance(raw_value, str) else ""

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
        - 요청 쿼리는 userSdwtProd/user_sdwt_prod를 모두 지원합니다.
        - 두 키가 동시에 존재하면 userSdwtProd(camelCase)를 우선합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) userSdwtProd 검증
        # -----------------------------------------------------------------------------
        target_user_sdwt_prod = self._resolve_target_user_sdwt_prod_for_get(request)
        target_user_sdwt_error = self._ensure_valid_target_user_sdwt_prod(target_user_sdwt_prod)
        if target_user_sdwt_error is not None:
            return target_user_sdwt_error

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
                "jiraKey": jira_key,
                "templateKey": template_key,
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
        - 404: userSdwtProd 없음

        예시 요청:
        - 예시 요청: POST /api/v1/line-dashboard/jira-keys
          요청 바디 예시: {"userSdwtProd":"SDWT_A","jiraKey":"ABC","templateKey":"line_a"}

        snake/camel 호환:
        - 요청 본문은 userSdwtProd/user_sdwt_prod를 모두 지원합니다.
        - jiraKey/jira_key, templateKey/template_key를 모두 지원합니다.
        - 동일 의미의 camel/snake 키가 동시에 있으면 camelCase를 우선합니다.
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
        # 3) userSdwtProd 추출 및 검증
        # -----------------------------------------------------------------------------
        target_user_sdwt_prod = self._resolve_target_user_sdwt_prod_for_post(payload)
        target_user_sdwt_error = self._ensure_valid_target_user_sdwt_prod(target_user_sdwt_prod)
        if target_user_sdwt_error is not None:
            return target_user_sdwt_error

        # -----------------------------------------------------------------------------
        # 5) jiraKey/templateKey 추출 및 길이 검증
        # -----------------------------------------------------------------------------
        jira_key_provided, jira_key_raw = self._extract_payload_alias(
            payload,
            camel_key="jiraKey",
            snake_key="jira_key",
        )
        template_key_provided, template_key_raw = self._extract_payload_alias(
            payload,
            camel_key="templateKey",
            snake_key="template_key",
        )
        if not (jira_key_provided or template_key_provided):
            return JsonResponse({"error": "jiraKey or templateKey is required"}, status=400)
        if jira_key_provided and jira_key_raw is not None and not isinstance(jira_key_raw, str):
            return JsonResponse({"error": "jiraKey must be a string or null"}, status=400)
        if template_key_provided and template_key_raw is not None and not isinstance(
            template_key_raw, str
        ):
            return JsonResponse({"error": "templateKey must be a string or null"}, status=400)

        jira_key = jira_key_raw.strip() if isinstance(jira_key_raw, str) else ""
        if jira_key and len(jira_key) > self.MAX_PROJECT_KEY_LENGTH:
            return JsonResponse(
                {"error": f"jiraKey must be {self.MAX_PROJECT_KEY_LENGTH} characters or fewer"},
                status=400,
            )

        template_key = template_key_raw.strip() if isinstance(template_key_raw, str) else ""
        if template_key and len(template_key) > self.MAX_TEMPLATE_KEY_LENGTH:
            return JsonResponse(
                {"error": f"templateKey must be {self.MAX_TEMPLATE_KEY_LENGTH} characters or fewer"},
                status=400,
            )

        # -----------------------------------------------------------------------------
        # 6) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload_kwargs: dict[str, object] = {"target_user_sdwt_prod": target_user_sdwt_prod}
        if jira_key_provided:
            payload_kwargs["jira_key"] = jira_key or None
        if template_key_provided:
            payload_kwargs["jira_template_key"] = template_key or None

        template, updated = services.upsert_drone_sop_user_sdwt_channel(**payload_kwargs)
        return JsonResponse(
            {
                "userSdwtProd": target_user_sdwt_prod,
                "jiraKey": template.jira_key,
                "templateKey": template.jira_template_key,
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
            logger.exception("Failed to load Jira user SDWT prods")
            return JsonResponse({"error": "Failed to load Jira user SDWT prods"}, status=500)


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
            logger.exception("Failed to load history data")
            return JsonResponse({"error": "Failed to load history data"}, status=500)


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
            logger.exception("Failed to load distinct line ids")
            return JsonResponse({"error": "Failed to load line options"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopInstantInformView(DroneAuthenticatedView):
    """라인 대시보드에서 호출하는 Drone SOP 단건 즉시인폼 체크 요청."""

    permission_classes: tuple = ()

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
        payload = _parse_json_body_or_empty(request)
        raw_comment = payload.get("comment")
        if raw_comment is not None and not isinstance(raw_comment, str):
            return JsonResponse({"error": "comment must be a string"}, status=400)
        comment = raw_comment.strip() if isinstance(raw_comment, str) else None

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
        try:
            result = services.enqueue_drone_sop_jira_instant_inform(sop_id=sop_id, comment=comment)
            if result.already_informed:
                status = "already_informed"
            else:
                status = "queued"

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
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Drone SOP instant inform failed")
            return JsonResponse({"error": "Drone SOP instant inform failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopRetryChannelView(DroneAuthenticatedView):
    """라인 대시보드에서 호출하는 Drone SOP 단건 채널 재시도 요청."""

    permission_classes: tuple = ()

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
        payload = _parse_json_body_or_empty(request)
        raw_channel = payload.get("channel")
        if not isinstance(raw_channel, str):
            return JsonResponse({"error": "channel must be a string"}, status=400)
        channel = raw_channel.strip().lower()
        if not channel:
            return JsonResponse({"error": "channel is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Retry drone_sop #{sop_id} channel={channel}")
        merge_activity_metadata(request, resource="drone_sop", action="retry_channel", sop_id=sop_id, channel=channel)

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            result = services.retry_drone_sop_channel(sop_id=sop_id, channel=channel)
            if result.queued:
                status = "queued"
            elif result.already_sent:
                status = "already_sent"
            else:
                status = "already_pending"

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
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Drone SOP retry-channel failed")
            return JsonResponse({"error": "Drone SOP retry-channel failed"}, status=500)


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
        # -----------------------------------------------------------------------------
        # 1) Airflow 토큰 검증
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_airflow(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        _record_drone_sop_pipeline_activity(
            request,
            summary="Trigger drone_sop POP3 ingest",
            pipeline="pop3_ingest",
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            result = services.run_drone_sop_pop3_ingest_from_env()
            return _respond_pop3_ingest_result(request, result=result)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Failed to trigger drone SOP POP3 ingest")
            return JsonResponse({"error": "Drone SOP POP3 ingest failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopJiraPrecheckView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 Drone SOP Jira 후보 사전 확인 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """Jira 생성 대상 존재 여부를 반환합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/jira/precheck
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
        # -----------------------------------------------------------------------------
        # 1) Airflow 토큰 검증
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_airflow(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        _record_drone_sop_pipeline_activity(
            request,
            summary="Precheck drone_sop Jira candidates",
            pipeline="jira_precheck",
        )

        # -----------------------------------------------------------------------------
        # 3) 후보 존재 여부 조회 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            has_candidates = selectors.has_drone_sop_jira_candidates()
            return _respond_precheck_has_candidates(request, has_candidates=has_candidates)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Failed to precheck drone SOP Jira candidates")
            return JsonResponse({"error": "Drone SOP Jira precheck failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopJiraTriggerView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 Drone SOP Jira 생성 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """Jira 생성 트리거를 실행합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/jira/trigger
            헤더 예시: Authorization: Bearer <token>
            예시 바디: {"limit": 100}

        반환:
            예시 응답: 200 {"candidates": 10, "created": 9, "updated": 9, "skipped": false}

        부작용:
            Jira 생성 및 drone_sop 업데이트가 발생합니다.

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
        limit, error_response = _parse_limit_param(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 3) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        _record_drone_sop_pipeline_activity(
            request,
            summary="Trigger drone_sop Jira create",
            pipeline="jira_create",
            limit=limit,
        )

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            result = services.run_drone_sop_jira_create_from_env(limit=limit)
            return _respond_jira_trigger_result(request, result=result)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Failed to trigger drone SOP Jira create")
            return JsonResponse({"error": "Drone SOP Jira create failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopInformPrecheckView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 Drone SOP 멀티 채널 후보 사전 확인 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """멀티 채널 전송 대상 존재 여부를 반환합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/inform/precheck
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
        # -----------------------------------------------------------------------------
        # 1) Airflow 토큰 검증
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_airflow(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        _record_drone_sop_pipeline_activity(
            request,
            summary="Precheck drone_sop inform candidates",
            pipeline="inform_precheck",
        )

        # -----------------------------------------------------------------------------
        # 3) 후보 존재 여부 조회 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            has_candidates = selectors.has_drone_sop_inform_candidates()
            return _respond_precheck_has_candidates(request, has_candidates=has_candidates)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Failed to precheck drone SOP inform candidates")
            return JsonResponse({"error": "Drone SOP inform precheck failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopInformTriggerView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 Drone SOP 멀티 채널 전송 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """멀티 채널 전송 트리거를 실행합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/inform/trigger
            헤더 예시: Authorization: Bearer <token>
            예시 바디: {"limit": 100}

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
        limit, error_response = _parse_limit_param(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 3) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        _record_drone_sop_pipeline_activity(
            request,
            summary="Trigger drone_sop inform create",
            pipeline="inform_create",
            limit=limit,
        )

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            result = services.run_drone_sop_inform_from_env(limit=limit)
            return _respond_inform_trigger_result(request, result=result)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Failed to trigger drone SOP inform create")
            return JsonResponse({"error": "Drone SOP inform create failed"}, status=500)


__all__ = [
    "DroneEarlyInformView",
    "DroneSopInstantInformView",
    "DroneSopJiraPrecheckView",
    "DroneSopJiraTriggerView",
    "DroneSopInformPrecheckView",
    "DroneSopInformTriggerView",
    "DroneSopPop3IngestTriggerView",
    "LineHistoryView",
    "LineIdListView",
]
