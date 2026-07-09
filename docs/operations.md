# 운영/개발 명령

이 문서는 로컬 실행, 테스트, 마이그레이션 확인, management command를 정리합니다.

## 실행 진입점

일반 작업에서는 root의 `make` target을 사용합니다.
root compose 파일은 Makefile이 감싸는 실행 구현이고, `compose/` 아래 파일은 내부 조립용입니다.

| 환경 | 기본 명령 | 용도 | dependency source |
| --- | --- | --- | --- |
| `dev` | `make dev` | 로컬 개발 전용 | public registry/package source |
| `oidc` | `make oidc` | 사내 OIDC 검증/스테이징 | internal mirror |
| `prod` | `make prod` | 운영 compose 조립 | internal mirror |

`dev`는 로컬 PC에서만 사용하는 개발 환경입니다.
`oidc`와 `prod`는 Docker image와 package manager source를 내부 mirror로 고정합니다.

## app / infra 구분

| 그룹 | 포함 서비스 | 설명 |
| --- | --- | --- |
| `app` | API, Web, Nginx, MinIO, MinIO init | 실제 앱 실행에 필요한 서비스 |
| `dev app` 추가 | dummy ADFS/RAG/LLM/Mail/Jira | 로컬 외부계 대체 서비스 |
| `infra` | Airflow DB, Airflow init/webserver/scheduler, FTP | 데이터 적재와 Airflow DAG 검증용 기반 서비스 |

로컬 개발 기본 실행:

```bash
make dev
```

app만 조작:

```bash
make dev-app-up
make dev-app-build
make dev-app-down
make oidc-app-up
make oidc-app-build
make oidc-app-down
make prod-app-up
make prod-app-build
make prod-app-down
```

Airflow/FTP 기반 데이터 적재 작업이 필요하면 infra를 별도로 조작합니다.
OIDC/prod infra에는 monitoring 서비스도 함께 포함됩니다.

```bash
make dev-infra-up
make dev-infra-build
make dev-infra-down
make oidc-infra-up
make oidc-infra-build
make oidc-infra-down
make prod-infra-up
make prod-infra-build
make prod-infra-down
```

OIDC/prod compose에는 Airflow/FTP 외에 monitoring 서비스도 포함됩니다.

주요 주소:

| 서비스 | 주소 |
| --- | --- |
| Web | `http://localhost:3000` |
| API | `http://localhost:8000` |
| Nginx | `http://localhost` |
| Dummy ADFS/RAG/LLM/Mail/Jira | `http://localhost:9102` |
| MinIO | `http://localhost:9000`, `http://localhost:9001` |

## 프론트 명령

```bash
npm run web:dev
npm run web:build
npm run web:lint
npm run agent:audit
npm run agent:audit:docs
npm run agent:audit:web-boundary
npm run agent:audit:ui
```

## 백엔드 검증

백엔드는 Docker Compose `api` 컨테이너 기준입니다.

```bash
make check-api
make test-api
make makemigrations-check
```

## Management command

| Command | 설명 |
| --- | --- |
| `ensure_dev_database` | dev 환경에서 Django 기본 DB와 필수 PostgreSQL extension 생성 |
| `process_email_outbox` | EmailOutbox RAG 작업 처리 |
| `seed_dummy_emails` | 로컬 개발용 더미 Email 데이터 생성 |
| `load_m_tkin_prevent` | `m_tkin_prevent` incoming 파일 적재 |
| `load_ctttm_workorder_list` | `ctttm_workorder_list` incoming 파일 적재 |
| `load_ct_process_comment` | `ct_process_comment` incoming 파일 적재 |
| `summarize_ct_process_comment` | `ct_process_comment` OpenWebUI 요약 처리 |
| `load_eqp_status_chg` | `eqp_status_chg` incoming 파일 적재 |
| `load_mi_tip_update_hist` | `mi_tip_update_hist` incoming 파일 적재 |
| `load_racb_list` | `racb_list` incoming 파일 적재 |
| `load_mes_line_mapping_info` | `mes_line_mapping_info` incoming 파일 전체 교체 적재 |
| `load_station_master` | `station_master` incoming 파일 전체 교체 적재 |
| `seed_drone_dummy_data` | 로컬 개발용 Drone SOP 더미 데이터 생성 |
| `seed_drone_targets_from_file` | JSON/CSV 기준 Drone SOP/발송 이력/알림 설정 초기화 후 target/channel/recipient seed |
| `prune_drone_sop` | 보관 기간 초과 Drone SOP 데이터 정리 |
| `purge_drone_sop` | Drone SOP 데이터 전체 삭제 또는 dry-run 확인 |

실행 예시:

```bash
docker compose -f docker-compose.dev.yml exec -T api python manage.py ensure_dev_database
docker compose -f docker-compose.dev.yml exec -T api python manage.py process_email_outbox
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_dummy_emails
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_m_tkin_prevent
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_ctttm_workorder_list
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_ct_process_comment
docker compose -f docker-compose.dev.yml exec -T api python manage.py summarize_ct_process_comment
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_eqp_status_chg
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_mi_tip_update_hist
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_racb_list
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_mes_line_mapping_info
docker compose -f docker-compose.dev.yml exec -T api python manage.py load_station_master
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_drone_dummy_data --prefix DEMO --reset
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_drone_targets_from_file --file /app/config/drone_targets.json --dry-run
docker compose -f docker-compose.dev.yml exec -T api python manage.py prune_drone_sop
docker compose -f docker-compose.dev.yml exec -T api python manage.py purge_drone_sop --dry-run
```

