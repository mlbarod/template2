# Codex가 2026-07-06에 생성

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ct_process_comment", "0003_ctprocesscomment_llm_summary"),
    ]

    operations = [
        migrations.AddField(
            model_name="ctprocesscomment",
            name="llm_core_summary",
            field=models.TextField(blank=True, null=True),
        ),
    ]
