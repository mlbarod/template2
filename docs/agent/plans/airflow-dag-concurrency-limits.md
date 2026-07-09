# ExecPlan: Airflow DAG 동시성 제한

## 목표
- `data_movement_file_load` DAG는 동시에 실행 가능한 task를 최대 3개로 제한한다.
- 나머지 DAG는 각 DAG별 동시에 실행 가능한 task를 최대 2개로 제한한다.
- 대상 DAG task 전체가 공유하는 Airflow pool을 지정해서 전체 running task를 3개 슬롯으로 제한한다.
- DAG별 schedule과 HTTP timeout은 env override 없이 각 DAG 코드에 고정값으로 작성한다.

## 현재 상태
- `airflow/dags`에는 DAG 파일 7개가 있다.
- 모든 DAG는 `max_active_runs=1`로 같은 DAG run 중복 실행을 막고 있다.
- DAG별 `max_active_tasks` 제한이 적용되어 있다.
- DAG별 schedule과 HTTP timeout 일부가 환경 변수 override를 읽고 있다.

## 범위
- 수정 대상은 `airflow/dags/*.py` 중 실제 DAG 정의 파일로 제한한다.
- `failure_alerts.py`는 DAG 정의 파일이 아니므로 수정하지 않는다.
- Airflow metadata DB, Compose, env 파일은 수정하지 않는다.
- Airflow init 단계에서 pool을 idempotent하게 생성해 별도 CLI 실행을 피한다.
- DAG별 schedule/HTTP timeout은 Airflow DAG 파일과 운영 문서에서만 관리한다.

## 설계
- DAG 생성자에 `max_active_tasks`를 추가한다.
- `data_movement_file_load`는 `max_active_tasks=3`을 사용한다.
- 나머지 DAG는 `max_active_tasks=2`를 사용한다.
- 기존 `max_active_runs=1`은 유지한다.
- 공통 pool 이름은 `dag_concurrency.py`에 모아 모든 DAG task가 같은 pool을 참조하게 한다.
- 공통 pool 기본 이름은 `shared_dag_concurrency_pool`이며, `AIRFLOW_DAG_SHARED_POOL`로 override 가능하게 한다.
- `airflow-init`에서 `airflow pools set`을 실행해 metadata DB에 pool slot 3개를 보장한다.
- schedule과 HTTP timeout은 env contract에서 제외하고 코드에 직접 작성한다.
- API base URL, trigger token, shared pool, failure callback, limit/dry-run 같은 운영 입력은 env 기반을 유지한다.

## 실행 단계
- [x] `data_movement_file_load.py`의 pool 설정 제거 및 `max_active_tasks=3` 추가
- [x] 나머지 DAG 파일에 `max_active_tasks=2` 추가
- [x] 공통 pool 설정 모듈 추가
- [x] 모든 DAG task에 공통 pool 지정
- [x] `airflow-init`에 공통 pool 생성 명령 추가
- [x] DAG schedule/HTTP timeout env override 제거
- [x] Python 문법 검증 실행
- [x] 변경 범위 확인

## 검증
- `python3 -m py_compile airflow/dags/*.py`
- 기대 결과: 모든 DAG 파일이 문법 오류 없이 컴파일된다.

## 위험과 대응
- 위험: `max_active_tasks`는 전체 DAG 수 합산 제한이 아니라 DAG별 task 동시성 제한이다.
- 대응: 사용자 요청을 각 DAG별 병렬 task 제한으로 해석했음을 결과에 명시한다.
- 위험: Airflow pool은 DAG run 수가 아니라 task instance 실행 수를 제한한다.
- 대응: 모든 DAG task에 같은 pool을 적용해 대상 DAG 전체 running task를 3개로 제한하고, pool 생성 CLI가 필요함을 명시한다.
- 위험: schedule/HTTP timeout env override 제거 후 운영 중 즉시 변경하려면 코드 배포가 필요하다.
- 대응: 사용자가 요청한 명시적 DAG 코드 관리를 우선하고 문서에서 env override 설명을 제거한다.

## 진행 기록
- 2026-07-09: DAG별 `max_active_tasks` 적용 계획을 작성했다.
- 2026-07-09: `data_movement_file_load`는 3개, 나머지 DAG는 2개로 task 동시성 제한을 적용했다.
- 2026-07-09: `python3 -m py_compile airflow/dags/*.py` 검증을 통과했다.
- 2026-07-09: 여러 DAG 전체 동시 실행을 제한하기 위해 공통 Airflow pool 적용을 추가하기로 했다.
- 2026-07-09: `shared_dag_concurrency_pool` 공통 pool을 모든 DAG task에 지정했다.
- 2026-07-09: `python3 -m py_compile airflow/dags/*.py`와 task별 pool 적용 개수 검증을 통과했다.
- 2026-07-09: `airflow-init`에서 공통 pool을 자동 생성하도록 Compose와 env 주석을 갱신했다.
- 2026-07-09: DAG schedule과 HTTP timeout을 env override 대신 코드 고정값으로 관리하기로 했다.
- 2026-07-09: DAG 코드와 운영/설정 문서에서 schedule/HTTP timeout env override 설명을 제거했다.
