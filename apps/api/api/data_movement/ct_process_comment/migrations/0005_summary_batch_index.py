# Codex가 2026-07-07에 생성

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ct_process_comment", "0004_ctprocesscomment_llm_core_summary"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="ctprocesscomment",
            index=models.Index(
                fields=["-updated_at", "-id"],
                name="idx_ct_prc_cmt_pend",
                condition=models.Q(("update_flag", "Y")),
            ),
        ),
    ]
