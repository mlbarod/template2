# =============================================================================
# 모듈: 드론 서비스 파사드
# 주요 구성: early_inform/pop3/jira/inform/channels/shared
# 주요 가정: 외부에서는 api.drone.services를 통해 접근합니다.
# =============================================================================
"""드론 서비스 레이어 모듈입니다.

기능 영역별로 모듈을 분리했습니다:
 - 조기 알림 CRUD: `services/early_inform/early_inform.py`
 - Drone SOP POP3 수집: `services/pop3/sop_pop3.py`
 - Drone SOP Jira 연동: `services/jira/sop_jira.py`
 - Drone SOP 멀티 채널 알림: `services/inform/sop_inform.py`
 - 채널 키/템플릿 갱신: `services/channels/user_sdwt_channel.py`
 - 공통 유틸: `services/shared/utils.py`
 - 공통 알림 컨텍스트: `services/shared/inform_context.py`
 - 공통 대상 해석: `services/shared/notify_resolver.py`
 - 공통 정책: `services/shared/policy.py`

이 모듈은 안정적인 import 파사드 역할을 합니다(예: `from api.drone import services`).
"""

from __future__ import annotations

from .early_inform.early_inform import (
    DroneEarlyInformDuplicateError,
    DroneEarlyInformNotFoundError,
    DroneEarlyInformUpdateResult,
    create_early_inform_entry,
    delete_early_inform_entry,
    update_early_inform_entry,
)
from .inform.sop_inform import (
    DroneSopInformResult,
    has_drone_sop_pipeline_candidates,
    run_drone_sop_pipeline_from_env,
)
from .inform.retry_channel import DroneSopRetryChannelResult, retry_drone_sop_channel
from .jira.config import DroneJiraConfig
from .jira.sop_jira import (
    DroneSopInstantInformResult,
    DroneSopJiraCreateResult,
    enqueue_drone_sop_jira_instant_inform,
    run_drone_sop_jira_create_from_env,
)
from .channels import (
    DroneSopAffiliationSeedResult,
    DroneSopTargetMappingDuplicateError,
    DroneSopTargetMappingNotFoundError,
    create_drone_sop_target_mapping,
    delete_drone_sop_target_mapping,
    ensure_drone_sop_notification_target,
    get_or_create_drone_sop_target_by_name,
    normalize_recipient_channel,
    promote_drone_sop_external_recipients_for_user,
    replace_drone_sop_channel_recipients,
    seed_drone_sop_affiliation_notification_defaults,
    upsert_drone_sop_user_sdwt_channel,
)
from .pop3.config import DroneSopPop3Config, DroneSopPop3IngestResult, NeedToSendRule
from .pop3.sop_pop3 import run_drone_sop_pop3_ingest_from_env
from .shared.delivery_state import create_channel_delivery_with_dispatch
from .shared.legacy_delivery import pop_legacy_delivery_seed, seed_legacy_delivery_rows
from .table_ops import (
    TableNotFoundError,
    TableRecordNotFoundError,
    TableUpdateResult,
    get_table_record_delivery_update_payload,
    get_table_list_payload,
    update_table_record,
)

__all__ = [
    "DroneEarlyInformDuplicateError",
    "DroneEarlyInformNotFoundError",
    "DroneEarlyInformUpdateResult",
    "DroneJiraConfig",
    "DroneSopInstantInformResult",
    "DroneSopAffiliationSeedResult",
    "DroneSopInformResult",
    "DroneSopJiraCreateResult",
    "DroneSopRetryChannelResult",
    "DroneSopTargetMappingDuplicateError",
    "DroneSopTargetMappingNotFoundError",
    "DroneSopPop3Config",
    "DroneSopPop3IngestResult",
    "TableNotFoundError",
    "TableRecordNotFoundError",
    "TableUpdateResult",
    "NeedToSendRule",
    "create_early_inform_entry",
    "create_drone_sop_target_mapping",
    "create_channel_delivery_with_dispatch",
    "delete_drone_sop_target_mapping",
    "delete_early_inform_entry",
    "ensure_drone_sop_notification_target",
    "enqueue_drone_sop_jira_instant_inform",
    "get_table_record_delivery_update_payload",
    "get_table_list_payload",
    "get_or_create_drone_sop_target_by_name",
    "has_drone_sop_pipeline_candidates",
    "normalize_recipient_channel",
    "pop_legacy_delivery_seed",
    "promote_drone_sop_external_recipients_for_user",
    "replace_drone_sop_channel_recipients",
    "retry_drone_sop_channel",
    "run_drone_sop_jira_create_from_env",
    "run_drone_sop_pipeline_from_env",
    "run_drone_sop_pop3_ingest_from_env",
    "seed_legacy_delivery_rows",
    "seed_drone_sop_affiliation_notification_defaults",
    "upsert_drone_sop_user_sdwt_channel",
    "update_early_inform_entry",
    "update_table_record",
]
