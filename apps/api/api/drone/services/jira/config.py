# =============================================================================
# 모듈: Drone SOP Jira/CTTTM 설정
# 주요 기능: DroneJiraConfig, DroneCtttmConfig
# 주요 가정: settings/env에서 설정을 읽어옵니다.
# =============================================================================
"""Drone SOP Jira/CTTTM 설정 모델 모음."""

from __future__ import annotations

import os
from dataclasses import dataclass

from django.conf import settings

from ..shared.utils import _first_defined, _parse_bool, _parse_int


@dataclass(frozen=True)
class DroneJiraConfig:
    """Jira 연동 설정."""

    base_url: str
    token: str
    issue_type: str = "Task"
    use_bulk_api: bool = True
    bulk_size: int = 20
    connect_timeout: int = 5
    read_timeout: int = 20
    verify_ssl: bool = True
    user: str = ""

    @classmethod
    def from_settings(cls) -> "DroneJiraConfig":
        """settings/env에서 Jira 연동 설정을 로드합니다.

        반환:
            DroneJiraConfig 인스턴스.

        부작용:
            settings/env 값을 조회합니다.
        """

        # ---------------------------------------------------------------------
        # 1) 기본 설정 값 로드
        # ---------------------------------------------------------------------
        # settings에 명시된 값(빈 문자열 포함)을 env보다 우선 적용합니다.
        base_url = str(
            _first_defined(
                getattr(settings, "DRONE_JIRA_BASE_URL", None),
                os.getenv("DRONE_JIRA_BASE_URL"),
                "",
            )
            or ""
        ).strip()
        token = str(
            _first_defined(
                getattr(settings, "DRONE_JIRA_TOKEN", None),
                os.getenv("DRONE_JIRA_TOKEN"),
                "",
            )
            or ""
        ).strip()
        user = str(
            _first_defined(
                getattr(settings, "DRONE_JIRA_USER", None),
                os.getenv("DRONE_JIRA_USER"),
                "",
            )
            or ""
        ).strip()
        verify_ssl = _parse_bool(
            _first_defined(
                getattr(settings, "DRONE_JIRA_VERIFY_SSL", None),
                os.getenv("DRONE_JIRA_VERIFY_SSL"),
            ),
            False,
        )
        issue_type = str(
            _first_defined(
                getattr(settings, "DRONE_JIRA_ISSUE_TYPE", None),
                os.getenv("DRONE_JIRA_ISSUE_TYPE"),
                "Task",
            )
            or "Task"
        ).strip() or "Task"
        use_bulk_api = _parse_bool(
            _first_defined(
                getattr(settings, "DRONE_JIRA_USE_BULK_API", None),
                os.getenv("DRONE_JIRA_USE_BULK_API"),
            ),
            True,
        )
        bulk_size = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_JIRA_BULK_SIZE", None),
                os.getenv("DRONE_JIRA_BULK_SIZE"),
            ),
            20,
        )
        connect_timeout = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_JIRA_CONNECT_TIMEOUT", None),
                os.getenv("DRONE_JIRA_CONNECT_TIMEOUT"),
            ),
            5,
        )
        read_timeout = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_JIRA_READ_TIMEOUT", None),
                os.getenv("DRONE_JIRA_READ_TIMEOUT"),
            ),
            20,
        )
        # ---------------------------------------------------------------------
        # 2) 최소값 보정 후 반환
        # ---------------------------------------------------------------------
        return cls(
            base_url=base_url,
            token=token,
            issue_type=issue_type,
            use_bulk_api=use_bulk_api,
            bulk_size=max(1, bulk_size),
            connect_timeout=max(1, connect_timeout),
            read_timeout=max(1, read_timeout),
            verify_ssl=verify_ssl,
            user=user,
        )

    @property
    def create_url(self) -> str:
        """Jira 단건 생성 URL을 반환합니다."""

        return f"{self.base_url.rstrip('/')}/rest/api/2/issue?sendEvent=true"

    @property
    def bulk_url(self) -> str:
        """Jira 벌크 생성 URL을 반환합니다."""

        return f"{self.base_url.rstrip('/')}/rest/api/2/issue/bulk?sendEvent=true"


@dataclass(frozen=True)
class DroneCtttmConfig:
    """CTTTM 조회 및 URL 생성 설정."""

    table_name: str = ""
    base_url: str = ""

    @classmethod
    def from_settings(cls) -> "DroneCtttmConfig":
        """settings/env에서 CTTTM 설정을 로드합니다.

        반환:
            DroneCtttmConfig 인스턴스.

        부작용:
            settings/env 값을 조회합니다.
        """

        # ---------------------------------------------------------------------
        # 1) 테이블/URL 설정 로드
        # ---------------------------------------------------------------------
        table_name = (
            getattr(settings, "DRONE_CTTTM_TABLE_NAME", "")
            or os.getenv("DRONE_CTTTM_TABLE_NAME")
            or ""
        ).strip()
        base_url = (
            getattr(settings, "DRONE_CTTTM_BASE_URL", "")
            or os.getenv("DRONE_CTTTM_BASE_URL")
            or ""
        ).strip()
        return cls(table_name=table_name, base_url=base_url)


__all__ = ["DroneCtttmConfig", "DroneJiraConfig"]
