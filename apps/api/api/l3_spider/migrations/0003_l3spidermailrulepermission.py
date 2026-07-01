import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('l3_spider', '0002_l3spidermailrule_l3spidermaildelivery_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='L3SpiderMailRulePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_level', models.CharField(choices=[('read', 'Read'), ('write', 'Write')], default='read', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('granted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='l3_spider_mail_permissions_granted', to=settings.AUTH_USER_MODEL)),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permissions', to='l3_spider.l3spidermailrule')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='l3_spider_mail_rule_permissions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'l3_spider_mail_rule_permission',
                'ordering': ['rule_id', 'user_id'],
                'indexes': [models.Index(fields=['user', 'access_level'], name='idx_l3_mail_perm_user'), models.Index(fields=['rule', 'access_level'], name='idx_l3_mail_perm_rule')],
                'constraints': [models.UniqueConstraint(fields=('rule', 'user'), name='uniq_l3_mail_perm_user')],
            },
        ),
    ]
