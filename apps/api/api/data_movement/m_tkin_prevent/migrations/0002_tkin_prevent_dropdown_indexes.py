# Django 5.2.14가 2026-06-29에 생성

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("m_tkin_prevent", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="mtkinprevent",
            index=models.Index(
                fields=["eqp_id", "registration_level", "process_id"],
                name="idx_mtk_eqp_lvl_proc",
            ),
        ),
        migrations.AddIndex(
            model_name="mtkinprevent",
            index=models.Index(
                fields=["process_id", "eqp_id", "registration_level", "step_seq"],
                name="idx_mtk_prc_eqp_lvl_stp",
            ),
        ),
    ]
