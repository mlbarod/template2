from __future__ import annotations

from django.db import migrations, models


_CREATE_INDEX_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS public.l3_spider_daily_run_stats (
    date text NOT NULL,
    line_id text NOT NULL,
    process_id text NOT NULL,
    eds_step text NOT NULL,
    step_seq text NOT NULL,
    row_cnt int8 DEFAULT 0 NOT NULL,
    last_checked text NULL,
    CONSTRAINT daily_run_stats_pkey
        PRIMARY KEY (date, line_id, process_id, eds_step, step_seq)
);
CREATE INDEX IF NOT EXISTS idx_run_stats_date
    ON public.l3_spider_daily_run_stats USING btree (date);
CREATE INDEX IF NOT EXISTS idx_run_stats_date_line
    ON public.l3_spider_daily_run_stats USING btree (date, line_id);

CREATE TABLE IF NOT EXISTS public.l3_spider_file_index (
    filepath text NOT NULL,
    date text NOT NULL,
    line_id text NOT NULL,
    process_id text NOT NULL,
    eds_step text NOT NULL,
    step_seq text NOT NULL,
    ppid text NOT NULL,
    eqp_ids text NOT NULL,
    chamber_ids text NOT NULL,
    bin_names text NOT NULL,
    total_bin_cnt int4 NULL,
    row_cnt int8 NULL,
    has_high_risk int4 DEFAULT 0 NULL,
    high_risk_cnt int4 NULL,
    warning_cnt int4 NULL,
    normal_cnt int4 NULL,
    high_risk_eqcs text NULL,
    saved_at text NULL,
    CONSTRAINT file_index_pkey PRIMARY KEY (filepath)
);
CREATE INDEX IF NOT EXISTS idx_date_hr
    ON public.l3_spider_file_index USING btree (date, has_high_risk);
CREATE INDEX IF NOT EXISTS idx_date_line
    ON public.l3_spider_file_index USING btree (date, line_id);
CREATE INDEX IF NOT EXISTS idx_file_date_scope
    ON public.l3_spider_file_index USING btree (date, line_id, process_id, eds_step);

