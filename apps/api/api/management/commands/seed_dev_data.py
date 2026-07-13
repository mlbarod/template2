# =============================================================================
# 모듈 설명: 로컬 dev 더미 데이터를 통합 refresh하는 command를 제공합니다.
# - 주요 클래스: Command
# - 불변 조건: ENVIRONMENT=development 에서만 실행합니다.
# =============================================================================

from __future__ import annotations

import os
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from api.account.services import ensure_dev_dummy_superuser


def _env(name: str, default: str = "") -> str:
    """환경변수 문자열 값을 공백 제거 후 반환합니다."""

    return (os.getenv(name) or default).strip()


def _ensure_dev_seed_allowed() -> None:
    """dev seed refresh가 허용된 환경인지 확인합니다."""

    if _env("ENVIRONMENT").lower() != "development":
        raise CommandError(
            "seed_dev_data는 로컬 dev 환경에서만 실행할 수 있습니다. "
            "ENVIRONMENT=development 설정을 확인하세요."
        )


class Command(BaseCommand):
    """로컬 개발 더미 데이터를 prefix 기준으로 refresh합니다."""

    help = "Refresh deterministic dummy data for local dev only."

    def add_arguments(self, parser) -> None:
        """커맨드 인자를 정의합니다."""

        parser.add_argument(
            "--prefix",
            type=str,
            default=_env("DEV_SEED_PREFIX", "DEV"),
            help="더미 데이터 식별 prefix. 예: DEV",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="동일 prefix 더미 데이터를 먼저 삭제한 뒤 다시 적재합니다.",
        )
        parser.add_argument(
            "--skip-rag",
            action="store_true",
            help="이메일 더미 RAG 등록 호출을 건너뜁니다.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """dev dummy 사용자와 비즈니스 더미 데이터를 보장합니다."""

        _ensure_dev_seed_allowed()

        prefix = str(options.get("prefix") or "").strip().upper()
        if not prefix:
            raise CommandError("--prefix must not be empty")

        user = ensure_dev_dummy_superuser()
        if user is None:
            raise CommandError("dev dummy 사용자를 보장하지 못했습니다. DUMMY_ADFS_* 설정을 확인하세요.")

        reset = bool(options.get("reset"))
        skip_rag = bool(options.get("skip_rag"))
        self.stdout.write(
            f"[dev-seed] start prefix={prefix} reset={int(reset)} skip_rag={int(skip_rag)} "
            f"dummy={getattr(user, 'sabun', '')}"
        )

        call_command(
            "seed_dummy_emails",
            prefix=prefix,
            reset=reset,
            skip_rag=skip_rag,
            stdout=self.stdout,
            stderr=self.stderr,
        )
        call_command(
            "seed_drone_dummy_data",
            prefix=prefix,
            reset=reset,
            stdout=self.stdout,
            stderr=self.stderr,
        )

        self.stdout.write(self.style.SUCCESS(f"[dev-seed] done prefix={prefix}"))
