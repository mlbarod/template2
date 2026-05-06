# =============================================================================
# 모듈 설명: 소속 관련 서비스 로직을 제공합니다.
# - 주요 대상: get_affiliation_overview, ensure_affiliation_option, submit_affiliation_reconfirm_response
# - 불변 조건: 모든 쓰기 작업은 서비스 레이어에서 수행합니다.
# =============================================================================

"""소속 관련 서비스 로직 모음.

- 주요 대상: 소속 개요, 소속 옵션 보장, 재확인 처리, 옵션 페이로드
- 주요 엔드포인트/클래스: get_affiliation_overview 등
- 가정/불변 조건: 모든 쓰기 작업은 서비스 레이어에서 수행됨
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import Affiliation, UserCurrentAffiliation
from .. import selectors
from .access import _current_access_list
from .affiliation_requests import request_affiliation_change
from .utils import _same_user_sdwt_prod


def _update_affiliation_option_values(
    *,
    option: Affiliation,
    department: str,
    line: str,
    user_sdwt_prod: str,
) -> Affiliation:
    """소속 옵션의 표시 값을 필요한 경우에만 갱신합니다."""

    changed_fields: list[str] = []
    if option.department != department:
        option.department = department
        changed_fields.append("department")
    if option.line != line:
        option.line = line
        changed_fields.append("line")
    if option.user_sdwt_prod != user_sdwt_prod:
        option.user_sdwt_prod = user_sdwt_prod
        changed_fields.append("user_sdwt_prod")
    if changed_fields:
        option.save(update_fields=changed_fields)
    return option


def get_affiliation_overview(*, user: Any, timezone_name: str) -> dict[str, object]:
    """AccountAffiliationView(GET) 응답 payload를 구성합니다.

    입력:
    - user: Django 사용자 객체
    - timezone_name: 시간대 이름

    반환:
    - dict[str, object]: 소속 개요 payload

    부작용:
    - 없음

    오류:
    - 없음
    """

    access_list = _current_access_list(user)
    manageable = [entry["userSdwtProd"] for entry in access_list if entry["role"] == "manager"]
    options = selectors.list_affiliation_options()
    current_values = selectors.get_current_affiliation_values(user=user)
    current_department = current_values.get("department") or getattr(user, "department", None)

    knox_id = (getattr(user, "knox_id", None) or "").strip()
    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(knox_id=knox_id) if knox_id else None
    snapshot_user_sdwt_prod = (snapshot.predicted_user_sdwt_prod or "").strip() if snapshot else None
    snapshot_department = (snapshot.department or "").strip() if snapshot else None
    if not snapshot_department:
        snapshot_department = (getattr(user, "department", None) or "").strip() or None

    return {
        "currentUserSdwtProd": current_values.get("user_sdwt_prod"),
        "currentDepartment": current_department,
        "currentLine": current_values.get("line"),
        "timezone": timezone_name,
        "accessibleUserSdwtProds": access_list,
        "manageableUserSdwtProds": manageable,
        "affiliationOptions": options,
        "snapshotUserSdwtProd": snapshot_user_sdwt_prod or None,
        "snapshotDepartment": snapshot_department or None,
    }


def get_affiliation_reconfirm_status(*, user: Any) -> dict[str, object]:
    """사용자의 소속 재확인 상태와 예측값을 반환합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - dict[str, object]: 재확인 상태/예측 소속 정보

    부작용:
    - 없음

    오류:
    - 없음
    """

    if not user:
        return {"requiresReconfirm": False, "predictedUserSdwtProd": None, "currentUserSdwtProd": None}

    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(
        knox_id=getattr(user, "knox_id", "") or ""
    )
    predicted = snapshot.predicted_user_sdwt_prod if snapshot else None
    current_values = selectors.get_current_affiliation_values(user=user)
    return {
        "requiresReconfirm": bool(current_values.get("requires_reconfirm", False)),
        "predictedUserSdwtProd": predicted,
        "currentUserSdwtProd": current_values.get("user_sdwt_prod"),
    }


def auto_approve_affiliation_from_snapshot(
    *,
    user: Any,
    timezone_name: str,
) -> Tuple[dict[str, object], int] | None:
    """신규 사용자 첫 로그인 시 외부 예측 소속으로 자동 승인/적용합니다.

    입력:
    - user: Django 사용자 객체
    - timezone_name: 시간대 이름

    반환:
    - Tuple[dict[str, object], int] | None: 승인 결과 또는 None(미적용)

    부작용:
    - UserSdwtProdChange 생성 및 승인/적용
    - 사용자 소속 필드 업데이트

    오류:
    - 없음(조건 불충족 시 None 반환)
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 조건 확인
    # -----------------------------------------------------------------------------
    if not user:
        return None

    current_user_sdwt = (selectors.get_current_user_sdwt_prod(user=user) or "").strip()
    if current_user_sdwt:
        return None

    knox_id = (getattr(user, "knox_id", None) or "").strip()
    if not knox_id:
        return None

    if selectors.get_pending_user_sdwt_prod_change(user=user) is not None:
        return None

    # -----------------------------------------------------------------------------
    # 2) 외부 예측 소속 확인
    # -----------------------------------------------------------------------------
    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(knox_id=knox_id)
    if snapshot is None:
        return None

    predicted = (snapshot.predicted_user_sdwt_prod or "").strip()
    if not predicted:
        return None

    # -----------------------------------------------------------------------------
    # 3) 소속 옵션 확인
    # -----------------------------------------------------------------------------
    option = selectors.get_affiliation_option_by_user_sdwt_prod(user_sdwt_prod=predicted)
    if option is None:
        return None

    # -----------------------------------------------------------------------------
    # 4) 변경 요청 생성(예측값 일치 시 자동 적용)
    # -----------------------------------------------------------------------------
    return request_affiliation_change(
        user=user,
        option=option,
        to_user_sdwt_prod=predicted,
        effective_from=timezone.now(),
        timezone_name=timezone_name,
    )


