from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("drone", "0002_drone_sop_inform_channels"),
    ]

    operations = [
        migrations.AddField(
            model_name="dronesop",
            name="defect_png_url",
            field=models.TextField(blank=True, null=True),
        ),
    ]
