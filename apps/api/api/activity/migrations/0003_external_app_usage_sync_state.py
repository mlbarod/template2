from __future__ import annotations

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("activity", "0002_external_app_access_daily_stat"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalAppUsageSyncState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sync_key", models.CharField(max_length=80, unique=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_status", models.CharField(default="never", max_length=32)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "activity_external_app_usage_sync_state",
                "ordering": ["sync_key"],
            },
        ),
    ]
