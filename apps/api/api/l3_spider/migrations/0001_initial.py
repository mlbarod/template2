from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="L3SpiderExclusionFilter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_id", models.CharField(default="*", max_length=200)),
                ("process_id", models.CharField(default="*", max_length=200)),
                ("eds_step", models.CharField(default="*", max_length=200)),
                ("step_seq", models.CharField(default="*", max_length=200)),
                ("ppid", models.CharField(default="*", max_length=200)),
                ("eqpch", models.CharField(default="*", max_length=200)),
                ("bin_name", models.CharField(default="*", max_length=200)),
                ("date_from", models.DateField(blank=True, null=True)),
                ("date_to", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("memo", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="l3_spider_exclusion_filters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "l3_spider_exclusion_filter",
                "ordering": ["-created_at"],
            },
        ),
    ]
