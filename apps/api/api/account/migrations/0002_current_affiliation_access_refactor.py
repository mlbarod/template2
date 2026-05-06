# 수동 생성: 현재 소속과 접근 권한을 Affiliation 참조 구조로 전환합니다.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _normalize_user_sdwt_prod(value):
    if not isinstance(value, str):
        return ""
    return value.strip()


def _get_or_create_affiliation(Affiliation, *, user_sdwt_prod, department="", line=""):
    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return None

    existing = Affiliation.objects.filter(user_sdwt_prod__iexact=normalized).order_by("id").first()
    if existing is not None:
        return existing

    return Affiliation.objects.create(
        department=(department or "").strip(),
        line=(line or "").strip(),
        user_sdwt_prod=normalized,
    )


def backfill_current_affiliation_and_access(apps, schema_editor):
    User = apps.get_model("account", "User")
    Affiliation = apps.get_model("account", "Affiliation")
    UserCurrentAffiliation = apps.get_model("account", "UserCurrentAffiliation")
    UserSdwtProdAccess = apps.get_model("account", "UserSdwtProdAccess")

    for user in (
        User.objects.exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .iterator(chunk_size=1000)
    ):
        affiliation = _get_or_create_affiliation(
            Affiliation,
            user_sdwt_prod=user.user_sdwt_prod,
            department=user.department or "",
            line=user.line or "",
        )
        if affiliation is None:
            continue
        UserCurrentAffiliation.objects.update_or_create(
            user_id=user.id,
            defaults={
                "affiliation_id": affiliation.id,
                "source": "user_selected",
                "requires_reconfirm": bool(user.requires_affiliation_reconfirm),
                "confirmed_at": user.affiliation_confirmed_at,
            },
        )

    seen_access_keys = set()
    for access in UserSdwtProdAccess.objects.all().order_by("user_id", "id").iterator(chunk_size=1000):
        affiliation = _get_or_create_affiliation(
            Affiliation,
            user_sdwt_prod=access.user_sdwt_prod,
        )
        if affiliation is None:
            access.delete()
            continue

        access_key = (access.user_id, affiliation.id)
        if access_key in seen_access_keys:
            access.delete()
            continue

        access.affiliation_id = affiliation.id
        access.save(update_fields=["affiliation"])
        seen_access_keys.add(access_key)

    UserSdwtProdAccess.objects.filter(affiliation__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0001_initial"),
        ("drone", "0006_drone_sop_channel_recipient"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserCurrentAffiliation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("external_auto", "External Auto"),
                            ("user_selected", "User Selected"),
                            ("admin_assigned", "Admin Assigned"),
                        ],
                        default="user_selected",
                        max_length=32,
                    ),
                ),
                ("requires_reconfirm", models.BooleanField(default=False)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "affiliation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="current_users",
                        to="account.affiliation",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="current_affiliation",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "account_user_current_affiliation",
                "indexes": [
                    models.Index(fields=["affiliation"], name="idx_acc_usr_cur_aff_aff"),
                    models.Index(fields=["requires_reconfirm"], name="idx_acc_usr_cur_aff_req"),
                ],
            },
        ),
        migrations.AddField(
            model_name="usersdwtprodaccess",
            name="affiliation",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_accesses",
                to="account.affiliation",
            ),
        ),
        migrations.RunPython(backfill_current_affiliation_and_access, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="usersdwtprodaccess",
            name="uniq_acc_usr_sdw_prd_acs_02885",
        ),
        migrations.RemoveIndex(
            model_name="usersdwtprodaccess",
            name="idx_acc_usr_sdw_prd_acs_1a1f0",
        ),
        migrations.AlterField(
            model_name="usersdwtprodaccess",
            name="affiliation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_accesses",
                to="account.affiliation",
            ),
        ),
        migrations.RemoveField(
            model_name="usersdwtprodaccess",
            name="user_sdwt_prod",
        ),
        migrations.RemoveField(
            model_name="user",
            name="line",
        ),
        migrations.RemoveField(
            model_name="user",
            name="user_sdwt_prod",
        ),
        migrations.RemoveField(
            model_name="user",
            name="requires_affiliation_reconfirm",
        ),
        migrations.RemoveField(
            model_name="user",
            name="affiliation_confirmed_at",
        ),
        migrations.AddIndex(
            model_name="usersdwtprodaccess",
            index=models.Index(fields=["affiliation"], name="idx_acc_usr_sdw_prd_acs_aff"),
        ),
        migrations.AddConstraint(
            model_name="usersdwtprodaccess",
            constraint=models.UniqueConstraint(fields=("user", "affiliation"), name="uniq_acc_usr_sdw_prd_acs_aff"),
        ),
    ]
