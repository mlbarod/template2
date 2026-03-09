# =============================================================================
# 모듈: Drone 모듈 통합 검증용 더미 데이터 적재 커맨드
# 주요 기능: 매핑/채널/룰/조기알림/SOP 샘플 데이터를 결정적으로 업서트
# 불변 조건: prefix 기반으로 데이터 범위를 분리해 운영 데이터와 충돌을 줄입니다.
# =============================================================================

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.account import services as account_services
from api.drone.models import (
    DroneEarlyInform,
    DroneSOP,
    DroneSopNeedToSendRule,
    DroneSopUserSdwtChannel,
    DroneSopUserSdwtProdMap,
    build_sop_key,
)


def _normalize_prefix(raw: Any) -> str:
    """더미 데이터 prefix 입력을 정규화합니다."""

    return str(raw or "").strip().upper()


def _ensure_dev_seed_allowed() -> None:
    """docker-compose.dev 환경에서만 실행되도록 가드합니다."""

    environment = (os.getenv("ENVIRONMENT") or "").strip().lower()
    seed_allowed = (os.getenv("DRONE_SEED_ALLOWED") or "").strip().lower()
    if environment != "development" or seed_allowed not in {"1", "true", "yes"}:
        raise CommandError(
            "이 커맨드는 docker-compose.dev.yml 환경에서만 실행할 수 있습니다. "
            "ENVIRONMENT=development 및 DRONE_SEED_ALLOWED=1 설정을 확인하세요."
        )


def _purge_seeded_rows(*, prefix: str) -> dict[str, int]:
    """prefix 기준 더미 데이터만 선택적으로 삭제합니다."""

    deleted_sop, _ = DroneSOP.objects.filter(line_id__startswith=f"{prefix}-").delete()
    deleted_early, _ = DroneEarlyInform.objects.filter(line_id__startswith=f"{prefix}-").delete()
    deleted_channels, _ = DroneSopUserSdwtChannel.objects.filter(
        target_user_sdwt_prod__startswith=f"{prefix}_"
    ).delete()
    deleted_rules, _ = DroneSopNeedToSendRule.objects.filter(
        target_user_sdwt_prod__startswith=f"{prefix}_"
    ).delete()
    deleted_maps, _ = DroneSopUserSdwtProdMap.objects.filter(
        target_user_sdwt_prod__startswith=f"{prefix}_"
    ).delete()
    return {
        "drone_sop": int(deleted_sop),
        "early_inform": int(deleted_early),
        "channel": int(deleted_channels),
        "rule": int(deleted_rules),
        "map": int(deleted_maps),
    }


def _seed_affiliations(*, prefix: str, targets: list[str]) -> int:
    """target/user 소속 옵션을 생성해 대시보드 유효성 검증을 통과시킵니다."""

    rows = [
        ("DUMMY", f"{prefix}-L1", targets[0]),
        ("DUMMY", f"{prefix}-L2", targets[1]),
        ("DUMMY", f"{prefix}-L3", targets[2]),
        ("DUMMY", f"{prefix}-L4", targets[3]),
        ("DUMMY", f"{prefix}-L1", "USR-A"),
        ("DUMMY", f"{prefix}-L2", "USR-B"),
        ("DUMMY", f"{prefix}-L3", "USR-C"),
        ("DUMMY", f"{prefix}-L4", "USR-D"),
    ]
    for department, line, user_sdwt_prod in rows:
        account_services.ensure_affiliation_option(
            department=department,
            line=line,
            user_sdwt_prod=user_sdwt_prod,
        )
    return len(rows)


def _seed_maps(*, prefix: str, targets: list[str]) -> dict[str, int]:
    """sdwt/user -> target 매핑 샘플을 업서트합니다."""

    specs = [
        {"sdwt_prod": "SDWT-A", "user_sdwt_prod": "USR-A", "target_user_sdwt_prod": targets[0], "is_active": True},
        {"sdwt_prod": "SDWT-B", "user_sdwt_prod": None, "target_user_sdwt_prod": targets[1], "is_active": True},
        {"sdwt_prod": None, "user_sdwt_prod": "USR-C", "target_user_sdwt_prod": targets[2], "is_active": True},
        {
            "sdwt_prod": "SDWT-I",
            "user_sdwt_prod": "USR-I",
            "target_user_sdwt_prod": f"{prefix}_INACTIVE_MAP",
            "is_active": False,
        },
    ]
    created = 0
    updated = 0
    for spec in specs:
        _, was_created = DroneSopUserSdwtProdMap.objects.update_or_create(
            sdwt_prod=spec["sdwt_prod"],
            user_sdwt_prod=spec["user_sdwt_prod"],
            defaults={
                "target_user_sdwt_prod": spec["target_user_sdwt_prod"],
                "is_active": spec["is_active"],
            },
        )
        created += int(was_created)
        updated += int(not was_created)
    return {"created": created, "updated": updated}


