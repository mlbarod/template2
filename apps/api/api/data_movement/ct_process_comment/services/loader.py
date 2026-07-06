"""ct_process_comment 파일 적재 서비스입니다."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.db import connection, transaction
from django.utils import timezone

from api.data_movement.common.services.file_loader import (
    ClaimedDataFile,
    claim_incoming_file,
    delete_claimed_file,
    list_incoming_files,
)
from api.data_movement.common.services.streaming_csv import write_selected_deflate_csv
from api.data_movement.ct_process_comment.models import CtProcessCommentLoadJob
from api.data_movement.ct_process_comment.services import spec


@dataclass(frozen=True)
class SourceFileInfo:
    """파일명에서 추출한 적재 정보입니다."""

    file_timestamp: str


@dataclass(frozen=True)
class LoadFileOutcome:
    """단일 파일 처리 결과입니다."""

    file_name: str
    status: str
    row_count: int
    error_message: str | None = None


@dataclass(frozen=True)
class LoadRunSummary:
    """ct_process_comment 적재 실행 요약입니다."""

    outcomes: list[LoadFileOutcome]

    @property
    def processed_count(self) -> int:
        """처리한 파일 수를 반환합니다."""

        return len(self.outcomes)

    @property
    def success_count(self) -> int:
        """성공한 파일 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == CtProcessCommentLoadJob.Status.SUCCESS)

    @property
    def failure_count(self) -> int:
        """실패한 파일 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == CtProcessCommentLoadJob.Status.FAILED)


def parse_source_file_name(*, file_name: str) -> SourceFileInfo:
    """파일명에서 파일 timestamp를 추출합니다."""

    match = re.match(spec.SOURCE_FILE_PATTERN, file_name, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"지원하지 않는 파일명입니다: {file_name}")
    return SourceFileInfo(file_timestamp=match.group("file_timestamp"))


def _finish_job(
    *,
    job: CtProcessCommentLoadJob,
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


def _create_job(*, file_name: str, file_path: Path, source_info: SourceFileInfo | None) -> CtProcessCommentLoadJob:
    """파일 기준으로 적재 이력 row를 생성합니다."""

    return CtProcessCommentLoadJob.objects.create(
        file_name=file_name,
        file_path=str(file_path),
        file_timestamp=source_info.file_timestamp if source_info else None,
        status=CtProcessCommentLoadJob.Status.RUNNING,
        started_at=timezone.now(),
    )


def _quote_identifier(identifier: str) -> str:
    """SQL identifier를 quote 처리합니다."""

    return connection.ops.quote_name(identifier)


def _copy_selected_file_to_temp(*, cursor, selected_csv_path: Path) -> None:
    """선택 컬럼 CSV 파일을 temp table로 COPY 합니다."""

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


def _upsert_rows(*, selected_csv_path: Path) -> None:
    """workorder 기준 필터 후 ct_process_comment를 incremental upsert합니다."""

    quoted_table = _quote_identifier(spec.TABLE_NAME)
    quoted_temp = _quote_identifier(spec.TEMP_TABLE_NAME)
    quoted_workorder_table = _quote_identifier(spec.WORKORDER_TABLE_NAME)
    quoted_update_flag = _quote_identifier(spec.UPDATE_FLAG_COLUMN)
    quoted_llm_summary = _quote_identifier(spec.LLM_SUMMARY_COLUMN)
    quoted_llm_core_summary = _quote_identifier(spec.LLM_CORE_SUMMARY_COLUMN)
    temp_columns_sql = ", ".join(f"{_quote_identifier(column)} text" for column in spec.DB_COLUMNS)
    change_check_columns = [column for column in spec.DB_COLUMNS if column != spec.UPSERT_KEY]
    target_change_values = ", ".join(f"target.{_quote_identifier(column)}" for column in change_check_columns)
    excluded_change_values = ", ".join(f"EXCLUDED.{_quote_identifier(column)}" for column in change_check_columns)

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
                WITH normalized_source AS (
                    SELECT
                        NULLIF(src.workorder_id, '') AS workorder_id,
                        NULLIF(src.line_id, '') AS line_id,
                        NULLIF(src.process_id, '') AS process_id,
                        NULLIF(src.process_seq, '')::double precision AS process_seq,
                        NULLIF(src.comment_seq, '') AS comment_seq,
                        NULLIF(src.eqp_id, '') AS eqp_id,
                        NULLIF(src.freeze_yn, '') AS freeze_yn,
                        NULLIF(src.contents, '') AS contents,
                        NULLIF(src.contents_text, '') AS contents_text,
                        NULLIF(src.create_date, '')::timestamp AS create_date,
                        NULLIF(src.create_user, '') AS create_user,
                        NULLIF(src.update_date, '')::timestamp AS update_date,
                        NULLIF(src.update_user, '') AS update_user,
                        NULLIF(src.use_yn, '') AS use_yn,
                        NULLIF(src.modify_user, '') AS modify_user,
                        NULLIF(src.modify_date, '')::timestamp AS modify_date,
                        NULLIF(src.pbu_part_key, '') AS pbu_part_key,
                        src.ctid AS source_ctid
                    FROM {quoted_temp} src
                    WHERE NULLIF(src.workorder_id, '') IS NOT NULL
                      AND EXISTS (
                          SELECT 1
                          FROM {quoted_workorder_table} workorder
                          WHERE workorder.workorder_id = src.workorder_id
                      )
                ),
                latest_source AS (
                    SELECT DISTINCT ON (workorder_id)
                        workorder_id,
                        line_id,
                        process_id,
                        process_seq,
                        comment_seq,
                        eqp_id,
                        freeze_yn,
                        contents,
                        contents_text,
                        create_date,
                        create_user,
                        update_date,
                        update_user,
                        use_yn,
                        modify_user,
                        modify_date,
                        pbu_part_key
                    FROM normalized_source
                    ORDER BY
                        workorder_id,
                        update_date DESC NULLS LAST,
                        modify_date DESC NULLS LAST,
                        create_date DESC NULLS LAST,
                        source_ctid DESC
                )
                INSERT INTO {quoted_table} AS target
                    (
                        workorder_id,
                        line_id,
                        process_id,
                        process_seq,
                        comment_seq,
                        eqp_id,
                        freeze_yn,
                        contents,
                        contents_text,
                        create_date,
                        create_user,
                        update_date,
                        update_user,
                        use_yn,
                        modify_user,
                        modify_date,
                        pbu_part_key,
                        {quoted_update_flag}
                    )
                SELECT
                    workorder_id,
                    line_id,
                    process_id,
                    process_seq,
                    comment_seq,
                    eqp_id,
                    freeze_yn,
                    contents,
                    contents_text,
                    create_date,
                    create_user,
                    update_date,
                    update_user,
                    use_yn,
                    modify_user,
                    modify_date,
                    pbu_part_key,
                    'Y'
                FROM latest_source
                ON CONFLICT (workorder_id)
                DO UPDATE SET
                    line_id = EXCLUDED.line_id,
                    process_id = EXCLUDED.process_id,
                    process_seq = EXCLUDED.process_seq,
                    comment_seq = EXCLUDED.comment_seq,
                    eqp_id = EXCLUDED.eqp_id,
                    freeze_yn = EXCLUDED.freeze_yn,
                    contents = EXCLUDED.contents,
                    contents_text = EXCLUDED.contents_text,
                    create_date = EXCLUDED.create_date,
                    create_user = EXCLUDED.create_user,
                    update_date = EXCLUDED.update_date,
                    update_user = EXCLUDED.update_user,
                    use_yn = EXCLUDED.use_yn,
                    modify_user = EXCLUDED.modify_user,
                    modify_date = EXCLUDED.modify_date,
                    pbu_part_key = EXCLUDED.pbu_part_key,
                    {quoted_update_flag} = 'Y',
                    {quoted_llm_summary} = CASE
                        WHEN target.contents_text IS DISTINCT FROM EXCLUDED.contents_text THEN NULL
                        ELSE target.{quoted_llm_summary}
                    END,
                    {quoted_llm_core_summary} = CASE
                        WHEN target.contents_text IS DISTINCT FROM EXCLUDED.contents_text THEN NULL
                        ELSE target.{quoted_llm_core_summary}
                    END,
                    updated_at = NOW()
                WHERE ({target_change_values}) IS DISTINCT FROM ({excluded_change_values})
                """
            )
            cursor.execute(
                f"""
                DELETE FROM {quoted_table} comment
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM {quoted_workorder_table} workorder
                    WHERE workorder.workorder_id = comment.workorder_id
                )
                """
            )


