# ExecPlan: data_movement Airflow DAG

## 목표
- `data_movement` 파일 적재를 Airflow polling 방식으로 자동 트리거한다.
- Airflow는 주기적으로 Django API trigger endpoint를 호출하고, API는 기존 loader service를 실행한다.

## 현재 상태
- 테이블별 loader command는 `load_m_tkin_prevent`, `load_ctttm_workorder_list`, `load_ct_process_comment`로 존재한다.
- 기존 Airflow DAG는 백엔드 컨테이너 직접 실행이 아니라 HTTP API 호출 패턴을 사용한다.
- `ct_process_comment`는 `ctttm_workorder_list`에 존재하는 workorder만 적재한다.

## 범위
- 수정할 영역:
  - `apps/api/api/data_movement`
  - `apps/api/api/urls.py`
  - `apps/api/config/settings.py`
  - `airflow/dags`
  - `env/airflow.common.env`
  - 관련 docs
- 수정하지 않을 영역:
  - data_movement table schema/migration
  - 파일 loader business rule
  - Airflow 인프라 compose 추가

## 설계
- `POST /api/v1/data-movement/<table_name>/load/` endpoint를 추가한다.
- endpoint는 `AIRFLOW_TRIGGER_TOKEN` Bearer 인증을 사용한다.
- request 옵션은 `limit`, `dry_run`만 허용하고 파일 경로는 서버 env 설정을 사용한다.
- Airflow DAG `data_movement_file_load`는 1분 기본 schedule로 세 endpoint를 호출한다.
- `ctttm_workorder_list` task 성공 후 `ct_process_comment` task를 실행한다.

## 실행 단계
- [x] ExecPlan 작성
- [x] API coordinator app/urls/views/tests 추가
- [x] global URL registry와 installed app 갱신
- [x] Airflow DAG 추가
- [x] docs inventory/backend/operations/configuration 갱신
- [x] syntax/test 검증

## 검증
- `python3 -m py_compile airflow/dags/data_movement_file_load.py`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`

## 위험과 대응
- 위험: Airflow runtime이 API 컨테이너 내부 command를 실행할 수 없다.
- 대응: 기존 DAG 패턴과 동일하게 HTTP API trigger endpoint를 호출한다.
- 위험: comment 적재가 workorder 적재보다 먼저 실행되면 일부 row가 제외된다.
- 대응: DAG task dependency를 `ctttm_workorder_list >> ct_process_comment`로 둔다.

## 진행 기록
- 2026-05-30: Airflow polling DAG와 API trigger endpoint 방식으로 진행한다.
- 2026-05-30: `data_movement_file_load` DAG, API trigger endpoint, 문서와 테스트를 추가했다.
