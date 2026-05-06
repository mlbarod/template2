# =============================================================================
# 모듈 설명: account 도메인의 Django Admin 설정을 제공합니다.
# - 주요 대상: 사용자/소속/권한/변경 요청 관리 화면
# - 불변 조건: 관리자 작업은 서비스 정책을 따라야 합니다.
# =============================================================================

"""계정 도메인 Django Admin 설정 모음.

- 주요 대상: 사용자/소속/권한/변경 요청 관리 화면
- 주요 엔드포인트/클래스: AccountUserAdmin, UserSdwtProdChangeAdmin 등
- 가정/불변 조건: 관리 화면에서의 변경은 서비스 정책을 준수해야 함
"""
from __future__ import annotations

from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.widgets import AdminSplitDateTime
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, SetUnusablePasswordMixin, UserChangeForm, UsernameField
from django.utils import timezone

from api.account import services
from api.account.selectors import get_current_affiliation_values, get_current_user_sdwt_prod_change
from api.account.models import (
    Affiliation,
    ExternalAffiliationSnapshot,
    User,
    UserCurrentAffiliation,
    UserProfile,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)
from api.common.services import UNASSIGNED_USER_SDWT_PROD


class AccountUserCreationForm(SetUnusablePasswordMixin, BaseUserCreationForm):
    """관리자 사용자 생성을 위한 커스텀 폼입니다."""

    usable_password = SetUnusablePasswordMixin.create_usable_password_field()

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("knox_id",)
        field_classes = {"knox_id": UsernameField}

    def __init__(self, *args, **kwargs):
        """비밀번호 입력을 선택 사항으로 변경합니다.

        입력:
        - *args, **kwargs: Django 폼 초기화 인자

        반환:
        - 없음

        부작용:
        - password 필드의 required 속성을 변경

        오류:
        - 없음
        """
        super().__init__(*args, **kwargs)
        # -----------------------------------------------------------------------------
        # 1) 비밀번호 필드 필수 해제
        # -----------------------------------------------------------------------------
        self.fields["password1"].required = False
        self.fields["password2"].required = False

        # -----------------------------------------------------------------------------
        # 2) knox_id 필수 설정
        # -----------------------------------------------------------------------------
        self.fields["knox_id"].required = True

    def clean(self):
        """knox_id 기반 식별 값 중복을 확인합니다.

        입력:
        - 없음

        반환:
        - dict: 정제된 폼 데이터

        부작용:
        - knox_id 중복 시 에러 추가

        오류:
        - 없음
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 검증 수행
        # -----------------------------------------------------------------------------
        cleaned_data = super().clean()

        # -----------------------------------------------------------------------------
        # 2) knox_id 확인
        # -----------------------------------------------------------------------------
        knox_id = cleaned_data.get("knox_id")
        if not knox_id:
            return cleaned_data

        # -----------------------------------------------------------------------------
        # 3) 사용자 식별 필드 중복 확인
        # -----------------------------------------------------------------------------
        username_field = User.USERNAME_FIELD
        if (
            User.objects.filter(**{username_field: knox_id})
            .exclude(pk=getattr(self.instance, "pk", None))
            .exists()
        ):
            self.add_error("knox_id", "이미 사용 중인 식별 값입니다.")
        return cleaned_data

    def save(self, commit=True):
        """knox_id를 사용자 식별 필드에 반영해 저장합니다.

        입력:
        - commit: 즉시 저장 여부

        반환:
        - User: 저장(또는 미저장)된 사용자 인스턴스

        부작용:
        - 사용자 식별 필드 값 설정

        오류:
        - 없음
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 저장 준비
        # -----------------------------------------------------------------------------
        user = super().save(commit=False)

        # -----------------------------------------------------------------------------
        # 2) 사용자 식별 필드 동기화
        # -----------------------------------------------------------------------------
        knox_id = self.cleaned_data.get("knox_id")
        if knox_id:
            setattr(user, User.USERNAME_FIELD, knox_id)

        # -----------------------------------------------------------------------------
        # 3) 저장 및 M2M 처리
        # -----------------------------------------------------------------------------
        if commit:
            user.save()
            if hasattr(self, "save_m2m"):
                self.save_m2m()
        return user


