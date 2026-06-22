"""mi_tip_update_hist 파일 적재 서비스입니다."""

from __future__ import annotations

import csv
import hashlib
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as datetime_timezone
from pathlib import Path
from typing import Sequence

from django.db import connection, transaction
from django.utils import timezone

from api.data_movement.common.services.file_loader import (
    ClaimedDataFile,
    claim_incoming_file,
    delete_claimed_file,
    list_incoming_files,
)
from api.data_movement.common.services.streaming_csv import iter_deflate_text_lines, parse_csv_datetime
from api.data_movement.mi_tip_update_hist.models import MiTipUpdateHistLoadJob
from api.data_movement.mi_tip_update_hist.services import spec


@dataclass(frozen=True)
class LoadFileOutcome:
    """단일 파일 처리 결과입니다."""

    file_name: str
    status: str
    row_count: int
    error_message: str | None = None


@dataclass(frozen=True)
class LoadRunSummary:
    """mi_tip_update_hist 적재 실행 요약입니다."""

    outcomes: list[LoadFileOutcome]

    @property
    def processed_count(self) -> int:
        """처리한 파일 수를 반환합니다."""

        return len(self.outcomes)

    @property
    def success_count(self) -> int:
        """성공한 파일 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == MiTipUpdateHistLoadJob.Status.SUCCESS)

    @property
    def failure_count(self) -> int:
        """실패한 파일 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == MiTipUpdateHistLoadJob.Status.FAILED)


def _finish_job(
    *,
    job: MiTipUpdateHistLoadJob,
    status: str,
    row_count: int,
    error_message: str | None = None,
) -> None:
    """적재 이력 row를 최종 상태로 갱신합니다."""

    job.status = status
    job.row_count = row_count
    job.error_message = error_message
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "row_count", "error_message", "finished_at"])


def _create_job(*, file_name: str, file_path: Path) -> MiTipUpdateHistLoadJob:
    """파일 기준으로 적재 이력 row를 생성합니다."""

    return MiTipUpdateHistLoadJob.objects.create(
        file_name=file_name,
        file_path=str(file_path),
        status=MiTipUpdateHistLoadJob.Status.RUNNING,
        started_at=timezone.now(),
    )


def _quote_identifier(identifier: str) -> str:
    """SQL identifier를 quote 처리합니다."""

    return connection.ops.quote_name(identifier)


def _retention_cutoff() -> datetime:
    """파일 필터와 DB purge에 함께 사용할 180일 cutoff를 반환합니다."""

    cutoff = timezone.now() - timedelta(days=spec.RETENTION_DAYS)
    if timezone.is_aware(cutoff):
        return cutoff.astimezone(datetime_timezone.utc).replace(tzinfo=None)
    return cutoff


def _build_eqp_cb(*, eqp_id: str, tip_chamber_id: str) -> str:
    """원천 EQP/chamber 값을 timeline 조회용 eqp_cb로 변환합니다."""

    chamber = tip_chamber_id.strip()
    if "-" in chamber or "MAIN" in chamber.upper():
        return eqp_id
    return f"{eqp_id}-{chamber}"


def _lookup_key(value: str) -> str:
    """조회용 정규화 키를 생성합니다."""

    return value.strip().upper()


def _nullable_source_value(value: str) -> str:
    """원천 CSV의 null 리터럴을 DB NULL로 적재할 빈 문자열로 정규화합니다."""

    normalized = value.strip()
    if normalized.casefold() == "null":
        return ""
    return normalized


def _map_event_type(*, tip_type: str, tip_chg_type: str, tip_level: str) -> str:
    """TIP 원천 타입 3종을 timeline event_type으로 매핑합니다."""

    raw_event_type = f"{tip_type}/{tip_chg_type}/{tip_level}"
    return spec.LEVEL_MAPPING.get(raw_event_type, "unknown")


