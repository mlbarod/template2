"""ct_process_comment OpenWebUI 요약 management command입니다."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from api.data_movement.ct_process_comment import services


class Command(BaseCommand):
    """Airflow에서 호출할 ct_process_comment 요약 command입니다."""

    help = "Summarize CT_PROCESS_COMMENT rows with update_flag=Y via OpenWebUI."

    def add_arguments(self, parser) -> None:
        """command 옵션을 등록합니다."""

        parser.add_argument("--limit", dest="limit", type=int, help="처리할 최대 row 수")
        parser.add_argument("--workorder-id", dest="workorder_id", help="특정 workorder_id만 처리")
        parser.add_argument("--dry-run", dest="dry_run", action="store_true", help="외부 호출/DB 반영 없이 대상만 확인")

    def handle(self, *args, **options) -> None:
        """ct_process_comment OpenWebUI 요약을 실행합니다."""

        limit = options.get("limit")
        if limit is not None and limit < 1:
            raise CommandError("--limit은 1 이상이어야 합니다.")

        summary = services.summarize_pending_ct_process_comments(
            limit=limit,
            workorder_id=options.get("workorder_id"),
            dry_run=options["dry_run"],
        )

        if summary.processed_count == 0:
            self.stdout.write("요약 대상 없음")
            return

        for outcome in summary.outcomes:
            message = f"{outcome.status}: workorder_id={outcome.workorder_id}"
            if outcome.error_message:
                message = f"{message}, error={outcome.error_message}"
            self.stdout.write(message)

        self.stdout.write(
            f"summary: processed={summary.processed_count}, "
            f"success={summary.success_count}, failed={summary.failure_count}, "
            f"skipped={summary.skipped_count}, dry_run={summary.dry_run_count}"
        )
        if summary.failure_count:
            raise CommandError(f"ct_process_comment 요약 실패 row 수: {summary.failure_count}")