def _seed_channels(*, targets: list[str]) -> dict[str, int]:
    """target 기준 채널 설정 샘플을 업서트합니다."""

    specs = [
        {
            "target_user_sdwt_prod": targets[0],
            "jira_key": "DRA",
            "chatroom_id": 100001,
            "jira_template_key": "common",
            "mail_template_key": "common",
            "messenger_template_key": "common",
            "jira_enabled": True,
            "messenger_enabled": True,
            "mail_enabled": True,
            "is_active": True,
        },
        {
            "target_user_sdwt_prod": targets[1],
            "jira_key": "DRB",
            "chatroom_id": 100002,
            "jira_template_key": "h1",
            "mail_template_key": "h1",
            "messenger_template_key": "h1",
            "jira_enabled": True,
            "messenger_enabled": False,
            "mail_enabled": True,
            "is_active": True,
        },
        {
            "target_user_sdwt_prod": targets[2],
            "jira_key": "DRC",
            "chatroom_id": 100003,
            "jira_template_key": "common",
            "mail_template_key": "common",
            "messenger_template_key": "common",
            "jira_enabled": True,
            "messenger_enabled": True,
            "mail_enabled": True,
            "is_active": False,
        },
        {
            "target_user_sdwt_prod": targets[3],
            "jira_key": "DRD",
            "chatroom_id": 100004,
            "jira_template_key": "h1",
            "mail_template_key": "h1",
            "messenger_template_key": "h1",
            "jira_enabled": True,
            "messenger_enabled": True,
            "mail_enabled": False,
            "is_active": True,
        },
    ]
    created = 0
    updated = 0
    for spec in specs:
        target = str(spec["target_user_sdwt_prod"])
        defaults = {key: value for key, value in spec.items() if key != "target_user_sdwt_prod"}
        _, was_created = DroneSopUserSdwtChannel.objects.update_or_create(
            target_user_sdwt_prod=target,
            defaults=defaults,
        )
        created += int(was_created)
        updated += int(not was_created)
    return {"created": created, "updated": updated}


def _seed_rules(*, targets: list[str]) -> dict[str, int]:
    """needtosend 룰 샘플을 업서트합니다."""

    specs = [
        {"target_user_sdwt_prod": targets[0], "comment_last_at": "$AOK", "ignore_sample_type": False, "is_active": True},
        {"target_user_sdwt_prod": targets[1], "comment_last_at": "$BOK", "ignore_sample_type": False, "is_active": True},
        {"target_user_sdwt_prod": targets[2], "comment_last_at": "$GOK", "ignore_sample_type": False, "is_active": False},
        {"target_user_sdwt_prod": targets[3], "comment_last_at": "$DOK", "ignore_sample_type": True, "is_active": True},
    ]
    created = 0
    updated = 0
    for spec in specs:
        target = str(spec["target_user_sdwt_prod"])
        defaults = {key: value for key, value in spec.items() if key != "target_user_sdwt_prod"}
        _, was_created = DroneSopNeedToSendRule.objects.update_or_create(
            target_user_sdwt_prod=target,
            defaults=defaults,
        )
        created += int(was_created)
        updated += int(not was_created)
    return {"created": created, "updated": updated}


def _seed_early_inform(*, prefix: str) -> dict[str, int]:
    """조기 알림 스텝 샘플을 업서트합니다."""

    specs = [
        {"line_id": f"{prefix}-L1", "main_step": "MS10", "custom_end_step": "ST003", "updated_by": "seed"},
        {"line_id": f"{prefix}-L2", "main_step": "MS20", "custom_end_step": "ST004", "updated_by": "seed"},
    ]
    created = 0
    updated = 0
    for spec in specs:
        _, was_created = DroneEarlyInform.objects.update_or_create(
            line_id=spec["line_id"],
            main_step=spec["main_step"],
            defaults={
                "custom_end_step": spec["custom_end_step"],
                "updated_by": spec["updated_by"],
            },
        )
        created += int(was_created)
        updated += int(not was_created)
    return {"created": created, "updated": updated}