def _build_tip_event_key(
    *,
    eqp_cb: str,
    gpm_update_date: str,
    event_type: str,
    process_id: str,
    step_seq: str,
    ppid: str,
    tip_comment: str,
) -> str:
    """원천 PK가 없는 TIP row의 upsert key를 안정적으로 생성합니다."""

    raw_key = "\x1f".join(
        [
            eqp_cb,
            gpm_update_date,
            event_type,
            process_id,
            step_seq,
            ppid,
            tip_comment,
        ]
    )
    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()


def _copy_selected_file_to_temp(*, cursor, selected_csv_path: Path) -> None:
    """선별 CSV 파일을 temp table로 COPY 합니다."""

    quoted_temp = _quote_identifier(spec.TEMP_TABLE_NAME)
    quoted_columns = ", ".join(_quote_identifier(column) for column in spec.DB_COLUMNS)
    copy_sql = f"""
        COPY {quoted_temp} ({quoted_columns})
        FROM STDIN
        WITH (
            FORMAT CSV,
            NULL '',
            QUOTE '"',
            ESCAPE '"'
        )
    """
    copy_cursor = getattr(cursor, "cursor", cursor)
    if not hasattr(copy_cursor, "copy"):
        raise RuntimeError("psycopg3 COPY API를 사용할 수 없습니다.")

    with copy_cursor.copy(copy_sql) as copy:
        with selected_csv_path.open("r", encoding="utf-8") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                copy.write(chunk)


def _write_selected_csv(*, source_path: Path, output_dir: Path, cutoff: datetime) -> tuple[Path, int]:
    """원본 deflate CSV에서 저장 대상 row와 파생 컬럼을 추출한 임시 CSV를 생성합니다."""

    source_indexes = {column: index for index, column in enumerate(spec.FILE_COLUMNS)}
    required_width = len(spec.FILE_COLUMNS)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".selected.csv",
        dir=output_dir,
        delete=False,
        newline="",
    ) as handle:
        selected_path = Path(handle.name)
        writer = csv.writer(handle)
        row_count = 0

        reader = csv.reader(iter_deflate_text_lines(file_path=source_path), delimiter=spec.FILE_SEPARATOR)
        for row_index, row in enumerate(reader, start=1):
            if not row or all(not value.strip() for value in row):
                continue
            if len(row) < required_width:
                raise ValueError(f"CSV row {row_index} 컬럼 수가 부족합니다: {len(row)}")

            eqp_id = row[source_indexes["eqp_id"]].strip()
            if not eqp_id.lower().startswith("e"):
                continue

            gpm_update_date_raw = row[source_indexes["gpm_update_date"]].strip()
            gpm_update_date = parse_csv_datetime(gpm_update_date_raw)
            if gpm_update_date is None or gpm_update_date < cutoff:
                continue

            tip_type = row[source_indexes["tip_type"]].strip()
            tip_chg_type = row[source_indexes["tip_chg_type"]].strip()
            tip_level = row[source_indexes["tip_level"]].strip()
            event_type = _map_event_type(
                tip_type=tip_type,
                tip_chg_type=tip_chg_type,
                tip_level=tip_level,
            )
            step_seq = _nullable_source_value(row[source_indexes["step_seq"]])
            process_id = _nullable_source_value(row[source_indexes["process_id"]])
            ppid = _nullable_source_value(row[source_indexes["ppid"]])
            tip_comment = _nullable_source_value(row[source_indexes["tip_comment"]])
            eqp_cb = _build_eqp_cb(
                eqp_id=eqp_id,
                tip_chamber_id=row[source_indexes["tip_chamber_id"]].strip(),
            )
            tip_event_key = _build_tip_event_key(
                eqp_cb=eqp_cb,
                gpm_update_date=gpm_update_date_raw,
                event_type=event_type,
                process_id=process_id,
                step_seq=step_seq,
                ppid=ppid,
                tip_comment=tip_comment,
            )

            selected_values = [
                tip_event_key,
                _nullable_source_value(row[source_indexes["line_id"]]),
                eqp_cb,
                _lookup_key(eqp_cb),
                step_seq,
                process_id,
                ppid,
                _nullable_source_value(row[source_indexes["reticle_id"]]),
                _nullable_source_value(row[source_indexes["product_id"]]),
                _nullable_source_value(row[source_indexes["sum_time"]]),
                _nullable_source_value(row[source_indexes["rule_pkg_update_date"]]),
                gpm_update_date_raw,
                _nullable_source_value(row[source_indexes["register_name"]]),
                event_type,
                tip_type,
                tip_chg_type,
                tip_level,
                tip_comment,
                _nullable_source_value(row[source_indexes["tkin_restrc_lot_count"]]),
                _nullable_source_value(row[source_indexes["cur_tkin_lot_count"]]),
                _nullable_source_value(row[source_indexes["term_intlk_occur_time"]]),
                _nullable_source_value(row[source_indexes["last_update_date"]]),
            ]
            writer.writerow(selected_values)
            row_count += 1

    return selected_path, row_count


