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
L3_SPIDER_MAIL_TRIGGER_URL = f"{AIRFLOW_API_BASE_URL}/api/v1/l3_spider/mail-rules/trigger"
L3_SPIDER_MAIL_TRIGGER_HTTP_TIMEOUT = int(os.getenv("L3_SPIDER_MAIL_TRIGGER_HTTP_TIMEOUT") or "60")
L3_SPIDER_MAIL_TRIGGER_SCHEDULE = os.getenv("L3_SPIDER_MAIL_TRIGGER_SCHEDULE") or "*/5 * * * *"
L3_SPIDER_MAIL_TRIGGER_LIMIT = int(os.getenv("L3_SPIDER_MAIL_TRIGGER_LIMIT") or "20")


def run_l3_spider_mail_trigger(**_context):
    """L3 Spider 메일 rule 처리를 Django API에 위임합니다."""

    if not AIRFLOW_API_BASE_URL:
        raise ValueError("AIRFLOW_API_BASE_URL is not set")

    headers = {"Accept": "application/json", "X-Forwarded-Proto": "https"}
    if AIRFLOW_TRIGGER_TOKEN:
        headers["Authorization"] = f"Bearer {AIRFLOW_TRIGGER_TOKEN}"

    request_kwargs = {
        "url": L3_SPIDER_MAIL_TRIGGER_URL,
        "headers": headers,
        "timeout": L3_SPIDER_MAIL_TRIGGER_HTTP_TIMEOUT,
    }
    if L3_SPIDER_MAIL_TRIGGER_LIMIT > 0:
        request_kwargs["json"] = {"limit": L3_SPIDER_MAIL_TRIGGER_LIMIT}

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
    dag_id="l3_spider_mail_trigger",
    default_args=default_args,
    schedule=L3_SPIDER_MAIL_TRIGGER_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=2,
    is_paused_upon_creation=False,
    tags=["l3-spider", "mail"],
) as dag:
    trigger_l3_spider_mail = PythonOperator(
        task_id="trigger_l3_spider_mail",
        python_callable=run_l3_spider_mail_trigger,
        pool=SHARED_DAG_CONCURRENCY_POOL,
    )
