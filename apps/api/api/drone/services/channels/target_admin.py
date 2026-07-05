"""Drone SOP target superuser 관리 서비스입니다."""

from __future__ import annotations

from django.db import IntegrityError, transaction

from ...models import DroneSopTarget
from .user_sdwt_upsert import normalize_user_sdwt_channel_target

MAX_TARGET_LENGTH = 64
MAX_LINE_ID_LENGTH = 50


class DroneSopTargetAdminDuplicateError(ValueError):
    """동일한 target_user_sdwt_prod가 이미 있을 때 발생하는 오류입니다."""


class DroneSopTargetAdminNotFoundError(ValueError):
    """관리 대상 target row가 없을 때 발생하는 오류입니다."""


def _normalize_target_id(value: object) -> int:
    """target id 입력을 양의 정수로 정규화합니다."""

    try:
        target_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("id is required") from exc
    if target_id <= 0:
        raise ValueError("id is required")
    return target_id


def _normalize_line_id(value: object) -> str:
    """line_id 필수 입력을 검증하고 공백을 제거합니다."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("lineId is required")
    normalized = value.strip()
    if len(normalized) > MAX_LINE_ID_LENGTH:
        raise ValueError("lineId must be 50 characters or fewer")
    return normalized


def _normalize_target_user_sdwt_prod(value: object) -> str:
    """target_user_sdwt_prod 필수 입력을 검증하고 길이를 제한합니다."""

    normalized = normalize_user_sdwt_channel_target(value)
    if len(normalized) > MAX_TARGET_LENGTH:
        raise ValueError("targetUserSdwtProd must be 64 characters or fewer")
    return normalized


def _lock_target_by_id(*, target_id: int) -> DroneSopTarget:
    """PK 기준 target row를 잠금 조회합니다."""

    target = DroneSopTarget.objects.select_for_update().filter(id=target_id).first()
    if target is None:
        raise DroneSopTargetAdminNotFoundError("target not found")
    return target


def _raise_if_duplicate_target(*, target_user_sdwt_prod: str, exclude_id: int | None = None) -> None:
    """대소문자 비구분 target 중복을 검사합니다."""

    queryset = DroneSopTarget.objects.select_for_update().filter(
        target_user_sdwt_prod__iexact=target_user_sdwt_prod,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(id=exclude_id)
    if queryset.exists():
        raise DroneSopTargetAdminDuplicateError("target already exists")


def create_drone_sop_target_admin_row(*, line_id: object, target_user_sdwt_prod: object) -> DroneSopTarget:
    """superuser 관리 화면에서 DroneSopTarget row를 생성합니다.

    입력:
        line_id: target 소유 line ID.
        target_user_sdwt_prod: target 식별자.

    반환:
        생성된 DroneSopTarget.

    부작용:
        DroneSopTarget row를 생성합니다.
    """

    normalized_line_id = _normalize_line_id(line_id)
    normalized_target = _normalize_target_user_sdwt_prod(target_user_sdwt_prod)
    with transaction.atomic():
        _raise_if_duplicate_target(target_user_sdwt_prod=normalized_target)
        try:
            return DroneSopTarget.objects.create(
                line_id=normalized_line_id,
                target_user_sdwt_prod=normalized_target,
            )
        except IntegrityError as exc:
            raise DroneSopTargetAdminDuplicateError("target already exists") from exc


def update_drone_sop_target_admin_row(
    *,
    target_id: object,
    line_id: object,
    target_user_sdwt_prod: object,
) -> DroneSopTarget:
    """superuser 관리 화면에서 DroneSopTarget row를 수정합니다.

    입력:
        target_id: DroneSopTarget PK.
        line_id: 변경할 line ID.
        target_user_sdwt_prod: 변경할 target 식별자.

    반환:
        수정된 DroneSopTarget.

    부작용:
        DroneSopTarget row를 저장합니다.
    """

    normalized_id = _normalize_target_id(target_id)
    normalized_line_id = _normalize_line_id(line_id)
    normalized_target = _normalize_target_user_sdwt_prod(target_user_sdwt_prod)
    with transaction.atomic():
        target = _lock_target_by_id(target_id=normalized_id)
        _raise_if_duplicate_target(
            target_user_sdwt_prod=normalized_target,
            exclude_id=target.id,
        )

        update_fields: list[str] = []
        if target.line_id != normalized_line_id:
            target.line_id = normalized_line_id
            update_fields.append("line_id")
        if target.target_user_sdwt_prod != normalized_target:
            target.target_user_sdwt_prod = normalized_target
            update_fields.append("target_user_sdwt_prod")
        if update_fields:
            target.save(update_fields=[*update_fields, "updated_at"])
        return target


def delete_drone_sop_target_admin_row(*, target_id: object) -> None:
    """superuser 관리 화면에서 DroneSopTarget row를 삭제합니다.

    입력:
        target_id: DroneSopTarget PK.

    부작용:
        DroneSopTarget row를 삭제합니다.
        연결된 mapping/channel/recipient/rule은 cascade되고 dispatch target FK는 null 처리됩니다.
    """

    normalized_id = _normalize_target_id(target_id)
    with transaction.atomic():
        target = _lock_target_by_id(target_id=normalized_id)
        target.delete()


__all__ = [
    "DroneSopTargetAdminDuplicateError",
    "DroneSopTargetAdminNotFoundError",
    "create_drone_sop_target_admin_row",
    "delete_drone_sop_target_admin_row",
    "update_drone_sop_target_admin_row",
]
