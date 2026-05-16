from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

AIRFLOW_API_BASE_URL = (os.getenv("AIRFLOW_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
AIRFLOW_TRIGGER_TOKEN = os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
ACCOUNT_EXTERNAL_AFFILIATIONS_SYNC_TRIGGER_URL = (
    f"{AIRFLOW_API_BASE_URL}/api/v1/account/external-affiliations/sync"
)
ACCOUNT_EXTERNAL_AFFILIATIONS_SYNC_HTTP_TIMEOUT = int(
    os.getenv("ACCOUNT_EXTERNAL_AFFILIATIONS_SYNC_HTTP_TIMEOUT") or "60"
)
ACCOUNT_EXTERNAL_AFFILIATIONS_SYNC_SCHEDULE = (
    os.getenv("ACCOUNT_EXTERNAL_AFFILIATIONS_SYNC_SCHEDULE") or "@daily"
)
EXTERNAL_AFFILIATION_COLUMN_RENAMES = {
    "tdvt_nm": "user_sdwt_prod",
    "sso_id": "knox_id",
    "org_dept_kor_nm": "department",
    "emp_prf_fllnm": "username",
}
EXTERNAL_AFFILIATION_RECORD_COLUMNS = [
    "knox_id",
    "username",
    "department",
    "user_sdwt_prod",
    "source_updated_at",
]


def build_external_affiliations_payload(payload: Any) -> dict[str, list[dict[str, object]]]:
    """사내 서버에서 받은 DataFrame을 외부 소속 동기화 API payload로 변환합니다."""

    renamed_payload = payload.rename(columns=EXTERNAL_AFFILIATION_COLUMN_RENAMES)
    available_columns = [
        column for column in EXTERNAL_AFFILIATION_RECORD_COLUMNS if column in renamed_payload.columns
    ]
    normalized_payload = renamed_payload[available_columns].where(renamed_payload.notna(), None)
    return {"records": normalized_payload.to_dict("records")}


def run_account_external_affiliations_sync(**_context):
    if not AIRFLOW_API_BASE_URL:
        raise ValueError("AIRFLOW_API_BASE_URL is not set")

    headers = {"Accept": "application/json", "X-Forwarded-Proto": "https"}
    if AIRFLOW_TRIGGER_TOKEN:
        headers["Authorization"] = f"Bearer {AIRFLOW_TRIGGER_TOKEN}"

    # 사내 서버 수신부에서 받은 DataFrame은 아래 helper로 API payload 형식에 맞춥니다.
    # payload = build_external_affiliations_payload(payload)
    # records 예시:
    # [{"knox_id": "K1", "username": "홍길동", "department": "DeptA", "user_sdwt_prod": "G1"}]
    payload = {"records": []}

    response = requests.post(
        ACCOUNT_EXTERNAL_AFFILIATIONS_SYNC_TRIGGER_URL,
        headers=headers,
        json=payload,
        timeout=ACCOUNT_EXTERNAL_AFFILIATIONS_SYNC_HTTP_TIMEOUT,
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code}


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="account_external_affiliations_sync",
    default_args=default_args,
    schedule=ACCOUNT_EXTERNAL_AFFILIATIONS_SYNC_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["account", "affiliation", "external"],
) as dag:
    sync_external_affiliations = PythonOperator(
        task_id="sync_external_affiliations",
        python_callable=run_account_external_affiliations_sync,
    )
