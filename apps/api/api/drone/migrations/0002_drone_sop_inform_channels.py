# Django 5.2.9로 2026-02-25 00:00에 생성

import django.db.models.functions.datetime
from django.db import migrations, models
from django.db.models import Q


def _copy_jira_user_templates(apps, schema_editor):  # 커버리지 제외: pragma: no cover
    old_model = apps.get_model("drone", "DroneSopJiraUserTemplate")
    new_model = apps.get_model("drone", "DroneSopUserSdwtChannel")

    rows = []
    for row in old_model.objects.all():
        target = (row.user_sdwt_prod or "").strip()
        if not target:
            continue
        rows.append(
            new_model(
                target_user_sdwt_prod=target,
                jira_key=row.jira_key or None,
                jira_template_key=row.template_key or None,
                is_active=True,
            )
        )

    if rows:
        new_model.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("drone", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dronesop",
            name="send_mail",
            field=models.SmallIntegerField(blank=True, db_default=0, default=0, null=True),
        ),
        migrations.AddField(
            model_name="dronesop",
            name="send_messenger",
            field=models.SmallIntegerField(blank=True, db_default=0, default=0, null=True),
        ),
        migrations.AddField(
            model_name="dronesop",
            name="jira_reason",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="dronesop",
            name="mail_reason",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="dronesop",
            name="messenger_reason",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name="dronesop",
            name="sdwt_prod",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name="dronesop",
            name="user_sdwt_prod",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.CreateModel(
            name="DroneSopUserSdwtChannel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_user_sdwt_prod", models.CharField(max_length=64)),
                ("jira_key", models.CharField(blank=True, max_length=64, null=True)),
                ("chatroom_id", models.BigIntegerField(blank=True, null=True)),
                ("jira_template_key", models.CharField(blank=True, max_length=50, null=True)),
                ("mail_template_key", models.CharField(blank=True, max_length=50, null=True)),
                ("messenger_template_key", models.CharField(blank=True, max_length=50, null=True)),
                ("jira_enabled", models.BooleanField(default=True)),
                ("messenger_enabled", models.BooleanField(default=True)),
                ("mail_enabled", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_default=django.db.models.functions.datetime.Now()),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, db_default=django.db.models.functions.datetime.Now()),
                ),
            ],
            options={
                "db_table": "drone_sop_user_sdwt_channel",
                "constraints": [
                    models.UniqueConstraint(fields=("target_user_sdwt_prod",), name="uniq_dro_sop_usr_chn"),
                ],
            },
        ),
        migrations.RunPython(
            _copy_jira_user_templates,
            migrations.RunPython.noop,
        ),
        migrations.CreateModel(
            name="DroneSopUserSdwtProdMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sdwt_prod", models.CharField(blank=True, max_length=64, null=True)),
                ("user_sdwt_prod", models.CharField(blank=True, max_length=64, null=True)),
                ("target_user_sdwt_prod", models.CharField(max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_default=django.db.models.functions.datetime.Now()),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, db_default=django.db.models.functions.datetime.Now()),
                ),
            ],
            options={
                "db_table": "drone_sop_user_sdwt_map",
                "constraints": [
                    models.CheckConstraint(
                        check=(
                            (Q(("sdwt_prod__isnull", False)) & ~Q(("sdwt_prod", "")))
                            | (Q(("user_sdwt_prod__isnull", False)) & ~Q(("user_sdwt_prod", "")))
                        ),
                        name="chk_dro_sop_sdw_usr_req",
                    ),
                    models.UniqueConstraint(
                        fields=("sdwt_prod", "user_sdwt_prod"),
                        condition=(
                            Q(("sdwt_prod__isnull", False))
                            & ~Q(("sdwt_prod", ""))
                            & Q(("user_sdwt_prod__isnull", False))
                            & ~Q(("user_sdwt_prod", ""))
                        ),
                        name="uniq_dro_sop_sdw_usr_map",
                    ),
                    models.UniqueConstraint(
                        fields=("sdwt_prod",),
                        condition=(
                            Q(("sdwt_prod__isnull", False))
                            & ~Q(("sdwt_prod", ""))
                            & (Q(("user_sdwt_prod__isnull", True)) | Q(("user_sdwt_prod", "")))
                        ),
                        name="uniq_dro_sop_sdw_map",
                    ),
                    models.UniqueConstraint(
                        fields=("user_sdwt_prod",),
                        condition=(
                            Q(("user_sdwt_prod__isnull", False))
                            & ~Q(("user_sdwt_prod", ""))
                            & (Q(("sdwt_prod__isnull", True)) | Q(("sdwt_prod", "")))
                        ),
                        name="uniq_dro_sop_usr_map",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="DroneSopNeedToSendRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_user_sdwt_prod", models.CharField(max_length=64)),
                ("comment_last_at", models.CharField(max_length=64)),
                ("ignore_sample_type", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_default=django.db.models.functions.datetime.Now()),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, db_default=django.db.models.functions.datetime.Now()),
                ),
            ],
            options={
                "db_table": "drone_sop_needtosend_rule",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("target_user_sdwt_prod",),
                        name="uniq_dro_sop_nts_trg",
                    )
                ],
            },
        ),
        migrations.DeleteModel(
            name="DroneSopJiraUserTemplate",
        ),
    ]