로컬 dev 로그인 사용자는 `env/api.dev.env`의 `DEV_AUTO_AFFILIATION_ALLOWED=1` 설정으로 기본 소속이 보장됩니다.
OIDC/운영 환경에서는 자동 소속 변경을 실행하지 않습니다.

## Data Movement Airflow DAG

`airflow/dags/data_movement_file_load.py`는 기본 1분 주기로 아래 파일 적재 endpoint를 호출합니다.

```text
POST /api/v1/data-movement/m_tkin_prevent/load/
POST /api/v1/data-movement/ctttm_workorder_list/load/
POST /api/v1/data-movement/ct_process_comment/load/
POST /api/v1/data-movement/eqp_status_chg/load/
POST /api/v1/data-movement/mi_tip_update_hist/load/
POST /api/v1/data-movement/racb_list/load/
POST /api/v1/data-movement/mes_line_mapping_info/load/
POST /api/v1/data-movement/station_master/load/
```

`ct_process_comment`는 workorder 목록을 참조하므로 DAG에서 `ctttm_workorder_list` 이후 실행됩니다.
`data_movement_file_load`는 `max_active_runs=1`, `max_active_tasks=3`으로 같은 DAG run 중복과 DAG 내부 task 병렬 실행 수를 제한합니다.
나머지 Airflow DAG는 `max_active_runs=1`, `max_active_tasks=2`를 사용합니다.
모든 DAG task는 `shared_dag_concurrency_pool`을 공유하며, `airflow-init`가 기본 3 slots로 pool을 생성/갱신합니다.
따라서 대상 DAG들의 전체 동시 실행은 DAG run 개수가 아니라 running task instance 기준 최대 3개로 제한됩니다.
pool 이름과 slot 수는 `env/airflow.common.env`의 `AIRFLOW_DAG_SHARED_POOL`, `AIRFLOW_DAG_SHARED_POOL_SLOTS`로 override할 수 있습니다.
`eqp_status_chg`는 `/data/data_movement/m_eqp_status_chg/incoming/*m_eqp_status_chg*.csv.deflate` 파일을 `eqp_event_key` 기준으로 upsert하고 180일 retention을 적용합니다.
`mi_tip_update_hist`는 `/data/data_movement/mi_tip_update_hist/incoming/*mi_tip_update_hist*.csv.deflate` 파일을 TIP timeline 조회용 row로 적재합니다.
`racb_list`는 `/data/data_movement/racb_list/incoming/*racb_list*.csv.deflate` 파일을 `c_racb_id` 최신 row 기준으로 설비별 `eqp_cb` row로 펼쳐 적재합니다.
`mes_line_mapping_info`는 `/data/data_movement/mes_line_mapping_info/incoming/*_MES_MAPPING_INFO_*.csv.deflate` 파일을 테이블 전체 snapshot으로 적재합니다.
`station_master`는 `/data/data_movement/station_master/incoming/*_STATION_MASTER_*.csv.deflate` 파일을 테이블 전체 snapshot으로 적재합니다.
파일 적재 DAG는 코드에 고정된 `*/1 * * * *` schedule과 1800초 HTTP timeout을 사용합니다.
처리량 제한과 dry-run payload만 Airflow 환경 변수로 조정합니다.

```text
DATA_MOVEMENT_LOAD_LIMIT=
DATA_MOVEMENT_LOAD_DRY_RUN=false
```

`airflow/dags/ct_process_comment_summary.py`는 별도 DAG `ct_process_comment_summary`로 아래 endpoint를 호출합니다.
요약은 `update_flag='Y'` row를 OpenWebUI로 처리하므로 파일 적재 DAG와 독립적으로 재시도하거나 중지할 수 있습니다.

```text
POST /api/v1/data-movement/ct_process_comment/summarize/
```

```text
DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_LIMIT=
DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_DRY_RUN=false
```

요약 DAG도 코드에 고정된 `*/1 * * * *` schedule과 1800초 HTTP timeout을 사용합니다.

송신 측에서 최종 파일명으로 직접 전송할 수 있으므로 API loader는 전송 중으로 보이는 파일을 적재 후보에서 제외합니다.
기본값은 마지막 수정 후 60초 이상 지난 파일만 후보로 보고, 1초 뒤 size/mtime이 그대로인 파일만 이번 실행에서 처리합니다.

```text
DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=60
DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=1
```

### Data Movement FTP

Compose의 `ftp` service는 API와 같은 host path를 공유합니다.
기본 host path는 `./data/data_movement`이며 API 컨테이너에서는 `/data/data_movement`로 보입니다.

```bash
make dev-infra-up
```

FTP 접속 기본값:

```text
host=<compose host>
port=6380
user=ftpuser
password=ftp1234
passive ports=8076-8079
```

