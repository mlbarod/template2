from django.db import migrations
from django.utils import timezone


LEGACY_L0_SCOPE_KEY = "fdc-trend"
LEGACY_L0_SCOPE_NAME = "FDC Trend"
L0_SCOPE_KEY = "l0-spider"
L0_SCOPE_NAME = "L0 Spider"
L1_SCOPE_KEY = "l1-spider"
L1_SCOPE_NAME = "L1 Spider"


def _require_app_scope(scope, *, key):
    """기존 scope가 앱 권한 계약과 충돌하지 않는지 확인합니다."""

    if scope.scope_type != "app":
        raise RuntimeError(f"AccessScope '{key}'의 scope_type이 app이 아닙니다.")


def _backfill_new_scopes(apps, *, scopes):
    """이번 migration에서 새로 만든 앱 scope를 기존 사용자에게 승계합니다."""

    if not scopes:
        return

    User = apps.get_model("account", "User")
    UserAccess = apps.get_model("account", "UserAccess")
    users = list(User.objects.values_list("id", "department"))
    now = timezone.now()
    for scope in scopes:
        UserAccess.objects.bulk_create(
            [
                UserAccess(
                    scope_id=scope.id,
                    user_id=user_id,
                    department=(department or "").strip() or None,
                    status="allowed",
                    role="viewer",
                    requested_at=now,
                    decided_at=now,
                    created_at=now,
                    updated_at=now,
                )
                for user_id, department in users
            ],
            batch_size=1000,
            ignore_conflicts=True,
        )


def migrate_spider_access_scopes(apps, _schema_editor):
    """기존 FDC scope와 결정을 L0로 옮기고 L1 scope를 추가합니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    legacy_scope = AccessScope.objects.filter(key=LEGACY_L0_SCOPE_KEY).first()
    l0_scope = AccessScope.objects.filter(key=L0_SCOPE_KEY).first()
    if legacy_scope is not None and l0_scope is not None:
        raise RuntimeError(
            f"AccessScope '{LEGACY_L0_SCOPE_KEY}'와 '{L0_SCOPE_KEY}'가 동시에 존재합니다."
        )

    created_scopes = []
    if legacy_scope is not None:
        _require_app_scope(legacy_scope, key=LEGACY_L0_SCOPE_KEY)
        legacy_scope.key = L0_SCOPE_KEY
        legacy_scope.name = L0_SCOPE_NAME
        legacy_scope.save(update_fields=["key", "name", "updated_at"])
        l0_scope = legacy_scope
    elif l0_scope is not None:
        _require_app_scope(l0_scope, key=L0_SCOPE_KEY)
        if l0_scope.name != L0_SCOPE_NAME:
            l0_scope.name = L0_SCOPE_NAME
            l0_scope.save(update_fields=["name", "updated_at"])
    else:
        l0_scope = AccessScope.objects.create(
            key=L0_SCOPE_KEY,
            name=L0_SCOPE_NAME,
            scope_type="app",
            is_active=True,
            requestable=False,
            default_role="viewer",
        )
        created_scopes.append(l0_scope)

    l1_scope, l1_created = AccessScope.objects.get_or_create(
        key=L1_SCOPE_KEY,
        defaults={
            "name": L1_SCOPE_NAME,
            "scope_type": "app",
            "is_active": True,
            "requestable": False,
            "default_role": "viewer",
        },
    )
    _require_app_scope(l1_scope, key=L1_SCOPE_KEY)
    if l1_created:
        created_scopes.append(l1_scope)

    _backfill_new_scopes(apps, scopes=created_scopes)


def restore_legacy_fdc_scope(apps, _schema_editor):
    """코드 롤백 시 L0 scope 키를 기존 FDC 키로 되돌립니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    legacy_scope = AccessScope.objects.filter(key=LEGACY_L0_SCOPE_KEY).first()
    l0_scope = AccessScope.objects.filter(key=L0_SCOPE_KEY).first()
    if legacy_scope is not None and l0_scope is not None:
        raise RuntimeError(
            f"AccessScope '{LEGACY_L0_SCOPE_KEY}'와 '{L0_SCOPE_KEY}'가 동시에 존재합니다."
        )
    if l0_scope is None:
        return

    _require_app_scope(l0_scope, key=L0_SCOPE_KEY)
    l0_scope.key = LEGACY_L0_SCOPE_KEY
    l0_scope.name = LEGACY_L0_SCOPE_NAME
    l0_scope.save(update_fields=["key", "name", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0002_access_permissions"),
    ]

    operations = [
        migrations.RunPython(
            migrate_spider_access_scopes,
            restore_legacy_fdc_scope,
        ),
    ]
