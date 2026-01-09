from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0012_rename_user_userid_to_avatarid"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersdwtprodaccess",
            name="role",
            field=models.CharField(
                choices=[("viewer", "Viewer"), ("member", "Member"), ("manager", "Manager")],
                default="viewer",
                max_length=16,
            ),
        ),
        migrations.RemoveField(
            model_name="usersdwtprodaccess",
            name="can_manage",
        ),
    ]
