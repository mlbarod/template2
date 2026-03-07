# =============================================================================
# 모듈: Drone SOP POP3 설정/룰
# 주요 기능: NeedToSendRule, DroneSopPop3Config, DroneSopPop3IngestResult
# 주요 가정: 설정은 settings/env에서 주입됩니다.
# =============================================================================
"""Drone SOP POP3 설정 및 규칙 모음."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from ..shared.utils import _first_defined, _parse_bool, _parse_int

def _as_int_bool(value: Any) -> int:
    """불리언 값을 0/1 정수로 변환합니다.

    인자:
        value: 원본 값.

    반환:
        1(True) 또는 0(False).

    부작용:
        없음. 순수 변환입니다.
    """

    return 1 if bool(value) else 0


@dataclass(frozen=True)
class NeedToSendRule:
    """needtosend 계산 규칙을 정의합니다."""

    comment_last_at: str
    ignore_sample_type: bool = False

    def compute(self, row: dict[str, Any]) -> int:
        """규칙에 따라 needtosend 값을 계산합니다.

        인자:
            row: Drone SOP 행 dict(행 데이터).

        반환:
            needtosend 값(0/1).

        부작용:
            없음. 순수 계산입니다.
        """

        # ---------------------------------------------------------------------
        # 1) 댓글/마지막 태그 추출
        # ---------------------------------------------------------------------
        comment = str(row.get("comment") or "").strip()
        last_at = comment.split("@")[-1] if comment else ""
        # ---------------------------------------------------------------------
        # 2) 샘플 타입 조건 처리
        # ---------------------------------------------------------------------
        if not self.ignore_sample_type:
            sample_type = str(row.get("sample_type") or "").strip()
            if sample_type == "ENGR_PRODUCTION":
                return 0
        # ---------------------------------------------------------------------
        # 3) 규칙 비교 결과 반환
        # ---------------------------------------------------------------------
        return _as_int_bool(last_at == self.comment_last_at)


def _load_include_subjects(raw: Any) -> tuple[str, ...]:
    """환경변수 기반 Drone SOP 메일 제목 포함 목록을 로드합니다.

    인자:
        raw: 제목 목록 문자열(콤마 구분).

    반환:
        소문자화된 제목 튜플.

    부작용:
        없음. 순수 파싱입니다.
    """

    # ---------------------------------------------------------------------
    # 1) 입력 정규화
    # ---------------------------------------------------------------------
    text = str(raw or "").strip()
    if not text:
        return ()

    # ---------------------------------------------------------------------
    # 2) 콤마 구분 문자열 파싱
    # ---------------------------------------------------------------------
    subjects: list[str] = []
    for item in text.split(","):
        cleaned = item.strip().strip("\"'").lower()
        if cleaned:
            subjects.append(cleaned)

    return tuple(subjects)


@dataclass(frozen=True)
class DroneSopPop3IngestResult:
    """Drone SOP POP3 수집 실행 결과."""

    matched_mails: int = 0
    upserted_rows: int = 0
    deleted_mails: int = 0
    pruned_rows: int = 0
    skipped: bool = False
    skip_reason: str | None = None


@dataclass(frozen=True)
class DroneSopPop3Config:
    """Drone SOP POP3 수집 설정."""

    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    timeout: int = 60
    include_subjects: tuple[str, ...] = ()
    dummy_mode: bool = False
    dummy_mail_messages_url: str = ""
    # 임시 부가기능(sidecar) endpoint: 비어 있으면 전송을 수행하지 않습니다.
    defectmap_url: str = ""

    @classmethod
    def from_settings(cls) -> "DroneSopPop3Config":
        """settings/env에서 POP3 수집 설정을 로드합니다.

        반환:
            DroneSopPop3Config 인스턴스.

        부작용:
            settings/env 값을 조회합니다.
        """

        # ---------------------------------------------------------------------
        # 1) POP3 기본 설정 로드
        # ---------------------------------------------------------------------
        host = (getattr(settings, "DRONE_SOP_POP3_HOST", "") or "").strip()
        port = _parse_int(getattr(settings, "DRONE_SOP_POP3_PORT", None), 995)
        username = (getattr(settings, "DRONE_SOP_POP3_USERNAME", "") or "").strip()
        password = (getattr(settings, "DRONE_SOP_POP3_PASSWORD", "") or "").strip()
        use_ssl = _parse_bool(getattr(settings, "DRONE_SOP_POP3_USE_SSL", None), True)
        timeout = _parse_int(getattr(settings, "DRONE_SOP_POP3_TIMEOUT", None), 60)
        include_subjects_raw = os.getenv("DRONE_SOP_POP3_SUBJECT")
        include_subjects = _load_include_subjects(include_subjects_raw)
        # ---------------------------------------------------------------------
        # 2) 더미 모드 설정 로드
        # ---------------------------------------------------------------------
        dummy_mode = _parse_bool(
            _first_defined(
                getattr(settings, "DRONE_SOP_DUMMY_MODE", None),
                os.getenv("DRONE_SOP_DUMMY_MODE"),
            ),
            False,
        )
        dummy_mail_messages_url = (
            getattr(settings, "DRONE_SOP_DUMMY_MAIL_MESSAGES_URL", "")
            or os.getenv("DRONE_SOP_DUMMY_MAIL_MESSAGES_URL")
            or ""
        ).strip()
        defectmap_url = (
            getattr(settings, "DRONE_SOP_DEFECTMAP_URL", "")
            or os.getenv("DRONE_SOP_DEFECTMAP_URL")
            or ""
        ).strip()

        # ---------------------------------------------------------------------
        # 3) 설정 객체 반환
        # ---------------------------------------------------------------------
        return cls(
            host=host,
            port=port,
            username=username,
            password=password,
            use_ssl=use_ssl,
            timeout=timeout,
            include_subjects=include_subjects,
            dummy_mode=dummy_mode,
            dummy_mail_messages_url=dummy_mail_messages_url,
            defectmap_url=defectmap_url,
        )


__all__ = [
    "DroneSopPop3Config",
    "DroneSopPop3IngestResult",
    "NeedToSendRule",
    "_as_int_bool",
]
