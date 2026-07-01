# =============================================================================
# 모듈: L3 Spider 셀렉터
# 주요 함수: get_data_root, iter_data_files, read_parquet_columns, list_mail_rules_for_user
# 주요 가정: 파일시스템/DB 조회만 수행하며 쓰기 작업은 하지 않습니다.
# =============================================================================
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q

import pandas as pd


def get_data_root() -> Path:
    """L3 Spider 데이터 루트 경로를 반환합니다."""

    return Path(settings.L3_SPIDER_DATA_ROOT).expanduser().resolve()


def ensure_data_root() -> Path:
    """데이터 루트가 존재하는지 확인하고 경로를 반환합니다."""

    root = get_data_root()
    if not root.exists():
        raise FileNotFoundError(f"L3 Spider 데이터 경로를 찾을 수 없습니다: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"L3 Spider 데이터 경로가 폴더가 아닙니다: {root}")
    return root


def iter_data_files(selection: dict[str, object]) -> Iterable[Path]:
    """선택 조건에 해당하는 Parquet 파일 목록을 순회합니다."""

    root = ensure_data_root()
    root_resolved = root.resolve()
    for date in selection.get("dates", []):
        for line_id in selection.get("lineIds", []):
            for process_id in selection.get("processIds", []):
                for eds_step in selection.get("edsSteps", []):
                    dir_path = root / date / line_id / process_id / eds_step
                    try:
                        dir_path.resolve().relative_to(root_resolved)
                    except ValueError as exc:
                        raise ValueError("데이터 경로가 루트 밖으로 벗어났습니다.") from exc
                    if not dir_path.exists() or not dir_path.is_dir():
                        continue
                    for path in dir_path.iterdir():
                        if path.is_file():
                            yield path


def iter_filter_candidate_files(
    dates: list[str],
    line_ids: list[str],
    process_ids: list[str],
    eds_step: str,
    step_seq: str,
    ppid: str,
) -> Iterable[Path]:
    """step_seq#ppid#* 패턴에 해당하는 파일만 순회합니다."""

    root = ensure_data_root()
    root_resolved = root.resolve()
    prefix = f"{step_seq}#{ppid}#"

    for date in dates:
        for line_id in line_ids:
            for process_id in process_ids:
                dir_path = root / date / line_id / process_id / eds_step
                try:
                    dir_path.resolve().relative_to(root_resolved)
                except ValueError:
                    continue
                if not dir_path.exists() or not dir_path.is_dir():
                    continue
                for path in dir_path.iterdir():
                    if path.is_file() and path.name.startswith(prefix):
                        yield path


def iter_all_data_files() -> Iterable[Path]:
    """데이터 루트 아래의 모든 일반 파일을 순회합니다."""

    root = ensure_data_root()
    for path in root.glob("*/*/*/*/*"):
        if path.is_file():
            yield path


def read_parquet_columns(path: Path, columns: Sequence[str]) -> pd.DataFrame:
    """필요 컬럼만 우선 읽고, 누락 컬럼이 있으면 가능한 컬럼만 반환합니다."""

    try:
        return pd.read_parquet(path, engine="pyarrow", columns=list(columns))
    except Exception:
        frame = pd.read_parquet(path, engine="pyarrow")
        if "display status" in frame.columns and "display_status" not in frame.columns:
            frame = frame.rename(columns={"display status": "display_status"})
        available_columns = [column for column in columns if column in frame.columns]
        return frame[available_columns]


def list_mail_rules_for_user(user_id: int):
    """사용자가 읽을 수 있는 L3 Spider 메일 rule 목록을 조회합니다."""

    from .models import L3SpiderMailRule

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .prefetch_related("permissions__user")
        .filter(Q(created_by_id=user_id) | Q(permissions__user_id=user_id))
        .distinct()
    )


def get_mail_rule_for_user(*, rule_id: int, user_id: int):
    """사용자가 읽을 수 있는 L3 Spider 메일 rule 단건을 조회합니다."""

    from .models import L3SpiderMailRule

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .prefetch_related("permissions__user")
        .filter(Q(created_by_id=user_id) | Q(permissions__user_id=user_id))
        .distinct()
        .get(pk=rule_id)
    )


def get_writable_mail_rule_for_user(*, rule_id: int, user_id: int):
    """사용자가 수정할 수 있는 L3 Spider 메일 rule 단건을 조회합니다."""

    from .models import L3SpiderMailRule, L3SpiderMailRulePermission

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .prefetch_related("permissions__user")
        .filter(
            Q(created_by_id=user_id)
            | Q(
                permissions__user_id=user_id,
                permissions__access_level=L3SpiderMailRulePermission.AccessLevels.WRITE,
            )
        )
        .distinct()
        .get(pk=rule_id)
    )


def get_owned_mail_rule_for_user(*, rule_id: int, user_id: int):
    """사용자가 owner인 L3 Spider 메일 rule 단건을 조회합니다."""

    from .models import L3SpiderMailRule

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .prefetch_related("permissions__user")
        .get(pk=rule_id, created_by_id=user_id)
    )


def list_mail_rule_permissions(*, rule_id: int):
    """메일 rule의 공유 권한 목록을 조회합니다."""

    from .models import L3SpiderMailRulePermission

    return (
        L3SpiderMailRulePermission.objects.select_related("user", "granted_by")
        .filter(rule_id=rule_id)
        .order_by("user__username", "user__sabun", "id")
    )


def find_user_for_mail_rule_permission(identifier: str):
    """메일 rule 권한 부여 대상 사용자를 식별자로 조회합니다."""

    user_model = get_user_model()
    value = str(identifier or "").strip()
    if not value:
        return None

    query = Q(sabun=value)
    lowered = value.lower()
    query |= Q(email__iexact=lowered)
    query |= Q(username__iexact=value)
    query |= Q(knox_id__iexact=value)
    return user_model.objects.filter(query).order_by("id").first()


def list_active_mail_rules_for_trigger(*, limit: int):
    """Airflow trigger가 처리할 활성 메일 rule 목록을 조회합니다."""

    from .models import L3SpiderMailRule

    return (
        L3SpiderMailRule.objects.select_related("created_by")
        .filter(is_active=True)
        .order_by("send_time", "id")[:limit]
    )
