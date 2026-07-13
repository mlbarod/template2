#!/usr/bin/env python3
"""기존 평면형 env 파일을 새 카테고리 구조로 분류합니다.

주요 기능:
- 기존 env 파일은 수정하거나 삭제하지 않습니다.
- dry-run에서는 환경변수 값 없이 키와 대상 경로만 출력합니다.
- apply에서는 같은 서버의 출력 디렉터리에 새 env 파일을 생성합니다.
- 입력과 출력의 모든 ``KEY=VALUE`` 할당이 보존되는지 내부에서 검증합니다.

핵심 전제:
- source 디렉터리에는 변경 전 이름의 env 파일 11개가 있어야 합니다.
- ``api.common.env``에 새 키가 추가됐다면 이 스크립트의 카테고리 맵에도
  먼저 키를 등록해야 합니다. 알 수 없는 키는 임의 분류하지 않습니다.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ENV_ASSIGNMENT_PATTERN = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)$")


# =============================================================================
# API 공통 키 카테고리
# =============================================================================
API_CATEGORY_KEYS: dict[str, frozenset[str]] = {
    "api/core.env": frozenset(
        {
            "DJANGO_ALLOWED_HOSTS",
            "DATA_UPLOAD_MAX_MEMORY_SIZE",
            "DJANGO_TIME_ZONE",
            "DJANGO_SUPERUSER_SABUN",
            "DJANGO_SUPERUSER_USERNAME",
            "DJANGO_SUPERUSER_EMAIL",
            "DJANGO_SUPERUSER_PASSWORD",
            "USE_X_FORWARDED_HOST",
            "DJANGO_USE_PROXY_SSL_HEADER",
            "SECURE_REFERRER_POLICY",
            "PUBLIC_API_BASE_URL",
            "GUNICORN_WORKERS",
            "GUNICORN_THREADS",
            "AIRFLOW_TRIGGER_TOKEN",
        }
    ),
    "api/database.env": frozenset(
        {
            "DJANGO_DB_ENGINE",
            "DJANGO_DB_NAME",
            "DJANGO_DB_USER",
            "DJANGO_DB_PASSWORD",
            "DJANGO_DB_HOST",
            "DJANGO_DB_PORT",
            "DJANGO_DB_CONN_MAX_AGE",
        }
    ),
    "api/auth.env": frozenset(
        {
            "DJANGO_LOGIN_REDIRECT_URL",
            "DJANGO_LOGOUT_REDIRECT_URL",
            "OIDC_CLIENT_ID",
            "OIDC_ISSUER",
            "ADFS_AUTH_URL",
            "ADFS_LOGOUT_URL",
            "OIDC_REDIRECT_URI",
            "ADFS_CER_PATH",
            "ALLOWED_REDIRECT_HOSTS",
        }
    ),
    "api/data-files.env": frozenset(
        {
            "OBSERVER_QUERY_DAYS",
            "RACB_REPORT_BASE_URL",
            "L3_SPIDER_DATA_ROOT",
            "L3_SPIDER_MAX_CHART_POINTS_PER_PANEL",
            "L3_SPIDER_MAIL_SENDER",
            "L3_SPIDER_MAIL_TARGET_URL",
            "PM_COMPARISON_DATA_ROOT",
            "PM_COMPARISON_MAX_FILES",
            "PM_COMPARISON_MAX_META_DIRS",
            "EXTERNAL_APP_USAGE_API_URLS",
            "EXTERNAL_APP_USAGE_API_TIMEOUT_SECONDS",
            "DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS",
            "DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS",
            "DATA_MOVEMENT_M_TKIN_PREVENT_DIR",
            "DATA_MOVEMENT_CTTTM_WORKORDER_LIST_DIR",
            "DATA_MOVEMENT_CT_PROCESS_COMMENT_DIR",
            "DATA_MOVEMENT_MES_LINE_MAPPING_INFO_DIR",
            "DATA_MOVEMENT_EQP_STATUS_CHG_DIR",
            "DATA_MOVEMENT_MI_TIP_UPDATE_HIST_DIR",
            "DATA_MOVEMENT_RACB_LIST_DIR",
            "DATA_MOVEMENT_STATION_MASTER_DIR",
        }
    ),
    "api/assistant-rag.env": frozenset(
        {
            "ASSISTANT_DUMMY_MODE",
            "ASSISTANT_DUMMY_REPLY",
            "ASSISTANT_DUMMY_CONTEXTS",
            "ASSISTANT_DUMMY_DELAY_MS",
            "ASSISTANT_RAG_URL",
            "ASSISTANT_RAG_INSERT_URL",
            "ASSISTANT_RAG_DELETE_URL",
            "ASSISTANT_RAG_INDEX_INFO_URL",
            "ASSISTANT_RAG_INDEX_NAME",
            "RAG_INDEX_LIST",
            "RAG_INDEX_DEFAULT",
            "RAG_INDEX_EMAILS",
            "ASSISTANT_RAG_PERMISSION_GROUPS",
            "ASSISTANT_RAG_CHUNK_FACTOR",
            "ASSISTANT_RAG_HEADERS",
            "ASSISTANT_RAG_NUM_DOCS",
            "ASSISTANT_LLM_URL",
            "ASSISTANT_LLM_COMMON_HEADERS",
            "ASSISTANT_LLM_CREDENTIAL",
            "ASSISTANT_LLM_MODEL",
            "ASSISTANT_LLM_TEMPERATURE",
            "ASSISTANT_LLM_SYSTEM_MESSAGE",
            "ASSISTANT_REQUEST_TIMEOUT",
            "OPENWEBUI_URL",
            "OPENWEBUI_API_TOKEN",
            "OPENWEBUI_MODEL",
            "OPENWEBUI_COMMON_HEADERS",
            "OPENWEBUI_TIMEOUT_SECONDS",
            "OPENWEBUI_SUMMARY_BATCH_SIZE",
        }
    ),
    "api/emails.env": frozenset(
        {
            "EMAIL_POP3_HOST",
            "EMAIL_POP3_PORT",
            "EMAIL_POP3_USERNAME",
            "EMAIL_POP3_PASSWORD",
            "EMAIL_POP3_USE_SSL",
            "EMAIL_POP3_TIMEOUT",
            "EMAIL_EXCLUDED_SUBJECT_PREFIXES",
            "MAIL_API_URL",
            "MAIL_API_KEY",
            "MAIL_API_SYSTEM_ID",
            "MAIL_API_KNOX_ID",
        }
    ),
    "api/drone.env": frozenset(
        {
            "DRONE_SOP_POP3_HOST",
            "DRONE_SOP_POP3_PORT",
            "DRONE_SOP_POP3_USERNAME",
            "DRONE_SOP_POP3_PASSWORD",
            "DRONE_SOP_POP3_USE_SSL",
            "DRONE_SOP_POP3_TIMEOUT",
            "DRONE_SOP_POP3_SUBJECT",
            "DRONE_SOP_ENGR_FALLBACK_VALUES",
            "DRONE_SOP_USER_SDWT_OVERRIDE_MAP",
            "DRONE_SOP_DUMMY_MODE",
            "DRONE_SOP_DUMMY_MAIL_MESSAGES_URL",
            "DRONE_SOP_DEFECTMAP_URL",
            "DRONE_JIRA_BASE_URL",
            "DRONE_JIRA_TOKEN",
            "DRONE_JIRA_ISSUE_TYPE",
            "DRONE_JIRA_USE_BULK_API",
            "DRONE_JIRA_BULK_SIZE",
            "DRONE_JIRA_CONNECT_TIMEOUT",
            "DRONE_JIRA_READ_TIMEOUT",
            "DRONE_JIRA_USER",
            "DRONE_JIRA_VERFY_SSL",
            "DRONE_CTTTM_TABLE_NAME",
            "DRONE_CTTTM_BASE_URL",
            "DRONE_MESSENGER_TTL",
            "KNOX_MESSENGER_API_BASE_URL",
            "KNOX_MESSENGER_AUTHORIZATION",
            "KNOX_MESSENGER_SYSTEM_ID",
            "KNOX_MESSENGER_TIMEOUT_SECONDS",
            "DRONE_MAIL_SENDER",
        }
    ),
}


# API 공통 파일 외에는 파일 전체가 새 경로 하나로 이동합니다.
DIRECT_FILE_MAPPINGS: dict[str, str] = {
    "api.dev.env": "api/profiles/dev.env",
    "api.oidc.dev.env": "api/profiles/oidc.env",
    "api.prod.env": "api/profiles/prod.env",
    "web.common.env": "web/common.env",
    "web.dev.env": "web/profiles/dev.env",
    "web.oidc.dev.env": "web/profiles/oidc.env",
    "web.prod.env": "web/profiles/prod.env",
    "airflow.common.env": "infra/airflow.env",
    "minio.env": "infra/minio.env",
    "grafana.env": "infra/grafana.env",
}


OUTPUT_DESCRIPTIONS: dict[str, str] = {
    "api/core.env": "Django 핵심 런타임 설정",
    "api/database.env": "Django 데이터베이스 설정",
    "api/auth.env": "Django 인증/OIDC 설정",
    "api/data-files.env": "업무 데이터와 파일 경로 설정",
    "api/assistant-rag.env": "Assistant/RAG/LLM 설정",
    "api/emails.env": "Email 수집과 Mail API 설정",
    "api/drone.env": "Drone/Jira/Messenger 설정",
    "api/profiles/dev.env": "API dev 환경 override",
    "api/profiles/oidc.env": "API OIDC 환경 override",
    "api/profiles/prod.env": "API prod 환경 override",
    "web/common.env": "Web 공통 설정",
    "web/profiles/dev.env": "Web dev 환경 설정",
    "web/profiles/oidc.env": "Web OIDC 환경 설정",
    "web/profiles/prod.env": "Web prod 환경 설정",
    "infra/airflow.env": "Airflow 설정",
    "infra/minio.env": "MinIO 설정",
    "infra/grafana.env": "Grafana 설정",
}


class MigrationError(RuntimeError):
    """안전하게 마이그레이션을 계속할 수 없을 때 발생합니다."""


@dataclass(frozen=True)
class EnvEntry:
    """환경변수 한 줄과 출처 정보를 보존합니다."""

    key: str
    raw: str
    source_name: str
    line_number: int


def parse_env_file(path: Path) -> list[EnvEntry]:
    """env 파일에서 ``KEY=VALUE`` 할당만 읽고 중복 키를 검증합니다.

    입력값:
    - path: 읽을 기존 env 파일 경로

    반환값:
    - 원본 값을 그대로 가진 EnvEntry 목록

    오류 조건:
    - 같은 파일에 동일 키가 두 번 있으면 MigrationError를 발생시킵니다.
    """

    entries: list[EnvEntry] = []
    seen: dict[str, int] = {}

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = ENV_ASSIGNMENT_PATTERN.match(line)
        if match is None:
            continue

        key = match.group("key")
        if key in seen:
            raise MigrationError(
                f"중복 키가 있습니다: {path.name}:{seen[key]},{line_number} {key}"
            )
        seen[key] = line_number
        entries.append(
            EnvEntry(
                key=key,
                raw=line,
                source_name=path.name,
                line_number=line_number,
            )
        )

    return entries


def build_category_owner() -> dict[str, str]:
    """API 공통 키마다 유일한 대상 파일이 있는지 검증해 반환합니다."""

    owner: dict[str, str] = {}
    duplicate_keys: list[str] = []

    for relative_path, keys in API_CATEGORY_KEYS.items():
        for key in keys:
            if key in owner:
                duplicate_keys.append(key)
            owner[key] = relative_path

    if duplicate_keys:
        raise MigrationError(
            "스크립트 카테고리 맵에 중복 키가 있습니다: "
            + ", ".join(sorted(duplicate_keys))
        )
    return owner


def load_legacy_entries(source_dir: Path) -> dict[str, list[EnvEntry]]:
    """필수 기존 env 파일을 모두 읽습니다."""

    required_names = ["api.common.env", *DIRECT_FILE_MAPPINGS]
    missing = [name for name in required_names if not (source_dir / name).is_file()]
    if missing:
        raise MigrationError("기존 env 파일이 없습니다: " + ", ".join(sorted(missing)))

    return {name: parse_env_file(source_dir / name) for name in required_names}


def classify_entries(
    legacy_entries: dict[str, list[EnvEntry]],
) -> dict[str, list[EnvEntry]]:
    """기존 env 할당을 새 상대 경로별로 분류합니다."""

    outputs: dict[str, list[EnvEntry]] = {
        relative_path: [] for relative_path in OUTPUT_DESCRIPTIONS
    }
    owner = build_category_owner()
    unknown_keys: list[str] = []

    for entry in legacy_entries["api.common.env"]:
        relative_path = owner.get(entry.key)
        if relative_path is None:
            unknown_keys.append(entry.key)
            continue
        outputs[relative_path].append(entry)

    if unknown_keys:
        raise MigrationError(
            "분류 기준에 없는 api.common.env 키가 있습니다: "
            + ", ".join(sorted(unknown_keys))
        )

    for source_name, relative_path in DIRECT_FILE_MAPPINGS.items():
        outputs[relative_path].extend(legacy_entries[source_name])

    return outputs


def verify_assignment_preservation(
    legacy_entries: dict[str, list[EnvEntry]],
    outputs: dict[str, list[EnvEntry]],
) -> None:
    """입력과 출력의 전체 할당이 값까지 동일한지 확인합니다."""

    source_counter = Counter(
        entry.raw for entries in legacy_entries.values() for entry in entries
    )
    output_counter = Counter(entry.raw for entries in outputs.values() for entry in entries)

    if source_counter != output_counter:
        missing_keys = sorted(
            entry.key
            for entries in legacy_entries.values()
            for entry in entries
            if output_counter[entry.raw] < source_counter[entry.raw]
        )
        raise MigrationError(
            "출력에서 보존되지 않은 env 키가 있습니다: " + ", ".join(missing_keys)
        )


def render_output(relative_path: str, entries: Iterable[EnvEntry]) -> str:
    """값을 변경하지 않고 새 env 파일 내용을 만듭니다."""

    description = OUTPUT_DESCRIPTIONS[relative_path]
    lines = [
        f"# {description}",
        "# scripts/migrate_legacy_env.py가 기존 env에서 분류한 파일입니다.",
        "",
    ]
    lines.extend(entry.raw for entry in entries)
    return "\n".join(lines) + "\n"


def print_dry_run(outputs: dict[str, list[EnvEntry]]) -> None:
    """값을 노출하지 않고 키와 대상 파일만 출력합니다."""

    for relative_path in sorted(outputs):
        for entry in outputs[relative_path]:
            print(f"{entry.key} -> {relative_path}")

    total = sum(len(entries) for entries in outputs.values())
    print(f"dry-run 완료: {total}개 키, {len(outputs)}개 대상 파일")


def backup_existing_outputs(output_dir: Path, destination_paths: Iterable[Path]) -> Path | None:
    """덮어쓸 기존 출력 파일을 같은 서버의 백업 디렉터리에 보관합니다."""

    existing_paths = [path for path in destination_paths if path.exists()]
    if not existing_paths:
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_root = output_dir / ".legacy-env-migration-backup" / timestamp

    for path in existing_paths:
        relative_path = path.relative_to(output_dir)
        backup_path = backup_root / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)

    return backup_root


def atomic_write(path: Path, content: str) -> None:
    """같은 파일시스템의 임시 파일을 이용해 env 파일을 원자적으로 교체합니다."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as temporary_file:
        temporary_file.write(content)
        temporary_path = Path(temporary_file.name)

    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, path)


