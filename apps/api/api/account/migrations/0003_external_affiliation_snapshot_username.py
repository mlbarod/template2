from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0002_current_affiliation_access_refactor"),
    ]

    operations = [
        migrations.AddField(
            model_name="externalaffiliationsnapshot",
            name="username",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
    ]
