# =============================================================================
# 모듈: Drone SOP 채널 설정 서비스
# 주요 함수: get_or_create_drone_sop_target_by_name, upsert_drone_sop_user_sdwt_channel
# 주요 가정: target_user_sdwt_prod 단위로 단일 알림 target을 관리합니다.
# =============================================================================
"""Drone SOP 채널 설정 갱신 서비스 모음."""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from ...models import DroneSopNeedToSendRule, DroneSopTarget, DroneSopTargetChannelConfig
from .normalization import UNSET as _UNSET, same_text as _same_text
from .user_sdwt_upsert import (
    normalize_user_sdwt_channel_target,
    normalize_user_sdwt_channel_upsert_fields,
    UserSdwtChannelUpsertFields,
)


def _set_value_if_changed(*, instance: object, field_name: str, value: object, update_fields: list[str]) -> None:
    """모델 필드 값이 실제로 바뀐 경우에만 저장 대상 필드에 추가합니다."""

    if value is _UNSET:
        return
    if getattr(instance, field_name) != value:
        setattr(instance, field_name, value)
        update_fields.append(field_name)


def _get_or_create_channel_config(
    *,
    target: DroneSopTarget,
    channel: str,
) -> tuple[DroneSopTargetChannelConfig, bool]:
    """target/channel 설정 row를 잠금 기준으로 조회하거나 생성합니다."""

    config = (
        DroneSopTargetChannelConfig.objects.select_for_update()
        .filter(target=target, channel=channel)
        .order_by("id")
        .first()
    )
    if config is not None:
        return config, False
    try:
        # unique 충돌이 발생하면 savepoint만 롤백하고 외부 transaction은 유지합니다.
        with transaction.atomic():
            return DroneSopTargetChannelConfig.objects.create(target=target, channel=channel), True
    except IntegrityError:
        concurrent = (
            DroneSopTargetChannelConfig.objects.select_for_update()
            .filter(target=target, channel=channel)
            .order_by("id")
            .first()
        )
        if concurrent is None:
            raise
        return concurrent, False


def _lock_target_by_name(*, normalized_target: str) -> DroneSopTarget | None:
    """대소문자 비구분 target row를 잠금 상태로 조회합니다."""

    return (
        DroneSopTarget.objects.select_for_update()
        .filter(target_user_sdwt_prod__iexact=normalized_target)
        .order_by("id")
        .first()
    )


def _create_target_or_reselect(*, normalized_target: str, line_id: str) -> tuple[DroneSopTarget, bool]:
    """동시 생성 충돌 시 기존 target을 다시 잠금 조회합니다."""

    try:
        # unique 충돌이 발생하면 savepoint만 롤백하고 외부 transaction은 유지합니다.
        with transaction.atomic():
            return (
                DroneSopTarget.objects.create(
                    target_user_sdwt_prod=normalized_target,
                    line_id=line_id,
                ),
                True,
            )
    except IntegrityError:
        concurrent = _lock_target_by_name(normalized_target=normalized_target)
        if concurrent is None:
            raise
        return concurrent, False


def get_or_create_drone_sop_target_by_name(
    *,
    target_user_sdwt_prod: str,
    line_id: str = "",
) -> DroneSopTarget:
    """target 이름으로 target row를 조회하거나 생성합니다.

    입력:
    - target_user_sdwt_prod: target 식별자
    - line_id: 신규 target 생성 시 저장할 라인 ID

    반환:
    - DroneSopTarget: 기존 또는 신규 target row

    부작용:
    - target이 없으면 DroneSopTarget row를 생성합니다.

    오류:
    - ValueError: target_user_sdwt_prod가 비어 있을 때
    """

    normalized_target = normalize_user_sdwt_channel_target(target_user_sdwt_prod)
    normalized_line_id = str(line_id or "")
    with transaction.atomic():
        target = _lock_target_by_name(normalized_target=normalized_target)
        if target is not None:
            return target
        target, _ = _create_target_or_reselect(
            normalized_target=normalized_target,
            line_id=normalized_line_id,
        )
        return target


def _apply_single_channel_config(
    *,
    target: DroneSopTarget,
    channel: str,
    enabled: bool | object = _UNSET,
    template_key: str | None | object = _UNSET,
    jira_project_key: str | None | object = _UNSET,
    chatroom_id: int | None | object = _UNSET,
    force_new_chatroom: bool | object = _UNSET,
) -> bool:
    """채널별 설정 필드를 별도 config row에 반영합니다."""

    if (
        enabled is _UNSET
        and template_key is _UNSET
        and jira_project_key is _UNSET
        and chatroom_id is _UNSET
        and force_new_chatroom is _UNSET
    ):
        return False

    config, created = _get_or_create_channel_config(target=target, channel=channel)
    update_fields: list[str] = []
    _set_value_if_changed(instance=config, field_name="enabled", value=enabled, update_fields=update_fields)
    _set_value_if_changed(instance=config, field_name="template_key", value=template_key, update_fields=update_fields)
    _set_value_if_changed(
        instance=config,
        field_name="jira_project_key",
        value=jira_project_key,
        update_fields=update_fields,
    )
    _set_value_if_changed(instance=config, field_name="chatroom_id", value=chatroom_id, update_fields=update_fields)
    _set_value_if_changed(
        instance=config,
        field_name="force_new_chatroom",
        value=force_new_chatroom,
        update_fields=update_fields,
    )
    if update_fields:
        config.save(update_fields=[*update_fields, "updated_at"])
    return created or bool(update_fields)


