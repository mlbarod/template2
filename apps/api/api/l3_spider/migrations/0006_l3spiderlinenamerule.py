# Django 5.2.14에서 2026-07-13 10:46에 생성했습니다.

import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("l3_spider", "0005_manage_index_tables"),
    ]

    operations = [
        migrations.CreateModel(
            name="L3SpiderLineNameRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "rule_type",
                    models.CharField(
                        choices=[("base", "Base"), ("override", "Override")],
                        max_length=16,
                    ),
                ),
                ("line_id", models.CharField(default="*", max_length=200)),
                ("process_id", models.CharField(default="*", max_length=200)),
                ("step_seq", models.CharField(default="*", max_length=200)),
                ("line_name", models.CharField(max_length=200)),
                ("priority", models.PositiveIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "l3_spider_line_name_rule",
                "ordering": ["priority", "id"],
                "indexes": [
                    models.Index(
                        fields=["is_active", "rule_type", "priority"],
                        name="idx_l3_line_rule_lookup",
                    ),
                    models.Index(fields=["line_name"], name="idx_l3_line_rule_name"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("rule_type__in", ["base", "override"])),
                        name="chk_l3_line_rule_type",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("rule_type", "base"), ("step_seq", "*")),
                            models.Q(("line_id", "*"), ("rule_type", "override")),
                            _connector="OR",
                        ),
                        name="chk_l3_line_rule_scope",
                    ),
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("rule_type"),
                        django.db.models.functions.text.Lower("line_id"),
                        django.db.models.functions.text.Lower("process_id"),
                        django.db.models.functions.text.Lower("step_seq"),
                        condition=models.Q(("is_active", True)),
                        name="uniq_l3_line_rule_key",
                    ),
                ],
            },
        ),
    ]
