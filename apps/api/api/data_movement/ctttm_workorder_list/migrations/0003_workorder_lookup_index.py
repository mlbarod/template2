# Codex가 2026-07-07에 생성

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ctttm_workorder_list", "0002_lookup_index"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="ctttmworkorderlist",
            index=models.Index(
                fields=["workorder_id", "-inprg_date", "-id"],
                name="idx_ctttm_wo_dt_id",
            ),
        ),
    ]
