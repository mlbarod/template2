"""m_tkin_prevent 적재 대상 및 처리 이력 모델입니다."""

from __future__ import annotations

from django.db import models
from django.db.models.functions import Now


class MTkinPrevent(models.Model):
    """m_tkin_prevent 원천 데이터를 저장합니다."""

    operator_name = models.TextField(null=True, blank=True)
    tkin_prevent_comment = models.TextField(null=True, blank=True)
    ppid = models.TextField(null=True, blank=True)
    registration_date = models.DateTimeField(null=True, blank=True)
    registration_level = models.TextField(null=True, blank=True)
    fa_object2 = models.TextField(null=True, blank=True)
    line_id = models.TextField(null=True, blank=True)
    tkin_prevent_type = models.TextField(null=True, blank=True)
    tkin_restrc_lot_count = models.FloatField(null=True, blank=True)
    last_update_date = models.DateTimeField(null=True, blank=True)
    process_id = models.TextField(null=True, blank=True)
    tkin_lot_count = models.FloatField(null=True, blank=True)
    step_seq = models.TextField(null=True, blank=True)
    metro_lot_count = models.FloatField(null=True, blank=True)
    reticle_id = models.TextField(null=True, blank=True)
    metro_step = models.TextField(null=True, blank=True)
    product_id = models.TextField(null=True, blank=True)
    reg_dept_name = models.TextField(null=True, blank=True)
    update_date = models.DateTimeField(null=True, blank=True)
    eqp_id = models.TextField(null=True, blank=True)
    tkin_prevent_chamber_id = models.TextField(null=True, blank=True)
    schedule_priority = models.TextField(null=True, blank=True)
    photo_comment = models.TextField(null=True, blank=True)
    level2_comment = models.TextField(null=True, blank=True)
    level2_restrc_lot_count = models.FloatField(null=True, blank=True)
    term_intlk_count = models.TextField(null=True, blank=True)
    term_intlk_hour = models.TextField(null=True, blank=True)
    tip_code = models.TextField(null=True, blank=True)
    expo_time = models.TextField(null=True, blank=True)
    check_time = models.FloatField(null=True, blank=True)
    term1_residual_time = models.FloatField(null=True, blank=True)
    check_time2 = models.FloatField(null=True, blank=True)
    term2_residual_time = models.FloatField(null=True, blank=True)
    last_tkout_time = models.TextField(null=True, blank=True)
    first_intlk_time = models.TextField(null=True, blank=True)
    tkin_time = models.TextField(null=True, blank=True)
    term_intlk_group_type = models.TextField(null=True, blank=True)
    focus_value = models.TextField(null=True, blank=True)
    prev_rels_level = models.TextField(null=True, blank=True)
    data_chg_type = models.TextField(null=True, blank=True)
    level2_chk_cnt = models.FloatField(null=True, blank=True)
    sample_group_vals = models.TextField(null=True, blank=True)
    auto_tip_rels_type = models.TextField(null=True, blank=True)
    seq_order_no = models.FloatField(null=True, blank=True)
    cd_type = models.TextField(null=True, blank=True)
    rels_group_desc = models.TextField(null=True, blank=True)
    pm_reset_yn = models.TextField(null=True, blank=True)
    rsc_code = models.TextField(null=True, blank=True)
    rsc_chk_mins = models.TextField(null=True, blank=True)
    base_focus_spec = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "m_tkin_prevent"
        indexes = [
            models.Index(fields=["line_id"], name="idx_m_tkin_prevent_ln"),
            models.Index(fields=["eqp_id", "registration_level", "process_id"], name="idx_mtk_eqp_lvl_proc"),
            models.Index(
                fields=["process_id", "eqp_id", "registration_level", "step_seq"],
                name="idx_mtk_prc_eqp_lvl_stp",
            ),
            models.Index(
                fields=["process_id", "step_seq", "registration_level", "eqp_id"],
                name="idx_mtk_prc_stp_lvl_eqp",
            ),
        ]

    def __str__(self) -> str:
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"m_tkin_prevent {self.line_id or '-'}"


class MTkinPreventLoadJob(models.Model):
    """m_tkin_prevent 파일 적재 처리 이력을 저장합니다."""

    class Status(models.TextChoices):
        """파일 적재 상태 값입니다."""

        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        DRY_RUN = "dry_run", "Dry run"

    file_name = models.TextField()
    file_path = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    replace_values = models.JSONField(default=list, blank=True)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "m_tkin_prevent_load_job"
        indexes = [
            models.Index(fields=["status"], name="idx_m_tkin_prv_job_sts"),
            models.Index(fields=["created_at"], name="idx_m_tkin_prv_job_crt"),
        ]

    def __str__(self) -> str:
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"{self.file_name} ({self.status})"
