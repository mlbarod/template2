"""Drone SOP 채널 설정 서비스 파사드입니다."""

from __future__ import annotations

from .affiliation_seed import (
    DroneSopAffiliationSeedResult,
    seed_drone_sop_affiliation_notification_defaults,
    seed_drone_sop_notification_defaults_from_rows,
)
from .recipients import (
    normalize_recipient_channel,
    promote_drone_sop_external_recipients_for_user,
    replace_drone_sop_channel_recipients,
)
from .target_mapping import (
    DroneSopTargetMappingDuplicateError,
    DroneSopTargetMappingNotFoundError,
    create_drone_sop_target_mapping,
    delete_drone_sop_target_mapping,
)
from .user_sdwt_channel import (
    ensure_drone_sop_notification_target,
    get_or_create_drone_sop_target_by_name,
    upsert_drone_sop_user_sdwt_channel,
)

__all__ = [
    "DroneSopAffiliationSeedResult",
    "DroneSopTargetMappingDuplicateError",
    "DroneSopTargetMappingNotFoundError",
    "create_drone_sop_target_mapping",
    "delete_drone_sop_target_mapping",
    "ensure_drone_sop_notification_target",
    "get_or_create_drone_sop_target_by_name",
    "normalize_recipient_channel",
    "promote_drone_sop_external_recipients_for_user",
    "replace_drone_sop_channel_recipients",
    "seed_drone_sop_affiliation_notification_defaults",
    "seed_drone_sop_notification_defaults_from_rows",
    "upsert_drone_sop_user_sdwt_channel",
]
