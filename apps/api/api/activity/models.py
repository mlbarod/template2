# =============================================================================
# 모듈 설명: 활동 로그 모델을 정의합니다.
# - 주요 클래스: ActivityLog, ExternalAppAccessDailyStat
# - 불변 조건: created_at은 타임존 인식(UTC) 값입니다.
# =============================================================================
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class ActivityLog(models.Model):
    """사용자 요청/응답의 핵심 정보를 저장하는 활동 로그 모델입니다."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=255)
    path = models.CharField(max_length=512)
    method = models.CharField(max_length=10)
    status_code = models.PositiveIntegerField(default=200)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "activity_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:  # 디버깅용 문자열(커버리지 제외): pragma: no cover
        """디버깅용 표시 문자열을 반환합니다."""
        username = self.user.get_username() if self.user else "anonymous"
        return f"{self.method} {self.path} by {username} -> {self.status_code}"


class ExternalAppAccessDailyStat(models.Model):
    """외부 앱의 일별 접속 집계값을 저장합니다."""

    SOURCE_TYPE_MANUAL = "manual"

    app_id = models.CharField(max_length=120)
    app_name = models.CharField(max_length=160)
    stat_date = models.DateField(db_index=True)
    access_count = models.PositiveIntegerField(default=0)
    unique_user_count = models.PositiveIntegerField(default=0)
    source_type = models.CharField(max_length=32, default=SOURCE_TYPE_MANUAL)
    source_name = models.CharField(max_length=80, default=SOURCE_TYPE_MANUAL)
    memo = models.TextField(blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "activity_external_app_access_daily_stat"
        ordering = ["-stat_date", "app_name", "app_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["app_id", "stat_date", "source_name"],
                name="uniq_act_ext_daily_key",
            )
        ]
        indexes = [
            models.Index(fields=["stat_date", "app_id"], name="idx_act_ext_date_app"),
        ]

    def __str__(self) -> str:  # 디버깅용 문자열(커버리지 제외): pragma: no cover
        """디버깅용 표시 문자열을 반환합니다."""
        return f"{self.stat_date} {self.app_id} {self.access_count}"


class ExternalAppUsageSyncState(models.Model):
    """외부 앱 사용량 API 동기화 상태를 저장합니다."""

    sync_key = models.CharField(max_length=80, unique=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=32, default="never")
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "activity_external_app_usage_sync_state"
        ordering = ["sync_key"]

    def __str__(self) -> str:  # 디버깅용 문자열(커버리지 제외): pragma: no cover
        """디버깅용 표시 문자열을 반환합니다."""
        return f"{self.sync_key} {self.last_status}"


__all__ = ["ActivityLog", "ExternalAppAccessDailyStat", "ExternalAppUsageSyncState"]
