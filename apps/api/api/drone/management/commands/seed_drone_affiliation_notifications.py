# =============================================================================
# 모듈: Drone SOP account 소속 기반 알림 초기 세팅 커맨드
# 주요 기능: Drone SOP/발송 이력/알림 설정 초기화 후 재생성
# 불변 조건: account 소속은 seed 입력 source로만 사용합니다.
# =============================================================================
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from api.drone import services


class Command(BaseCommand):
    """account 소속 기준으로 Drone SOP 알림 기본 설정을 생성합니다."""

    help = "Seed Drone SOP notification targets, mappings, channels, and recipients from account affiliations."

    def add_arguments(self, parser) -> None:
        """커맨드 옵션을 등록합니다."""

        parser.add_argument(
            "--line-id",
            default="",
            help="특정 line_id만 초기 세팅합니다. 생략하면 전체 account_affiliation을 대상으로 합니다.",
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
        """초기 세팅을 실행하고 결과를 출력합니다."""

        dry_run = bool(options.get("dry_run"))
        with transaction.atomic():
            result = services.seed_drone_sop_affiliation_notification_defaults(
                line_id=str(options.get("line_id") or ""),
                template_key=str(options.get("template_key") or "common"),
                comment_keyword=str(options.get("comment_keyword") or "$SETUP_EQP"),
            )
            if dry_run:
                transaction.set_rollback(True)

        counts = " ".join(f"{key}={value}" for key, value in result.as_dict().items())
        prefix = "dry-run: " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}drone affiliation notification seed complete: {counts}"))
