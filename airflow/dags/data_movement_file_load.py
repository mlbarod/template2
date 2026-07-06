from __future__ import annotations

import os
from typing import Any

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

AIRFLOW_API_BASE_URL = (os.getenv("AIRFLOW_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
AIRFLOW_TRIGGER_TOKEN = os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
DATA_MOVEMENT_LOAD_HTTP_TIMEOUT = int(os.getenv("DATA_MOVEMENT_LOAD_HTTP_TIMEOUT") or "1800")
DATA_MOVEMENT_LOAD_SCHEDULE = os.getenv("DATA_MOVEMENT_LOAD_SCHEDULE") or "*/1 * * * *"


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


def run_data_movement_load(*, table_name: str, **_context):
    """테이블별 data_movement 적재 API를 호출합니다."""

    if not AIRFLOW_API_BASE_URL:
        raise ValueError("AIRFLOW_API_BASE_URL is not set")
    if not AIRFLOW_TRIGGER_TOKEN:
        raise ValueError("AIRFLOW_TRIGGER_TOKEN is not set")

    payload: dict[str, object] = {}
    limit = _parse_optional_int(os.getenv("DATA_MOVEMENT_LOAD_LIMIT"))
    if limit is not None:
        payload["limit"] = limit
    if _parse_bool(os.getenv("DATA_MOVEMENT_LOAD_DRY_RUN")):
        payload["dry_run"] = True

    response = requests.post(
        f"{AIRFLOW_API_BASE_URL}/api/v1/data-movement/{table_name}/load/",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {AIRFLOW_TRIGGER_TOKEN}",
            "X-Forwarded-Proto": "https",
        },
        json=payload or None,
        timeout=DATA_MOVEMENT_LOAD_HTTP_TIMEOUT,
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code}


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
}

with DAG(
    dag_id="data_movement_file_load",
    default_args=default_args,
    schedule=DATA_MOVEMENT_LOAD_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["data_movement", "file_load"],
) as dag:
    load_m_tkin_prevent = PythonOperator(
        task_id="load_m_tkin_prevent",
        python_callable=run_data_movement_load,
        op_kwargs={"table_name": "m_tkin_prevent"},
    )

    load_ctttm_workorder_list = PythonOperator(
        task_id="load_ctttm_workorder_list",
        python_callable=run_data_movement_load,
        op_kwargs={"table_name": "ctttm_workorder_list"},
    )

    load_ct_process_comment = PythonOperator(
        task_id="load_ct_process_comment",
        python_callable=run_data_movement_load,
        op_kwargs={"table_name": "ct_process_comment"},
    )

    load_eqp_status_chg = PythonOperator(
        task_id="load_eqp_status_chg",
        python_callable=run_data_movement_load,
        op_kwargs={"table_name": "eqp_status_chg"},
    )

    load_mi_tip_update_hist = PythonOperator(
        task_id="load_mi_tip_update_hist",
        python_callable=run_data_movement_load,
        op_kwargs={"table_name": "mi_tip_update_hist"},
    )

    load_racb_list = PythonOperator(
        task_id="load_racb_list",
        python_callable=run_data_movement_load,
        op_kwargs={"table_name": "racb_list"},
    )

    load_mes_line_mapping_info = PythonOperator(
        task_id="load_mes_line_mapping_info",
        python_callable=run_data_movement_load,
        op_kwargs={"table_name": "mes_line_mapping_info"},
    )

    load_station_master = PythonOperator(
        task_id="load_station_master",
        python_callable=run_data_movement_load,
        op_kwargs={"table_name": "station_master"},
    )

    load_ctttm_workorder_list >> load_ct_process_comment