class AccountUserChangeForm(UserChangeForm):
    """관리자 사용자 변경을 위한 커스텀 폼입니다."""

    user_sdwt_prod_effective_from = forms.SplitDateTimeField(
        required=False,
        label="user_sdwt_prod 변경 시각",
        help_text="현재 user_sdwt_prod가 적용되는 기준 시각(effective_from)입니다. "
        "이 값을 변경하면 Emails에서 소속 변경 이후 메일 이동 시 이 시각이 사용됩니다.",
        widget=AdminSplitDateTime(),
    )

    class Meta(UserChangeForm.Meta):
        model = User
        exclude = (User.USERNAME_FIELD,)
        field_classes = {"knox_id": UsernameField}

    def __init__(self, *args, **kwargs):
        """현재 user_sdwt_prod 변경 시각을 초기값으로 채웁니다.

        입력:
        - *args, **kwargs: Django 폼 초기화 인자

        반환:
        - 없음

        부작용:
        - user_sdwt_prod_effective_from 초기값 설정

        오류:
        - 없음
        """
        super().__init__(*args, **kwargs)
        # -----------------------------------------------------------------------------
        # 1) 신규 객체는 초기값 설정 없이 종료
        # -----------------------------------------------------------------------------
        if not getattr(self.instance, "pk", None):
            return

        # -----------------------------------------------------------------------------
        # 2) 현재 변경 이력 조회 및 초기값 설정
        # -----------------------------------------------------------------------------
        change = get_current_user_sdwt_prod_change(user=self.instance)
        if change is None:
            return

        self.fields["user_sdwt_prod_effective_from"].initial = change.effective_from


