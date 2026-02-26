# =============================================================================
# 모듈: DroneEarlyInform 서비스
# 주요 기능: 생성/수정/삭제, 중복/미존재 예외 처리
# 주요 가정: 유니크 제약 위반 시 중복 오류로 처리합니다.
# =============================================================================
"""DroneEarlyInform CRUD 서비스 모듈입니다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction

from ... import selectors
from ...models import DroneEarlyInform


class DroneEarlyInformDuplicateError(RuntimeError):
    """DroneEarlyInform의 유니크 제약 위반(중복) 시 발생합니다."""


class DroneEarlyInformNotFoundError(RuntimeError):
    """DroneEarlyInform 레코드가 없을 때 발생합니다."""


@dataclass(frozen=True)
class DroneEarlyInformUpdateResult:
    """조기 알림 설정 업데이트 결과를 담습니다."""

    entry: DroneEarlyInform
    previous_entry: DroneEarlyInform


def create_early_inform_entry(
    *,
    line_id: str,
    main_step: str,
    custom_end_step: str | None,
    updated_by: str | None,
) -> DroneEarlyInform:
    """조기 알림 설정을 생성합니다.

    인자:
        line_id: 라인 ID.
        main_step: 메인 스텝.
        custom_end_step: 커스텀 종료 스텝(옵션).
        updated_by: 수정자 식별자.

    반환:
        생성된 DroneEarlyInform 인스턴스.

    부작용:
        DroneEarlyInform 레코드가 생성됩니다.

    오류:
        중복 키 충돌 시 DroneEarlyInformDuplicateError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 트랜잭션 내 레코드 생성
    # -----------------------------------------------------------------------------
    try:
        with transaction.atomic():
            return DroneEarlyInform.objects.create(
                line_id=line_id,
                main_step=main_step,
                custom_end_step=custom_end_step,
                updated_by=updated_by,
            )
    except IntegrityError as exc:
        raise DroneEarlyInformDuplicateError("An entry for this main step already exists") from exc


def update_early_inform_entry(
    *,
    entry_id: int,
    updates: dict[str, Any],
    updated_by: str | None,
) -> DroneEarlyInformUpdateResult:
    """조기 알림 설정을 부분 업데이트합니다.

    인자:
        entry_id: 업데이트 대상 ID.
        updates: 업데이트할 필드 dict.
        updated_by: 수정자 식별자.

    반환:
        업데이트 결과(현재/이전 스냅샷 포함).

    부작용:
        DroneEarlyInform 레코드가 수정됩니다.

    오류:
        유효한 필드가 없으면 ValueError,
        레코드가 없으면 DroneEarlyInformNotFoundError,
        중복 키 충돌 시 DroneEarlyInformDuplicateError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 허용 필드 필터링
    # -----------------------------------------------------------------------------
    allowed_fields = {"line_id", "main_step", "custom_end_step"}
    filtered_updates = {key: value for key, value in updates.items() if key in allowed_fields}

    if not filtered_updates and updated_by is None:
        raise ValueError("No valid fields to update")

    # -----------------------------------------------------------------------------
    # 2) 트랜잭션 내 조회/업데이트
    # -----------------------------------------------------------------------------
    try:
        with transaction.atomic():
            entry = selectors.get_early_inform_entry_for_update(entry_id=entry_id)
            if entry is None:
                raise DroneEarlyInformNotFoundError("Entry not found")

            previous_entry = DroneEarlyInform(
                id=entry.id,
                line_id=entry.line_id,
                main_step=entry.main_step,
                custom_end_step=entry.custom_end_step,
                updated_by=entry.updated_by,
                updated_at=entry.updated_at,
            )

            for key, value in filtered_updates.items():
                setattr(entry, key, value)
            entry.updated_by = updated_by
            entry.save()
    except IntegrityError as exc:
        raise DroneEarlyInformDuplicateError("An entry for this main step already exists") from exc

    return DroneEarlyInformUpdateResult(entry=entry, previous_entry=previous_entry)


def delete_early_inform_entry(*, entry_id: int) -> DroneEarlyInform:
    """조기 알림 설정을 삭제합니다.

    인자:
        entry_id: 삭제 대상 ID.

    반환:
        삭제된 DroneEarlyInform 인스턴스.

    부작용:
        DroneEarlyInform 레코드가 삭제됩니다.

    오류:
        레코드가 없으면 DroneEarlyInformNotFoundError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 트랜잭션 내 조회/삭제
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        entry = selectors.get_early_inform_entry_for_update(entry_id=entry_id)
        if entry is None:
            raise DroneEarlyInformNotFoundError("Entry not found")
        entry.delete()
        return entry
