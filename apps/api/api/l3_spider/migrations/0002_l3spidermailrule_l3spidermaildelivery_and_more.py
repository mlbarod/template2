import datetime
import django.contrib.postgres.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('l3_spider', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='L3SpiderMailRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='L3 Spider 알림', max_length=100)),
                ('line_id', models.CharField(default='*', max_length=200)),
                ('process_id', models.CharField(default='*', max_length=200)),
                ('eds_step', models.CharField(default='*', max_length=200)),
                ('step_seq', models.CharField(default='*', max_length=200)),
                ('ppid', models.CharField(default='*', max_length=200)),
                ('eqpch', models.CharField(default='*', max_length=200)),
                ('bin_name', models.CharField(default='*', max_length=200)),
                ('date_from', models.DateField(blank=True, null=True)),
                ('date_to', models.DateField(blank=True, null=True)),
                ('severity_mode', models.CharField(choices=[('high_risk', 'High Risk Chamber'), ('warning_or_high_risk', 'Warning + High Risk')], default='high_risk', max_length=32)),
                ('receiver_emails', django.contrib.postgres.fields.ArrayField(base_field=models.EmailField(max_length=254), blank=True, default=list, size=None)),
                ('schedule_type', models.CharField(choices=[('daily', 'Daily')], default='daily', max_length=16)),
                ('send_time', models.TimeField(default=datetime.time(9, 0))),
                ('timezone', models.CharField(default='Asia/Seoul', max_length=64)),
                ('is_active', models.BooleanField(default=True)),
                ('memo', models.TextField(blank=True, default='')),
                ('last_sent_at', models.DateTimeField(blank=True, null=True)),
                ('last_checked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='l3_spider_mail_rules', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'l3_spider_mail_rule',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='L3SpiderMailDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_key', models.CharField(max_length=500)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Skipped')], max_length=16)),
                ('event_date', models.CharField(blank=True, default='', max_length=20)),
                ('display_status', models.CharField(blank=True, default='', max_length=64)),
                ('receiver_emails', django.contrib.postgres.fields.ArrayField(base_field=models.EmailField(max_length=254), blank=True, default=list, size=None)),
                ('payload_snapshot', models.JSONField(blank=True, default=dict)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='l3_spider.l3spidermailrule')),
            ],
            options={
                'db_table': 'l3_spider_mail_delivery',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='l3spidermailrule',
            index=models.Index(fields=['created_by', 'is_active'], name='idx_l3_mail_rule_owner'),
        ),
        migrations.AddIndex(
            model_name='l3spidermailrule',
            index=models.Index(fields=['is_active', 'send_time'], name='idx_l3_mail_rule_due'),
        ),
        migrations.AddIndex(
            model_name='l3spidermaildelivery',
            index=models.Index(fields=['rule', 'status'], name='idx_l3_mail_dlv_rule'),
        ),
        migrations.AddIndex(
            model_name='l3spidermaildelivery',
            index=models.Index(fields=['status', 'sent_at'], name='idx_l3_mail_dlv_status'),
        ),
        migrations.AddConstraint(
            model_name='l3spidermaildelivery',
            constraint=models.UniqueConstraint(fields=('rule', 'event_key'), name='uniq_l3_mail_dlv_event'),
        ),
    ]
