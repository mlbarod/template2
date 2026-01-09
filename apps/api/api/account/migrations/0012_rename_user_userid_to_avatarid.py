from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0011_remove_affiliation_jira_key"),
    ]

    operations = [
        migrations.RenameField(
            model_name="user",
            old_name="userid",
            new_name="avatarid",
        ),
    ]
