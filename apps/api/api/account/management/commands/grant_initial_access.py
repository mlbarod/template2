"""배포 초기 혼선을 막기 위해 현재 사용자에게 Portal/앱 접근 권한을 부여합니다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from api.account.models import (
    ACCESS_SCOPE_PORTAL,
    AccessAuditLog,
    AccessRole,
    AccessScope,
    UserAccess,
)


INITIAL_ACCESS_REASON = "초기 배포 전체 권한 부여"
INITIAL_ACCESS_MARKER_REASON = "초기 배포 전체 권한 부여 완료"
INITIAL_ACCESS_LOCK_ID = 917513070132


@dataclass(frozen=True)
class AccessTarget:
    """권한을 부여할 사용자와 scope 조합입니다."""

    user_id: int
    department: str | None
    scope_id: int


class Command(BaseCommand):
    """현재 사용자에게 Portal과 활성 앱 scope 접근 권한을 일괄 부여합니다."""

    help = "현재 활성 사용자에게 Portal과 활성 앱 전체 접근 권한을 allowed 상태로 부여합니다."

    def add_arguments(self, parser) -> None:
        """운영자가 dry-run과 기존 상태 덮어쓰기 여부를 선택할 수 있게 합니다."""

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB를 변경하지 않고 생성/변경 예정 건수만 출력합니다.",
        )
        parser.add_argument(
            "--overwrite-existing",
            action="store_true",
            help="기존 pending/denied 상태도 allowed로 변경합니다.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="완료 marker가 있어도 명시적으로 다시 실행합니다.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="bulk 작업 batch 크기입니다.",
        )

    def handle(self, *args, **options) -> None:
        """Portal과 활성 앱 scope의 누락 권한을 생성하고 필요 시 기존 상태를 갱신합니다."""

        dry_run = bool(options["dry_run"])
        overwrite_existing = bool(options["overwrite_existing"])
        force = bool(options["force"])
        batch_size = int(options["batch_size"] or 1000)
        if batch_size <= 0:
            raise CommandError("--batch-size는 1 이상이어야 합니다.")

        if not force and self._has_completion_marker():
            self.stdout.write("초기 접근 권한 부여가 이미 완료되어 건너뜁니다.")
            return

        if not dry_run:
            with transaction.atomic():
                self._acquire_run_lock()
                if not force and self._has_completion_marker():
                    self.stdout.write("초기 접근 권한 부여가 이미 완료되어 건너뜁니다.")
                    return
                rows_to_create, rows_to_update, audit_logs, plan_summary = self._build_plan(
                    overwrite_existing=overwrite_existing,
                )
                self._write_plan(
                    plan_summary=plan_summary,
                    rows_to_create=rows_to_create,
                    rows_to_update=rows_to_update,
                    dry_run=False,
                )
                UserAccess.objects.bulk_create(rows_to_create, batch_size=batch_size)
                if rows_to_update:
                    UserAccess.objects.bulk_update(
                        rows_to_update,
                        ["department", "status", "role", "reason", "decided_at", "updated_at"],
                        batch_size=batch_size,
                    )
                AccessAuditLog.objects.bulk_create(
                    [*audit_logs, self._build_completion_marker(plan_summary=plan_summary)],
                    batch_size=batch_size,
                )

            self.stdout.write(self.style.SUCCESS("초기 접근 권한 부여를 완료했습니다."))
            return

        rows_to_create, rows_to_update, _audit_logs, plan_summary = self._build_plan(
            overwrite_existing=overwrite_existing,
        )
        self._write_plan(
            plan_summary=plan_summary,
            rows_to_create=rows_to_create,
            rows_to_update=rows_to_update,
            dry_run=True,
        )

    def _build_plan(
        self,
        *,
        overwrite_existing: bool,
    ) -> tuple[list[UserAccess], list[UserAccess], list[AccessAuditLog], dict[str, int]]:
        """초기 권한 부여 실행 계획을 계산합니다."""

        scopes = self._get_target_scopes()
        users = self._get_active_users()
        targets = self._build_targets(scopes=scopes, users=users)
        existing_by_key = self._get_existing_access_rows(targets=targets)
        rows_to_create, rows_to_update, audit_logs = self._plan_changes(
            targets=targets,
            existing_by_key=existing_by_key,
            overwrite_existing=overwrite_existing,
        )
        return (
            rows_to_create,
            rows_to_update,
            audit_logs,
            {"users": len(users), "scopes": len(scopes)},
        )

    def _write_plan(
        self,
        *,
        plan_summary: dict[str, int],
        rows_to_create: list[UserAccess],
        rows_to_update: list[UserAccess],
        dry_run: bool,
    ) -> None:
        """실행 계획을 표준 출력에 남깁니다."""

        self.stdout.write(
            "초기 접근 권한 부여 계획: "
            f"users={plan_summary['users']}, scopes={plan_summary['scopes']}, "
            f"create={len(rows_to_create)}, update={len(rows_to_update)}, dryRun={dry_run}"
        )

    def _has_completion_marker(self) -> bool:
        """초기 권한 부여가 이미 완료되었는지 확인합니다."""

        return AccessAuditLog.objects.filter(
            action=AccessAuditLog.Actions.USER_ACCESS_UPDATE,
            after__marker="grant_initial_access",
            reason=INITIAL_ACCESS_MARKER_REASON,
        ).exists()

    def _acquire_run_lock(self) -> None:
        """PostgreSQL 환경에서 동시 시작 시 한 실행만 통과하도록 잠급니다."""

        if connection.vendor != "postgresql":
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [INITIAL_ACCESS_LOCK_ID])

    def _build_completion_marker(self, *, plan_summary: dict[str, int]) -> AccessAuditLog:
        """1회 실행 완료 여부를 판단할 marker 감사 로그를 생성합니다."""

        return AccessAuditLog(
            action=AccessAuditLog.Actions.USER_ACCESS_UPDATE,
            before={},
            after={
                "marker": "grant_initial_access",
                "users": plan_summary["users"],
                "scopes": plan_summary["scopes"],
            },
            reason=INITIAL_ACCESS_MARKER_REASON,
        )

    def _get_target_scopes(self) -> list[AccessScope]:
        """Portal과 활성 앱 scope를 Portal 우선 순서로 반환합니다."""

        portal_scope = AccessScope.objects.filter(key=ACCESS_SCOPE_PORTAL).first()
        if portal_scope is None:
            raise CommandError(f"Portal scope가 없습니다: {ACCESS_SCOPE_PORTAL}")
        if portal_scope.scope_type != AccessScope.ScopeTypes.PORTAL:
            raise CommandError(f"Portal scope 유형이 잘못되었습니다: {portal_scope.scope_type}")
        if not portal_scope.is_active:
            raise CommandError("Portal scope가 비활성 상태입니다.")

        app_scopes = list(
            AccessScope.objects.filter(
                scope_type=AccessScope.ScopeTypes.APP,
                is_active=True,
            ).order_by("key")
        )
        return [portal_scope, *app_scopes]

    def _get_active_users(self) -> list[dict[str, Any]]:
        """권한 부여 대상 활성 사용자 목록을 조회합니다."""

        User = get_user_model()
        return list(User.objects.filter(is_active=True).order_by("id").values("id", "department"))

    def _build_targets(
        self,
        *,
        scopes: list[AccessScope],
        users: list[dict[str, Any]],
    ) -> list[AccessTarget]:
        """사용자와 scope의 조합 목록을 생성합니다."""

        targets = []
        for user in users:
            department = self._normalize_department(user.get("department"))
            for scope in scopes:
                targets.append(
                    AccessTarget(
                        user_id=int(user["id"]),
                        department=department,
                        scope_id=scope.id,
                    )
                )
        return targets

    def _get_existing_access_rows(
        self,
        *,
        targets: list[AccessTarget],
    ) -> dict[tuple[int, int], UserAccess]:
        """대상 사용자/scope 조합의 기존 UserAccess row를 조회합니다."""

        if not targets:
            return {}
        user_ids = {target.user_id for target in targets}
        scope_ids = {target.scope_id for target in targets}
        rows = UserAccess.objects.filter(user_id__in=user_ids, scope_id__in=scope_ids)
        return {(row.user_id, row.scope_id): row for row in rows}

    def _plan_changes(
        self,
        *,
        targets: list[AccessTarget],
        existing_by_key: dict[tuple[int, int], UserAccess],
        overwrite_existing: bool,
    ) -> tuple[list[UserAccess], list[UserAccess], list[AccessAuditLog]]:
        """생성/수정할 UserAccess와 감사 로그를 계산합니다."""

        now = timezone.now()
        rows_to_create: list[UserAccess] = []
        rows_to_update: list[UserAccess] = []
        audit_logs: list[AccessAuditLog] = []
        for target in targets:
            existing = existing_by_key.get((target.user_id, target.scope_id))
            if existing is None:
                access = UserAccess(
                    scope_id=target.scope_id,
                    user_id=target.user_id,
                    department=target.department,
                    status=UserAccess.Status.ALLOWED,
                    role=AccessRole.VIEWER,
                    requested_at=now,
                    decided_at=now,
                    created_at=now,
                    updated_at=now,
                )
                rows_to_create.append(access)
                audit_logs.append(self._build_audit_log(target=target, before={}, after=self._snapshot(access)))
                continue

            if not overwrite_existing or existing.status == UserAccess.Status.ALLOWED:
                continue

            before = self._snapshot(existing)
            existing.department = target.department
            existing.status = UserAccess.Status.ALLOWED
            existing.role = AccessRole.VIEWER
            existing.reason = None
            existing.decided_at = now
            existing.updated_at = now
            rows_to_update.append(existing)
            audit_logs.append(self._build_audit_log(target=target, before=before, after=self._snapshot(existing)))

        return rows_to_create, rows_to_update, audit_logs

    def _build_audit_log(
        self,
        *,
        target: AccessTarget,
        before: dict[str, object],
        after: dict[str, object],
    ) -> AccessAuditLog:
        """초기 권한 부여 감사 로그 row를 생성합니다."""

        return AccessAuditLog(
            scope_id=target.scope_id,
            target_user_id=target.user_id,
            action=AccessAuditLog.Actions.GRANT,
            before=before,
            after=after,
            reason=INITIAL_ACCESS_REASON,
        )

    @staticmethod
    def _snapshot(access: UserAccess) -> dict[str, object]:
        """감사 로그에 남길 접근 권한 상태를 직렬화합니다."""

        return {
            "scopeId": access.scope_id,
            "userId": access.user_id,
            "department": access.department,
            "status": access.status,
            "role": access.role,
            "reason": access.reason,
        }

    @staticmethod
    def _normalize_department(value: Any) -> str | None:
        """부서 문자열을 공백 제거 기준으로 정규화합니다."""

        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None
