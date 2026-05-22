# =============================================================================
# 모듈: Drone SOP 파일 target 기반 알림 초기 세팅 커맨드
# 주요 기능: JSON/CSV target 목록으로 Drone SOP/발송 이력/알림 설정 초기화 후 재생성
# 불변 조건: recipients는 account 사용자 pool 기준으로 자동 생성합니다.
# =============================================================================
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.drone import services


def _normalize_text(value: Any) -> str:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    return value.strip() if isinstance(value, str) else ""


_CSV_TRUE_VALUES = {"1", "true", "t", "yes", "y"}
_CSV_FALSE_VALUES = {"0", "false", "f", "no", "n"}


def _parse_csv_bool(value: Any, *, field_name: str, row_index: int) -> bool | None:
    """CSV boolean 값을 정규화하고 빈 값은 기본값 위임용 None으로 반환합니다."""

    normalized = _normalize_text(value).casefold()
    if not normalized:
        return None
    if normalized in _CSV_TRUE_VALUES:
        return True
    if normalized in _CSV_FALSE_VALUES:
        return False
    raise CommandError(f"CSV row {row_index}.{field_name} must be a boolean")


def _parse_csv_int(value: Any, *, field_name: str, row_index: int) -> int | None:
    """CSV 양의 정수 값을 정규화하고 빈 값은 None으로 반환합니다."""

    normalized = _normalize_text(value)
    if not normalized:
        return None
    try:
        parsed = int(normalized)
    except ValueError as exc:
        raise CommandError(f"CSV row {row_index}.{field_name} must be a positive integer") from exc
    if parsed <= 0:
        raise CommandError(f"CSV row {row_index}.{field_name} must be a positive integer")
    return parsed


def _set_text_if_present(target: dict[str, Any], *, key: str, value: Any) -> None:
    """CSV 문자열 값이 있을 때만 config dict에 반영합니다."""

    normalized = _normalize_text(value)
    if normalized:
        target[key] = normalized


def _set_value_if_present(target: dict[str, Any], *, key: str, value: Any) -> None:
    """CSV 정규화 값이 None이 아닐 때만 config dict에 반영합니다."""

    if value is not None:
        target[key] = value


def _build_csv_channels(row: dict[str, Any], *, row_index: int) -> dict[str, dict[str, Any]]:
    """CSV flat channel 컬럼을 기존 JSON channel 구조로 변환합니다."""

    jira: dict[str, Any] = {}
    _set_value_if_present(
        jira,
        key="enabled",
        value=_parse_csv_bool(row.get("jira_enabled"), field_name="jira_enabled", row_index=row_index),
    )
    _set_text_if_present(jira, key="template_key", value=row.get("jira_template_key"))
    _set_text_if_present(jira, key="jira_project_key", value=row.get("jira_project_key"))

    messenger: dict[str, Any] = {}
    _set_value_if_present(
        messenger,
        key="enabled",
        value=_parse_csv_bool(row.get("messenger_enabled"), field_name="messenger_enabled", row_index=row_index),
    )
    _set_text_if_present(messenger, key="template_key", value=row.get("messenger_template_key"))
    _set_value_if_present(
        messenger,
        key="chatroom_id",
        value=_parse_csv_int(
            row.get("messenger_chatroom_id"),
            field_name="messenger_chatroom_id",
            row_index=row_index,
        ),
    )
    _set_value_if_present(
        messenger,
        key="force_new_chatroom",
        value=_parse_csv_bool(
            row.get("messenger_force_new_chatroom"),
            field_name="messenger_force_new_chatroom",
            row_index=row_index,
        ),
    )

    mail: dict[str, Any] = {}
    _set_value_if_present(
        mail,
        key="enabled",
        value=_parse_csv_bool(row.get("mail_enabled"), field_name="mail_enabled", row_index=row_index),
    )
    _set_text_if_present(mail, key="template_key", value=row.get("mail_template_key"))

    return {"jira": jira, "messenger": messenger, "mail": mail}


def _build_csv_needtosend_rule(row: dict[str, Any], *, row_index: int) -> dict[str, Any]:
    """CSV flat rule 컬럼을 기존 JSON needtosend_rule 구조로 변환합니다."""

    rule: dict[str, Any] = {}
    _set_value_if_present(
        rule,
        key="enabled",
        value=_parse_csv_bool(row.get("needtosend_enabled"), field_name="needtosend_enabled", row_index=row_index),
    )
    _set_text_if_present(rule, key="comment_keyword", value=row.get("needtosend_comment_keyword"))
    _set_value_if_present(
        rule,
        key="ignore_sample_type",
        value=_parse_csv_bool(
            row.get("needtosend_ignore_sample_type"),
            field_name="needtosend_ignore_sample_type",
            row_index=row_index,
        ),
    )
    return rule


def _build_csv_mappings(row: dict[str, Any], *, row_index: int) -> list[dict[str, str]] | None:
    """CSV mappings JSON 셀을 기존 JSON mappings 구조로 변환합니다."""

    raw_mappings = _normalize_text(row.get("mappings"))
    if not raw_mappings:
        return None

    try:
        payload = json.loads(raw_mappings)
    except json.JSONDecodeError as exc:
        raise CommandError(f"CSV row {row_index}.mappings must be a JSON array") from exc
    if not isinstance(payload, list):
        raise CommandError(f"CSV row {row_index}.mappings must be a JSON array")

    mappings: list[dict[str, str]] = []
    for mapping_index, mapping in enumerate(payload, start=1):
        if not isinstance(mapping, dict):
            raise CommandError(f"CSV row {row_index}.mappings[{mapping_index}] must be an object")
        sdwt_prod = _normalize_text(mapping.get("sdwt_prod"))
        user_sdwt_prod = _normalize_text(mapping.get("user_sdwt_prod"))
        if not sdwt_prod and not user_sdwt_prod:
            raise CommandError(
                f"CSV row {row_index}.mappings[{mapping_index}] requires sdwt_prod or user_sdwt_prod"
            )
        mappings.append({"sdwt_prod": sdwt_prod, "user_sdwt_prod": user_sdwt_prod})
    return mappings


