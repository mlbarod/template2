# Django 5.2.14가 2026-05-27에 생성

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drone", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dronesop",
            name="ctttm_urls",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
