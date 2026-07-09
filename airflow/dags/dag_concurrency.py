from __future__ import annotations

import os

SHARED_DAG_CONCURRENCY_POOL = (
    os.getenv("AIRFLOW_DAG_SHARED_POOL") or "shared_dag_concurrency_pool"
)
