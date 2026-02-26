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
from .inform.sop_inform import DroneSopInformResult, run_drone_sop_inform_from_env
from .jira.config import DroneJiraConfig
from .jira.sop_jira import (
    DroneSopInstantInformResult,
    DroneSopJiraCreateResult,
    _jira_session,
    _update_drone_sop_jira_status,
    enqueue_drone_sop_jira_instant_inform,
    run_drone_sop_jira_create_from_env,
)
from .channels.user_sdwt_channel import upsert_drone_sop_user_sdwt_channel
from .pop3.config import DroneSopPop3Config, DroneSopPop3IngestResult, NeedToSendRule
from .pop3.sop_pop3 import (
    _build_drone_sop_row,
    _upsert_drone_sop_rows,
    run_drone_sop_pop3_ingest_from_env,
)
from .shared.utils import (
    _lock_key,
    _parse_bool,
    _parse_int,
    _release_advisory_lock,
    _try_advisory_lock,
)

__all__ = [
    "DroneEarlyInformDuplicateError",
    "DroneEarlyInformNotFoundError",
    "DroneEarlyInformUpdateResult",
    "DroneJiraConfig",
    "DroneSopInstantInformResult",
    "DroneSopInformResult",
    "DroneSopJiraCreateResult",
    "DroneSopPop3Config",
    "DroneSopPop3IngestResult",
    "NeedToSendRule",
    "_build_drone_sop_row",
    "_jira_session",
    "_lock_key",
    "_parse_bool",
    "_parse_int",
    "_release_advisory_lock",
    "_try_advisory_lock",
    "_update_drone_sop_jira_status",
    "_upsert_drone_sop_rows",
    "create_early_inform_entry",
    "delete_early_inform_entry",
    "enqueue_drone_sop_jira_instant_inform",
    "run_drone_sop_inform_from_env",
    "run_drone_sop_jira_create_from_env",
    "run_drone_sop_pop3_ingest_from_env",
    "upsert_drone_sop_user_sdwt_channel",
    "update_early_inform_entry",
]