def _upsert_rows(*, selected_csv_path: Path, cutoff: datetime) -> None:
    """tip_event_key 기준으로 TIP 이력을 upsert하고 retention을 정리합니다."""

    quoted_table = _quote_identifier(spec.TABLE_NAME)
    quoted_temp = _quote_identifier(spec.TEMP_TABLE_NAME)
    temp_columns_sql = ", ".join(f"{_quote_identifier(column)} text" for column in spec.DB_COLUMNS)
    change_columns: Sequence[str] = [column for column in spec.DB_COLUMNS if column != spec.UPSERT_KEY]
    update_assignments = ",\n".join(
        f"{_quote_identifier(column)} = EXCLUDED.{_quote_identifier(column)}"
        for column in change_columns
    )
    target_change_values = ", ".join(f"target.{_quote_identifier(column)}" for column in change_columns)
    excluded_change_values = ", ".join(f"EXCLUDED.{_quote_identifier(column)}" for column in change_columns)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {quoted_temp}")
            cursor.execute(
                f"""
                CREATE TEMP TABLE {quoted_temp}
                ({temp_columns_sql})
                ON COMMIT DROP
                """
            )
            _copy_selected_file_to_temp(cursor=cursor, selected_csv_path=selected_csv_path)
            cursor.execute(
                f"""
                INSERT INTO {quoted_table} AS target
                    (
                        tip_event_key,
                        line_id,
                        eqp_cb,
                        eqp_cb_lookup,
                        step_seq,
                        process_id,
                        ppid,
                        reticle_id,
                        product_id,
                        sum_time,
                        rule_pkg_update_date,
                        gpm_update_date,
                        register_name,
                        event_type,
                        tip_type,
                        tip_chg_type,
                        tip_level,
                        tip_comment,
                        tkin_restrc_lot_count,
                        cur_tkin_lot_count,
                        term_intlk_occur_time,
                        last_update_date
                    )
                SELECT DISTINCT ON (NULLIF(src.tip_event_key, ''))
                    NULLIF(src.tip_event_key, ''),
                    NULLIF(src.line_id, ''),
                    NULLIF(src.eqp_cb, ''),
                    NULLIF(src.eqp_cb_lookup, ''),
                    NULLIF(src.step_seq, ''),
                    NULLIF(src.process_id, ''),
                    NULLIF(src.ppid, ''),
                    NULLIF(src.reticle_id, ''),
                    NULLIF(src.product_id, ''),
                    NULLIF(src.sum_time, ''),
                    NULLIF(src.rule_pkg_update_date, '')::timestamp,
                    NULLIF(src.gpm_update_date, '')::timestamp,
                    NULLIF(src.register_name, ''),
                    NULLIF(src.event_type, ''),
                    NULLIF(src.tip_type, ''),
                    NULLIF(src.tip_chg_type, ''),
                    NULLIF(src.tip_level, ''),
                    NULLIF(src.tip_comment, ''),
                    NULLIF(src.tkin_restrc_lot_count, '')::numeric,
                    NULLIF(src.cur_tkin_lot_count, '')::numeric,
                    NULLIF(src.term_intlk_occur_time, ''),
                    NULLIF(src.last_update_date, '')::timestamp
                FROM {quoted_temp} src
                WHERE NULLIF(src.tip_event_key, '') IS NOT NULL
                  AND NULLIF(src.eqp_cb, '') IS NOT NULL
                  AND NULLIF(src.gpm_update_date, '') IS NOT NULL
                ORDER BY
                    NULLIF(src.tip_event_key, ''),
                    NULLIF(src.last_update_date, '')::timestamp DESC NULLS LAST,
                    NULLIF(src.gpm_update_date, '')::timestamp DESC
                ON CONFLICT (tip_event_key)
                DO UPDATE SET
                    {update_assignments},
                    updated_at = NOW()
                WHERE ({target_change_values}) IS DISTINCT FROM ({excluded_change_values})
                """
            )
            cursor.execute(
                f"""
                DELETE FROM {quoted_table}
                WHERE gpm_update_date < %s
                """,
                [cutoff],
            )


