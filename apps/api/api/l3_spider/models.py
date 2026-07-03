# =============================================================================
# 모듈: L3 Spider 모델
# =============================================================================
from __future__ import annotations

from datetime import time as datetime_time

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


class L3SpiderExclusionFilter(models.Model):
    """L3 Spider 이상감지 제외 필터 규칙.

    각 필드는 와일드카드 패턴을 지원합니다.
      * : 모든 값 (제한 없음)
      % : 임의 문자열 (PP% → PP로 시작, %PP% → PP 포함)
    """

    line_id = models.CharField(max_length=200, default="*")
    process_id = models.CharField(max_length=200, default="*")
    eds_step = models.CharField(max_length=200, default="*")
    step_seq = models.CharField(max_length=200, default="*")
    ppid = models.CharField(max_length=200, default="*")
    eqpch = models.CharField(max_length=200, default="*")
    bin_name = models.CharField(max_length=200, default="*")
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    memo = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="l3_spider_exclusion_filters",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "l3_spider_exclusion_filter"
        ordering = ["-created_at"]


class L3SpiderMailRule(models.Model):
    """L3 Spider 이상감지 메일 발송 규칙.

    각 패턴 필드는 제외 필터와 같은 와일드카드 규칙을 사용합니다.
      * : 모든 값 (제한 없음)
      % : 임의 문자열 (PP% → PP로 시작, %PP% → PP 포함)
    """

    class SeverityModes(models.TextChoices):
        HIGH_RISK = "high_risk", "High Risk Chamber"
        WARNING_OR_HIGH_RISK = "warning_or_high_risk", "Warning + High Risk"

    class ScheduleTypes(models.TextChoices):
        DAILY = "daily", "Daily"

    name = models.CharField(max_length=100, default="L3 Spider 알림")
    line_id = models.CharField(max_length=200, default="*")
    process_id = models.CharField(max_length=200, default="*")
    eds_step = models.CharField(max_length=200, default="*")
    step_seq = models.CharField(max_length=200, default="*")
    ppid = models.CharField(max_length=200, default="*")
    eqpch = models.CharField(max_length=200, default="*")
    bin_name = models.CharField(max_length=200, default="*")
    date_to = models.DateField(null=True, blank=True)
    severity_mode = models.CharField(
        max_length=32,
        choices=SeverityModes.choices,
        default=SeverityModes.HIGH_RISK,
    )
    receiver_emails = ArrayField(models.EmailField(max_length=254), default=list, blank=True)
    schedule_type = models.CharField(
        max_length=16,
        choices=ScheduleTypes.choices,
        default=ScheduleTypes.DAILY,
    )
    send_time = models.TimeField(default=datetime_time(9, 0))
    timezone = models.CharField(max_length=64, default="Asia/Seoul")
    is_active = models.BooleanField(default=True)
    memo = models.TextField(blank=True, default="")
    last_sent_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="l3_spider_mail_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "l3_spider_mail_rule"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by", "is_active"], name="idx_l3_mail_rule_owner"),
            models.Index(fields=["is_active", "send_time"], name="idx_l3_mail_rule_due"),
        ]


class L3SpiderMailDelivery(models.Model):
    """L3 Spider 메일 발송 이력.

    같은 rule과 event_key 조합은 한 번만 발송되도록 DB 제약으로 보호합니다.
    """

    class Statuses(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    rule = models.ForeignKey(
        L3SpiderMailRule,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event_key = models.CharField(max_length=500)
    status = models.CharField(max_length=16, choices=Statuses.choices)
    event_date = models.CharField(max_length=20, blank=True, default="")
    display_status = models.CharField(max_length=64, blank=True, default="")
    receiver_emails = ArrayField(models.EmailField(max_length=254), default=list, blank=True)
    payload_snapshot = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "l3_spider_mail_delivery"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["rule", "event_key"],
                name="uniq_l3_mail_dlv_event",
            )
        ]
        indexes = [
            models.Index(fields=["rule", "status"], name="idx_l3_mail_dlv_rule"),
            models.Index(fields=["status", "sent_at"], name="idx_l3_mail_dlv_status"),
        ]


class L3SpiderMailRulePermission(models.Model):
    """L3 Spider 메일 rule 공유 권한.

    owner는 별도 row 없이 모든 권한을 갖고, 이 모델은 추가 공유 대상만 저장합니다.
    """

    class AccessLevels(models.TextChoices):
        READ = "read", "Read"
        WRITE = "write", "Write"

    rule = models.ForeignKey(
        L3SpiderMailRule,
        on_delete=models.CASCADE,
        related_name="permissions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="l3_spider_mail_rule_permissions",
    )
    access_level = models.CharField(
        max_length=16,
        choices=AccessLevels.choices,
        default=AccessLevels.READ,
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="l3_spider_mail_permissions_granted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "l3_spider_mail_rule_permission"
        ordering = ["rule_id", "user_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["rule", "user"],
                name="uniq_l3_mail_perm_user",
            )
        ]
        indexes = [
            models.Index(fields=["user", "access_level"], name="idx_l3_mail_perm_user"),
            models.Index(fields=["rule", "access_level"], name="idx_l3_mail_perm_rule"),
        ]