def _apply_channel_config_updates(
    *,
    target: DroneSopTarget,
    fields: UserSdwtChannelUpsertFields,
) -> bool:
    """정규화된 입력을 jira/messenger/mail 채널 설정으로 분배합니다."""

    changed = False
    changed = _apply_single_channel_config(
        target=target,
        channel=DroneSopTargetChannelConfig.Channels.JIRA,
        enabled=fields.jira_enabled,
        template_key=fields.jira_template_key,
        jira_project_key=fields.jira_key,
    ) or changed

    messenger_template_key = fields.messenger_template_key
    existing_messenger = target._get_channel_config(channel=DroneSopTargetChannelConfig.Channels.MESSENGER)
    if (
        messenger_template_key is _UNSET
        and fields.jira_template_key is not _UNSET
        and not (existing_messenger.template_key if existing_messenger else None)
    ):
        messenger_template_key = fields.jira_template_key

    changed = _apply_single_channel_config(
        target=target,
        channel=DroneSopTargetChannelConfig.Channels.MESSENGER,
        enabled=fields.messenger_enabled,
        template_key=messenger_template_key,
        chatroom_id=fields.chatroom_id,
        force_new_chatroom=fields.force_new_chatroom,
    ) or changed
    changed = _apply_single_channel_config(
        target=target,
        channel=DroneSopTargetChannelConfig.Channels.MAIL,
        enabled=fields.mail_enabled,
        template_key=fields.mail_template_key,
    ) or changed
    return changed


def _apply_needtosend_rule_updates(
    *,
    target: DroneSopTarget,
    fields: UserSdwtChannelUpsertFields,
) -> bool:
    """target별 needtosend 규칙을 별도 rule row에 반영합니다."""

    if (
        fields.needtosend_comment_last_at is _UNSET
        and fields.needtosend_ignore_sample_type is _UNSET
        and fields.needtosend_enabled is _UNSET
    ):
        return False

    rule, created = DroneSopNeedToSendRule.objects.select_for_update().get_or_create(target=target)
    update_fields: list[str] = []
    _set_value_if_changed(
        instance=rule,
        field_name="comment_keyword",
        value=fields.needtosend_comment_last_at,
        update_fields=update_fields,
    )
    _set_value_if_changed(
        instance=rule,
        field_name="ignore_sample_type",
        value=fields.needtosend_ignore_sample_type,
        update_fields=update_fields,
    )
    _set_value_if_changed(
        instance=rule,
        field_name="enabled",
        value=fields.needtosend_enabled,
        update_fields=update_fields,
    )
    if update_fields:
        rule.save(update_fields=[*update_fields, "updated_at"])
    return created or bool(update_fields)


