# ExecPlan: ct_process_comment summary DAG split

## 목표
- `ct_process_comment` OpenWebUI/LLM 요약 트리거를 파일 적재 DAG에서 분리한다.
- 파일 적재 실패/성공 상태와 요약 외부 호출 상태를 Airflow에서 별도로 운영할 수 있게 한다.

## 현재 상태
- 변경 전에는 `airflow/dags/data_movement_file_load.py`가 파일 적재 endpoint와 `ct_process_comment/summarize/` endpoint를 함께 호출했다.
- `ct_process_comment` 적재는 `ctttm_workorder_list` 적재 이후 실행된다.
- 요약 대상은 `update_flag='Y'` row라서 별도 DAG에서 반복 실행해도 같은 API 계약을 유지할 수 있다.

## 범위
- 수정: Airflow DAG 파일, Airflow compose 환경 변수, 운영/설정/data movement 문서.
- 수정하지 않음: Django API, DB schema, OpenWebUI request/response 계약, loader business rule.

## 설계
- `data_movement_file_load`는 파일 적재 endpoint만 호출한다.
- 새 `ct_process_comment_summary` DAG가 `POST /api/v1/data-movement/ct_process_comment/summarize/`만 호출한다.
- 새 DAG는 `DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_SCHEDULE`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_HTTP_TIMEOUT`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_LIMIT`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_DRY_RUN`을 읽는다.
- API/auth 계약 변화는 없다. 기존 `AIRFLOW_TRIGGER_TOKEN` Bearer header를 유지한다.

## 실행 단계
- [x] 기존 파일 적재 DAG에서 요약 함수/task/dependency 제거
- [x] 요약 전용 DAG 추가
- [x] Airflow compose 환경 변수 추가
- [x] 관련 문서 갱신
- [x] Python compile 검증 및 변경 diff 확인

## 검증
- `python -m py_compile airflow/dags/data_movement_file_load.py airflow/dags/ct_process_comment_summary.py`
- `git diff --check`

## 위험과 대응
- 위험: 새 DAG schedule env가 Airflow webserver/scheduler에 전달되지 않으면 기본값만 사용된다.
- 대응: `compose/airflow.yml`의 Airflow 서비스 환경 변수에 summary schedule/옵션을 추가한다.

## 진행 기록
- 2026-07-06: 사용자가 요약 트리거 DAG 분리를 요청해 실행 계획을 작성했다.
- 2026-07-06: `ct_process_comment_summary` DAG를 추가하고 `data_movement_file_load`를 파일 적재 전용으로 변경했다.
- 2026-07-06: `python3 -m py_compile`과 `git diff --check` 검증을 통과했다.