def _write_selected_csv(*, source_path: Path, output_dir: Path) -> tuple[Path, int]:
    """원본 deflate CSV에서 저장 대상 컬럼만 추출한 임시 CSV를 생성합니다."""

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".selected.csv",
        dir=output_dir,
        delete=False,
    ) as handle:
        selected_path = Path(handle.name)

    try:
        row_count = write_selected_deflate_csv(
            source_path=source_path,
            output_path=selected_path,
            file_columns=spec.FILE_COLUMNS,
            db_columns=spec.DB_COLUMNS,
            excluded_row_filters=spec.EXCLUDED_ROW_FILTERS,
            prefix_row_filters=spec.PREFIX_ROW_FILTERS,
            separator=spec.FILE_SEPARATOR,
        )
    except Exception:
        selected_path.unlink(missing_ok=True)
        raise

    return selected_path, row_count


def _load_claimed_file(*, claimed_file: ClaimedDataFile) -> LoadFileOutcome:
    """processing으로 선점한 comment 파일을 incremental 반영합니다."""

    source_info: SourceFileInfo | None = None
    job: CtProcessCommentLoadJob | None = None
    selected_path: Path | None = None

    try:
        source_info = parse_source_file_name(file_name=claimed_file.original_name)
        job = _create_job(
            file_name=claimed_file.original_name,
            file_path=claimed_file.original_path,
            source_info=source_info,
        )
        selected_path, row_count = _write_selected_csv(
            source_path=claimed_file.working_path,
            output_dir=claimed_file.working_path.parent,
        )
        if row_count == 0:
            raise ValueError(f"empty dataframe: {claimed_file.original_path}")

        _upsert_rows(selected_csv_path=selected_path)

        _finish_job(job=job, status=CtProcessCommentLoadJob.Status.SUCCESS, row_count=row_count)
        return LoadFileOutcome(
            file_name=claimed_file.original_name,
            status=CtProcessCommentLoadJob.Status.SUCCESS,
            row_count=row_count,
        )
    except Exception as exc:
        error_message = str(exc)
        if job is None:
            job = _create_job(
                file_name=claimed_file.original_name,
                file_path=claimed_file.original_path,
                source_info=source_info,
            )
        _finish_job(
            job=job,
            status=CtProcessCommentLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
        return LoadFileOutcome(
            file_name=claimed_file.original_name,
            status=CtProcessCommentLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
    finally:
        if selected_path is not None:
            selected_path.unlink(missing_ok=True)
        delete_claimed_file(claimed_file=claimed_file)


def _dry_run_one_file(*, file_path: Path) -> LoadFileOutcome:
    """파일 이동 없이 단일 comment 파일을 파싱 검증합니다."""

    source_info: SourceFileInfo | None = None
    selected_path: Path | None = None
    job: CtProcessCommentLoadJob | None = None

    try:
        source_info = parse_source_file_name(file_name=file_path.name)
        job = _create_job(file_name=file_path.name, file_path=file_path, source_info=source_info)
        with tempfile.TemporaryDirectory() as temp_dir:
            selected_path, row_count = _write_selected_csv(source_path=file_path, output_dir=Path(temp_dir))
            if row_count == 0:
                raise ValueError(f"empty dataframe: {file_path}")
        _finish_job(job=job, status=CtProcessCommentLoadJob.Status.DRY_RUN, row_count=row_count)
        return LoadFileOutcome(
            file_name=file_path.name,
            status=CtProcessCommentLoadJob.Status.DRY_RUN,
            row_count=row_count,
        )
    except Exception as exc:
        error_message = str(exc)
        if job is None:
            job = _create_job(file_name=file_path.name, file_path=file_path, source_info=source_info)
        _finish_job(
            job=job,
            status=CtProcessCommentLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
        return LoadFileOutcome(
            file_name=file_path.name,
            status=CtProcessCommentLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
    finally:
        if selected_path is not None:
            selected_path.unlink(missing_ok=True)


def load_ct_process_comment_files(
    *,
    data_dir: Path | str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> LoadRunSummary:
    """ct_process_comment deflate CSV 파일들을 순차 적재합니다."""

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
