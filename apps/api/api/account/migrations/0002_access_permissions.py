# Django 5.2.14가 2026-07-11 01:16에 생성

import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


DEFAULT_ACCESS_SCOPE = "portal"
DEFAULT_ACCESS_SCOPE_NAME = "Portal"
DEFAULT_ACCESS_DEPARTMENT = "메모리Etch기술팀(글로벌 제조&인프라총괄)"
ACCESS_MANAGERS_GROUP_NAME = "Access Managers"
MANAGE_ACCESS_CODENAME = "manage_access"
MANAGE_ACCESS_NAME = "포털 및 앱 접근 권한 관리"
APP_ACCESS_SCOPES = (
    ("appstore", "Appstore"),
    ("line-dashboard", "ESOP Dashboard"),
    ("observer", "Observer"),
    ("emails", "Emails"),
    ("l3-spider", "L3 Spider"),
    ("fdc-trend", "FDC Trend"),
    ("pm-spider", "PM Spider"),
    ("tttm-spider", "TTTM Spider"),
    ("teamstaff", "Teamstaff"),
    ("voc", "VoE"),
    ("assistant", "Assistant"),
    ("access-stats", "접속 현황"),
)


def _seed_access_scopes(apps):
    """포털과 앱 접근 scope 및 기본 부서 정책을 생성합니다."""

    AccessPolicyRule = apps.get_model("account", "AccessPolicyRule")
    AccessScope = apps.get_model("account", "AccessScope")

    portal_scope, _created = AccessScope.objects.get_or_create(
        key=DEFAULT_ACCESS_SCOPE,
        defaults={
            "name": DEFAULT_ACCESS_SCOPE_NAME,
            "scope_type": "portal",
            "is_active": True,
            "requestable": True,
            "default_role": "viewer",
        },
    )
    AccessPolicyRule.objects.get_or_create(
        scope=portal_scope,
        rule_type="department",
        value=DEFAULT_ACCESS_DEPARTMENT,
        defaults={"role": "viewer", "is_active": True},
    )

    for key, name in APP_ACCESS_SCOPES:
        scope, created = AccessScope.objects.get_or_create(
            key=key,
            defaults={
                "name": name,
                "scope_type": "app",
                "is_active": True,
                "requestable": False,
                "default_role": "viewer",
            },
        )
        if not created and scope.scope_type != "app":
            raise RuntimeError(f"AccessScope '{key}'의 scope_type이 app이 아닙니다.")


