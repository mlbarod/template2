# Django 5.2.14 기준 scope 기반 접근 권한 모델 추가

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


DEFAULT_ACCESS_SCOPE = "portal"
DEFAULT_ACCESS_SCOPE_NAME = "Portal"
DEFAULT_ACCESS_DEPARTMENT = "메모리Etch기술팀(글로벌 제조&인프라총괄)"


def seed_default_access_scope(apps, schema_editor):
    """기본 portal scope와 department 정책을 생성합니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    AccessPolicyRule = apps.get_model("account", "AccessPolicyRule")

    scope, _created = AccessScope.objects.get_or_create(
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
        scope=scope,
        rule_type="department",
        value=DEFAULT_ACCESS_DEPARTMENT,
        defaults={
            "role": "viewer",
            "is_active": True,
        },
    )


def unseed_default_access_scope(apps, schema_editor):
    """롤백 시 기본 portal scope를 제거합니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    AccessScope.objects.filter(key=DEFAULT_ACCESS_SCOPE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccessScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=128)),
                (
                    "scope_type",
                    models.CharField(
                        choices=[("portal", "Portal"), ("app", "App"), ("feature", "Feature")],
                        default="app",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("requestable", models.BooleanField(default=True)),
                (
                    "default_role",
                    models.CharField(
                        choices=[("viewer", "Viewer"), ("member", "Member"), ("manager", "Manager"), ("admin", "Admin")],
                        default="viewer",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "account_access_scope",
                "indexes": [
                    models.Index(fields=["scope_type"], name="idx_acc_acc_scp_typ"),
                    models.Index(fields=["is_active"], name="idx_acc_acc_scp_act"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AccessPolicyRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "rule_type",
                    models.CharField(
                        choices=[
                            ("department", "Department"),
                            ("profile_role", "Profile Role"),
                            ("user_sdwt_prod_role", "User SDWT Prod Role"),
                            ("authenticated", "Authenticated"),
                        ],
                        max_length=32,
                    ),
                ),
                ("value", models.CharField(blank=True, max_length=150)),
                (
                    "role",
                    models.CharField(
                        choices=[("viewer", "Viewer"), ("member", "Member"), ("manager", "Manager"), ("admin", "Admin")],
                        default="viewer",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "scope",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="policy_rules",
                        to="account.accessscope",
                    ),
                ),
            ],
            options={
                "db_table": "account_access_policy_rule",
                "indexes": [
                    models.Index(fields=["scope", "is_active"], name="idx_acc_pol_rule_scp_act"),
                    models.Index(fields=["rule_type"], name="idx_acc_pol_rule_typ"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("scope", "rule_type", "value"), name="uniq_acc_pol_rule_scp_val"),
                ],
            },
        ),
        migrations.CreateModel(
            name="UserAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department", models.CharField(blank=True, max_length=128, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("allowed", "Allowed"), ("denied", "Denied")],
                        default="pending",
                        max_length=16,
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[("viewer", "Viewer"), ("member", "Member"), ("manager", "Manager"), ("admin", "Admin")],
                        default="viewer",
                        max_length=16,
                    ),
                ),
                ("reason", models.TextField(blank=True, null=True)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="access_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "scope",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_accesses",
                        to="account.accessscope",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_grants",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "account_user_access",
                "indexes": [
                    models.Index(fields=["scope"], name="idx_acc_usr_acc_scp"),
                    models.Index(fields=["status"], name="idx_acc_usr_acc_sts"),
                    models.Index(fields=["department"], name="idx_acc_usr_acc_dep"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("scope", "user"), name="uniq_acc_usr_acc_scp_usr"),
                ],
            },
        ),
        migrations.RunPython(seed_default_access_scope, unseed_default_access_scope),
    ]
