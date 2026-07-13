# =============================================================================
# 모듈 설명: 로컬 dev 계정 보장 헬퍼를 제공합니다.
# - 주요 함수: ensure_dev_dummy_superuser
# - 불변 조건: ENVIRONMENT=development 인 경우에만 dummy 사용자를 보정합니다.
# =============================================================================

from __future__ import annotations

import os
from typing import Any

from django.contrib.auth import get_user_model


def _env(key: str, default: str = "") -> str:
    """환경변수 문자열 값을 공백 제거 후 반환합니다."""

    value = os.environ.get(key)
    if value is None:
        return default
    value = value.strip()
    return value or default


def ensure_dev_dummy_superuser() -> Any | None:
    """development 환경의 dummy ADFS 사용자를 staff 슈퍼유저로 생성/보정합니다.

    입력:
    - 없음

    반환:
    - User | None: 보장된 dummy 사용자 또는 dev 환경이 아니면 None

    부작용:
    - dev 환경에서 `DUMMY_ADFS_*` 기준 사용자 생성/갱신 가능

    오류:
    - DB 저장 중 발생한 예외는 호출자에게 전파
    """

    if _env("ENVIRONMENT").lower() != "development":
        return None

    sabun = _env("DUMMY_ADFS_SABUN")
    loginid = _env("DUMMY_ADFS_LOGINID")
    if not sabun or not loginid:
        return None

    UserModel = get_user_model()
    defaults = {
        "username": _env("DUMMY_ADFS_NAME", "Dummy User"),
        "knox_id": loginid,
        "email": _env("DUMMY_ADFS_EMAIL", "dummy.user@example.com"),
        "department": _env("DUMMY_ADFS_DEPT", "Development"),
    }
    user = UserModel.objects.filter(sabun=sabun).first()
    if user is None:
        return UserModel.objects.create_superuser(
            sabun=sabun,
            password=_env("DJANGO_SUPERUSER_PASSWORD", "dkssud123!"),
            **defaults,
        )

    update_fields: list[str] = []
    for field_name, value in defaults.items():
        if value and getattr(user, field_name) != value:
            setattr(user, field_name, value)
            update_fields.append(field_name)

    for field_name in ("is_staff", "is_superuser"):
        if getattr(user, field_name) is not True:
            setattr(user, field_name, True)
            update_fields.append(field_name)

    if update_fields:
        user.save(update_fields=update_fields)

    return user
