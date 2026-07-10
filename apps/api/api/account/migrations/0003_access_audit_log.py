# Django 5.2.14 기준 scope 접근 권한 감사 로그 모델 추가

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0002_access_scope"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AccessAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("approve", "Approve"),
                            ("reject", "Reject"),
                            ("grant", "Grant"),
                            ("revoke", "Revoke"),
                            ("reset_to_policy", "Reset to policy"),
                            ("change_role", "Change role"),
                            ("user_access_update", "User access update"),
                            ("policy_create", "Policy create"),
                            ("policy_update", "Policy update"),
                            ("policy_delete", "Policy delete"),
                        ],
                        max_length=32,
                    ),
                ),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
                ("reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="access_audit_actions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "policy_rule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="account.accesspolicyrule",
                    ),
                ),
                (
                    "scope",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="account.accessscope",
                    ),
                ),
                (
                    "target_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="access_audit_targets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "account_access_audit_log",
                "indexes": [
                    models.Index(fields=["scope", "created_at"], name="idx_acc_aud_scp_ct"),
                    models.Index(fields=["target_user", "created_at"], name="idx_acc_aud_tgt_ct"),
                    models.Index(fields=["actor", "created_at"], name="idx_acc_aud_act_ct"),
                    models.Index(fields=["action"], name="idx_acc_aud_action"),
                ],
            },
        ),
    ]
