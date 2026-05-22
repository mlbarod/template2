# =============================================================================
# 모듈: Drone SOP JSON target 기반 알림 초기 세팅 커맨드
# 주요 기능: JSON target 목록으로 Drone SOP/발송 이력/알림 설정 초기화 후 재생성
# 불변 조건: 입력 JSON은 department/line/user_sdwt_prod만 요구합니다.
# =============================================================================
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.drone import services


def _normalize_text(value: Any) -> str:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    return value.strip() if isinstance(value, str) else ""


def _load_seed_rows(*, file_path: str) -> list[dict[str, str]]:
    """JSON 파일을 읽어 seed row 목록으로 검증/정규화합니다."""

    path = Path(file_path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise CommandError(f"failed to read file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"invalid JSON file: {path}") from exc

    if not isinstance(payload, dict):
        raise CommandError("JSON root must be an object")
    targets = payload.get("targets")
    if not isinstance(targets, list):
        raise CommandError("JSON field 'targets' must be a list")

    rows: list[dict[str, str]] = []
    for index, target in enumerate(targets, start=1):
        if not isinstance(target, dict):
            raise CommandError(f"targets[{index}] must be an object")
        department = _normalize_text(target.get("department"))
        line = _normalize_text(target.get("line"))
        user_sdwt_prod = _normalize_text(target.get("user_sdwt_prod"))
        if not line:
            raise CommandError(f"targets[{index}].line is required")
        if not user_sdwt_prod:
            raise CommandError(f"targets[{index}].user_sdwt_prod is required")
        rows.append(
            {
                "department": department,
                "line_id": line,
                "user_sdwt_prod": user_sdwt_prod,
            }
        )
    return rows


class Command(BaseCommand):
    """JSON target 목록 기준으로 Drone SOP 알림 기본 설정을 생성합니다."""

    help = "Seed Drone SOP notification targets, mappings, channel defaults, rules, and recipients from JSON."

    def add_arguments(self, parser) -> None:
        """커맨드 옵션을 등록합니다."""

        parser.add_argument(
            "--file",
            required=True,
            help="department/line/user_sdwt_prod targets JSON 파일 경로입니다.",
        )
        parser.add_argument(
            "--template-key",
            default="common",
            help="새 채널 설정에 사용할 template_key입니다. 기본값은 common입니다.",
        )
        parser.add_argument(
            "--comment-keyword",
            default="$SETUP_EQP",
            help="새 자동예약 규칙에 저장할 comment keyword입니다. 기본값은 $SETUP_EQP입니다.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="생성 예정 카운트만 계산하고 DB 변경을 롤백합니다.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """JSON seed를 실행하고 결과를 출력합니다."""

        rows = _load_seed_rows(file_path=str(options.get("file") or ""))
        dry_run = bool(options.get("dry_run"))
        with transaction.atomic():
            result = services.seed_drone_sop_notification_defaults_from_rows(
                rows=rows,
                template_key=str(options.get("template_key") or "common"),
                comment_keyword=str(options.get("comment_keyword") or "$SETUP_EQP"),
            )
            if dry_run:
                transaction.set_rollback(True)

        counts = " ".join(f"{key}={value}" for key, value in result.as_dict().items())
        prefix = "dry-run: " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}drone JSON target seed complete: {counts}"))
