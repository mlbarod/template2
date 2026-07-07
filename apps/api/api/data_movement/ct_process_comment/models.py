"""ct_process_comment 적재 대상 및 처리 이력 모델입니다."""

from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.db.models.functions import Now


class CtProcessComment(models.Model):
    """CT_PROCESS_COMMENT 원천 데이터를 workorder 기준 최신 상태로 저장합니다."""

    workorder_id = models.CharField(max_length=80)
    line_id = models.TextField(null=True, blank=True)
    process_id = models.TextField(null=True, blank=True)
    process_seq = models.FloatField(null=True, blank=True)
    comment_seq = models.TextField(null=True, blank=True)
    eqp_id = models.TextField(null=True, blank=True)
    freeze_yn = models.TextField(null=True, blank=True)
    contents = models.TextField(null=True, blank=True)
    contents_text = models.TextField(null=True, blank=True)
    llm_summary = models.TextField(null=True, blank=True)
    llm_core_summary = models.TextField(null=True, blank=True)
    create_date = models.DateTimeField(null=True, blank=True)
    create_user = models.TextField(null=True, blank=True)
    update_date = models.DateTimeField(null=True, blank=True)
    update_user = models.TextField(null=True, blank=True)
    use_yn = models.TextField(null=True, blank=True)
    modify_user = models.TextField(null=True, blank=True)
    modify_date = models.DateTimeField(null=True, blank=True)
    pbu_part_key = models.TextField(null=True, blank=True)
    update_flag = models.CharField(max_length=1, default="N")
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "ct_process_comment"
        indexes = [
            models.Index(fields=["line_id"], name="idx_ct_prc_cmt_line"),
            models.Index(fields=["eqp_id"], name="idx_ct_prc_cmt_eqp"),
            models.Index(fields=["create_date"], name="idx_ct_prc_cmt_crt"),
            models.Index(
                fields=["-updated_at", "-id"],
                name="idx_ct_prc_cmt_pend",
                condition=Q(update_flag="Y"),
            ),
        ]
        constraints = [
            models.UniqueConstraint(fields=["workorder_id"], name="uniq_ct_prc_cmt_wo"),
        ]

    def __str__(self) -> str:
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return self.workorder_id


class CtProcessCommentLoadJob(models.Model):
    """ct_process_comment 파일 적재 처리 이력을 저장합니다."""

    class Status(models.TextChoices):
        """파일 적재 상태 값입니다."""

        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        DRY_RUN = "dry_run", "Dry run"

    file_name = models.TextField()
    file_path = models.TextField()
    file_timestamp = models.CharField(max_length=13, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "ct_process_comment_load_job"
        indexes = [
            models.Index(fields=["status"], name="idx_ct_prc_cmt_lj_sts"),
            models.Index(fields=["created_at"], name="idx_ct_prc_cmt_lj_crt"),
        ]

    def __str__(self) -> str:
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"{self.file_name} ({self.status})"
