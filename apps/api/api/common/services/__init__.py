# =============================================================================
# 모듈 설명: 공용 서비스/헬퍼의 공개 파사드를 제공합니다.
# - 주요 대상: 활동 로그, 요청 헬퍼, DB/스토리지, 미들웨어
# - 불변 조건: 외부 모듈은 이 파사드를 통해 공용 기능을 사용합니다.
# =============================================================================

"""공용 서비스 모듈의 공개 파사드.

- 주요 대상: 활동 로그/요청 헬퍼/DB 헬퍼/스토리지/미들웨어
- 주요 엔드포인트/클래스: ActivityLoggingMiddleware, KnoxIdRequiredMiddleware 등
- 가정/불변 조건: 공용 로직은 여기에서 일관되게 노출됨
"""
from __future__ import annotations

from .activity_logging import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)
from .affiliations import (
    UNKNOWN,
    UNASSIGNED_USER_SDWT_PROD,
    UNCLASSIFIED_USER_SDWT_PROD,
)
from .db import execute, get_cursor, run_query
from .middleware import ActivityLoggingMiddleware, KnoxIdRequiredMiddleware
from .normalization import normalize_text
from .request_helpers import (
    ensure_airflow_token,
    extract_first_error_message,
    extract_bearer_token,
    parse_json_body,
    parse_json_body_or_error_when_present,
    resolve_frontend_target,
)
from .storage import (
    delete_object,
    download_bytes,
    ensure_minio_bucket,
    get_minio_client,
    upload_bytes,
)

__all__ = [
    "ActivityLoggingMiddleware",
    "KnoxIdRequiredMiddleware",
    "UNKNOWN",
    "UNASSIGNED_USER_SDWT_PROD",
    "UNCLASSIFIED_USER_SDWT_PROD",
    "delete_object",
    "download_bytes",
    "ensure_airflow_token",
    "ensure_minio_bucket",
    "execute",
    "extract_first_error_message",
    "extract_bearer_token",
    "get_cursor",
    "get_minio_client",
    "merge_activity_metadata",
    "normalize_text",
    "parse_json_body",
    "parse_json_body_or_error_when_present",
    "resolve_frontend_target",
    "run_query",
    "set_activity_new_state",
    "set_activity_previous_state",
    "set_activity_summary",
    "upload_bytes",
]
