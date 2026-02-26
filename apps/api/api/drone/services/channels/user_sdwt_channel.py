# =============================================================================
# 모듈: Drone SOP 채널 설정 서비스
# 주요 함수: upsert_drone_sop_user_sdwt_channel
# 주요 가정: target_user_sdwt_prod 단위로 단일 행을 관리합니다.
# =============================================================================
"""Drone SOP 채널 설정 갱신 서비스 모음."""

from __future__ import annotations

from django.db import transaction

from ...models import DroneSopUserSdwtChannel

_UNSET = object()


def upsert_drone_sop_user_sdwt_channel(
    *,
    target_user_sdwt_prod: str,
    jira_key: str | None | object = _UNSET,
    chatroom_id: int | None | object = _UNSET,
    jira_template_key: str | None | object = _UNSET,
    mail_template_key: str | None | object = _UNSET,
    messenger_template_key: str | None | object = _UNSET,
    jira_enabled: bool | object = _UNSET,
    messenger_enabled: bool | object = _UNSET,
    mail_enabled: bool | object = _UNSET,
) -> tuple[DroneSopUserSdwtChannel, int]:
    """target_user_sdwt_prod에 대한 채널 키/템플릿을 생성 또는 갱신합니다.

    입력:
    - target_user_sdwt_prod: 최종 소속 식별자
    - jira_key: Jira 프로젝트 키(없으면 None, 미지정 시 _UNSET)
    - chatroom_id: 채팅룸 ID(없으면 None, 미지정 시 _UNSET)
    - jira_template_key: Jira 템플릿 키(없으면 None, 미지정 시 _UNSET)
    - mail_template_key: 메일 템플릿 키(없으면 None, 미지정 시 _UNSET)
    - messenger_template_key: 메신저 템플릿 키(없으면 None, 미지정 시 _UNSET)
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
        jira_key is _UNSET
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

    _validate_optional_str(jira_key, "jira_key")
    _validate_optional_chatroom_id(chatroom_id)
    _validate_optional_str(jira_template_key, "jira_template_key")
    _validate_optional_str(mail_template_key, "mail_template_key")
    _validate_optional_str(messenger_template_key, "messenger_template_key")
    if jira_enabled is not _UNSET and not isinstance(jira_enabled, bool):
        raise ValueError("jira_enabled must be bool")
    if messenger_enabled is not _UNSET and not isinstance(messenger_enabled, bool):
        raise ValueError("messenger_enabled must be bool")
    if mail_enabled is not _UNSET and not isinstance(mail_enabled, bool):
        raise ValueError("mail_enabled must be bool")

    normalized_target = target_user_sdwt_prod.strip()

    # -----------------------------------------------------------------------------
    # 2) 행 조회/생성 및 업데이트
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        channel, created = DroneSopUserSdwtChannel.objects.select_for_update().get_or_create(
            target_user_sdwt_prod=normalized_target
        )
        update_fields: list[str] = []

        if jira_key is not _UNSET and channel.jira_key != jira_key:
            channel.jira_key = jira_key
            update_fields.append("jira_key")
        if chatroom_id is not _UNSET:
            if channel.chatroom_id != chatroom_id:
                channel.chatroom_id = chatroom_id
                update_fields.append("chatroom_id")
        if jira_template_key is not _UNSET and channel.jira_template_key != jira_template_key:
            channel.jira_template_key = jira_template_key
            update_fields.append("jira_template_key")
        if mail_template_key is not _UNSET and channel.mail_template_key != mail_template_key:
            channel.mail_template_key = mail_template_key
            update_fields.append("mail_template_key")
        if messenger_template_key is not _UNSET and channel.messenger_template_key != messenger_template_key:
            channel.messenger_template_key = messenger_template_key
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
            channel.save(update_fields=[*update_fields, "updated_at"])
            return channel, 1

        if created:
            return channel, 1

    return channel, 0


__all__ = ["upsert_drone_sop_user_sdwt_channel"]