def upsert_drone_sop_user_sdwt_channel(
    *,
    target_user_sdwt_prod: str,
    line_id: str | None | object = _UNSET,
    source: str | object = _UNSET,
    actor: Any | None = None,
    jira_key: str | None | object = _UNSET,
    chatroom_id: int | None | object = _UNSET,
    force_new_chatroom: bool | object = _UNSET,
    jira_template_key: str | None | object = _UNSET,
    mail_template_key: str | None | object = _UNSET,
    messenger_template_key: str | None | object = _UNSET,
    jira_enabled: bool | object = _UNSET,
    messenger_enabled: bool | object = _UNSET,
    mail_enabled: bool | object = _UNSET,
    needtosend_comment_last_at: str | None | object = _UNSET,
    needtosend_ignore_sample_type: bool | object = _UNSET,
    needtosend_enabled: bool | object = _UNSET,
) -> tuple[DroneSopTarget, int]:
    """target_user_sdwt_prod에 대한 알림 target/채널 설정을 생성 또는 갱신합니다.

    입력:
    - target_user_sdwt_prod: 최종 소속 식별자
    - line_id: target 소유 라인(없으면 기존 값을 유지)
    - source: 기존 API 호환용 입력(저장하지 않음)
    - actor: 기존 API 호환용 입력(저장하지 않음)
    - jira_key: Jira 프로젝트 키(없으면 None, 미지정 시 _UNSET)
    - chatroom_id: 채팅룸 ID(없으면 None, 미지정 시 _UNSET)
    - force_new_chatroom: 다음 메신저 발송 시 새 채팅방 생성 여부(미지정 시 _UNSET)
    - jira_template_key: Jira 템플릿 키(없으면 None, 미지정 시 _UNSET)
    - mail_template_key: 메일 템플릿 키(없으면 None, 미지정 시 _UNSET)
    - messenger_template_key: 메신저 템플릿 키(없으면 None, 미지정 시 _UNSET)
      (미지정이고 기존 messenger_template_key가 비어 있으면 jira_template_key를 기본값으로 동기화)
    - jira_enabled: Jira 채널 활성 여부(미지정 시 _UNSET)
    - messenger_enabled: 메신저 채널 활성 여부(미지정 시 _UNSET)
    - mail_enabled: 메일 채널 활성 여부(미지정 시 _UNSET)
    - needtosend_comment_last_at: 자동 예약 포함 키워드(미지정 시 _UNSET)
    - needtosend_ignore_sample_type: 샘플 타입 제외 규칙 무시 여부(미지정 시 _UNSET)
    - needtosend_enabled: 자동 예약 규칙 활성 여부(미지정 시 _UNSET)

    반환:
    - (DroneSopTarget, int): (갱신된 엔티티, 갱신 여부)

    부작용:
    - DroneSopTarget upsert 수행

    오류:
    - ValueError: 필수 입력 누락 또는 갱신 대상 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    normalized_target = normalize_user_sdwt_channel_target(target_user_sdwt_prod)
    fields = normalize_user_sdwt_channel_upsert_fields(
        line_id=line_id,
        jira_key=jira_key,
        chatroom_id=chatroom_id,
        force_new_chatroom=force_new_chatroom,
        jira_template_key=jira_template_key,
        mail_template_key=mail_template_key,
        messenger_template_key=messenger_template_key,
        jira_enabled=jira_enabled,
        messenger_enabled=messenger_enabled,
        mail_enabled=mail_enabled,
        needtosend_comment_last_at=needtosend_comment_last_at,
        needtosend_ignore_sample_type=needtosend_ignore_sample_type,
        needtosend_enabled=needtosend_enabled,
    )
    if not fields.has_any_field():
        raise ValueError("at least one field is required")
    # -----------------------------------------------------------------------------
    # 2) 행 조회/생성 및 업데이트
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        channel = _lock_target_by_name(normalized_target=normalized_target)
        created = channel is None
        if channel is None:
            if fields.line_id is _UNSET or not fields.line_id:
                raise ValueError("line_id is required for new target")
            channel, created = _create_target_or_reselect(
                normalized_target=normalized_target,
                line_id=fields.line_id,
            )
        update_fields: list[str] = []

        if fields.line_id is not _UNSET:
            if not fields.line_id and created:
                raise ValueError("line_id is required for new target")
            if fields.line_id:
                if channel.line_id and not _same_text(channel.line_id, fields.line_id):
                    raise ValueError("targetUserSdwtProd already belongs to another line")
                if channel.line_id != fields.line_id:
                    channel.line_id = fields.line_id
                    update_fields.append("line_id")
        if update_fields:
            if created:
                channel.save()
            else:
                channel.save(update_fields=[*update_fields, "updated_at"])
        elif created:
            channel.save()

        config_changed = _apply_channel_config_updates(target=channel, fields=fields)
        rule_changed = _apply_needtosend_rule_updates(target=channel, fields=fields)
        if created or update_fields or config_changed or rule_changed:
            channel = (
                DroneSopTarget.objects.prefetch_related("channel_configs", "needtosend_rule")
                .filter(pk=channel.pk)
                .get()
            )
            return channel, 1

    return channel, 0


def ensure_drone_sop_notification_target(
    *,
    line_id: str,
    target_user_sdwt_prod: str,
    actor: Any | None = None,
    source: str = DroneSopTarget.Sources.CUSTOM,
) -> tuple[DroneSopTarget, int]:
    """라인별 Drone SOP 알림 target을 생성하거나 기존 target을 반환합니다.

    입력:
    - line_id: target 소유 라인
    - target_user_sdwt_prod: 알림 target 식별자
    - actor: 기존 API 호환용 입력(저장하지 않음)
    - source: 기존 API 호환용 입력(저장하지 않음)

    반환:
    - (DroneSopTarget, int): (target row, 변경 여부)

    부작용:
    - target이 없으면 DroneSopTarget row를 생성합니다.

    오류:
    - ValueError: line/target/source가 유효하지 않거나 target이 다른 line에 속할 때
    """

    return upsert_drone_sop_user_sdwt_channel(
        target_user_sdwt_prod=target_user_sdwt_prod,
        line_id=line_id,
        source=source,
        actor=actor,
    )


__all__ = [
    "ensure_drone_sop_notification_target",
    "get_or_create_drone_sop_target_by_name",
    "upsert_drone_sop_user_sdwt_channel",
]