def _backfill_existing_user_app_access(apps):
    """적용 시점의 기존 사용자에게 활성 앱의 누락 권한을 허용합니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    UserAccess = apps.get_model("account", "UserAccess")
    User = apps.get_model("account", "User")

    users = list(User.objects.values_list("id", "department"))
    scopes = AccessScope.objects.filter(scope_type="app", is_active=True)
    now = timezone.now()
    for scope in scopes:
        existing_user_ids = set(
            UserAccess.objects.filter(scope_id=scope.id).values_list("user_id", flat=True)
        )
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
                if user_id not in existing_user_ids
            ],
            batch_size=1000,
        )


def _migrate_access_managers(apps):
    """기존 프로필 관리자와 직접 permission 보유자를 표준 그룹으로 이전합니다."""

    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("account", "User")
    UserProfile = apps.get_model("account", "UserProfile")

    content_type, _created = ContentType.objects.get_or_create(
        app_label="account",
        model="user",
    )
    permission, _created = Permission.objects.get_or_create(
        content_type=content_type,
        codename=MANAGE_ACCESS_CODENAME,
        defaults={"name": MANAGE_ACCESS_NAME},
    )
    group, _created = Group.objects.get_or_create(name=ACCESS_MANAGERS_GROUP_NAME)
    group.permissions.add(permission)

    user_permission_model = User.user_permissions.through
    user_ids = set(
        UserProfile.objects.filter(role="admin").values_list("user_id", flat=True)
    )
    user_ids.update(
        user_permission_model.objects.filter(permission_id=permission.id).values_list(
            "user_id",
            flat=True,
        )
    )
    user_group_model = User.groups.through
    existing_user_ids = set(
        user_group_model.objects.filter(
            group_id=group.id,
            user_id__in=user_ids,
        ).values_list("user_id", flat=True)
    )
    user_group_model.objects.bulk_create(
        [
            user_group_model(group_id=group.id, user_id=user_id)
            for user_id in user_ids
            if user_id not in existing_user_ids
        ],
        ignore_conflicts=True,
    )
    user_permission_model.objects.filter(permission_id=permission.id).delete()


def seed_access_permission_data(apps, _schema_editor):
    """통합 권한 migration의 초기 데이터와 기존 사용자 승계를 적용합니다."""

    _seed_access_scopes(apps)
    _backfill_existing_user_app_access(apps)
    _migrate_access_managers(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='user',
            options={'permissions': [('manage_access', '포털 및 앱 접근 권한 관리')]},
        ),
        migrations.CreateModel(
            name='AccessScope',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=64, unique=True)),
                ('name', models.CharField(max_length=128)),
                ('scope_type', models.CharField(choices=[('portal', 'Portal'), ('app', 'App'), ('feature', 'Feature')], default='app', max_length=16)),
                ('is_active', models.BooleanField(default=True)),
                ('requestable', models.BooleanField(default=True)),
                ('default_role', models.CharField(choices=[('viewer', 'Viewer'), ('member', 'Member'), ('manager', 'Manager'), ('admin', 'Admin')], default='viewer', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'account_access_scope',
                'indexes': [models.Index(fields=['scope_type'], name='idx_acc_acc_scp_typ'), models.Index(fields=['is_active'], name='idx_acc_acc_scp_act')],
                'constraints': [models.CheckConstraint(condition=models.Q(('scope_type__in', ('portal', 'app', 'feature'))), name='chk_acc_scp_typ_valid'), models.CheckConstraint(condition=models.Q(('default_role__in', ('viewer', 'member', 'manager', 'admin'))), name='chk_acc_scp_role_valid'), models.CheckConstraint(condition=models.Q(models.Q(('scope_type', 'app'), _negated=True), ('requestable', False), _connector='OR'), name='chk_acc_scp_app_not_req')],
            },
        ),
        migrations.CreateModel(
            name='AccessPolicyRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rule_type', models.CharField(choices=[('department', 'Department')], max_length=32)),
                ('value', models.CharField(blank=True, max_length=150)),
                ('role', models.CharField(choices=[('viewer', 'Viewer'), ('member', 'Member'), ('manager', 'Manager'), ('admin', 'Admin')], default='viewer', max_length=16)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('scope', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='policy_rules', to='account.accessscope')),
            ],
            options={
                'db_table': 'account_access_policy_rule',
            },
        ),
        migrations.CreateModel(
            name='AccessAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('request', 'Request'), ('approve', 'Approve'), ('reject', 'Reject'), ('grant', 'Grant'), ('revoke', 'Revoke'), ('reset_to_policy', 'Reset to policy'), ('change_role', 'Change role'), ('user_access_update', 'User access update'), ('policy_create', 'Policy create'), ('policy_update', 'Policy update'), ('policy_delete', 'Policy delete'), ('scope_create', 'Scope create'), ('scope_update', 'Scope update'), ('scope_delete', 'Scope delete'), ('access_manager_grant', 'Access manager grant'), ('access_manager_revoke', 'Access manager revoke')], max_length=32)),
                ('before', models.JSONField(blank=True, default=dict)),
                ('after', models.JSONField(blank=True, default=dict)),
                ('reason', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_audit_actions', to=settings.AUTH_USER_MODEL)),
                ('target_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_audit_targets', to=settings.AUTH_USER_MODEL)),
                ('policy_rule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='account.accesspolicyrule')),
                ('scope', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='account.accessscope')),
            ],
            options={
                'db_table': 'account_access_audit_log',
            },
        ),
        migrations.CreateModel(
            name='UserAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('department', models.CharField(blank=True, max_length=128, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('allowed', 'Allowed'), ('denied', 'Denied')], default='pending', max_length=16)),
                ('role', models.CharField(choices=[('viewer', 'Viewer'), ('member', 'Member'), ('manager', 'Manager'), ('admin', 'Admin')], default='viewer', max_length=16)),
                ('reason', models.TextField(blank=True, null=True)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_decisions', to=settings.AUTH_USER_MODEL)),
                ('scope', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_accesses', to='account.accessscope')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_grants', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'account_user_access',
            },
        ),
        migrations.AddIndex(
            model_name='accesspolicyrule',
            index=models.Index(fields=['scope', 'is_active'], name='idx_acc_pol_rule_scp_act'),
        ),
        migrations.AddIndex(
            model_name='accesspolicyrule',
            index=models.Index(fields=['rule_type'], name='idx_acc_pol_rule_typ'),
        ),
        migrations.AddConstraint(
            model_name='accesspolicyrule',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower(django.db.models.functions.text.Trim('value')), models.F('scope'), models.F('rule_type'), name='uniq_acc_pol_scp_typ_val_ci'),
        ),
        migrations.AddConstraint(
            model_name='accesspolicyrule',
            constraint=models.CheckConstraint(condition=models.Q(('rule_type', 'department')), name='chk_acc_pol_rule_typ_dep'),
        ),
        migrations.AddConstraint(
            model_name='accesspolicyrule',
            constraint=models.CheckConstraint(condition=models.Q(('role__in', ('viewer', 'member', 'manager', 'admin'))), name='chk_acc_pol_role_valid'),
        ),
        migrations.AddIndex(
            model_name='accessauditlog',
            index=models.Index(fields=['scope', 'created_at'], name='idx_acc_aud_scp_ct'),
        ),
        migrations.AddIndex(
            model_name='accessauditlog',
            index=models.Index(fields=['target_user', 'created_at'], name='idx_acc_aud_tgt_ct'),
        ),
        migrations.AddIndex(
            model_name='accessauditlog',
            index=models.Index(fields=['actor', 'created_at'], name='idx_acc_aud_act_ct'),
        ),
        migrations.AddIndex(
            model_name='accessauditlog',
            index=models.Index(fields=['action'], name='idx_acc_aud_action'),
        ),
        migrations.AddIndex(
            model_name='useraccess',
            index=models.Index(fields=['scope'], name='idx_acc_usr_acc_scp'),
        ),
        migrations.AddIndex(
            model_name='useraccess',
            index=models.Index(fields=['status'], name='idx_acc_usr_acc_sts'),
        ),
        migrations.AddIndex(
            model_name='useraccess',
            index=models.Index(fields=['department'], name='idx_acc_usr_acc_dep'),
        ),
        migrations.AddConstraint(
            model_name='useraccess',
            constraint=models.UniqueConstraint(fields=('scope', 'user'), name='uniq_acc_usr_acc_scp_usr'),
        ),
        migrations.AddConstraint(
            model_name='useraccess',
            constraint=models.CheckConstraint(condition=models.Q(('status__in', ('pending', 'allowed', 'denied'))), name='chk_acc_usr_acc_sts_valid'),
        ),
        migrations.AddConstraint(
            model_name='useraccess',
            constraint=models.CheckConstraint(condition=models.Q(('role__in', ('viewer', 'member', 'manager', 'admin'))), name='chk_acc_usr_acc_role_valid'),
        ),
        migrations.RunPython(
            seed_access_permission_data,
            migrations.RunPython.noop,
        ),
    ]
