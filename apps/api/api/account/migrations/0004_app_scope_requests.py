from django.db import migrations


def enable_app_scope_requests(apps, _schema_editor):
    """앱 권한도 사용자가 직접 신청할 수 있게 전환합니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    AccessScope.objects.filter(scope_type="app").update(requestable=True)


def disable_app_scope_requests(apps, _schema_editor):
    """롤백 시 기존처럼 앱 권한 직접 신청을 비활성화합니다."""

    AccessScope = apps.get_model("account", "AccessScope")
    AccessScope.objects.filter(scope_type="app").update(requestable=False)


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0003_spider_access_scopes"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="accessscope",
            name="chk_acc_scp_app_not_req",
        ),
        migrations.RunPython(
            enable_app_scope_requests,
            disable_app_scope_requests,
        ),
    ]
