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
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, SetUnusablePasswordMixin, UserChangeForm, UsernameField
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from api.account import services
from api.account.selectors import get_current_affiliation_values, get_current_user_sdwt_prod_change
from api.account.models import (
    ACCESS_MANAGERS_GROUP_NAME,
    ACCESS_SCOPE_PORTAL,
    MANAGE_ACCESS_PERMISSION,
    SYSTEM_ACCESS_SCOPE_KEYS,
    AccessAuditLog,
    AccessPolicyRule,
    AccessScope,
    Affiliation,
    ExternalAffiliationSnapshot,
    User,
    UserAccess,
    UserCurrentAffiliation,
    UserProfile,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)
from api.common.services import UNASSIGNED_USER_SDWT_PROD


_SENSITIVE_USER_PERMISSION_FIELDS = ("is_staff", "is_superuser", "groups", "user_permissions")
_MANAGE_ACCESS_BEFORE_ATTRIBUTE = "_account_manage_access_before"


def _user_has_manage_access_capability(*, user_id: int | None) -> bool:
    """DB 기준으로 사용자의 접근 권한 관리 capability 보유 여부를 반환합니다."""

    if not user_id:
        return False
    app_label, codename = MANAGE_ACCESS_PERMISSION.split(".", maxsplit=1)
    return User.objects.filter(pk=user_id).filter(
        Q(is_superuser=True)
        | Q(
            user_permissions__content_type__app_label=app_label,
            user_permissions__codename=codename,
        )
        | Q(
            groups__permissions__content_type__app_label=app_label,
            groups__permissions__codename=codename,
        )
    ).exists()