def _seed_sop_rows(*, prefix: str, targets: list[str]) -> dict[str, int]:
    """다양한 전송 상태를 포함한 DroneSOP 샘플을 업서트합니다."""

    now = timezone.now()
    rows: list[dict[str, Any]] = [
        {
            "line_id": f"{prefix}-L1",
            "sdwt_prod": "SDWT-A",
            "sample_type": "NORMAL",
            "eqp_id": "EQP-A1",
            "chamber_ids": "1",
            "lot_id": "LOT-A-001",
            "main_step": "MS10",
            "status": "COMPLETE",
            "comment": "inspect@$AOK",
            "user_sdwt_prod": "USR-A",
            "target_user_sdwt_prod": targets[0],
            "needtosend": 1,
            "instant_inform": 0,
            "send_jira": 0,
            "send_messenger": 0,
            "send_mail": 0,
        },
        {
            "line_id": f"{prefix}-L1",
            "sdwt_prod": "SDWT-A",
            "sample_type": "NORMAL",
            "eqp_id": "EQP-A2",
            "chamber_ids": "1",
            "lot_id": "LOT-A-002",
            "main_step": "MS10",
            "status": "IN_PROGRESS",
            "comment": "manual-urgent",
            "user_sdwt_prod": "USR-A",
            "target_user_sdwt_prod": targets[0],
            "needtosend": 0,
            "instant_inform": 1,
            "send_jira": 0,
            "send_messenger": 0,
            "send_mail": 0,
        },
        {
            "line_id": f"{prefix}-L1",
            "sdwt_prod": "SDWT-A",
            "sample_type": "NORMAL",
            "eqp_id": "EQP-A3",
            "chamber_ids": "1",
            "lot_id": "LOT-A-003",
            "main_step": "MS10",
            "status": "COMPLETE",
            "comment": "blocked",
            "user_sdwt_prod": "USR-A",
            "target_user_sdwt_prod": targets[0],
            "needtosend": 0,
            "instant_inform": 0,
            "send_jira": 0,
            "send_messenger": 0,
            "send_mail": 0,
        },
        {
            "line_id": f"{prefix}-L1",
            "sdwt_prod": "SDWT-A",
            "sample_type": "NORMAL",
            "eqp_id": "EQP-A4",
            "chamber_ids": "1",
            "lot_id": "LOT-A-004",
            "main_step": "MS10",
            "status": "IN_PROGRESS",
            "comment": "waiting",
            "user_sdwt_prod": "USR-A",
            "target_user_sdwt_prod": targets[0],
            "needtosend": 1,
            "instant_inform": 0,
            "send_jira": 0,
            "send_messenger": 0,
            "send_mail": 0,
        },
        {
            "line_id": f"{prefix}-L1",
            "sdwt_prod": "SDWT-A",
            "sample_type": "NORMAL",
            "eqp_id": "EQP-A5",
            "chamber_ids": "1",
            "lot_id": "LOT-A-005",
            "main_step": "MS10",
            "status": "COMPLETE",
            "comment": "done@$AOK",
            "user_sdwt_prod": "USR-A",
            "target_user_sdwt_prod": targets[0],
            "needtosend": 1,
            "instant_inform": 0,
            "send_jira": 1,
            "send_messenger": 1,
            "send_mail": 1,
            "jira_key": "DRA-100",
            "inform_step": "ST010",
            "informed_at": now - timedelta(hours=2),
        },
        {
            "line_id": f"{prefix}-L1",
            "sdwt_prod": "SDWT-X",
            "sample_type": "NORMAL",
            "eqp_id": "EQP-A6",
            "chamber_ids": "1",
            "lot_id": "LOT-A-006",
            "main_step": "MS10",
            "status": "COMPLETE",
            "comment": "no-target",
            "user_sdwt_prod": "USR-NOMAP",
            "target_user_sdwt_prod": None,
            "needtosend": 1,
            "instant_inform": 0,
            "send_jira": 0,
            "send_messenger": 0,
            "send_mail": 0,
        },
        {
            "line_id": f"{prefix}-L2",
            "sdwt_prod": "SDWT-B",
            "sample_type": "NORMAL",
            "eqp_id": "EQP-B1",
            "chamber_ids": "2",
            "lot_id": "LOT-B-001",
            "main_step": "MS20",
            "status": "COMPLETE",
            "comment": "ok@$BOK",
            "user_sdwt_prod": "USR-B",
            "target_user_sdwt_prod": targets[1],
            "needtosend": 1,
            "instant_inform": 0,
            "send_jira": 0,
            "send_messenger": 0,
            "send_mail": 0,
        },
        {
            "line_id": f"{prefix}-L2",
            "sdwt_prod": "SDWT-B",
            "sample_type": "NORMAL",
            "eqp_id": "EQP-B2",
            "chamber_ids": "2",
            "lot_id": "LOT-B-002",
            "main_step": "MS20",
            "status": "COMPLETE",
            "comment": "retry-jira",
            "user_sdwt_prod": "USR-B",
            "target_user_sdwt_prod": targets[1],
            "needtosend": 1,
            "instant_inform": 0,
            "send_jira": -1,
            "jira_reason": "NO_PROJECT_KEY",
            "send_messenger": 0,
            "send_mail": 0,
        },
        {
            "line_id": f"{prefix}-L3",
            "sdwt_prod": "SDWT-C",
            "sample_type": "NORMAL",
            "eqp_id": "EQP-C1",
            "chamber_ids": "3",
            "lot_id": "LOT-C-001",
            "main_step": "MS30",
            "status": "COMPLETE",
            "comment": "inactive-rule@$GOK",
            "user_sdwt_prod": "USR-C",
            "target_user_sdwt_prod": targets[2],
            "needtosend": 0,
            "instant_inform": 0,
            "send_jira": 0,
            "send_messenger": 0,
            "send_mail": 0,
        },
        {
            "line_id": f"{prefix}-L4",
            "sdwt_prod": "SDWT-D",
            "sample_type": "ENGR_PRODUCTION",
            "eqp_id": "EQP-D1",
            "chamber_ids": "4",
            "lot_id": "LOT-D-001",
            "main_step": "MS40",
            "status": "COMPLETE",
            "comment": "ignore-sample@$DOK",
            "user_sdwt_prod": "USR-D",
            "target_user_sdwt_prod": targets[3],
            "needtosend": 1,
            "instant_inform": 0,
            "send_jira": 0,
            "send_messenger": -1,
            "messenger_reason": "CHATROOM_NOT_FOUND",
            "send_mail": 0,
        },
    ]

    created = 0
    updated = 0
    for row in rows:
        row_defaults = dict(row)
        row_defaults.setdefault("knox_id", "seed-user")
        row_defaults.setdefault("sample_group", "SEED")
        row_defaults.setdefault("proc_id", "PROC-1")
        row_defaults.setdefault("ppid", "PPID-1")
        row_defaults.setdefault("metro_current_step", "ST003")
        row_defaults.setdefault("metro_steps", "ST001,ST002,ST003")
        row_defaults.setdefault("metro_end_step", "ST010")
        sop_key = build_sop_key(
            line_id=row_defaults.get("line_id"),
            eqp_id=row_defaults.get("eqp_id"),
            chamber_ids=row_defaults.get("chamber_ids"),
            lot_id=row_defaults.get("lot_id"),
            main_step=row_defaults.get("main_step"),
        )
        row_defaults["sop_key"] = sop_key
        _, was_created = DroneSOP.objects.update_or_create(
            sop_key=sop_key,
            defaults=row_defaults,
        )
        created += int(was_created)
        updated += int(not was_created)
    return {"created": created, "updated": updated}


