"""Drone SOP 알림 target mapping 생성 서비스."""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from ...models import DroneSopTargetMapping
from .normalization import normalize_required_mapping_value as _normalize_required_mapping_value
from .user_sdwt_channel import ensure_drone_sop_notification_target


class DroneSopTargetMappingDuplicateError(ValueError):
    """이미 등록된 target mapping이 있을 때 발생하는 오류입니다."""


class DroneSopTargetMappingNotFoundError(ValueError):
    """삭제할 target mapping이 없을 때 발생하는 오류입니다."""


def create_drone_sop_target_mapping(
    *,
    line_id: str,
    target_user_sdwt_prod: str,
    sdwt_prod: str,
    user_sdwt_prod: str,
    actor: Any | None = None,
) -> DroneSopTargetMapping:
    """sdwt_prod/user_sdwt_prod 조합을 target_user_sdwt_prod에 연결합니다.

    입력:
    - line_id: target 소유 라인
    - target_user_sdwt_prod: 알림 target 식별자
    - sdwt_prod: 설비 분임조 값
    - user_sdwt_prod: 사용자 분임조 값
    - actor: 생성 요청 사용자

    반환:
    - 생성된 DroneSopTargetMapping

    부작용:
    - target이 없으면 DroneSopTarget row를 생성합니다.
    오류:
    - ValueError: 필수 입력 누락, line/target 불일치
    - DroneSopTargetMappingDuplicateError: 동일 조합이 이미 존재
    """

    normalized_line_id = _normalize_required_mapping_value(line_id, "lineId")
    normalized_target = _normalize_required_mapping_value(target_user_sdwt_prod, "targetUserSdwtProd")
    normalized_sdwt = _normalize_required_mapping_value(sdwt_prod, "sdwtProd")
    normalized_user_sdwt = _normalize_required_mapping_value(user_sdwt_prod, "userSdwtProd")

    with transaction.atomic():
        duplicate = (
            DroneSopTargetMapping.objects.select_for_update()
            .filter(
                sdwt_prod__iexact=normalized_sdwt,
                user_sdwt_prod__iexact=normalized_user_sdwt,
            )
            .order_by("id")
            .first()
        )
        if duplicate is not None:
            raise DroneSopTargetMappingDuplicateError("target mapping already exists")

        target, _ = ensure_drone_sop_notification_target(
            line_id=normalized_line_id,
            target_user_sdwt_prod=normalized_target,
            actor=actor,
        )

        try:
            return DroneSopTargetMapping.objects.create(
                sdwt_prod=normalized_sdwt,
                user_sdwt_prod=normalized_user_sdwt,
                target=target,
            )
        except IntegrityError as exc:
            raise DroneSopTargetMappingDuplicateError("target mapping already exists") from exc


def delete_drone_sop_target_mapping(
    *,
    line_id: str,
    target_user_sdwt_prod: str,
    sdwt_prod: str,
    user_sdwt_prod: str,
) -> None:
    """target_user_sdwt_prod에 연결된 sdwt_prod/user_sdwt_prod 지정 조합을 삭제합니다.

    입력:
    - line_id: target 소유 라인
    - target_user_sdwt_prod: 알림 target 식별자
    - sdwt_prod: 설비 분임조 값
    - user_sdwt_prod: 사용자 분임조 값

    부작용:
    - 일치하는 DroneSopTargetMapping row를 삭제합니다.

    오류:
    - ValueError: 필수 입력 누락
    - DroneSopTargetMappingNotFoundError: 일치하는 지정 조합 없음
    """

    normalized_line_id = _normalize_required_mapping_value(line_id, "lineId")
    normalized_target = _normalize_required_mapping_value(target_user_sdwt_prod, "targetUserSdwtProd")
    normalized_sdwt = _normalize_required_mapping_value(sdwt_prod, "sdwtProd")
    normalized_user_sdwt = _normalize_required_mapping_value(user_sdwt_prod, "userSdwtProd")

    with transaction.atomic():
        mapping = (
            DroneSopTargetMapping.objects.select_for_update()
            .filter(
                target__line_id__iexact=normalized_line_id,
                target__target_user_sdwt_prod__iexact=normalized_target,
                sdwt_prod__iexact=normalized_sdwt,
                user_sdwt_prod__iexact=normalized_user_sdwt,
            )
            .order_by("id")
            .first()
        )
        if mapping is None:
            raise DroneSopTargetMappingNotFoundError("target mapping not found")
        mapping.delete()


__all__ = [
    "DroneSopTargetMappingDuplicateError",
    "DroneSopTargetMappingNotFoundError",
    "create_drone_sop_target_mapping",
    "delete_drone_sop_target_mapping",
]