CREATE TABLE IF NOT EXISTS public.l3_spider_run_status (
    date text NOT NULL,
    status text NOT NULL,
    completed_at text NULL,
    failed_count int4 DEFAULT 0 NULL,
    CONSTRAINT run_status_pkey PRIMARY KEY (date)
);
"""

_DROP_INDEX_TABLES_SQL = """
DROP TABLE IF EXISTS public.l3_spider_run_status;
DROP TABLE IF EXISTS public.l3_spider_file_index;
DROP TABLE IF EXISTS public.l3_spider_daily_run_stats;
"""

_EXPECTED_COLUMNS = {
    "l3_spider_daily_run_stats": [
        ("date", "text", False, None),
        ("line_id", "text", False, None),
        ("process_id", "text", False, None),
        ("eds_step", "text", False, None),
        ("step_seq", "text", False, None),
        ("row_cnt", "bigint", False, "0"),
        ("last_checked", "text", True, None),
    ],
    "l3_spider_file_index": [
        ("filepath", "text", False, None),
        ("date", "text", False, None),
        ("line_id", "text", False, None),
        ("process_id", "text", False, None),
        ("eds_step", "text", False, None),
        ("step_seq", "text", False, None),
        ("ppid", "text", False, None),
        ("eqp_ids", "text", False, None),
        ("chamber_ids", "text", False, None),
        ("bin_names", "text", False, None),
        ("total_bin_cnt", "integer", True, None),
        ("row_cnt", "bigint", True, None),
        ("has_high_risk", "integer", True, "0"),
        ("high_risk_cnt", "integer", True, None),
        ("warning_cnt", "integer", True, None),
        ("normal_cnt", "integer", True, None),
        ("high_risk_eqcs", "text", True, None),
        ("saved_at", "text", True, None),
    ],
    "l3_spider_run_status": [
        ("date", "text", False, None),
        ("status", "text", False, None),
        ("completed_at", "text", True, None),
        ("failed_count", "integer", True, "0"),
    ],
}

_EXPECTED_CONSTRAINTS = {
    "l3_spider_daily_run_stats": {
        "daily_run_stats_pkey": ["date", "line_id", "process_id", "eds_step", "step_seq"],
        "idx_run_stats_date": ["date"],
        "idx_run_stats_date_line": ["date", "line_id"],
    },
    "l3_spider_file_index": {
        "file_index_pkey": ["filepath"],
        "idx_date_hr": ["date", "has_high_risk"],
        "idx_date_line": ["date", "line_id"],
        "idx_file_date_scope": ["date", "line_id", "process_id", "eds_step"],
    },
    "l3_spider_run_status": {
        "run_status_pkey": ["date"],
    },
}


def _normalize_default(value: str | None) -> str | None:
    """PostgreSQL이 기본값에 덧붙이는 숫자 타입 캐스트를 제거합니다."""

    if value is None:
        return None
    normalized = value.replace("::bigint", "").replace("::integer", "").strip()
    return normalized.strip("()")


def _validate_managed_table_schema(apps, schema_editor) -> None:
    """기존 또는 신규 테이블이 합의된 PostgreSQL DDL과 일치하는지 확인합니다."""

    # sqlmigrate는 SQL을 실행하지 않고 수집만 하므로 실제 적용 시에만 검증합니다.
    if schema_editor.collect_sql:
        return

    connection = schema_editor.connection
    with connection.cursor() as cursor:
        for table_name, expected_columns in _EXPECTED_COLUMNS.items():
            cursor.execute(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s "
                "ORDER BY ordinal_position",
                [table_name],
            )
            actual_columns = [
                (name, data_type, nullable == "YES", _normalize_default(default))
                for name, data_type, nullable, default in cursor.fetchall()
            ]
            if actual_columns != expected_columns:
                raise RuntimeError(
                    f"public.{table_name} 컬럼 계약이 다릅니다: "
                    f"expected={expected_columns}, actual={actual_columns}"
                )

            constraints = connection.introspection.get_constraints(cursor, table_name)
            for constraint_name, expected_fields in _EXPECTED_CONSTRAINTS[table_name].items():
                constraint = constraints.get(constraint_name)
                expected_primary_key = constraint_name.endswith("_pkey")
                valid_constraint = (
                    constraint is not None
                    and constraint["columns"] == expected_fields
                    and constraint["primary_key"] is expected_primary_key
                    and (expected_primary_key or constraint["index"])
                )
                if not valid_constraint:
                    raise RuntimeError(
                        f"public.{table_name} 제약/인덱스 계약이 다릅니다: "
                        f"{constraint_name} expected={expected_fields}, actual={constraint}"
                    )


class Migration(migrations.Migration):

    dependencies = [
        ("l3_spider", "0004_remove_mail_rule_date_from"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=_CREATE_INDEX_TABLES_SQL,
                    reverse_sql=_DROP_INDEX_TABLES_SQL,
                ),
                migrations.RunPython(
                    _validate_managed_table_schema,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name="L3SpiderRunStatus",
                    fields=[
                        ("date", models.TextField(primary_key=True, serialize=False)),
                        ("status", models.TextField()),
                        ("completed_at", models.TextField(blank=True, null=True)),
                        (
                            "failed_count",
                            models.IntegerField(
                                blank=True,
                                db_default=0,
                                default=0,
                                null=True,
                            ),
                        ),
                    ],
                    options={"db_table": "l3_spider_run_status"},
                ),
                migrations.CreateModel(
                    name="L3SpiderDailyRunStats",
                    fields=[
                        ("date", models.TextField()),
                        ("line_id", models.TextField()),
                        ("process_id", models.TextField()),
                        ("eds_step", models.TextField()),
                        ("step_seq", models.TextField()),
                        ("row_cnt", models.BigIntegerField(db_default=0, default=0)),
                        ("last_checked", models.TextField(blank=True, null=True)),
                        (
                            "pk",
                            models.CompositePrimaryKey(
                                "date",
                                "line_id",
                                "process_id",
                                "eds_step",
                                "step_seq",
                                blank=True,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "l3_spider_daily_run_stats",
                        "indexes": [
                            models.Index(fields=["date"], name="idx_run_stats_date"),
                            models.Index(
                                fields=["date", "line_id"],
                                name="idx_run_stats_date_line",
                            ),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name="L3SpiderFileIndex",
                    fields=[
                        ("filepath", models.TextField(primary_key=True, serialize=False)),
                        ("date", models.TextField()),
                        ("line_id", models.TextField()),
                        ("process_id", models.TextField()),
                        ("eds_step", models.TextField()),
                        ("step_seq", models.TextField()),
                        ("ppid", models.TextField()),
                        ("eqp_ids", models.TextField()),
                        ("chamber_ids", models.TextField()),
                        ("bin_names", models.TextField()),
                        ("total_bin_cnt", models.IntegerField(blank=True, null=True)),
                        ("row_cnt", models.BigIntegerField(blank=True, null=True)),
                        (
                            "has_high_risk",
                            models.IntegerField(
                                blank=True,
                                db_default=0,
                                default=0,
                                null=True,
                            ),
                        ),
                        ("high_risk_cnt", models.IntegerField(blank=True, null=True)),
                        ("warning_cnt", models.IntegerField(blank=True, null=True)),
                        ("normal_cnt", models.IntegerField(blank=True, null=True)),
                        ("high_risk_eqcs", models.TextField(blank=True, null=True)),
                        ("saved_at", models.TextField(blank=True, null=True)),
                    ],
                    options={
                        "db_table": "l3_spider_file_index",
                        "indexes": [
                            models.Index(
                                fields=["date", "has_high_risk"],
                                name="idx_date_hr",
                            ),
                            models.Index(
                                fields=["date", "line_id"],
                                name="idx_date_line",
                            ),
                            models.Index(
                                fields=["date", "line_id", "process_id", "eds_step"],
                                name="idx_file_date_scope",
                            ),
                        ],
                    },
                ),
            ],
        ),
    ]