class SuperuserWriteAdminMixin:
    """민감한 접근 권한 모델의 Admin 쓰기를 superuser에게만 허용합니다."""

    def has_add_permission(self, request):
        """superuser에게만 생성 권한을 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """superuser에게만 변경 권한을 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """superuser에게만 삭제 권한을 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_delete_permission(request, obj)


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(Group)
class AccountGroupAdmin(DjangoGroupAdmin):
    """Django Group의 권한 구성을 superuser만 관리하도록 제한합니다."""

    actions = ()

    def has_add_permission(self, request):
        """superuser에게만 그룹 생성 권한을 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """표준 권한 관리자 그룹은 불변으로 두고 나머지는 superuser만 변경합니다."""

        if obj is not None and obj.name == ACCESS_MANAGERS_GROUP_NAME:
            return False
        return bool(getattr(request.user, "is_superuser", False)) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """표준 권한 관리자 그룹 삭제를 막고 나머지는 superuser만 삭제합니다."""

        if obj is not None and obj.name == ACCESS_MANAGERS_GROUP_NAME:
            return False
        return bool(getattr(request.user, "is_superuser", False)) and super().has_delete_permission(request, obj)


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

    def get_readonly_fields(self, request, obj=None):
        """일반 staff가 인증·권한 관련 민감 필드를 변경하지 못하게 합니다."""

        readonly_fields = tuple(super().get_readonly_fields(request, obj))
        if getattr(request.user, "is_superuser", False):
            return readonly_fields
        return tuple(dict.fromkeys((*readonly_fields, *_SENSITIVE_USER_PERMISSION_FIELDS)))

    def has_change_permission(self, request, obj=None):
        """일반 staff가 superuser 또는 권한 관리자 계정을 변경하지 못하게 합니다."""

        if (
            obj is not None
            and not getattr(request.user, "is_superuser", False)
            and _user_has_manage_access_capability(user_id=obj.pk)
        ):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """일반 staff가 superuser 또는 권한 관리자 계정을 삭제하지 못하게 합니다."""

        if (
            obj is not None
            and not getattr(request.user, "is_superuser", False)
            and _user_has_manage_access_capability(user_id=obj.pk)
        ):
            return False
        return super().has_delete_permission(request, obj)

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
        setattr(
            request,
            _MANAGE_ACCESS_BEFORE_ATTRIBUTE,
            _user_has_manage_access_capability(user_id=obj.pk),
        )

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

    def save_related(self, request, form, formsets, change):
        """권한 관리자 capability의 유효 부여·회수를 감사 로그에 기록합니다."""

        before = bool(
            getattr(
                request,
                _MANAGE_ACCESS_BEFORE_ATTRIBUTE,
                _user_has_manage_access_capability(user_id=form.instance.pk),
            )
        )
        with transaction.atomic():
            super().save_related(request, form, formsets, change)
            after = _user_has_manage_access_capability(user_id=form.instance.pk)
            if before == after:
                return
            AccessAuditLog.objects.create(
                actor=request.user if getattr(request.user, "is_authenticated", False) else None,
                target_user=form.instance,
                action=(
                    AccessAuditLog.Actions.ACCESS_MANAGER_GRANT
                    if after
                    else AccessAuditLog.Actions.ACCESS_MANAGER_REVOKE
                ),
                before={"canManageAccess": before},
                after={"canManageAccess": after},
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


def _serialize_admin_policy_rule(obj):
    """Admin 감사 로그용 정책 규칙 snapshot을 반환합니다."""

    if obj is None:
        return {}
    return {
        "id": obj.id,
        "scope": getattr(obj.scope, "key", None),
        "ruleType": obj.rule_type,
        "value": obj.value,
        "role": obj.role,
        "isActive": obj.is_active,
    }


def _serialize_admin_access_scope(obj):
    """Admin 감사 로그용 접근 scope snapshot을 반환합니다."""

    if obj is None:
        return {}
    return {
        "id": obj.id,
        "key": obj.key,
        "name": obj.name,
        "scopeType": obj.scope_type,
        "isActive": obj.is_active,
        "requestable": obj.requestable,
        "defaultRole": obj.default_role,
    }


def _serialize_admin_user_access(obj):
    """Admin 감사 로그용 사용자 접근 상태 snapshot을 반환합니다."""

    if obj is None:
        return {}
    decided_by = getattr(obj, "decided_by", None)
    return {
        "id": obj.id,
        "scope": getattr(obj.scope, "key", None),
        "status": obj.status,
        "role": obj.role,
        "department": obj.department,
        "reason": obj.reason,
        "user": {
            "id": obj.user_id,
            "knoxId": getattr(obj.user, "knox_id", None),
        },
        "decidedBy": {
            "id": decided_by.id,
            "knoxId": getattr(decided_by, "knox_id", None),
        } if decided_by else None,
    }


def _resolve_admin_user_access_action(*, before, after):
    """Admin 사용자 접근 변경 내용을 감사 로그 action으로 분류합니다."""

    if after.get("status") == UserAccess.Status.DENIED:
        return AccessAuditLog.Actions.REVOKE
    if after.get("status") == UserAccess.Status.ALLOWED:
        if before.get("status") == UserAccess.Status.ALLOWED and before.get("role") != after.get("role"):
            return AccessAuditLog.Actions.CHANGE_ROLE
        return AccessAuditLog.Actions.GRANT
    return AccessAuditLog.Actions.USER_ACCESS_UPDATE


@admin.register(AccessScope)
class AccessScopeAdmin(SuperuserWriteAdminMixin, admin.ModelAdmin):
    """접근 권한 대상 관리 화면 설정입니다."""

    list_display = ("key", "name", "scope_type", "is_active", "requestable", "default_role", "created_at")
    list_filter = ("scope_type", "is_active", "requestable")
    search_fields = ("key", "name")
    ordering = ("key",)

    def get_readonly_fields(self, request, obj=None):
        """시스템 scope의 식별 키와 유형은 Admin에서 변경하지 못하게 합니다."""

        if obj is not None and obj.key in SYSTEM_ACCESS_SCOPE_KEYS:
            return ("key", "scope_type")
        return ()

    def has_delete_permission(self, request, obj=None):
        """시스템 scope 삭제 권한을 항상 거부합니다."""

        if obj is not None and obj.key in SYSTEM_ACCESS_SCOPE_KEYS:
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        """scope 변경을 저장하고 같은 트랜잭션에서 감사 로그를 생성합니다."""

        with transaction.atomic():
            before_obj = AccessScope.objects.filter(pk=obj.pk).first() if change else None
            if before_obj is not None and before_obj.key in SYSTEM_ACCESS_SCOPE_KEYS:
                if obj.key != before_obj.key:
                    raise ValidationError({"key": "시스템 scope key는 변경할 수 없습니다."})
                if obj.scope_type != before_obj.scope_type:
                    raise ValidationError({"scope_type": "시스템 scope 유형은 변경할 수 없습니다."})

            before = _serialize_admin_access_scope(before_obj)
            super().save_model(request, obj, form, change)
            after = _serialize_admin_access_scope(obj)
            AccessAuditLog.objects.create(
                scope=obj,
                actor=request.user if getattr(request.user, "is_authenticated", False) else None,
                action=AccessAuditLog.Actions.SCOPE_UPDATE if change else AccessAuditLog.Actions.SCOPE_CREATE,
                before=before,
                after=after,
            )

    def delete_model(self, request, obj):
        """일반 scope 삭제를 기록하고 시스템 scope 삭제는 거부합니다."""

        if obj.key in SYSTEM_ACCESS_SCOPE_KEYS:
            raise PermissionDenied("시스템 scope는 삭제할 수 없습니다.")

        with transaction.atomic():
            before = _serialize_admin_access_scope(obj)
            AccessAuditLog.objects.create(
                scope=obj,
                actor=request.user if getattr(request.user, "is_authenticated", False) else None,
                action=AccessAuditLog.Actions.SCOPE_DELETE,
                before=before,
                after={},
            )
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """일괄 삭제에서도 시스템 scope를 제외하고 개별 감사 로그를 남깁니다."""

        for obj in list(queryset):
            if obj.key not in SYSTEM_ACCESS_SCOPE_KEYS:
                self.delete_model(request, obj)


@admin.register(AccessPolicyRule)
class AccessPolicyRuleAdmin(SuperuserWriteAdminMixin, admin.ModelAdmin):
    """scope별 기본 접근 정책 관리 화면 설정입니다."""

    list_display = ("scope_key", "rule_type", "value", "role", "is_active", "created_at")
    list_filter = ("scope__key", "rule_type", "role", "is_active")
    search_fields = ("scope__key", "scope__name", "value")
    autocomplete_fields = ("scope",)
    ordering = ("scope__key", "rule_type", "value")

    @admin.display(ordering="scope__key", description="scope")
    def scope_key(self, obj):
        return getattr(obj.scope, "key", "") or ""

    def save_model(self, request, obj, form, change):
        """관리자 직접 정책 변경도 감사 로그에 기록합니다."""

        with transaction.atomic():
            before_obj = AccessPolicyRule.objects.filter(pk=obj.pk).select_related("scope").first() if change else None
            before = _serialize_admin_policy_rule(before_obj) if before_obj else {}
            super().save_model(request, obj, form, change)
            after = _serialize_admin_policy_rule(obj)
            AccessAuditLog.objects.create(
                scope=obj.scope,
                actor=request.user if getattr(request.user, "is_authenticated", False) else None,
                policy_rule=obj,
                action=AccessAuditLog.Actions.POLICY_UPDATE if change else AccessAuditLog.Actions.POLICY_CREATE,
                before=before,
                after=after,
            )

    def delete_model(self, request, obj):
        """관리자 직접 정책 삭제도 감사 로그에 기록합니다."""

        with transaction.atomic():
            before = _serialize_admin_policy_rule(obj)
            AccessAuditLog.objects.create(
                scope=obj.scope,
                actor=request.user if getattr(request.user, "is_authenticated", False) else None,
                policy_rule=obj,
                action=AccessAuditLog.Actions.POLICY_DELETE,
                before=before,
                after={},
            )
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """관리자 일괄 정책 삭제도 감사 로그에 기록합니다."""

        for obj in list(queryset.select_related("scope")):
            self.delete_model(request, obj)


@admin.register(UserAccess)
class UserAccessAdmin(SuperuserWriteAdminMixin, admin.ModelAdmin):
    """사용자별 scope 접근 상태 관리 화면 설정입니다."""

    list_display = (
        "scope_key",
        "user_knox_id",
        "department",
        "status",
        "role",
        "requested_at",
        "decided_by_knox_id",
        "decided_at",
    )
    list_filter = ("scope__key", "status", "role", "department")
    search_fields = (
        "scope__key",
        "scope__name",
        "user__knox_id",
        "user__email",
        "user__username",
        "department",
        "decided_by__knox_id",
    )
    autocomplete_fields = ("scope", "user", "decided_by")
    readonly_fields = ("requested_at", "updated_at")
    ordering = ("-requested_at", "-id")

    @admin.display(ordering="scope__key", description="scope")
    def scope_key(self, obj):
        return getattr(obj.scope, "key", "") or ""

    @admin.display(ordering="user__knox_id", description="사용자 knox_id")
    def user_knox_id(self, obj):
        return getattr(obj.user, "knox_id", None) or ""

    @admin.display(ordering="decided_by__knox_id", description="결정자 knox_id")
    def decided_by_knox_id(self, obj):
        decided_by = getattr(obj, "decided_by", None)
        return getattr(decided_by, "knox_id", None) or ""

    def save_model(self, request, obj, form, change):
        """관리자 직접 사용자 접근 상태 변경도 감사 로그에 기록합니다."""

        with transaction.atomic():
            before_obj = (
                UserAccess.objects.filter(pk=obj.pk).select_related("scope", "user", "decided_by").first()
                if change
                else None
            )
            before = _serialize_admin_user_access(before_obj) if before_obj else {}
            super().save_model(request, obj, form, change)
            after = _serialize_admin_user_access(obj)
            AccessAuditLog.objects.create(
                scope=obj.scope,
                actor=request.user if getattr(request.user, "is_authenticated", False) else None,
                target_user=obj.user,
                action=_resolve_admin_user_access_action(before=before, after=after),
                before=before,
                after=after,
                reason=obj.reason,
            )

    def delete_model(self, request, obj):
        """관리자 직접 사용자 접근 row 삭제도 감사 로그에 기록합니다."""

        with transaction.atomic():
            before = _serialize_admin_user_access(obj)
            AccessAuditLog.objects.create(
                scope=obj.scope,
                actor=request.user if getattr(request.user, "is_authenticated", False) else None,
                target_user=obj.user,
                action=AccessAuditLog.Actions.RESET_TO_POLICY,
                before=before,
                after={},
            )
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """관리자 일괄 사용자 접근 row 삭제도 감사 로그에 기록합니다."""

        for obj in list(queryset.select_related("scope", "user", "decided_by")):
            self.delete_model(request, obj)


@admin.register(AccessAuditLog)
class AccessAuditLogAdmin(admin.ModelAdmin):
    """scope 접근 권한 감사 로그 조회 화면 설정입니다."""

    actions = ()
    list_display = (
        "created_at",
        "scope_key",
        "action",
        "target_user_knox_id",
        "actor_knox_id",
        "policy_rule_label",
    )
    list_filter = ("scope__key", "action", "created_at")
    search_fields = (
        "scope__key",
        "actor__knox_id",
        "target_user__knox_id",
        "policy_rule__value",
        "reason",
    )
    readonly_fields = (
        "id",
        "scope",
        "actor",
        "target_user",
        "policy_rule",
        "action",
        "before",
        "after",
        "reason",
        "created_at",
    )
    ordering = ("-created_at", "-id")

    def has_add_permission(self, request):
        """감사 로그 수동 추가를 허용하지 않습니다."""

        return False

    def has_change_permission(self, request, obj=None):
        """감사 로그 수정을 허용하지 않습니다."""

        return False

    def has_delete_permission(self, request, obj=None):
        """감사 로그 삭제를 허용하지 않습니다."""

        return False

    @admin.display(ordering="scope__key", description="scope")
    def scope_key(self, obj):
        return getattr(obj.scope, "key", "") or ""

    @admin.display(ordering="target_user__knox_id", description="대상 knox_id")
    def target_user_knox_id(self, obj):
        return getattr(obj.target_user, "knox_id", None) or ""

    @admin.display(ordering="actor__knox_id", description="작업자 knox_id")
    def actor_knox_id(self, obj):
        return getattr(obj.actor, "knox_id", None) or ""

    @admin.display(ordering="policy_rule__value", description="정책")
    def policy_rule_label(self, obj):
        policy_rule = getattr(obj, "policy_rule", None)
        if policy_rule is None:
            return ""
        return f"{policy_rule.rule_type}:{policy_rule.value}"


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
        "username",
        "predicted_user_sdwt_prod",
        "source_updated_at",
        "last_seen_at",
    )
    search_fields = ("knox_id", "username", "predicted_user_sdwt_prod")
    ordering = ("-last_seen_at", "-id")
