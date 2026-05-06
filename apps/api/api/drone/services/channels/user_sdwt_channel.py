# =============================================================================
# 모듈: Drone SOP 채널 설정 서비스
# 주요 함수: upsert_drone_sop_user_sdwt_channel, ensure_drone_sop_notification_target
# 주요 가정: target_user_sdwt_prod 단위로 단일 알림 target을 관리합니다.
# =============================================================================
"""Drone SOP 채널 설정 갱신 서비스 모음."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from ... import selectors
from ...models import DroneSopUserSdwtChannel

_UNSET = object()
VALID_TARGET_SOURCES = {
    DroneSopUserSdwtChannel.Sources.AFFILIATION,
    DroneSopUserSdwtChannel.Sources.CUSTOM,
}


def _normalize_optional_text(value: Any) -> str:
    """선택 문자열 값을 공백 제거 기준으로 정규화합니다."""

    return value.strip() if isinstance(value, str) else ""


def _same_text(left: str | None, right: str | None) -> bool:
    """대소문자 차이를 무시하고 두 문자열이 같은지 확인합니다."""

    normalized_left = _normalize_optional_text(left)
    normalized_right = _normalize_optional_text(right)
    return normalized_left.casefold() == normalized_right.casefold()


def _normalize_target_source(value: str | object) -> str | object:
    """target source 값을 허용된 값으로 정규화합니다."""

    if value is _UNSET:
        return value
    normalized = _normalize_optional_text(value)
    if normalized not in VALID_TARGET_SOURCES:
        raise ValueError("source must be affiliation or custom")
    return normalized


def upsert_drone_sop_user_sdwt_channel(
    *,
    target_user_sdwt_prod: str,
    line_id: str | None | object = _UNSET,
    source: str | object = _UNSET,
    actor: Any | None = None,
    jira_key: str | None | object = _UNSET,
    chatroom_id: int | None | object = _UNSET,
    jira_template_key: str | None | object = _UNSET,
    mail_template_key: str | None | object = _UNSET,
    messenger_template_key: str | None | object = _UNSET,
    jira_enabled: bool | object = _UNSET,
    messenger_enabled: bool | object = _UNSET,
    mail_enabled: bool | object = _UNSET,
) -> tuple[DroneSopUserSdwtChannel, int]:
    """target_user_sdwt_prod에 대한 알림 target/채널 설정을 생성 또는 갱신합니다.

    입력:
    - target_user_sdwt_prod: 최종 소속 식별자
    - line_id: target 소유 라인(없으면 기존 값을 유지)
    - source: affiliation/custom 중 target 생성 출처
    - actor: target을 생성한 사용자
    - jira_key: Jira 프로젝트 키(없으면 None, 미지정 시 _UNSET)
    - chatroom_id: 채팅룸 ID(없으면 None, 미지정 시 _UNSET)
    - jira_template_key: Jira 템플릿 키(없으면 None, 미지정 시 _UNSET)
    - mail_template_key: 메일 템플릿 키(없으면 None, 미지정 시 _UNSET)
    - messenger_template_key: 메신저 템플릿 키(없으면 None, 미지정 시 _UNSET)
      (미지정이고 기존 messenger_template_key가 비어 있으면 jira_template_key를 기본값으로 동기화)
    - jira_enabled: Jira 채널 활성 여부(미지정 시 _UNSET)
    - messenger_enabled: 메신저 채널 활성 여부(미지정 시 _UNSET)
    - mail_enabled: 메일 채널 활성 여부(미지정 시 _UNSET)

    반환:
    - (DroneSopUserSdwtChannel, int): (갱신된 엔티티, 갱신 여부)

    부작용:
    - DroneSopUserSdwtChannel upsert 수행

    오류:
    - ValueError: 필수 입력 누락 또는 갱신 대상 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(target_user_sdwt_prod, str) or not target_user_sdwt_prod.strip():
        raise ValueError("target_user_sdwt_prod is required")
    if (
        line_id is _UNSET
        and source is _UNSET
        and jira_key is _UNSET
        and chatroom_id is _UNSET
        and jira_template_key is _UNSET
        and mail_template_key is _UNSET
        and messenger_template_key is _UNSET
        and jira_enabled is _UNSET
        and messenger_enabled is _UNSET
        and mail_enabled is _UNSET
    ):
        raise ValueError("at least one field is required")

    def _validate_optional_str(value: object, field_name: str) -> None:
        if value is _UNSET:
            return
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field_name} must be string or None")

    def _validate_optional_chatroom_id(value: object) -> None:
        if value is _UNSET or value is None:
            return
        if not isinstance(value, int) or value <= 0:
            raise ValueError("chatroom_id must be positive int or None")

    def _normalize_optional_template_key(value: object) -> str | None | object:
        if value is _UNSET or value is None:
            return value
        assert isinstance(value, str)
        cleaned = value.strip()
        return cleaned or None

    _validate_optional_str(jira_key, "jira_key")
    _validate_optional_chatroom_id(chatroom_id)
    _validate_optional_str(jira_template_key, "jira_template_key")
    _validate_optional_str(mail_template_key, "mail_template_key")
    _validate_optional_str(messenger_template_key, "messenger_template_key")
    normalized_line_id = _normalize_optional_text(line_id) if line_id is not _UNSET else _UNSET
    normalized_source = _normalize_target_source(source)
    if jira_enabled is not _UNSET and not isinstance(jira_enabled, bool):
        raise ValueError("jira_enabled must be bool")
    if messenger_enabled is not _UNSET and not isinstance(messenger_enabled, bool):
        raise ValueError("messenger_enabled must be bool")
    if mail_enabled is not _UNSET and not isinstance(mail_enabled, bool):
        raise ValueError("mail_enabled must be bool")

    normalized_jira_template_key = _normalize_optional_template_key(jira_template_key)
    normalized_mail_template_key = _normalize_optional_template_key(mail_template_key)
    normalized_messenger_template_key = _normalize_optional_template_key(messenger_template_key)

    normalized_target = target_user_sdwt_prod.strip()
    if (
        normalized_line_id is not _UNSET
        and normalized_line_id
        and not selectors.line_id_exists(line_id=normalized_line_id)
    ):
        raise ValueError("line_id must be an existing line")

    # -----------------------------------------------------------------------------
    # 2) 행 조회/생성 및 업데이트
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        channel = (
            DroneSopUserSdwtChannel.objects.select_for_update()
            .filter(target_user_sdwt_prod__iexact=normalized_target)
            .order_by("id")
            .first()
        )
        created = channel is None
        if channel is None:
            if normalized_line_id is _UNSET:
                raise ValueError("line_id is required for new target")
            channel = DroneSopUserSdwtChannel(target_user_sdwt_prod=normalized_target)
        update_fields: list[str] = []

        if normalized_line_id is not _UNSET:
            if not normalized_line_id and created:
                raise ValueError("line_id is required for new target")
            if normalized_line_id:
                if channel.line_id and not _same_text(channel.line_id, normalized_line_id):
                    raise ValueError("targetUserSdwtProd already belongs to another line")
                if channel.line_id != normalized_line_id:
                    channel.line_id = normalized_line_id
                    update_fields.append("line_id")
        if normalized_source is not _UNSET and (created or not channel.source) and channel.source != normalized_source:
            channel.source = normalized_source
            update_fields.append("source")
        if created and getattr(actor, "is_authenticated", False):
            channel.created_by = actor
            update_fields.append("created_by")

        if jira_key is not _UNSET and channel.jira_key != jira_key:
            channel.jira_key = jira_key
            update_fields.append("jira_key")
        if chatroom_id is not _UNSET:
            if channel.chatroom_id != chatroom_id:
                channel.chatroom_id = chatroom_id
                update_fields.append("chatroom_id")
        if (
            normalized_jira_template_key is not _UNSET
            and channel.jira_template_key != normalized_jira_template_key
        ):
            channel.jira_template_key = normalized_jira_template_key
            update_fields.append("jira_template_key")
        if (
            normalized_mail_template_key is not _UNSET
            and channel.mail_template_key != normalized_mail_template_key
        ):
            channel.mail_template_key = normalized_mail_template_key
            update_fields.append("mail_template_key")
        resolved_messenger_template_key = normalized_messenger_template_key
        if (
            resolved_messenger_template_key is _UNSET
            and normalized_jira_template_key is not _UNSET
            and not channel.messenger_template_key
        ):
            resolved_messenger_template_key = normalized_jira_template_key
        if (
            resolved_messenger_template_key is not _UNSET
            and channel.messenger_template_key != resolved_messenger_template_key
        ):
            channel.messenger_template_key = resolved_messenger_template_key
            update_fields.append("messenger_template_key")
        if jira_enabled is not _UNSET and channel.jira_enabled != jira_enabled:
            channel.jira_enabled = jira_enabled
            update_fields.append("jira_enabled")
        if messenger_enabled is not _UNSET and channel.messenger_enabled != messenger_enabled:
            channel.messenger_enabled = messenger_enabled
            update_fields.append("messenger_enabled")
        if mail_enabled is not _UNSET and channel.mail_enabled != mail_enabled:
            channel.mail_enabled = mail_enabled
            update_fields.append("mail_enabled")
        if not channel.is_active:
            channel.is_active = True
            update_fields.append("is_active")

        if update_fields:
            if created:
                channel.save()
            else:
                channel.save(update_fields=[*update_fields, "updated_at"])
            return channel, 1

        if created:
            channel.save()
            return channel, 1

    return channel, 0


def ensure_drone_sop_notification_target(
    *,
    line_id: str,
    target_user_sdwt_prod: str,
    actor: Any | None = None,
    source: str = DroneSopUserSdwtChannel.Sources.CUSTOM,
) -> tuple[DroneSopUserSdwtChannel, int]:
    """라인별 Drone SOP 알림 target을 생성하거나 기존 target을 반환합니다.

    입력:
    - line_id: target 소유 라인
    - target_user_sdwt_prod: 알림 target 식별자
    - actor: 생성 요청 사용자
    - source: affiliation/custom 중 생성 출처

    반환:
    - (DroneSopUserSdwtChannel, int): (target row, 변경 여부)

    부작용:
    - target이 없으면 DroneSopUserSdwtChannel row를 생성합니다.

    오류:
    - ValueError: line/target/source가 유효하지 않거나 target이 다른 line에 속할 때
    """

    return upsert_drone_sop_user_sdwt_channel(
        target_user_sdwt_prod=target_user_sdwt_prod,
        line_id=line_id,
        source=source,
        actor=actor,
    )


__all__ = ["ensure_drone_sop_notification_target", "upsert_drone_sop_user_sdwt_channel"]
