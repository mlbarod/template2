"""배포 전 접근 권한 데이터와 운영 capability의 정합성을 점검합니다."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

from api.account.models import (
    ACCESS_MANAGERS_GROUP_NAME,
    ACCESS_SCOPE_PORTAL,
    MANAGE_ACCESS_PERMISSION,
    SYSTEM_APP_SCOPE_KEYS,
    AccessPolicyRule,
    AccessRole,
    AccessScope,
    UserAccess,
)


class Command(BaseCommand):
    """접근 권한 배포를 막아야 할 데이터 불일치를 보고합니다."""

    help = "접근 권한 scope, 정책, 사용자 권한, 관리자 그룹의 정합성을 점검합니다."

    def handle(self, *args, **options):
        """읽기 전용 점검을 실행하고 문제가 있으면 실패 코드로 종료합니다."""

        findings = [
            *self._check_system_scopes(),
            *self._check_app_boolean_contract(),
            *self._check_policy_values(),
            *self._check_access_manager_group(),
        ]
        if findings:
            details = "\n".join(f"- {finding}" for finding in findings)
            raise CommandError(f"접근 권한 무결성 점검에 실패했습니다.\n{details}")

        self.stdout.write(self.style.SUCCESS("접근 권한 무결성 점검을 통과했습니다."))

    def _check_system_scopes(self) -> list[str]:
        """코드가 요구하는 시스템 scope의 존재와 유형을 확인합니다."""

        expected_types = {ACCESS_SCOPE_PORTAL: AccessScope.ScopeTypes.PORTAL}
        expected_types.update({key: AccessScope.ScopeTypes.APP for key in SYSTEM_APP_SCOPE_KEYS})
        scopes = AccessScope.objects.filter(key__in=expected_types).in_bulk(field_name="key")
        findings = []
        for key, expected_type in expected_types.items():
            scope = scopes.get(key)
            if scope is None:
                findings.append(f"시스템 scope가 없습니다: {key}")
            elif scope.scope_type != expected_type:
                findings.append(
                    f"시스템 scope 유형이 잘못되었습니다: {key}={scope.scope_type}, expected={expected_type}"
                )
        return findings

    def _check_app_boolean_contract(self) -> list[str]:
        """앱 scope와 연결된 role 값이 boolean 권한 계약을 따르는지 확인합니다."""

        findings = []
        app_scopes = AccessScope.objects.filter(scope_type=AccessScope.ScopeTypes.APP)
        invalid_scope_count = app_scopes.exclude(default_role=AccessRole.VIEWER).count()
        if invalid_scope_count:
            findings.append(f"boolean 계약을 벗어난 앱 scope가 {invalid_scope_count}건입니다.")

        invalid_policy_count = AccessPolicyRule.objects.filter(
            scope__scope_type=AccessScope.ScopeTypes.APP,
        ).exclude(role=AccessRole.VIEWER).count()
        if invalid_policy_count:
            findings.append(f"viewer가 아닌 앱 정책이 {invalid_policy_count}건입니다.")

        invalid_access_count = UserAccess.objects.filter(
            scope__scope_type=AccessScope.ScopeTypes.APP,
        ).exclude(role=AccessRole.VIEWER).count()
        if invalid_access_count:
            findings.append(f"viewer가 아닌 앱 사용자 권한이 {invalid_access_count}건입니다.")
        return findings

    def _check_policy_values(self) -> list[str]:
        """정책 값의 공백과 대소문자를 정규화했을 때 중복이 없는지 확인합니다."""

        findings = []
        seen_keys = {}
        for rule in AccessPolicyRule.objects.order_by("id").only("id", "scope_id", "rule_type", "value"):
            normalized_value = (rule.value or "").strip()
            if not normalized_value:
                findings.append(f"정책 값이 비어 있습니다: id={rule.id}")
                continue
            if rule.value != normalized_value:
                findings.append(f"정책 값 앞뒤에 공백이 있습니다: id={rule.id}")
            semantic_key = (rule.scope_id, rule.rule_type, normalized_value.casefold())
            if semantic_key in seen_keys:
                findings.append(
                    f"의미상 중복 정책이 있습니다: id={seen_keys[semantic_key]}, id={rule.id}"
                )
            else:
                seen_keys[semantic_key] = rule.id
        return findings

    def _check_access_manager_group(self) -> list[str]:
        """표준 권한 관리자 그룹이 capability permission을 보유하는지 확인합니다."""

        app_label, codename = MANAGE_ACCESS_PERMISSION.split(".", maxsplit=1)
        permission = Permission.objects.filter(
            content_type__app_label=app_label,
            codename=codename,
        ).first()
        if permission is None:
            return [f"permission이 없습니다: {MANAGE_ACCESS_PERMISSION}"]

        has_permission = Group.objects.filter(
            name=ACCESS_MANAGERS_GROUP_NAME,
            permissions=permission,
        ).exists()
        if not has_permission:
            return [
                f"{ACCESS_MANAGERS_GROUP_NAME} 그룹에 {MANAGE_ACCESS_PERMISSION} permission이 없습니다."
            ]
        return []
