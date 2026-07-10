# Django 5.2.14 기준 접근 요청과 scope 변경 감사 action 추가

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0003_access_audit_log"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accessauditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("request", "Request"),
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
                    ("scope_create", "Scope create"),
                    ("scope_update", "Scope update"),
                    ("scope_delete", "Scope delete"),
                ],
                max_length=32,
            ),
        ),
    ]
