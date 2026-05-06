# =============================================================================
# 모듈 설명: account 도메인 모델을 정의합니다.
# - 주요 대상: User, UserProfile, Affiliation, UserSdwtProdAccess, UserSdwtProdChange
# - 불변 조건: sabun은 사용자 고유키이며 각 모델은 db_table을 명시합니다.
# =============================================================================

"""계정/소속 도메인 모델 정의 모음.

- 주요 대상: User, UserProfile, Affiliation, UserSdwtProdAccess, UserSdwtProdChange
- 주요 엔드포인트/클래스: 각 모델 클래스
- 가정/불변 조건: sabun은 사용자 고유키이며 각 모델은 db_table을 명시함
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.conf import settings
from django.db import models


class UserManager(BaseUserManager):
    """sabun 기반 사용자 생성을 제공하는 커스텀 User 매니저입니다."""

    use_in_migrations = True

    def _create_user(self, sabun: str, password: str | None, **extra_fields) -> "User":
        """sabun 기반 사용자 생성 공통 로직을 수행합니다.

        입력:
        - sabun: 사용자 사번
        - password: 초기 비밀번호(없으면 unusable)
        - **extra_fields: 추가 필드 값

        반환:
        - User: 생성된 사용자 인스턴스

        부작용:
        - 사용자 레코드 생성(DB 쓰기)

        오류:
        - ValueError: sabun이 비어있을 때
        """
        # -----------------------------------------------------------------------------
        # 1) sabun 검증
        # -----------------------------------------------------------------------------
        if not sabun:
            raise ValueError("sabun is required")
        # -----------------------------------------------------------------------------
        # 2) 사용자 생성 및 저장
        # -----------------------------------------------------------------------------
        user = self.model(sabun=str(sabun).strip(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, sabun: str, password: str | None = None, **extra_fields) -> "User":
        """일반 사용자 계정을 생성합니다.

        입력:
        - sabun: 사용자 사번
        - password: 초기 비밀번호(선택)
        - **extra_fields: 추가 필드 값

        반환:
        - User: 생성된 사용자 인스턴스

        부작용:
        - 사용자 레코드 생성(DB 쓰기)

        오류:
        - ValueError: sabun이 비어있을 때
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(sabun, password, **extra_fields)

    def create_superuser(self, sabun: str, password: str | None = None, **extra_fields) -> "User":
        """슈퍼유저 계정을 생성합니다.

        입력:
        - sabun: 사용자 사번
        - password: 초기 비밀번호(선택)
        - **extra_fields: 추가 필드 값

        반환:
        - User: 생성된 슈퍼유저 인스턴스

        부작용:
        - 사용자 레코드 생성(DB 쓰기)

        오류:
        - ValueError: 필수 플래그가 올바르지 않을 때
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 플래그 설정
        # -----------------------------------------------------------------------------
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        # -----------------------------------------------------------------------------
        # 2) 플래그 유효성 검증
        # -----------------------------------------------------------------------------
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        # -----------------------------------------------------------------------------
        # 3) 공통 생성 로직 호출
        # -----------------------------------------------------------------------------
        return self._create_user(sabun, password, **extra_fields)


class User(AbstractUser):
    """ADFS/OIDC 클레임에서 받은 사용자 식별 정보를 저장하는 커스텀 사용자 모델입니다."""

    username = models.CharField(max_length=150, null=True, blank=True)
    sabun = models.CharField(max_length=50, unique=True)
    knox_id = models.CharField(max_length=150, null=True, blank=True, unique=True)
    avatarid = models.CharField(max_length=50, null=True, blank=True)
    username_en = models.CharField(max_length=150, null=True, blank=True)
    givenname = models.CharField(max_length=150, null=True, blank=True)
    surname = models.CharField(max_length=150, null=True, blank=True)
    deptid = models.CharField(max_length=50, null=True, blank=True)
    department = models.CharField(max_length=128, null=True, blank=True)
    grd_name = models.CharField(max_length=150, null=True, blank=True)
    grdname_en = models.CharField(max_length=150, null=True, blank=True)
    busname = models.CharField(max_length=150, null=True, blank=True)
    intcode = models.CharField(max_length=64, null=True, blank=True)
    intname = models.CharField(max_length=150, null=True, blank=True)
    origincomp = models.CharField(max_length=150, null=True, blank=True)
    employeetype = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = "account_user"

    objects = UserManager()

    USERNAME_FIELD = "sabun"
    REQUIRED_FIELDS: list[str] = []

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """사용자 표시용 문자열을 반환합니다."""
        return self.get_username()


class UserProfile(models.Model):
    """사용자 역할(role) 등 추가 정보를 저장하는 프로필 모델입니다."""

    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=32, choices=Roles.choices, default=Roles.VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_user_profile"

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """프로필 표시용 문자열을 반환합니다."""
        return f"{self.user.get_username()} ({self.get_role_display()})"


class Affiliation(models.Model):
    """department/line/user_sdwt_prod 조합의 허용 목록(소속 hierarchy)을 저장하는 모델입니다."""

    department = models.CharField(max_length=128)
    line = models.CharField(max_length=64)
    user_sdwt_prod = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_affiliation"
        constraints = [
            models.UniqueConstraint(
                fields=["user_sdwt_prod"],
                name="uniq_acc_aff_usr_sdw_prd",
            ),
        ]
        indexes = [
            models.Index(fields=["department"], name="idx_acc_aff_dep"),
            models.Index(fields=["line"], name="idx_acc_aff_ln"),
            models.Index(fields=["user_sdwt_prod"], name="idx_acc_aff_usr_sdw_prd"),
            models.Index(
                fields=["line", "user_sdwt_prod"],
                name="idx_acc_aff_ln_usr_sdw_prd",
            ),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """소속 표시용 문자열을 반환합니다."""
        return f"{self.department} / {self.line} / {self.user_sdwt_prod}"


class UserCurrentAffiliation(models.Model):
    """앱에서 실제 권한 판단에 사용하는 사용자의 현재 소속을 저장하는 모델입니다."""

    class Sources(models.TextChoices):
        EXTERNAL_AUTO = "external_auto", "External Auto"
        USER_SELECTED = "user_selected", "User Selected"
        ADMIN_ASSIGNED = "admin_assigned", "Admin Assigned"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="current_affiliation",
    )
    affiliation = models.ForeignKey(
        Affiliation,
        on_delete=models.PROTECT,
        related_name="current_users",
    )
    source = models.CharField(
        max_length=32,
        choices=Sources.choices,
        default=Sources.USER_SELECTED,
    )
    requires_reconfirm = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_user_current_affiliation"
        indexes = [
            models.Index(fields=["affiliation"], name="idx_acc_usr_cur_aff_aff"),
            models.Index(fields=["requires_reconfirm"], name="idx_acc_usr_cur_aff_req"),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """현재 소속 표시용 문자열을 반환합니다."""
        return f"{self.user_id} -> {self.affiliation.user_sdwt_prod}"


class UserSdwtProdAccess(models.Model):
    """사용자의 소속 옵션별 접근/관리 권한을 저장하는 모델입니다."""

    class Roles(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        MEMBER = "member", "Member"
        MANAGER = "manager", "Manager"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sdwt_prod_access",
    )
    affiliation = models.ForeignKey(
        Affiliation,
        on_delete=models.CASCADE,
        related_name="user_accesses",
    )
    role = models.CharField(max_length=16, choices=Roles.choices, default=Roles.VIEWER)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sdwt_prod_grants",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_user_sdwt_prod_access"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "affiliation"],
                name="uniq_acc_usr_sdw_prd_acs_aff",
            ),
        ]
        indexes = [
            models.Index(fields=["user"], name="idx_acc_usr_sdw_prd_acs_usr"),
            models.Index(
                fields=["affiliation"],
                name="idx_acc_usr_sdw_prd_acs_aff",
            ),
        ]

    @property
    def user_sdwt_prod(self) -> str:
        """권한이 연결된 소속의 user_sdwt_prod 값을 반환합니다."""
        return self.affiliation.user_sdwt_prod if self.affiliation_id else ""

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """접근 권한 표시용 문자열을 반환합니다."""
        return f"{self.user_id} -> {self.user_sdwt_prod} ({self.role})"


class UserSdwtProdChange(models.Model):
    """사용자 소속(user_sdwt_prod) 변경 요청/승인/적용 이력을 저장하는 모델입니다."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUPERSEDED = "SUPERSEDED", "Superseded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sdwt_prod_changes",
    )
    department = models.CharField(max_length=128, null=True, blank=True)
    line = models.CharField(max_length=64, null=True, blank=True)
    from_user_sdwt_prod = models.CharField(max_length=64, null=True, blank=True)
    to_user_sdwt_prod = models.CharField(max_length=64)
    effective_from = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    applied = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sdwt_prod_changes_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sdwt_prod_changes_created",
    )

    class Meta:
        db_table = "account_user_sdwt_prod_change"
        ordering = ["-effective_from", "-id"]
        indexes = [
            models.Index(
                fields=["user", "effective_from"],
                name="idx_acc_usr_sdw_prd_chg_364a4",
            ),
            models.Index(fields=["applied"], name="idx_acc_usr_sdw_prd_chg_app"),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """소속 변경 표시용 문자열을 반환합니다."""
        return f"{self.user_id} {self.from_user_sdwt_prod or '-'} -> {self.to_user_sdwt_prod} at {self.effective_from}"


class ExternalAffiliationSnapshot(models.Model):
    """외부 DB에서 가져온 예측 소속(user_sdwt_prod) 스냅샷을 저장합니다."""

    knox_id = models.CharField(max_length=150, unique=True)
    department = models.CharField(max_length=128, null=True, blank=True)
    predicted_user_sdwt_prod = models.CharField(max_length=64)
    source_updated_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_external_affiliation_snapshot"
        indexes = [
            models.Index(
                fields=["predicted_user_sdwt_prod"],
                name="idx_acc_ext_aff_snp_pred_54654",
            ),
            models.Index(
                fields=["source_updated_at"],
                name="idx_acc_ext_aff_snp_src_upd_at",
            ),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """외부 소속 스냅샷 표시용 문자열을 반환합니다."""
        return f"{self.knox_id} -> {self.predicted_user_sdwt_prod}"


__all__ = [
    "Affiliation",
    "ExternalAffiliationSnapshot",
    "User",
    "UserCurrentAffiliation",
    "UserProfile",
    "UserSdwtProdAccess",
    "UserSdwtProdChange",
]
