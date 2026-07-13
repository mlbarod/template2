# =============================================================================
# 모듈: L3 Spider line name rule CSV 적재 command
# 주요 기능: CSV 규칙 검증·정규화 후 L3SpiderLineNameRule 모델에 적재
# 불변 조건: CSV 순서는 priority로 보존하고 모든 쓰기는 단일 transaction에서 실행합니다.
# =============================================================================
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.l3_spider.models import L3SpiderLineNameRule


_REQUIRED_COLUMNS = {"type", "line_id", "process_id", "step_seq", "line_name"}
_REQUIRED_MODEL_FIELDS = {
    "rule_type",
    "line_id",
    "process_id",
    "step_seq",
    "line_name",
    "priority",
    "is_active",
}
_VALID_RULE_TYPES = {"base", "override"}
_WILDCARD_VALUES = {"", "%", "*"}


@dataclass(frozen=True)
class ParsedLineNameRule:
    """DB에 적재할 단일 line name 규칙입니다."""

    rule_type: str
    line_id: str
    process_id: str
    step_seq: str
    line_name: str
    priority: int

    @property
    def key(self) -> tuple[str, str, str, str]:
        """동일 규칙을 판별하는 정규화 key를 반환합니다."""

        return (
            self.rule_type,
            self.line_id.casefold(),
            self.process_id.casefold(),
            self.step_seq.casefold(),
        )


@dataclass(frozen=True)
class ParsedRuleSet:
    """CSV 파싱 결과와 중복으로 제외된 행 수입니다."""

    rules: list[ParsedLineNameRule]
    duplicate_count: int


def _normalize_pattern(value: object) -> str:
    """기존 CSV와 동일하게 빈 값, `%`, `*`를 공통 wildcard로 정규화합니다."""

    normalized = str(value or "").strip()
    return "*" if normalized in _WILDCARD_VALUES else normalized


def _load_rules_csv(path: Path) -> ParsedRuleSet:
    """CSV를 읽어 기존 매칭 의미와 순서를 보존한 규칙 목록으로 변환합니다."""

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            effective_lines = [
                line for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except OSError as exc:
        raise CommandError(f"line name rule CSV를 읽을 수 없습니다: {path}") from exc

    reader = csv.DictReader(effective_lines)
    fieldnames = set(reader.fieldnames or [])
    missing_columns = sorted(_REQUIRED_COLUMNS - fieldnames)
    if missing_columns:
        raise CommandError(
            "line name rule CSV 필수 컬럼이 없습니다: " + ", ".join(missing_columns)
        )

    rules: list[ParsedLineNameRule] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    duplicate_count = 0
    for priority, row in enumerate(reader, start=1):
        rule_type = str(row.get("type") or "").strip().casefold()
        if rule_type not in _VALID_RULE_TYPES:
            raise CommandError(
                f"line name rule CSV 데이터 행 {priority}의 type이 유효하지 않습니다: {rule_type!r}"
            )

        line_name = str(row.get("line_name") or "").strip()
        if not line_name:
            raise CommandError(f"line name rule CSV 데이터 행 {priority}의 line_name이 비어 있습니다.")

        # base는 step_seq를, override는 line_id를 사용하지 않으므로 wildcard로 통일합니다.
        line_id = _normalize_pattern(row.get("line_id"))
        process_id = _normalize_pattern(row.get("process_id"))
        step_seq = _normalize_pattern(row.get("step_seq"))
        if rule_type == "base":
            step_seq = "*"
        else:
            line_id = "*"

        rule = ParsedLineNameRule(
            rule_type=rule_type,
            line_id=line_id,
            process_id=process_id,
            step_seq=step_seq,
            line_name=line_name,
            priority=priority,
        )
        if rule.key in seen_keys:
            # 기존 CSV resolver의 exact setdefault/파일 순서 동작처럼 첫 규칙을 유지합니다.
            duplicate_count += 1
            continue
        seen_keys.add(rule.key)
        rules.append(rule)

    return ParsedRuleSet(rules=rules, duplicate_count=duplicate_count)


def _get_line_name_rule_model():
    """L3SpiderLineNameRule 모델의 import 필드 계약을 확인합니다."""

    field_names = {field.name for field in L3SpiderLineNameRule._meta.get_fields()}
    missing_fields = sorted(_REQUIRED_MODEL_FIELDS - field_names)
    if missing_fields:
        raise CommandError(
            "L3SpiderLineNameRule 필수 필드가 없습니다: " + ", ".join(missing_fields)
        )
    return L3SpiderLineNameRule


class Command(BaseCommand):
    """CSV의 L3 Spider line name 규칙을 대상 서버 DB에 적재합니다."""

    help = "Import L3 Spider line_name_rules.csv into L3SpiderLineNameRule."

    def add_arguments(self, parser) -> None:
        """CSV 경로와 적재 모드 옵션을 등록합니다."""

        parser.add_argument(
            "--path",
            dest="path",
            help="CSV 경로. 기본값: L3_SPIDER_DATA_ROOT/_meta/line_name_rules.csv",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="기존 line name 규칙 전체를 삭제한 뒤 CSV 규칙으로 교체",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="CSV와 모델 계약만 검증하고 DB에는 반영하지 않음",
        )

    def handle(self, *args, **options) -> None:
        """CSV 규칙을 검증하고 선택한 모드로 DB에 적재합니다."""

        default_path = Path(settings.L3_SPIDER_DATA_ROOT) / "_meta" / "line_name_rules.csv"
        path = Path(options["path"]).expanduser() if options.get("path") else default_path
        parsed = _load_rules_csv(path)
        model = _get_line_name_rule_model()

        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"dry-run 완료: path={path}, rules={len(parsed.rules)}, "
                    f"duplicates={parsed.duplicate_count}"
                )
            )
            return

        created_count = 0
        updated_count = 0
        unchanged_count = 0
        with transaction.atomic():
            if options["replace"]:
                model.objects.all().delete()

            for rule in parsed.rules:
                lookup = {
                    "rule_type": rule.rule_type,
                    "line_id__iexact": rule.line_id,
                    "process_id__iexact": rule.process_id,
                    "step_seq__iexact": rule.step_seq,
                    "is_active": True,
                }
                matches = model.objects.filter(**lookup).order_by("pk")
                if matches.count() > 1:
                    raise CommandError(f"활성 중복 line name rule이 있습니다: key={rule.key}")

                instance = matches.first()
                if instance is None:
                    model.objects.create(
                        rule_type=rule.rule_type,
                        line_id=rule.line_id,
                        process_id=rule.process_id,
                        step_seq=rule.step_seq,
                        line_name=rule.line_name,
                        priority=rule.priority,
                        is_active=True,
                    )
                    created_count += 1
                    continue

                if instance.line_name == rule.line_name and instance.priority == rule.priority:
                    unchanged_count += 1
                    continue
                instance.line_name = rule.line_name
                instance.priority = rule.priority
                instance.save()
                updated_count += 1

        # 같은 프로세스에서 후속 조회할 때 즉시 새 규칙을 사용하도록 snapshot을 비웁니다.
        from api.l3_spider.services import line_name_rules

        line_name_rules.clear_cache()

        mode = "replace" if options["replace"] else "upsert"
        self.stdout.write(
            self.style.SUCCESS(
                f"적재 완료: mode={mode}, path={path}, created={created_count}, "
                f"updated={updated_count}, unchanged={unchanged_count}, "
                f"duplicates={parsed.duplicate_count}"
            )
        )
