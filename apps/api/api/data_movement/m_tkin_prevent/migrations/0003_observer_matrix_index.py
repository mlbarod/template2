# Codex가 2026-07-07에 생성

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("m_tkin_prevent", "0002_tkin_prevent_dropdown_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="mtkinprevent",
            index=models.Index(
                fields=["process_id", "step_seq", "registration_level", "eqp_id"],
                name="idx_mtk_prc_stp_lvl_eqp",
            ),
        ),
    ]
