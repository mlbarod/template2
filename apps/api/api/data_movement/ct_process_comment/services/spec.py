"""ct_process_comment 파일 적재 spec입니다."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

TABLE_NAME = "ct_process_comment"
TEMP_TABLE_NAME = "tmp_ct_process_comment"
WORKORDER_TABLE_NAME = "ctttm_workorder_list"
FILE_PATTERN = "*_CT_PROCESS_COMMENT_*.csv.deflate"
SOURCE_FILE_PATTERN = r"^\d+_CT_PROCESS_COMMENT_(?P<file_timestamp>\d{8}_\d{4})\.csv\.deflate$"
FILE_SEPARATOR = "\x03"
DEFAULT_TABLE_DIR = Path(settings.DATA_MOVEMENT_CT_PROCESS_COMMENT_DIR)
UPSERT_KEY = "workorder_id"
UPDATE_FLAG_COLUMN = "update_flag"
LLM_SUMMARY_COLUMN = "llm_summary"
LLM_CORE_SUMMARY_COLUMN = "llm_core_summary"
EQP_ID_FILTER_COLUMN = "eqp_id"
EQP_ID_FILTER_PREFIXES = ("E",)

FILE_COLUMNS = [
    "workorder_id",
    "line_id",
    "process_id",
    "process_seq",
    "comment_seq",
    "eqp_id",
    "freeze_yn",
    "contents",
    "contents_text",
    "create_date",
    "create_user",
    "update_date",
    "update_user",
    "use_yn",
    "modify_user",
    "modify_date",
    "pbu_part_key",
]

DB_COLUMNS = FILE_COLUMNS
EXCLUDED_ROW_FILTERS = {
    "use_yn": {"N"},
}
PREFIX_ROW_FILTERS = {
    EQP_ID_FILTER_COLUMN: EQP_ID_FILTER_PREFIXES,
}
