from __future__ import annotations

import os
from typing import Any

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from failure_alerts import notify_airflow_task_failure

AIRFLOW_API_BASE_URL = (os.getenv("AIRFLOW_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
AIRFLOW_TRIGGER_TOKEN = os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_HTTP_TIMEOUT = int(
    os.getenv("DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_HTTP_TIMEOUT") or "1800"
)
DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_SCHEDULE = (
    os.getenv("DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_SCHEDULE") or "*/1 * * * *"
)


def _parse_optional_int(value: Any) -> int | None:
    """환경 변수 값을 양의 정수 옵션으로 변환합니다."""

    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_bool(value: Any) -> bool:
    """환경 변수 값을 boolean 옵션으로 변환합니다."""

    if value in (None, ""):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def run_ct_process_comment_summary(**_context):
    """ct_process_comment OpenWebUI 요약 API를 호출합니다."""

    if not AIRFLOW_API_BASE_URL:
        raise ValueError("AIRFLOW_API_BASE_URL is not set")
    if not AIRFLOW_TRIGGER_TOKEN:
        raise ValueError("AIRFLOW_TRIGGER_TOKEN is not set")

    payload: dict[str, object] = {}
    limit = _parse_optional_int(os.getenv("DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_LIMIT"))
    if limit is not None:
        payload["limit"] = limit
    if _parse_bool(os.getenv("DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_DRY_RUN")):
        payload["dry_run"] = True

    response = requests.post(
        f"{AIRFLOW_API_BASE_URL}/api/v1/data-movement/ct_process_comment/summarize/",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {AIRFLOW_TRIGGER_TOKEN}",
            "X-Forwarded-Proto": "https",
        },
        json=payload or None,
        timeout=DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_HTTP_TIMEOUT,
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code}


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "on_failure_callback": notify_airflow_task_failure,
}

with DAG(
    dag_id="ct_process_comment_summary",
    default_args=default_args,
    schedule=DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["data_movement", "summary"],
) as dag:
    summarize_ct_process_comment = PythonOperator(
        task_id="summarize_ct_process_comment",
        python_callable=run_ct_process_comment_summary,
    )
