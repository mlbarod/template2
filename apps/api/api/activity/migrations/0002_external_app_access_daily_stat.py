# Django 5.2.14가 2026-06-29에 생성

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("activity", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalAppAccessDailyStat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("app_id", models.CharField(max_length=120)),
                ("app_name", models.CharField(max_length=160)),
                ("stat_date", models.DateField(db_index=True)),
                ("access_count", models.PositiveIntegerField(default=0)),
                ("unique_user_count", models.PositiveIntegerField(default=0)),
                ("source_type", models.CharField(default="manual", max_length=32)),
                ("source_name", models.CharField(default="manual", max_length=80)),
                ("memo", models.TextField(blank=True)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "activity_external_app_access_daily_stat",
                "ordering": ["-stat_date", "app_name", "app_id"],
            },
        ),
        migrations.AddIndex(
            model_name="externalappaccessdailystat",
            index=models.Index(fields=["stat_date", "app_id"], name="idx_act_ext_date_app"),
        ),
        migrations.AddConstraint(
            model_name="externalappaccessdailystat",
            constraint=models.UniqueConstraint(
                fields=("app_id", "stat_date", "source_name"),
                name="uniq_act_ext_daily_key",
            ),
        ),
    ]
