# =============================================================================
# 모듈: L3 Spider 모델
# =============================================================================
from __future__ import annotations

from django.conf import settings
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