def ensure_affiliation_option(
    *,
    department: str,
    line: str,
    user_sdwt_prod: str,
) -> Affiliation:
    """소속 옵션을 생성하거나 기존 행을 갱신합니다.

    입력:
    - department: 부서 식별자
    - line: 라인 식별자
    - user_sdwt_prod: 소속 그룹 값
    반환:
    - Affiliation: 소속 옵션 객체

    부작용:
    - Affiliation 생성 또는 갱신

    오류:
    - ValueError: 필수 입력 누락
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화 및 검증
    # -----------------------------------------------------------------------------
    normalized_department = (department or "").strip()
    normalized_line = (line or "").strip()
    normalized_user_sdwt = (user_sdwt_prod or "").strip()
    if not normalized_department or not normalized_line or not normalized_user_sdwt:
        raise ValueError("department/line/user_sdwt_prod is required")

    # -----------------------------------------------------------------------------
    # 2) 옵션 조회 및 생성/갱신 처리
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        option = selectors.get_affiliation_option_by_user_sdwt_prod(
            user_sdwt_prod=normalized_user_sdwt,
        )
        if option is not None:
            option = _update_affiliation_option_values(
                option=option,
                department=normalized_department,
                line=normalized_line,
                user_sdwt_prod=normalized_user_sdwt,
            )
        else:
            try:
                with transaction.atomic():
                    option = Affiliation.objects.create(
                        department=normalized_department,
                        line=normalized_line,
                        user_sdwt_prod=normalized_user_sdwt,
                    )
            except IntegrityError:
                option = selectors.get_affiliation_option_by_user_sdwt_prod(
                    user_sdwt_prod=normalized_user_sdwt,
                )
                if option is None:
                    raise
                option = _update_affiliation_option_values(
                    option=option,
                    department=normalized_department,
                    line=normalized_line,
                    user_sdwt_prod=normalized_user_sdwt,
                )

        return option


def set_current_affiliation_for_user(
    *,
    user: Any,
    department: str,
    line: str,
    user_sdwt_prod: str,
    source: str | None = None,
) -> None:
    """사용자의 현재 앱 소속을 account 도메인 규칙으로 설정합니다.

    입력:
    - user: 대상 사용자
    - department: 부서 식별자
    - line: 라인 식별자
    - user_sdwt_prod: 소속 그룹 값
    - source: 소속 출처(없으면 USER_SELECTED)

    반환:
    - 없음

    부작용:
    - Affiliation 옵션 생성/갱신
    - UserCurrentAffiliation 생성/갱신

    오류:
    - ValueError: 필수 입력 누락
    """

    if user is None:
        raise ValueError("user is required")

    option = ensure_affiliation_option(
        department=department,
        line=line,
        user_sdwt_prod=user_sdwt_prod,
    )
    normalized_source = (source or "").strip() or UserCurrentAffiliation.Sources.USER_SELECTED
    with transaction.atomic():
        UserCurrentAffiliation.objects.update_or_create(
            user=user,
            defaults={
                "affiliation": option,
                "source": normalized_source,
                "requires_reconfirm": False,
            },
        )


def submit_affiliation_reconfirm_response(
    *,
    user: Any,
    accepted: bool,
    department: str | None,
    line: str | None,
    user_sdwt_prod: str | None,
    timezone_name: str,
) -> Tuple[dict[str, object], int]:
    """재확인 응답을 처리해 소속 변경을 적용하거나 승인 대기를 생성하거나 유지합니다.

    입력:
    - user: Django 사용자 객체
    - accepted: 재확인 수락 여부
    - department/line/user_sdwt_prod: 선택된 소속 정보
    - timezone_name: 시간대 이름

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - 예측값 일치 시 UserSdwtProdChange 생성/즉시 적용
    - 불일치 선택 시 UserSdwtProdChange 승인 대기 생성
    - 사용자 재확인 플래그 해제(기존 유지/적용/승인 대기 생성 성공 시)

    오류:
    - 400: 입력 오류
    - 401: 미인증
    - 409: 재확인 대상 아님
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 인증 확인
    # -----------------------------------------------------------------------------
    if not user:
        return {"error": "unauthorized"}, 401

    # -----------------------------------------------------------------------------
    # 2) 재확인 필요 여부 확인
    # -----------------------------------------------------------------------------
    current_affiliation = selectors.get_current_affiliation_record(user=user)
    if current_affiliation is None or not current_affiliation.requires_reconfirm:
        return {"error": "reconfirm not required"}, 409

    # -----------------------------------------------------------------------------
    # 3) 기존 소속 유지 선택 처리
    # -----------------------------------------------------------------------------
    if not accepted:
        current_affiliation.requires_reconfirm = False
        current_affiliation.save(update_fields=["requires_reconfirm"])
        return {
            "status": "kept",
            "userSdwtProd": selectors.get_current_user_sdwt_prod(user=user),
        }, 200

    # -----------------------------------------------------------------------------
    # 4) 적용 대상 user_sdwt_prod 결정
    # -----------------------------------------------------------------------------
    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(
        knox_id=getattr(user, "knox_id", "") or ""
    )
    predicted = (snapshot.predicted_user_sdwt_prod or "").strip() if snapshot else ""

    selected_user_sdwt = (user_sdwt_prod or "").strip()
    if not selected_user_sdwt:
        selected_user_sdwt = predicted

    if not selected_user_sdwt:
        return {"error": "user_sdwt_prod is required"}, 400

    current_user_sdwt = (selectors.get_current_user_sdwt_prod(user=user) or "").strip()
    if _same_user_sdwt_prod(current_user_sdwt, selected_user_sdwt):
        current_affiliation.requires_reconfirm = False
        current_affiliation.save(update_fields=["requires_reconfirm"])
        return {
            "status": "kept",
            "userSdwtProd": current_user_sdwt,
        }, 200

    # -----------------------------------------------------------------------------
    # 5) 소속 옵션 확인
    # -----------------------------------------------------------------------------
    option = selectors.get_affiliation_option_by_user_sdwt_prod(user_sdwt_prod=selected_user_sdwt)
    if option is None:
        return {"error": "Invalid user_sdwt_prod"}, 400

    # -----------------------------------------------------------------------------
    # 6) 변경 요청 생성 및 결과 반환
    # -----------------------------------------------------------------------------
    # 예측값과 다르면 승인 대기 강제
    force_pending = not _same_user_sdwt_prod(selected_user_sdwt, predicted)
    response_payload, status_code = request_affiliation_change(
        user=user,
        option=option,
        to_user_sdwt_prod=selected_user_sdwt,
        effective_from=timezone.now(),
        timezone_name=timezone_name,
        force_pending=force_pending,
    )

    if status_code in (200, 202):
        current_affiliation.requires_reconfirm = False
        current_affiliation.save(update_fields=["requires_reconfirm"])

    return response_payload, status_code