def apply_outputs(
    output_dir: Path,
    outputs: dict[str, list[EnvEntry]],
    *,
    force: bool,
) -> None:
    """분류 결과를 출력 디렉터리에 기록합니다."""

    destination_paths = [output_dir / relative_path for relative_path in outputs]
    existing_paths = [path for path in destination_paths if path.exists()]
    if existing_paths and not force:
        relative_names = [str(path.relative_to(output_dir)) for path in existing_paths]
        raise MigrationError(
            "대상 파일이 이미 있습니다. 확인 후 --force를 사용하세요: "
            + ", ".join(sorted(relative_names))
        )

    backup_root = backup_existing_outputs(output_dir, destination_paths) if force else None
    for relative_path, entries in outputs.items():
        atomic_write(output_dir / relative_path, render_output(relative_path, entries))

    if backup_root is not None:
        print(f"기존 출력 백업: {backup_root}")
    print(f"적용 완료: {sum(len(entries) for entries in outputs.values())}개 키")
    print(f"생성 파일: {len(outputs)}개")


def parse_args() -> argparse.Namespace:
    """명령행 인자를 파싱합니다."""

    parser = argparse.ArgumentParser(
        description="기존 env 파일을 서버 내부에서 새 카테고리 구조로 분류합니다."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("env"),
        help="변경 전 env 파일이 있는 디렉터리입니다. 기본값: env",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="새 구조를 생성할 디렉터리입니다. 기본값: source-dir과 동일",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제로 새 env 파일을 생성합니다. 생략하면 dry-run만 수행합니다.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="기존 대상 파일을 서버 내부에 백업한 후 덮어씁니다.",
    )
    return parser.parse_args()


def main() -> int:
    """입력 검증, 분류, 보존 검증 후 dry-run 또는 apply를 실행합니다."""

    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = (args.output_dir or args.source_dir).resolve()

    try:
        legacy_entries = load_legacy_entries(source_dir)
        outputs = classify_entries(legacy_entries)
        verify_assignment_preservation(legacy_entries, outputs)

        if args.apply:
            apply_outputs(output_dir, outputs, force=args.force)
        else:
            print_dry_run(outputs)
    except (MigrationError, OSError, UnicodeError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