def _load_csv_seed_rows(*, path: Path) -> list[dict[str, Any]]:
    """CSV 파일을 읽어 target row 목록으로 변환합니다."""

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise CommandError("CSV file must include a header row")

            rows: list[dict[str, Any]] = []
            seen_targets: set[str] = set()
            for row_index, raw_row in enumerate(reader, start=2):
                row = dict(raw_row)
                line = _normalize_text(row.get("line")) or _normalize_text(row.get("line_id"))
                target_user_sdwt_prod = _normalize_text(row.get("target_user_sdwt_prod")) or _normalize_text(
                    row.get("user_sdwt_prod")
                )
                if not line:
                    raise CommandError(f"CSV row {row_index}.line is required")
                if not target_user_sdwt_prod:
                    raise CommandError(f"CSV row {row_index}.target_user_sdwt_prod is required")

                target_key = target_user_sdwt_prod.casefold()
                if target_key in seen_targets:
                    raise CommandError(
                        f"CSV row {row_index} duplicates target_user_sdwt_prod={target_user_sdwt_prod}"
                    )
                seen_targets.add(target_key)

                seed_row = {
                    "department": _normalize_text(row.get("department")),
                    "line_id": line,
                    "target_user_sdwt_prod": target_user_sdwt_prod,
                    "recipient_user_sdwt_prod": _normalize_text(row.get("recipient_user_sdwt_prod")),
                    "channels": _build_csv_channels(row, row_index=row_index),
                    "needtosend_rule": _build_csv_needtosend_rule(row, row_index=row_index),
                }
                mappings = _build_csv_mappings(row, row_index=row_index)
                if mappings is not None:
                    seed_row["mappings"] = mappings
                rows.append(seed_row)
    except OSError as exc:
        raise CommandError(f"failed to read file: {path}") from exc

    return rows


def _load_json_seed_rows(*, path: Path) -> list[dict[str, Any]]:
    """JSON 파일을 읽어 seed row 목록으로 검증/정규화합니다."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise CommandError(f"failed to read file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"invalid JSON file: {path}") from exc

    if not isinstance(payload, dict):
        raise CommandError("JSON root must be an object")
    targets = payload.get("targets")
    if not isinstance(targets, list):
        raise CommandError("JSON field 'targets' must be a list")

    rows: list[dict[str, Any]] = []
    for index, target in enumerate(targets, start=1):
        if not isinstance(target, dict):
            raise CommandError(f"targets[{index}] must be an object")
        line = _normalize_text(target.get("line")) or _normalize_text(target.get("line_id"))
        target_user_sdwt_prod = _normalize_text(target.get("target_user_sdwt_prod")) or _normalize_text(
            target.get("user_sdwt_prod")
        )
        if not line:
            raise CommandError(f"targets[{index}].line is required")
        if not target_user_sdwt_prod:
            raise CommandError(f"targets[{index}].target_user_sdwt_prod is required")
        row = dict(target)
        row["line_id"] = line
        row["target_user_sdwt_prod"] = target_user_sdwt_prod
        rows.append(row)
    return rows


def _load_seed_rows(*, file_path: str) -> list[dict[str, Any]]:
    """JSON 또는 CSV 파일을 읽어 seed row 목록으로 검증/정규화합니다."""

    path = Path(file_path)
    if path.suffix.casefold() == ".csv":
        return _load_csv_seed_rows(path=path)
    return _load_json_seed_rows(path=path)


class Command(BaseCommand):
    """JSON/CSV target 목록 기준으로 Drone SOP 알림 기본 설정을 생성합니다."""

    help = "Seed Drone SOP notification targets, mappings, channel defaults, rules, and recipients from JSON or CSV."

    def add_arguments(self, parser) -> None:
        """커맨드 옵션을 등록합니다."""

        parser.add_argument(
            "--file",
            required=True,
            help="Drone target/channel/mapping 설정 JSON 또는 CSV 파일 경로입니다.",
        )
        parser.add_argument(
            "--template-key",
            default="common",
            help="새 채널 설정에 사용할 template_key입니다. 기본값은 common입니다.",
        )
        parser.add_argument(
            "--comment-keyword",
            default="$SETUP_EQP",
            help="새 자동예약 규칙에 저장할 comment keyword입니다. 기본값은 $SETUP_EQP입니다.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="생성 예정 카운트만 계산하고 DB 변경을 롤백합니다.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """JSON/CSV seed를 실행하고 결과를 출력합니다."""

        file_path = str(options.get("file") or "")
        rows = _load_seed_rows(file_path=file_path)
        dry_run = bool(options.get("dry_run"))
        with transaction.atomic():
            try:
                result = services.seed_drone_sop_notification_defaults_from_rows(
                    rows=rows,
                    template_key=str(options.get("template_key") or "common"),
                    comment_keyword=str(options.get("comment_keyword") or "$SETUP_EQP"),
                )
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            if dry_run:
                transaction.set_rollback(True)

        counts = " ".join(f"{key}={value}" for key, value in result.as_dict().items())
        prefix = "dry-run: " if dry_run else ""
        file_label = "CSV" if Path(file_path).suffix.casefold() == ".csv" else "JSON"
        self.stdout.write(self.style.SUCCESS(f"{prefix}drone {file_label} target seed complete: {counts}"))