def _load_claimed_file(*, claimed_file: ClaimedDataFile) -> LoadFileOutcome:
    """processing으로 선점한 mi_tip_update_hist 파일을 incremental 반영합니다."""

    selected_path: Path | None = None
    job = _create_job(file_name=claimed_file.original_name, file_path=claimed_file.original_path)

    try:
        cutoff = _retention_cutoff()
        selected_path, row_count = _write_selected_csv(
            source_path=claimed_file.working_path,
            output_dir=claimed_file.working_path.parent,
            cutoff=cutoff,
        )
        if row_count == 0:
            raise ValueError(f"empty dataframe: {claimed_file.original_path}")

        _upsert_rows(selected_csv_path=selected_path, cutoff=cutoff)
        _finish_job(job=job, status=MiTipUpdateHistLoadJob.Status.SUCCESS, row_count=row_count)
        return LoadFileOutcome(
            file_name=claimed_file.original_name,
            status=MiTipUpdateHistLoadJob.Status.SUCCESS,
            row_count=row_count,
        )
    except Exception as exc:
        error_message = str(exc)
        _finish_job(
            job=job,
            status=MiTipUpdateHistLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
        return LoadFileOutcome(
            file_name=claimed_file.original_name,
            status=MiTipUpdateHistLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
    finally:
        if selected_path is not None:
            selected_path.unlink(missing_ok=True)
        delete_claimed_file(claimed_file=claimed_file)


def _dry_run_one_file(*, file_path: Path) -> LoadFileOutcome:
    """파일 이동 없이 단일 mi_tip_update_hist 파일을 파싱 검증합니다."""

    selected_path: Path | None = None
    job = _create_job(file_name=file_path.name, file_path=file_path)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            selected_path, row_count = _write_selected_csv(
                source_path=file_path,
                output_dir=Path(temp_dir),
                cutoff=_retention_cutoff(),
            )
            if row_count == 0:
                raise ValueError(f"empty dataframe: {file_path}")
        _finish_job(job=job, status=MiTipUpdateHistLoadJob.Status.DRY_RUN, row_count=row_count)
        return LoadFileOutcome(
            file_name=file_path.name,
            status=MiTipUpdateHistLoadJob.Status.DRY_RUN,
            row_count=row_count,
        )
    except Exception as exc:
        error_message = str(exc)
        _finish_job(
            job=job,
            status=MiTipUpdateHistLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
        return LoadFileOutcome(
            file_name=file_path.name,
            status=MiTipUpdateHistLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
    finally:
        if selected_path is not None:
            selected_path.unlink(missing_ok=True)


def load_mi_tip_update_hist_files(
    *,
    data_dir: Path | str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> LoadRunSummary:
    """mi_tip_update_hist deflate CSV 파일들을 순차 적재합니다."""

    resolved_table_dir = Path(data_dir) if data_dir is not None else spec.DEFAULT_TABLE_DIR
    files = list_incoming_files(table_dir=resolved_table_dir, pattern=spec.FILE_PATTERN, limit=limit)
    outcomes = []
    for file_path in files:
        if dry_run:
            outcomes.append(_dry_run_one_file(file_path=file_path))
            continue
        claimed_file = claim_incoming_file(file_path=file_path, table_dir=resolved_table_dir)
        outcomes.append(_load_claimed_file(claimed_file=claimed_file))
    return LoadRunSummary(outcomes=outcomes)