@admin.register(User)
class AccountUserAdmin(DjangoUserAdmin):
    """사용자(User) 관리 화면 설정입니다."""

    form = AccountUserChangeForm
    add_form = AccountUserCreationForm
    actions = ()
    ordering = ("knox_id",)
    list_display = (
        "knox_id",
        "email",
        "current_department",
        "current_line",
        "current_user_sdwt_prod",
        "current_requires_reconfirm",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "current_affiliation__affiliation__line",
        "current_affiliation__requires_reconfirm",
    )
    search_fields = (
        "knox_id",
        "email",
        "department",
        "username",
        "first_name",
        "last_name",
        "current_affiliation__affiliation__department",
        "current_affiliation__affiliation__line",
        "current_affiliation__affiliation__user_sdwt_prod",
    )
    readonly_fields = (
        "current_department",
        "current_line",
        "current_user_sdwt_prod",
        "current_requires_reconfirm",
        "current_affiliation_confirmed_at",
    )

    fieldsets = (
        (None, {"fields": ("knox_id", "password")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Identity", {"fields": ("email",)}),
        ("Names", {"fields": ("username", "first_name", "last_name", "username_en", "givenname", "surname")}),
        (
            "Organization",
            {
                "fields": (
                    "deptid",
                    "department",
                    "current_department",
                    "current_line",
                    "current_user_sdwt_prod",
                    "current_requires_reconfirm",
                    "current_affiliation_confirmed_at",
                    "user_sdwt_prod_effective_from",
                    "grd_name",
                    "grdname_en",
                    "busname",
                    "intcode",
                    "intname",
                    "origincomp",
                    "employeetype",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "knox_id",
                    "usable_password",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    @admin.display(
        ordering="current_affiliation__affiliation__department",
        description="현재 department",
    )
    def current_department(self, obj):
        return get_current_affiliation_values(user=obj).get("department") or ""

    @admin.display(ordering="current_affiliation__affiliation__line", description="현재 line")
    def current_line(self, obj):
        return get_current_affiliation_values(user=obj).get("line") or ""

    @admin.display(
        ordering="current_affiliation__affiliation__user_sdwt_prod",
        description="현재 user_sdwt_prod",
    )
    def current_user_sdwt_prod(self, obj):
        return get_current_affiliation_values(user=obj).get("user_sdwt_prod") or ""

    @admin.display(
        boolean=True,
        ordering="current_affiliation__requires_reconfirm",
        description="재확인 필요",
    )
    def current_requires_reconfirm(self, obj):
        return bool(get_current_affiliation_values(user=obj).get("requires_reconfirm"))

    @admin.display(
        ordering="current_affiliation__confirmed_at",
        description="소속 확인 시각",
    )
    def current_affiliation_confirmed_at(self, obj):
        return get_current_affiliation_values(user=obj).get("confirmed_at")

    def save_model(self, request, obj, form, change):  # 타입 검사 생략: type: ignore[override]
        """관리자 저장 시 user_sdwt_prod 변경 시각을 동기화합니다.

        입력:
        - 요청: Django HttpRequest
        - obj: 저장 대상 User 객체
        - form: 변경 폼
        - change: 변경 여부 플래그

        반환:
        - 없음

        부작용:
        - UserSdwtProdChange.effective_from 갱신 가능
        - 관리자 메시지 출력

        오류:
        - 없음
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 저장 처리
        # -----------------------------------------------------------------------------
        super().save_model(request, obj, form, change)

        # -----------------------------------------------------------------------------
        # 2) 변경 시각 값 확인
        # -----------------------------------------------------------------------------
        effective_from = form.cleaned_data.get("user_sdwt_prod_effective_from")
        if effective_from is None:
            return

        # -----------------------------------------------------------------------------
        # 3) 타임존 보정
        # -----------------------------------------------------------------------------
        if timezone.is_naive(effective_from):
            effective_from = timezone.make_aware(effective_from, timezone.get_current_timezone())

        # -----------------------------------------------------------------------------
        # 4) 현재 user_sdwt_prod 유효성 확인
        # -----------------------------------------------------------------------------
        current_user_sdwt_prod = (get_current_affiliation_values(user=obj).get("user_sdwt_prod") or "").strip()
        if (
            not current_user_sdwt_prod
            or current_user_sdwt_prod.casefold() == UNASSIGNED_USER_SDWT_PROD.casefold()
        ):
            return

        # -----------------------------------------------------------------------------
        # 5) 변경 이력 조회
        # -----------------------------------------------------------------------------
        change_row = get_current_user_sdwt_prod_change(user=obj)
        if change_row is None:
            self.message_user(
                request,
                "현재 user_sdwt_prod에 대한 UserSdwtProdChange 기록이 없어 변경 시각을 저장할 수 없습니다. "
                "먼저 소속 변경을 적용(승인)하거나 UserSdwtProdChange에서 레코드를 생성해주세요.",
                level=messages.WARNING,
            )
            return

        # -----------------------------------------------------------------------------
        # 6) 변경 시각 업데이트
        # -----------------------------------------------------------------------------
        if change_row.effective_from != effective_from:
            change_row.effective_from = effective_from
            change_row.save(update_fields=["effective_from"])
            self.message_user(
                request,
                f"user_sdwt_prod 변경 시각을 {effective_from.isoformat()}로 업데이트했습니다.",
                level=messages.SUCCESS,
            )

    def get_result_label(self, result):  # 타입 검사 생략: type: ignore[override]
        return result.knox_id or str(result.pk)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """UserProfile 관리 화면 설정입니다."""

    list_display = ("user_knox_id", "role")
    list_filter = ("role",)
    search_fields = ("user__knox_id", "user__email")
    autocomplete_fields = ("user",)

    @admin.display(ordering="user__knox_id", description="사용자 knox_id")
    def user_knox_id(self, obj):
        return getattr(obj.user, "knox_id", None) or ""


@admin.register(Affiliation)
class AffiliationAdmin(admin.ModelAdmin):
    """Affiliation 관리 화면 설정입니다."""

    list_display = ("department", "line", "user_sdwt_prod")
    search_fields = ("department", "line", "user_sdwt_prod")
    list_filter = ("line",)
    ordering = ("department", "line", "user_sdwt_prod")


@admin.register(UserCurrentAffiliation)
class UserCurrentAffiliationAdmin(admin.ModelAdmin):
    """UserCurrentAffiliation 관리 화면 설정입니다."""

    list_display = (
        "user_knox_id",
        "department",
        "line",
        "user_sdwt_prod",
        "source",
        "requires_reconfirm",
        "confirmed_at",
    )
    list_filter = ("source", "requires_reconfirm", "affiliation__line")
    search_fields = (
        "user__knox_id",
        "user__email",
        "affiliation__department",
        "affiliation__line",
        "affiliation__user_sdwt_prod",
    )
    autocomplete_fields = ("user", "affiliation")
    ordering = ("user__knox_id",)

    @admin.display(ordering="user__knox_id", description="사용자 knox_id")
    def user_knox_id(self, obj):
        return getattr(obj.user, "knox_id", None) or ""

    @admin.display(ordering="affiliation__department", description="department")
    def department(self, obj):
        return getattr(obj.affiliation, "department", "") or ""

    @admin.display(ordering="affiliation__line", description="line")
    def line(self, obj):
        return getattr(obj.affiliation, "line", "") or ""

    @admin.display(ordering="affiliation__user_sdwt_prod", description="user_sdwt_prod")
    def user_sdwt_prod(self, obj):
        return getattr(obj.affiliation, "user_sdwt_prod", "") or ""


@admin.register(UserSdwtProdAccess)
class UserSdwtProdAccessAdmin(admin.ModelAdmin):
    """UserSdwtProdAccess 관리 화면 설정입니다."""

    list_display = ("user_knox_id", "affiliation_user_sdwt_prod", "role", "granted_by_knox_id", "created_at")
    list_filter = ("role", "affiliation__user_sdwt_prod")
    search_fields = (
        "user__knox_id",
        "user__email",
        "affiliation__department",
        "affiliation__line",
        "affiliation__user_sdwt_prod",
        "granted_by__knox_id",
        "granted_by__email",
    )
    autocomplete_fields = ("user", "affiliation", "granted_by")
    ordering = ("-created_at", "-id")

    @admin.display(ordering="user__knox_id", description="사용자 knox_id")
    def user_knox_id(self, obj):
        return getattr(obj.user, "knox_id", None) or ""

    @admin.display(ordering="affiliation__user_sdwt_prod", description="user_sdwt_prod")
    def affiliation_user_sdwt_prod(self, obj):
        return getattr(obj.affiliation, "user_sdwt_prod", "") or ""

    @admin.display(ordering="granted_by__knox_id", description="부여자 knox_id")
    def granted_by_knox_id(self, obj):
        granted_by = getattr(obj, "granted_by", None)
        return getattr(granted_by, "knox_id", None) or ""


@admin.register(UserSdwtProdChange)
class UserSdwtProdChangeAdmin(admin.ModelAdmin):
    """UserSdwtProdChange 관리 화면 설정입니다."""

    actions = ("approve_affiliation_changes",)
    list_display = (
        "user_knox_id",
        "from_user_sdwt_prod",
        "to_user_sdwt_prod",
        "effective_from",
        "status",
        "approved",
        "applied",
        "approved_by_knox_id",
        "approved_at",
    )
    list_filter = ("status", "approved", "applied", "to_user_sdwt_prod")
    search_fields = (
        "user__knox_id",
        "from_user_sdwt_prod",
        "to_user_sdwt_prod",
    )
    autocomplete_fields = ("user", "approved_by", "created_by")

    @admin.display(ordering="user__knox_id", description="사용자 knox_id")
    def user_knox_id(self, obj):
        return getattr(obj.user, "knox_id", None) or ""

    @admin.display(ordering="approved_by__knox_id", description="승인자 knox_id")
    def approved_by_knox_id(self, obj):
        approved_by = getattr(obj, "approved_by", None)
        return getattr(approved_by, "knox_id", None) or ""

    @admin.action(description="선택한 소속 변경 요청 승인")
    def approve_affiliation_changes(self, request, queryset):  # 타입 검사 생략: type: ignore[override]
        """선택된 소속 변경 요청을 승인 처리합니다.

        입력:
        - 요청: Django HttpRequest
        - queryset: 선택된 변경 요청 QuerySet

        반환:
        - 없음

        부작용:
        - 서비스 승인 로직 호출
        - 관리자 메시지 출력

        오류:
        - 없음(실패 건은 메시지로 집계)
        """
        # -----------------------------------------------------------------------------
        # 1) 사용자 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user or not request.user.is_authenticated:
            self.message_user(request, "승인 권한이 없습니다.", level=messages.ERROR)
            return None

        # -----------------------------------------------------------------------------
        # 2) 승인 처리 수행
        # -----------------------------------------------------------------------------
        approved_count = 0
        failed_count = 0
        failures: list[str] = []

        for change in queryset.iterator():
            payload, status_code = services.approve_affiliation_change(
                approver=request.user,
                change_id=change.id,
            )
            if status_code == 200:
                approved_count += 1
                continue

            failed_count += 1
            error_message = payload.get("error") if isinstance(payload, dict) else None
            failures.append(f"{change.id}: {error_message or 'unknown error'}")

        # -----------------------------------------------------------------------------
        # 3) 결과 메시지 출력
        # -----------------------------------------------------------------------------
        if failed_count:
            details = " | ".join(failures[:5])
            if len(failures) > 5:
                details = f"{details} | (+{len(failures) - 5} more)"
            self.message_user(
                request,
                f"승인 완료: {approved_count}건, 실패: {failed_count}건. 실패: {details}",
                level=messages.WARNING,
            )
            return None

        self.message_user(
            request,
            f"승인 완료: {approved_count}건.",
            level=messages.SUCCESS,
        )
        return None


@admin.register(ExternalAffiliationSnapshot)
class ExternalAffiliationSnapshotAdmin(admin.ModelAdmin):
    """ExternalAffiliationSnapshot 관리 화면 설정입니다."""

    list_display = (
        "knox_id",
        "predicted_user_sdwt_prod",
        "source_updated_at",
        "last_seen_at",
    )
    search_fields = ("knox_id", "predicted_user_sdwt_prod")
    ordering = ("-last_seen_at", "-id")
