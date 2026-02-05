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


@method_decorator(csrf_exempt, name="dispatch")
class DroneEarlyInformView(APIView):
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
        auth_response = _ensure_authenticated(request)
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
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

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
        user = getattr(request, "user", None)
        knox_id = None
        if user and getattr(user, "is_authenticated", False):
            knox_id = getattr(user, "knox_id", None)
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
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) id 검증
        # -----------------------------------------------------------------------------
        entry_id = payload.get("id")
        if not isinstance(entry_id, int):
            try:
                entry_id = int(entry_id)
            except (TypeError, ValueError):
                return JsonResponse({"error": "A valid id is required"}, status=400)
        if entry_id <= 0:
            return JsonResponse({"error": "A valid id is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 4) 액티비티 로그 및 업데이트 필드 수집
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Update drone_early_inform entry #{entry_id}")
        merge_activity_metadata(request, resource=self.TABLE_NAME, entryId=entry_id)

        updates: dict[str, Any] = {}
        user = getattr(request, "user", None)
        knox_id = None
        if user and getattr(user, "is_authenticated", False):
            knox_id = getattr(user, "knox_id", None)
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
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) id 검증
        # -----------------------------------------------------------------------------
        raw_id = request.GET.get("id")
        try:
            entry_id = int(raw_id)
        except (TypeError, ValueError):
            return JsonResponse({"error": "A valid id is required"}, status=400)
        if entry_id <= 0:
            return JsonResponse({"error": "A valid id is required"}, status=400)

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
    def _sanitize_line_id(value: Any) -> Optional[str]:
        """lineId 값을 정규화합니다.

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
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed if trimmed and len(trimmed) <= MAX_FIELD_LENGTH else None

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
        if isinstance(value, str):
            trimmed = value.strip()
        elif value is None:
            trimmed = ""
        else:
            trimmed = str(value).strip()
        # -----------------------------------------------------------------------------
        # 2) 필수/길이 검증
        # -----------------------------------------------------------------------------
        if not trimmed:
            return None
        return trimmed if len(trimmed) <= MAX_FIELD_LENGTH else None

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
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed if trimmed and len(trimmed) <= MAX_FIELD_LENGTH else None


@method_decorator(csrf_exempt, name="dispatch")
class DroneJiraKeyView(APIView):
    """user_sdwt_prod 단위 Jira 템플릿/프로젝트 키 조회/갱신 엔드포인트입니다."""

    MAX_PROJECT_KEY_LENGTH = 64
    MAX_TEMPLATE_KEY_LENGTH = 50

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
        - userSdwtProd / user_sdwt_prod (키 매핑)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) userSdwtProd 검증
        # -----------------------------------------------------------------------------
        user_sdwt_prod = (request.GET.get("userSdwtProd") or request.GET.get("user_sdwt_prod") or "").strip()
        if not user_sdwt_prod:
            return JsonResponse({"error": "userSdwtProd is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) userSdwtProd 존재 확인
        # -----------------------------------------------------------------------------
        if not selectors.affiliation_exists_for_user_sdwt_prod(user_sdwt_prod=user_sdwt_prod):
            return JsonResponse({"error": "userSdwtProd not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 4) Jira 키 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        entry = selectors.get_drone_sop_jira_user_template(user_sdwt_prod=user_sdwt_prod)
        jira_key = entry.jira_key if entry and entry.jira_key else None
        template_key = entry.template_key if entry and entry.template_key else None
        return JsonResponse(
            {
                "userSdwtProd": user_sdwt_prod,
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
        - userSdwtProd / user_sdwt_prod (키 매핑)
        - jiraKey / jira_key (키 매핑)
        - templateKey / template_key (키 매핑)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response
        if not getattr(request.user, "is_superuser", False):
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) userSdwtProd 추출 및 검증
        # -----------------------------------------------------------------------------
        user_sdwt_prod = (payload.get("userSdwtProd") or payload.get("user_sdwt_prod") or "").strip()
        if not user_sdwt_prod:
            return JsonResponse({"error": "userSdwtProd is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 4) userSdwtProd 존재 확인
        # -----------------------------------------------------------------------------
        if not selectors.affiliation_exists_for_user_sdwt_prod(user_sdwt_prod=user_sdwt_prod):
            return JsonResponse({"error": "userSdwtProd not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 5) jiraKey/templateKey 추출 및 길이 검증
        # -----------------------------------------------------------------------------
        jira_key_provided = "jiraKey" in payload or "jira_key" in payload
        template_key_provided = "templateKey" in payload or "template_key" in payload
        if not (jira_key_provided or template_key_provided):
            return JsonResponse({"error": "jiraKey or templateKey is required"}, status=400)

        jira_key_value = payload.get("jiraKey") if "jiraKey" in payload else payload.get("jira_key")
        jira_key = jira_key_value.strip() if isinstance(jira_key_value, str) else ""
        if jira_key and len(jira_key) > self.MAX_PROJECT_KEY_LENGTH:
            return JsonResponse(
                {"error": f"jiraKey must be {self.MAX_PROJECT_KEY_LENGTH} characters or fewer"},
                status=400,
            )

        template_key_value = (
            payload.get("templateKey") if "templateKey" in payload else payload.get("template_key")
        )
        template_key = template_key_value.strip() if isinstance(template_key_value, str) else ""
        if template_key and len(template_key) > self.MAX_TEMPLATE_KEY_LENGTH:
            return JsonResponse(
                {"error": f"templateKey must be {self.MAX_TEMPLATE_KEY_LENGTH} characters or fewer"},
                status=400,
            )

        # -----------------------------------------------------------------------------
        # 6) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload_kwargs: dict[str, object] = {"user_sdwt_prod": user_sdwt_prod}
        if jira_key_provided:
            payload_kwargs["jira_key"] = jira_key or None
        if template_key_provided:
            payload_kwargs["template_key"] = template_key or None

        template, updated = services.upsert_drone_sop_jira_user_template(**payload_kwargs)
        return JsonResponse(
            {
                "userSdwtProd": user_sdwt_prod,
                "jiraKey": template.jira_key,
                "templateKey": template.template_key,
                "updated": updated,
            }
        )


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
class DroneSopInstantInformView(APIView):
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
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱 및 comment 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request) or {}
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
class DroneSopPop3IngestTriggerView(APIView):
    """외부 Airflow에서 호출하는 Drone SOP POP3 수집 트리거."""

    permission_classes: tuple = ()

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
        auth_response = ensure_airflow_token(request, require_bearer=True)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        set_activity_summary(request, "Trigger drone_sop POP3 ingest")
        merge_activity_metadata(request, resource="drone_sop", pipeline="pop3_ingest")

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            result = services.run_drone_sop_pop3_ingest_from_env()
            set_activity_new_state(
                request,
                {
                    "matched": result.matched_mails,
                    "upserted": result.upserted_rows,
                    "deleted": result.deleted_mails,
                    "pruned": result.pruned_rows,
                    "skipped": result.skipped,
                    "skip_reason": result.skip_reason,
                },
            )
            return JsonResponse(
                {
                    "matched": result.matched_mails,
                    "upserted": result.upserted_rows,
                    "deleted": result.deleted_mails,
                    "pruned": result.pruned_rows,
                    "skipped": result.skipped,
                    "skipReason": result.skip_reason,
                }
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Failed to trigger drone SOP POP3 ingest")
            return JsonResponse({"error": "Drone SOP POP3 ingest failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopJiraPrecheckView(APIView):
    """외부 Airflow에서 호출하는 Drone SOP Jira 후보 사전 확인 트리거."""

    permission_classes: tuple = ()

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
        auth_response = ensure_airflow_token(request, require_bearer=True)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        set_activity_summary(request, "Precheck drone_sop Jira candidates")
        merge_activity_metadata(request, resource="drone_sop", pipeline="jira_precheck")

        # -----------------------------------------------------------------------------
        # 3) 후보 존재 여부 조회 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            has_candidates = selectors.has_drone_sop_jira_candidates()
            set_activity_new_state(request, {"has_candidates": has_candidates})
            return JsonResponse({"hasCandidates": has_candidates})
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Failed to precheck drone SOP Jira candidates")
            return JsonResponse({"error": "Drone SOP Jira precheck failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopJiraTriggerView(APIView):
    """외부 Airflow에서 호출하는 Drone SOP Jira 생성 트리거."""

    permission_classes: tuple = ()

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
        auth_response = ensure_airflow_token(request, require_bearer=True)
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
        # 3) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        set_activity_summary(request, "Trigger drone_sop Jira create")
        merge_activity_metadata(request, resource="drone_sop", pipeline="jira_create", limit=limit)

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            result = services.run_drone_sop_jira_create_from_env(limit=limit)
            set_activity_new_state(
                request,
                {
                    "candidates": result.candidates,
                    "created": result.created,
                    "updated_rows": result.updated_rows,
                    "skipped": result.skipped,
                    "skip_reason": result.skip_reason,
                },
            )
            return JsonResponse(
                {
                    "candidates": result.candidates,
                    "created": result.created,
                    "updated": result.updated_rows,
                    "skipped": result.skipped,
                    "skipReason": result.skip_reason,
                }
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            logger.exception("Failed to trigger drone SOP Jira create")
            return JsonResponse({"error": "Drone SOP Jira create failed"}, status=500)


__all__ = [
    "DroneEarlyInformView",
    "DroneSopInstantInformView",
    "DroneSopJiraPrecheckView",
    "DroneSopJiraTriggerView",
    "DroneSopPop3IngestTriggerView",
    "LineHistoryView",
    "LineIdListView",
]
