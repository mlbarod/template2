# =============================================================================
# 모듈: Drone SOP Jira HTTP 클라이언트
# 주요 기능: Jira API용 requests.Session 구성
# 주요 가정: 인증 정보는 DroneJiraConfig에서 제공됩니다.
# =============================================================================
"""Drone SOP Jira HTTP 세션 구성 모음."""

from __future__ import annotations

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import DroneJiraConfig


def _jira_session(config: DroneJiraConfig) -> requests.Session:
    """Jira API 호출용 requests.Session을 구성합니다.

    인자:
        config: Jira 설정.

    반환:
        requests.Session 인스턴스.

    부작용:
        세션 객체가 생성됩니다.
    """

    # -------------------------------------------------------------------------
    # 1) 세션 기본 설정
    # -------------------------------------------------------------------------
    sess = requests.Session()
    sess.trust_env = False
    sess.proxies = {}
    sess.verify = bool(config.verify_ssl)
    if not sess.verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # -------------------------------------------------------------------------
    # 2) 인증 헤더/인증 정보 설정
    # -------------------------------------------------------------------------
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Atlassian-Token": "no-check",
    }
    if config.user and config.token:
        sess.auth = (config.user, config.token)
    elif config.token:
        headers["Authorization"] = f"Bearer {config.token}"
    sess.headers.update(headers)

    # -------------------------------------------------------------------------
    # 3) 재시도 정책 설정
    # -------------------------------------------------------------------------
    retry = Retry(
        total=5,
        connect=5,
        read=3,
        backoff_factor=2,
        status_forcelist=[403, 502, 503, 504],
        allowed_methods=frozenset({"POST"}),
    )
    sess.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20))
    return sess


__all__ = ["_jira_session"]
