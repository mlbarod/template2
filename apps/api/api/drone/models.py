# =============================================================================
# 모듈: 드론 SOP/조기 알림 모델
# 주요 구성: DroneSOP, DroneEarlyInform, sdwt_prod/user_sdwt_prod 매핑 및 채널 설정
# 주요 가정: sop_key는 필드 조합으로 생성합니다.
# =============================================================================
from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.db.models.functions import Now


def build_sop_key(
    *,
    line_id: str | None,
    eqp_id: str | None,
    chamber_ids: str | None,
    lot_id: str | None,
    main_step: str | None,
) -> str:
    """Drone SOP 식별용 sop_key를 생성합니다.

    인자:
        line_id: 라인 ID.
        eqp_id: 장비 ID.
        chamber_ids: 챔버 ID 문자열.
        lot_id: LOT ID(로트 ID).
        main_step: 메인 스텝.

    반환:
        "|" 구분자를 사용한 결합 문자열.

    부작용:
        없음. 순수 문자열 조합입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화 헬퍼
    # -----------------------------------------------------------------------------
    def _normalize(value: str | None) -> str:
        if value is None:
            return ""
        return str(value).strip()

    # -----------------------------------------------------------------------------
    # 2) 필드 결합
    # -----------------------------------------------------------------------------
    return "|".join(
        [
            _normalize(line_id),
            _normalize(eqp_id),
            _normalize(chamber_ids),
            _normalize(lot_id),
            _normalize(main_step),
        ]
    )


class DroneSOP(models.Model):
    """Drone SOP 관련 데이터(알림/상태/지라 연동 등)를 저장하는 모델입니다."""

    sop_key = models.CharField(max_length=300, unique=True)
    line_id = models.CharField(max_length=50, null=True, blank=True)
    sdwt_prod = models.CharField(max_length=64, null=True, blank=True)
    sample_type = models.CharField(max_length=50, null=True, blank=True)
    sample_group = models.CharField(max_length=50, null=True, blank=True)
    eqp_id = models.CharField(max_length=50, null=True, blank=True)
    chamber_ids = models.CharField(max_length=50, null=True, blank=True)
    lot_id = models.CharField(max_length=50, null=True, blank=True)
    proc_id = models.CharField(max_length=50, null=True, blank=True)
    ppid = models.CharField(max_length=50, null=True, blank=True)
    main_step = models.CharField(max_length=50, null=True, blank=True)
    metro_current_step = models.CharField(max_length=50, null=True, blank=True)
    metro_steps = models.CharField(max_length=1000, null=True, blank=True)
    metro_end_step = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    knox_id = models.CharField(max_length=50, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    user_sdwt_prod = models.CharField(max_length=64, null=True, blank=True)
    defect_url = models.TextField(null=True, blank=True)
    defect_png_url = models.TextField(null=True, blank=True)
    send_jira = models.SmallIntegerField(null=True, blank=True, default=0, db_default=0)
    send_messenger = models.SmallIntegerField(null=True, blank=True, default=0, db_default=0)
    send_mail = models.SmallIntegerField(null=True, blank=True, default=0, db_default=0)
    jira_reason = models.CharField(max_length=64, null=True, blank=True)
    messenger_reason = models.CharField(max_length=64, null=True, blank=True)
    mail_reason = models.CharField(max_length=64, null=True, blank=True)
    instant_inform = models.SmallIntegerField(default=0)
    needtosend = models.SmallIntegerField(default=1)
    custom_end_step = models.CharField(max_length=50, null=True, blank=True)
    inform_step = models.CharField(max_length=50, null=True, blank=True)
    jira_key = models.CharField(max_length=50, null=True, blank=True)
    informed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "drone_sop"
        constraints = [
            models.UniqueConstraint(
                fields=["line_id", "eqp_id", "chamber_ids", "lot_id", "main_step"],
                name="uniq_dro_sop_ln_id_eqp_i_92d25",
            )
        ]
        indexes = [
            models.Index(fields=["send_jira", "needtosend"], name="idx_dro_sop_snd_jir_nts"),
            models.Index(fields=["sdwt_prod"], name="idx_dro_sop_sdw_prd"),
            models.Index(fields=["created_at", "id"], name="idx_dro_sop_crt_at_id"),
            models.Index(
                fields=["user_sdwt_prod", "created_at", "id"],
                name="idx_dro_sop_usr_sdw_prd_dd5e5",
            ),
            models.Index(fields=["send_jira"], name="idx_dro_sop_snd_jir"),
            models.Index(fields=["knox_id"], name="idx_dro_sop_knx_id"),
            models.Index(
                fields=["id"],
                name="idx_dro_sop_id_jir_pen",
                condition=Q(send_jira=0, needtosend=1, status="COMPLETE"),
            ),
        ]

    def __str__(self) -> str:  # 관리자/디버깅용 문자열 표현(커버리지 제외): pragma: no cover
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"SOP {self.line_id or '-'} {self.main_step or '-'}"

    def save(self, *args: object, **kwargs: object) -> None:
        """sop_key가 없으면 생성 후 저장합니다.

        부작용:
            DB 저장이 발생합니다.
        """

        # -------------------------------------------------------------------------
        # 1) sop_key 생성(없을 때만)
        # -------------------------------------------------------------------------
        if not self.sop_key:
            self.sop_key = build_sop_key(
                line_id=self.line_id,
                eqp_id=self.eqp_id,
                chamber_ids=self.chamber_ids,
                lot_id=self.lot_id,
                main_step=self.main_step,
            )
        # -------------------------------------------------------------------------
        # 2) 저장 호출
        # -------------------------------------------------------------------------
        super().save(*args, **kwargs)




class DroneSopUserSdwtProdMap(models.Model):
    """Drone SOP sdwt_prod/user_sdwt_prod 조합을 target_user_sdwt_prod로 매핑하는 모델입니다."""

    sdwt_prod = models.CharField(max_length=64, null=True, blank=True)
    user_sdwt_prod = models.CharField(max_length=64, null=True, blank=True)
    target_user_sdwt_prod = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "drone_sop_user_sdwt_map"
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(sdwt_prod__isnull=False) & ~Q(sdwt_prod=""))
                    | (Q(user_sdwt_prod__isnull=False) & ~Q(user_sdwt_prod=""))
                ),
                name="chk_dro_sop_sdw_usr_req",
            ),
            models.UniqueConstraint(
                fields=["sdwt_prod", "user_sdwt_prod"],
                name="uniq_dro_sop_sdw_usr_map",
                condition=(
                    Q(sdwt_prod__isnull=False)
                    & ~Q(sdwt_prod="")
                    & Q(user_sdwt_prod__isnull=False)
                    & ~Q(user_sdwt_prod="")
                ),
            ),
            models.UniqueConstraint(
                fields=["sdwt_prod"],
                name="uniq_dro_sop_sdw_map",
                condition=(
                    Q(sdwt_prod__isnull=False)
                    & ~Q(sdwt_prod="")
                    & (Q(user_sdwt_prod__isnull=True) | Q(user_sdwt_prod=""))
                ),
            ),
            models.UniqueConstraint(
                fields=["user_sdwt_prod"],
                name="uniq_dro_sop_usr_map",
                condition=(
                    Q(user_sdwt_prod__isnull=False)
                    & ~Q(user_sdwt_prod="")
                    & (Q(sdwt_prod__isnull=True) | Q(sdwt_prod=""))
                ),
            ),
        ]

    def __str__(self) -> str:  # 관리자/디버깅용 문자열 표현(커버리지 제외): pragma: no cover
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"{self.sdwt_prod or '-'} / {self.user_sdwt_prod or '-'} -> {self.target_user_sdwt_prod}"


class DroneSopUserSdwtChannel(models.Model):
    """target_user_sdwt_prod 기준 채널 키/템플릿/채팅룸 ID를 저장하는 모델입니다."""

    target_user_sdwt_prod = models.CharField(max_length=64)
    jira_key = models.CharField(max_length=64, null=True, blank=True)
    chatroom_id = models.BigIntegerField(null=True, blank=True)
    jira_template_key = models.CharField(max_length=50, null=True, blank=True)
    mail_template_key = models.CharField(max_length=50, null=True, blank=True)
    messenger_template_key = models.CharField(max_length=50, null=True, blank=True)
    jira_enabled = models.BooleanField(default=True)
    messenger_enabled = models.BooleanField(default=True)
    mail_enabled = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "drone_sop_user_sdwt_channel"
        constraints = [
            models.UniqueConstraint(
                fields=["target_user_sdwt_prod"],
                name="uniq_dro_sop_usr_chn",
            ),
        ]

    def __str__(self) -> str:  # 관리자/디버깅용 문자열 표현(커버리지 제외): pragma: no cover
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        chatroom_display = self.chatroom_id if self.chatroom_id is not None else "-"
        return f"{self.target_user_sdwt_prod} (jira={self.jira_key or '-'}, msg={chatroom_display})"


class DroneSopNeedToSendRule(models.Model):
    """target_user_sdwt_prod 기준 needtosend 계산 규칙을 저장하는 모델입니다."""

    target_user_sdwt_prod = models.CharField(max_length=64)
    comment_last_at = models.CharField(max_length=64)
    ignore_sample_type = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "drone_sop_needtosend_rule"
        constraints = [
            models.UniqueConstraint(
                fields=["target_user_sdwt_prod"],
                name="uniq_dro_sop_nts_trg",
            ),
        ]

    def __str__(self) -> str:  # 관리자/디버깅용 문자열 표현(커버리지 제외): pragma: no cover
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"{self.target_user_sdwt_prod} (comment_last_at={self.comment_last_at})"


class DroneEarlyInform(models.Model):
    """Drone 조기 알림 설정(라인/스텝 기준)을 저장하는 모델입니다."""

    line_id = models.CharField(max_length=50)
    main_step = models.CharField(max_length=50)
    custom_end_step = models.CharField(max_length=50, null=True, blank=True)
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "drone_early_inform"
        constraints = [
            models.UniqueConstraint(
                fields=["line_id", "main_step"],
                name="uniq_dro_erl_inf_ln_id_mn_stp",
            )
        ]

    def __str__(self) -> str:  # 관리자/디버깅용 문자열 표현(커버리지 제외): pragma: no cover
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"{self.line_id} - {self.main_step}"


__all__ = [
    "DroneEarlyInform",
    "DroneSOP",
    "DroneSopNeedToSendRule",
    "DroneSopUserSdwtChannel",
    "DroneSopUserSdwtProdMap",
    "build_sop_key",
]
