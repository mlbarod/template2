from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule

AIRFLOW_API_BASE_URL = (os.getenv("AIRFLOW_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
AIRFLOW_TRIGGER_TOKEN = os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
DRONE_SOP_POP3_INGEST_TRIGGER_URL = (
    f"{AIRFLOW_API_BASE_URL}/api/v1/line-dashboard/sop/ingest/pop3/trigger"
)
DRONE_SOP_INFORM_TRIGGER_URL = f"{AIRFLOW_API_BASE_URL}/api/v1/line-dashboard/sop/inform/trigger"
DRONE_SOP_POP3_INGEST_HTTP_TIMEOUT = int(os.getenv("DRONE_SOP_POP3_INGEST_HTTP_TIMEOUT") or "60")
DRONE_SOP_INFORM_HTTP_TIMEOUT = int(os.getenv("DRONE_SOP_INFORM_HTTP_TIMEOUT") or "60")
DRONE_SOP_POP3_INGEST_INFORM_CREATE_SCHEDULE = (
    os.getenv("DRONE_SOP_POP3_INGEST_INFORM_CREATE_SCHEDULE") or "*/1 * * * *"
)


def _parse_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
        if parsed <= 0:
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def run_drone_sop_pop3_ingest(**_context):
    if not AIRFLOW_API_BASE_URL:
        raise ValueError("AIRFLOW_API_BASE_URL is not set")

    headers = {"Accept": "application/json", "X-Forwarded-Proto": "https"}
    if AIRFLOW_TRIGGER_TOKEN:
        headers["Authorization"] = f"Bearer {AIRFLOW_TRIGGER_TOKEN}"

    response = requests.post(
        DRONE_SOP_POP3_INGEST_TRIGGER_URL,
        headers=headers,
        timeout=DRONE_SOP_POP3_INGEST_HTTP_TIMEOUT,
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code}


def run_drone_sop_inform_create(**_context):
    if not AIRFLOW_API_BASE_URL:
        raise ValueError("AIRFLOW_API_BASE_URL is not set")

    headers = {"Accept": "application/json"}
    if AIRFLOW_TRIGGER_TOKEN:
        headers["Authorization"] = f"Bearer {AIRFLOW_TRIGGER_TOKEN}"

    payload = {}
    limit = _parse_optional_int(os.getenv("DRONE_SOP_INFORM_LIMIT"))
    if limit is not None:
        payload["limit"] = limit

    response = requests.post(
        DRONE_SOP_INFORM_TRIGGER_URL,
        headers=headers,
        json=payload or None,
        timeout=DRONE_SOP_INFORM_HTTP_TIMEOUT,
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code}


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="drone_sop_pop3_ingest_inform_create",
    default_args=default_args,
    schedule=DRONE_SOP_POP3_INGEST_INFORM_CREATE_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["drone", "sop", "pop3", "inform"],
) as dag:
    ingest_pop3 = PythonOperator(
        task_id="ingest_pop3_drone_sop",
        python_callable=run_drone_sop_pop3_ingest,
    )

    create_inform = PythonOperator(
        task_id="create_inform_drone_sop",
        python_callable=run_drone_sop_inform_create,
        trigger_rule=TriggerRule.ALL_DONE,
    )

    ingest_pop3 >> create_inform
