from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion
import django.db.models.functions


def reset_target_configuration(apps, schema_editor):
    """기존 target 계열 설정을 삭제하고 새 정규화 구조를 빈 상태로 시작합니다."""

    DroneSopTarget = apps.get_model("drone", "DroneSopTarget")
    DroneSopTargetMapping = apps.get_model("drone", "DroneSopTargetMapping")
    DroneSopTargetRecipient = apps.get_model("drone", "DroneSopTargetRecipient")
    DroneSopTargetChannelConfig = apps.get_model("drone", "DroneSopTargetChannelConfig")
    DroneSopNeedToSendRule = apps.get_model("drone", "DroneSopNeedToSendRule")
    db_alias = schema_editor.connection.alias

    DroneSopTargetMapping.objects.using(db_alias).all().delete()
    DroneSopTargetRecipient.objects.using(db_alias).all().delete()
    DroneSopTargetChannelConfig.objects.using(db_alias).all().delete()
    DroneSopNeedToSendRule.objects.using(db_alias).all().delete()
    DroneSopTarget.objects.using(db_alias).all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("drone", "0019_target_dispatch_delivery_attempt"),
    ]

    operations = [
        migrations.CreateModel(
            name="DroneSopTargetChannelConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "channel",
                    models.CharField(
                        choices=[("jira", "Jira"), ("mail", "Mail"), ("messenger", "Messenger")],
                        max_length=16,
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("template_key", models.CharField(blank=True, max_length=50, null=True)),
                ("jira_project_key", models.CharField(blank=True, max_length=64, null=True)),
                ("chatroom_id", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_default=django.db.models.functions.Now())),
                ("updated_at", models.DateTimeField(auto_now=True, db_default=django.db.models.functions.Now())),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="channel_configs",
                        to="drone.dronesoptarget",
                    ),
                ),
            ],
            options={
                "db_table": "drone_sop_target_channel_config",
                "indexes": [
                    models.Index(fields=["channel", "enabled"], name="idx_dro_tgt_ch_cfg"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("target", "channel"), name="uniq_dro_tgt_ch_cfg"),
                    models.CheckConstraint(check=Q(("channel__in", ["jira", "mail", "messenger"])), name="chk_dro_tgt_ch_cfg_ch"),
                ],
            },
        ),
        migrations.CreateModel(
            name="DroneSopNeedToSendRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=False)),
                ("comment_keyword", models.CharField(blank=True, max_length=64, null=True)),
                ("ignore_sample_type", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_default=django.db.models.functions.Now())),
                ("updated_at", models.DateTimeField(auto_now=True, db_default=django.db.models.functions.Now())),
                (
                    "target",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="needtosend_rule",
                        to="drone.dronesoptarget",
                    ),
                ),
            ],
            options={
                "db_table": "drone_sop_needtosend_rule",
                "indexes": [
                    models.Index(fields=["enabled"], name="idx_dro_nts_rule_en"),
                ],
            },
        ),
        migrations.RunPython(reset_target_configuration, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="dronesoptarget",
            name="uniq_dro_sop_target",
        ),
        migrations.AddConstraint(
            model_name="dronesoptarget",
            constraint=models.UniqueConstraint(
                django.db.models.functions.Lower("target_user_sdwt_prod"),
                name="uniq_dro_sop_tgt_key",
            ),
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="chatroom_id",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="jira_enabled",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="jira_key",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="jira_template_key",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="mail_enabled",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="mail_template_key",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="messenger_enabled",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="messenger_template_key",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="needtosend_comment_last_at",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="needtosend_enabled",
        ),
        migrations.RemoveField(
            model_name="dronesoptarget",
            name="needtosend_ignore_sample_type",
        ),
    ]