class Command(BaseCommand):
    """Drone 모듈 검증용 더미 데이터를 적재합니다."""

    help = "Seed deterministic dummy rows for drone module end-to-end verification."

    def add_arguments(self, parser) -> None:
        """커맨드 인자를 정의합니다."""

        parser.add_argument(
            "--prefix",
            type=str,
            default="DUMMY",
            help="더미 데이터 식별 prefix. 예: DUMMY",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="동일 prefix 더미 데이터를 먼저 삭제한 뒤 다시 적재합니다.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """더미 데이터를 업서트하고 요약 결과를 출력합니다."""

        _ensure_dev_seed_allowed()

        prefix = _normalize_prefix(options.get("prefix"))
        if not prefix:
            raise CommandError("--prefix must not be empty")

        targets = [
            f"{prefix}_ALPHA",
            f"{prefix}_BETA",
            f"{prefix}_GAMMA",
            f"{prefix}_DELTA",
        ]

        with transaction.atomic():
            if bool(options.get("reset")):
                deleted = _purge_seeded_rows(prefix=prefix)
                self.stdout.write(f"[drone-seed] deleted={deleted}")

            affiliation_count = _seed_affiliations(prefix=prefix, targets=targets)
            map_result = _seed_maps(prefix=prefix, targets=targets)
            channel_result = _seed_channels(targets=targets)
            rule_result = _seed_rules(targets=targets)
            early_result = _seed_early_inform(prefix=prefix)
            sop_result = _seed_sop_rows(prefix=prefix, targets=targets)

        self.stdout.write(
            self.style.SUCCESS(
                "[drone-seed] done "
                f"prefix={prefix} "
                f"affiliations={affiliation_count} "
                f"maps={map_result} "
                f"channels={channel_result} "
                f"rules={rule_result} "
                f"early_inform={early_result} "
                f"sop={sop_result}"
            )
        )