def get_line_sdwt_options_payload(*, pairs: list[dict[str, str]]) -> dict[str, object]:
    """(line_id, user_sdwt_prod) 목록으로 LineSdwtOptionsView 응답 payload를 구성합니다.

    입력:
    - pairs: line_id/user_sdwt_prod 쌍 목록

    반환:
    - dict[str, object]: 옵션 페이로드

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 라인별 그룹화
    # -----------------------------------------------------------------------------
    grouped: Dict[str, List[str]] = {}
    for row in pairs:
        line_id = row["line_id"]
        user_sdwt_prod = row["user_sdwt_prod"]
        grouped.setdefault(line_id, []).append(user_sdwt_prod)

    # -----------------------------------------------------------------------------
    # 2) 라인별 옵션 구성
    # -----------------------------------------------------------------------------
    lines = [
        {
            "lineId": line_id,
            "userSdwtProds": sorted(list(set(user_sdwt_list))),
        }
        for line_id, user_sdwt_list in grouped.items()
    ]
    # -----------------------------------------------------------------------------
    # 3) 전체 user_sdwt_prod 집합 구성
    # -----------------------------------------------------------------------------
    all_user_sdwt = sorted(
        {usdwt for user_sdwt_list in grouped.values() for usdwt in user_sdwt_list}
    )

    # -----------------------------------------------------------------------------
    # 4) 페이로드 반환
    # -----------------------------------------------------------------------------
    return {"lines": lines, "userSdwtProds": all_user_sdwt}