운영/공유 환경에서는 아래 값을 env로 반드시 바꿉니다.

```text
FTP_USER
FTP_PASS
FTP_PASV_ADDRESS
FTP_PASV_MIN_PORT
FTP_PASV_MAX_PORT
DATA_MOVEMENT_HOST_PATH
```

### Drone JSON/CSV target seed

`seed_drone_targets_from_file`은 JSON/CSV의 `department`, `line`, `user_sdwt_prod` 목록을 기준으로
Drone SOP/발송 이력/알림 설정을 초기화한 뒤 다시 생성합니다.

입력 샘플은 `docs/examples/drone_targets.sample.json`,
`docs/examples/drone_targets.sample.csv`,
`docs/examples/drone_targets.multi_mapping.sample.csv`에 있습니다.

```json
{
  "targets": [
    {
      "department": "ENGR",
      "line": "L1",
      "target_user_sdwt_prod": "ETCH_A",
      "recipient_user_sdwt_prod": "ETCH_A",
      "channels": {
        "jira": {
          "enabled": false,
          "template_key": "common",
          "jira_project_key": "DRONE"
        },
        "messenger": {
          "enabled": true,
          "template_key": "common",
          "chatroom_id": null,
          "force_new_chatroom": true
        },
        "mail": {
          "enabled": true,
          "template_key": "common"
        }
      },
      "mappings": [
        {
          "sdwt_prod": "ETCH_A",
          "user_sdwt_prod": "ETCH_A"
        }
      ],
      "needtosend_rule": {
        "enabled": false,
        "comment_keyword": "$SETUP_EQP",
        "ignore_sample_type": false
      }
    }
  ]
}
```

주요 필드:

- `target_user_sdwt_prod`: `drone_sop_target.target_user_sdwt_prod`
- `recipient_user_sdwt_prod`: 수신인 자동 수집에 사용할 account 소속값
- `channels`: `drone_sop_target_channel_config` 생성값
- `mappings`: `drone_sop_target_mapping` 생성값
- `needtosend_rule`: `drone_sop_needtosend_rule` 생성값

사용 순서:

```bash
docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py seed_drone_targets_from_file \
  --file /app/config/drone_targets.json \
  --dry-run

docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py seed_drone_targets_from_file \
  --file /app/config/drone_targets.csv \
  --dry-run

docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py seed_drone_targets_from_file \
  --file /app/config/drone_targets.json
```

초기화 범위:

- `drone_sop`
- `drone_sop_target_dispatch`
- `drone_sop_delivery`
- `drone_sop_target`
- `drone_sop_target_mapping`
- `drone_sop_target_channel_config`
- `drone_sop_needtosend_rule`
- `drone_sop_target_recipient`

CSV에서 하나의 target에 mapping이 여러 개인 경우 target row는 하나만 작성하고 `mappings`
컬럼에 JSON 배열을 넣습니다. 같은 `target_user_sdwt_prod`가 여러 행에 반복되면 command가
오류로 중단됩니다.

JSON/CSV 파일은 `api` 컨테이너가 읽을 수 있는 경로에 배치해야 합니다.
실제 실행 전에는 반드시 `--dry-run` 출력의 삭제/생성 카운트를 확인합니다.

## 환경 변수 파일

| 파일 | 역할 |
| --- | --- |
| `env/api.common.env` | API 공통 설정 |
| `env/api.dev.env` | API 개발 오버라이드 |
| `env/web.dev.env` | Web 개발 설정 |
| `env/minio.env` | MinIO 설정 |

## 주의할 점

- backend 테스트와 Django 명령은 `api` 컨테이너에서 실행합니다.
- 외부 연동 URL은 하드코딩하지 않고 env로 관리합니다.
- auth/RAG/assistant/mail 계약을 바꾸면 `apps/adfs_dummy`도 함께 갱신합니다.

## 문서 검증

문서가 실제 route/model/env inventory와 크게 어긋나지 않는지 확인합니다.

```bash
npm run agent:audit:docs
```

검증 대상:

- backend API prefix와 주요 endpoint
- frontend route와 feature facade
- 주요 Django model class
- management command
- env group

## 장애 확인 순서

| 증상 | 먼저 확인할 것 |
| --- | --- |
| 화면이 API를 못 부름 | `VITE_BACKEND_URL`, Nginx proxy, Django allowed hosts/CORS/CSRF |
| 로그인 redirect 실패 | `OIDC_REDIRECT_URI`, `ALLOWED_REDIRECT_HOSTS`, session cookie secure/samesite |
| Emails 수집 실패 | POP3 env, Airflow token, dummy mail endpoint 동작 |
| RAG/Assistant 실패 | `ASSISTANT_*`, `RAG_*`, dummy RAG endpoint, permission group |
| Drone 알림 실패 | SOP 수집 결과, target/channel/recipient 설정, Jira/Mail/Messenger env |
| Observer 조회 실패 | `OBSERVER_QUERY_DAYS`, data movement 적재 상태, 기준 정보 endpoint |
| 파일/이미지 실패 | MinIO env, bucket 접근, asset sequence |
