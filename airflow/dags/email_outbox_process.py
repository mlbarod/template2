from __future__ import annotations

import os

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from dag_concurrency import SHARED_DAG_CONCURRENCY_POOL
from failure_alerts import notify_airflow_task_failure

AIRFLOW_API_BASE_URL = (os.getenv("AIRFLOW_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
AIRFLOW_TRIGGER_TOKEN = os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
EMAIL_OUTBOX_PROCESS_TRIGGER_URL = f"{AIRFLOW_API_BASE_URL}/api/v1/emails/outbox/process/"
EMAIL_OUTBOX_PROCESS_HTTP_TIMEOUT = int(os.getenv("EMAIL_OUTBOX_PROCESS_HTTP_TIMEOUT") or "60")
EMAIL_OUTBOX_PROCESS_SCHEDULE = os.getenv("EMAIL_OUTBOX_PROCESS_SCHEDULE") or "*/5 * * * *"
EMAIL_OUTBOX_PROCESS_LIMIT = int(os.getenv("EMAIL_OUTBOX_PROCESS_LIMIT") or "1000")


def run_email_outbox_process(**_context):
    if not AIRFLOW_API_BASE_URL:
        raise ValueError("AIRFLOW_API_BASE_URL is not set")

    headers = {"Accept": "application/json", "X-Forwarded-Proto": "https"}
    if AIRFLOW_TRIGGER_TOKEN:
        headers["Authorization"] = f"Bearer {AIRFLOW_TRIGGER_TOKEN}"

    request_kwargs = {
        "url": EMAIL_OUTBOX_PROCESS_TRIGGER_URL,
        "headers": headers,
        "timeout": EMAIL_OUTBOX_PROCESS_HTTP_TIMEOUT,
    }
    if EMAIL_OUTBOX_PROCESS_LIMIT > 0:
        request_kwargs["json"] = {"limit": EMAIL_OUTBOX_PROCESS_LIMIT}

    response = requests.post(**request_kwargs)
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
    dag_id="email_outbox_process",
    default_args=default_args,
    schedule=EMAIL_OUTBOX_PROCESS_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=2,
    tags=["email", "rag", "outbox"],
) as dag:
    process_outbox = PythonOperator(
        task_id="process_email_outbox",
        python_callable=run_email_outbox_process,
        pool=SHARED_DAG_CONCURRENCY_POOL,
    )
