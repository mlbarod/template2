"""ctttm_workorder_list 적재 대상 및 처리 이력 모델입니다."""

from __future__ import annotations

from django.db import models
from django.db.models.functions import Now


class CtttmWorkorderList(models.Model):
    """CTTTM workorder 원천 데이터를 source별 최신 스냅샷으로 저장합니다."""

    source_type = models.CharField(max_length=8)
    workorder_id = models.TextField(null=True, blank=True)
    line_id = models.TextField(null=True, blank=True)
    eqp_id = models.TextField(null=True, blank=True)
    eqp_id_lookup = models.TextField(null=True, blank=True)
    work_type = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    inprg_date = models.DateTimeField(null=True, blank=True)
    comp_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "ctttm_workorder_list"
        indexes = [
            models.Index(fields=["source_type"], name="idx_ctttm_wol_src"),
            models.Index(fields=["line_id"], name="idx_ctttm_wol_line"),
            models.Index(fields=["eqp_id"], name="idx_ctttm_wol_eqp"),
            models.Index(fields=["eqp_id_lookup", "-inprg_date"], name="idx_ctttm_lkp_dt"),
            models.Index(fields=["workorder_id", "-inprg_date", "-id"], name="idx_ctttm_wo_dt_id"),
        ]

    def __str__(self) -> str:
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"{self.source_type} {self.workorder_id or '-'}"

    def save(self, *args: object, **kwargs: object) -> None:
        """조회용 정규화 키를 채운 뒤 저장합니다."""

        self.eqp_id_lookup = (self.eqp_id or "").strip().upper() or None
        super().save(*args, **kwargs)


class CtttmWorkorderListLoadJob(models.Model):
    """ctttm_workorder_list 파일 적재 처리 이력을 저장합니다."""

    class Status(models.TextChoices):
        """파일 적재 상태 값입니다."""

        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        DRY_RUN = "dry_run", "Dry run"

    file_name = models.TextField()
    file_path = models.TextField()
    source_type = models.CharField(max_length=8, null=True, blank=True)
    file_timestamp = models.CharField(max_length=13, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "ctttm_workorder_list_load_job"
        indexes = [
            models.Index(fields=["source_type"], name="idx_ctttm_wolj_src"),
            models.Index(fields=["status"], name="idx_ctttm_wolj_sts"),
            models.Index(fields=["created_at"], name="idx_ctttm_wolj_crt"),
        ]

    def __str__(self) -> str:
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"{self.file_name} ({self.status})"
