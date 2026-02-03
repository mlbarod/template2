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

from typing import Any, Dict, Iterable, List, Tuple

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import Affiliation
from .. import selectors
from .access import _current_access_list
from .affiliation_requests import request_affiliation_change


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

    return {
        "currentUserSdwtProd": getattr(user, "user_sdwt_prod", None),
        "currentDepartment": getattr(user, "department", None),
        "currentLine": getattr(user, "line", None),
        "timezone": timezone_name,
        "accessibleUserSdwtProds": access_list,
        "manageableUserSdwtProds": manageable,
        "affiliationOptions": options,
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
    return {
        "requiresReconfirm": bool(getattr(user, "requires_affiliation_reconfirm", False)),
        "predictedUserSdwtProd": predicted,
        "currentUserSdwtProd": getattr(user, "user_sdwt_prod", None),
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

    current_user_sdwt = (getattr(user, "user_sdwt_prod", None) or "").strip()
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
    - Affiliation 생성

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
    # 2) 옵션 조회 및 생성 처리
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        option = selectors.get_affiliation_option(
            department=normalized_department,
            line=normalized_line,
            user_sdwt_prod=normalized_user_sdwt,
        )
        if option is None:
            try:
                option = Affiliation.objects.create(
                    department=normalized_department,
                    line=normalized_line,
                    user_sdwt_prod=normalized_user_sdwt,
                )
            except IntegrityError:
                option = selectors.get_affiliation_option(
                    department=normalized_department,
                    line=normalized_line,
                    user_sdwt_prod=normalized_user_sdwt,
                )
                if option is None:
                    raise

    return option


def sync_user_lines_from_affiliations(*, users: Iterable[Any], dry_run: bool = False) -> dict[str, object]:
    """line이 비어있는 사용자에게 소속 line 값을 동기화합니다.

    입력:
    - users: Django 사용자 객체 iterable
    - dry_run: True면 업데이트 없이 로그만 생성

    반환:
    - dict[str, object]: 처리 결과 요약 및 상세 로그

    부작용:
    - User.line 업데이트(dry_run=False)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 분류 및 후보 수집
    # -----------------------------------------------------------------------------
    total = 0
    updated = 0
    skipped_has_line = 0
    skipped_no_user_sdwt_prod = 0
    skipped_no_affiliation_line = 0
    logs: list[str] = []

    candidates: list[Any] = []
    user_sdwt_prods: set[str] = set()

    for user in users:
        total += 1
        user_label = getattr(user, "knox_id", None) or getattr(user, "pk", None) or "-"

        current_line = getattr(user, "line", None)
        if isinstance(current_line, str) and current_line.strip():
            skipped_has_line += 1
            logs.append(f"SKIP(기존 line 존재): {user_label} line={current_line}")
            continue

        current_sdwt = getattr(user, "user_sdwt_prod", None)
        if not isinstance(current_sdwt, str) or not current_sdwt.strip():
            skipped_no_user_sdwt_prod += 1
            logs.append(f"SKIP(user_sdwt_prod 없음): {user_label}")
            continue

        normalized_sdwt = current_sdwt.strip()
        candidates.append(user)
        user_sdwt_prods.add(normalized_sdwt)

    # -----------------------------------------------------------------------------
    # 2) 소속 line 매핑 조회
    # -----------------------------------------------------------------------------
    line_map = selectors.get_affiliation_lines_by_user_sdwt_prods(
        user_sdwt_prods=list(user_sdwt_prods)
    )

    # -----------------------------------------------------------------------------
    # 3) 업데이트 대상 확정
    # -----------------------------------------------------------------------------
    to_update: list[Any] = []
    for user in candidates:
        user_label = getattr(user, "knox_id", None) or getattr(user, "pk", None) or "-"
        current_sdwt = getattr(user, "user_sdwt_prod", None)
        normalized_sdwt = (current_sdwt or "").strip()
        line_value = line_map.get(normalized_sdwt)
        if not isinstance(line_value, str) or not line_value.strip():
            skipped_no_affiliation_line += 1
            logs.append(f"SKIP(소속 line 없음): {user_label} user_sdwt_prod={normalized_sdwt}")
            continue

        user.line = line_value
        to_update.append(user)
        updated += 1
        logs.append(f"UPDATED: {user_label} user_sdwt_prod={normalized_sdwt} line={line_value}")

    # -----------------------------------------------------------------------------
    # 4) 벌크 업데이트
    # -----------------------------------------------------------------------------
    if to_update and not dry_run:
        UserModel = get_user_model()
        with transaction.atomic():
            UserModel.objects.bulk_update(to_update, ["line"], batch_size=1000)

    return {
        "total": total,
        "updated": updated,
        "skipped_has_line": skipped_has_line,
        "skipped_no_user_sdwt_prod": skipped_no_user_sdwt_prod,
        "skipped_no_affiliation_line": skipped_no_affiliation_line,
        "logs": logs,
        "dry_run": dry_run,
    }


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
    - 예측값 일치 또는 승인자 부재 시 UserSdwtProdChange 생성/즉시 적용
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
    if not getattr(user, "requires_affiliation_reconfirm", False):
        return {"error": "reconfirm not required"}, 409

    # -----------------------------------------------------------------------------
    # 3) 기존 소속 유지 선택 처리
    # -----------------------------------------------------------------------------
    if not accepted:
        user.requires_affiliation_reconfirm = False
        user.save(update_fields=["requires_affiliation_reconfirm"])
        return {
            "status": "kept",
            "userSdwtProd": getattr(user, "user_sdwt_prod", None),
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

    current_user_sdwt = (getattr(user, "user_sdwt_prod", None) or "").strip()
    if current_user_sdwt and current_user_sdwt == selected_user_sdwt:
        user.requires_affiliation_reconfirm = False
        user.save(update_fields=["requires_affiliation_reconfirm"])
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
    force_pending = selected_user_sdwt != predicted
    response_payload, status_code = request_affiliation_change(
        user=user,
        option=option,
        to_user_sdwt_prod=selected_user_sdwt,
        effective_from=timezone.now(),
        timezone_name=timezone_name,
        force_pending=force_pending,
    )

    if status_code in (200, 202):
        user.requires_affiliation_reconfirm = False
        user.save(update_fields=["requires_affiliation_reconfirm"])

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
