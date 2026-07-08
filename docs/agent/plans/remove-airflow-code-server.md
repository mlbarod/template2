# ExecPlan: remove Airflow code-server

## 목표
- Airflow 이미지와 Compose 실행 구성에서 code-server를 제거한다.
- Airflow webserver, scheduler, init, PostgreSQL 실행 흐름은 유지한다.

## 현재 상태
- `airflow/Dockerfile`은 code-server 설치 없이 공식 Airflow image를 base로 내부 apt/pip mirror 설정과 선택적 BigDataQuery ODBC 드라이버 설치만 담당하는 최소 Dockerfile로 유지한다.
- `airflow/online/Dockerfile`은 registry image 직접 사용 전환 후 제거했다.
- `compose/airflow.yml`, `compose/airflow.internal.yml`, `airflow/docker-compose.yaml`에서 `airflow-code` service를 제거했다.
- `airflow/online/`, `airflow/scripts/`, 빈 `airflow/vendor/`는 registry image 직접 사용 전환 후 제거했다.
- 루트 dev compose는 `apache/airflow:2.11.0`를 직접 사용한다.
- OIDC/prod compose는 Docker Hub mirror의 `apache/airflow:2.11.0`를 base image로 빌드한 `airflow:2.11.0-internal`을 사용한다.

## 범위
- 수정할 영역: Airflow Compose 조각과 Airflow 문서.
- 수정하지 않을 영역: Airflow DAG 코드, API/Web contract, DB schema, auth/env contract.

## 설계
- 루트 Compose의 Airflow image는 custom build image를 만들지 않고 registry image를 직접 사용한다.
- `airflow-code` service와 `CODE_SERVER_PASSWORD`, `AIRFLOW_CODE_SERVER_PORT` 사용을 제거한다.
- 루트 dev Compose와 Airflow 단독 Compose는 Airflow Dockerfile을 build하지 않는다.
- OIDC/prod Compose는 Airflow Dockerfile을 build해 내부 apt/pip mirror 설정과 BigDataQuery ODBC 드라이버를 주입한다.
- ODBC DSN 파일은 repo에 저장하지 않고 운영에서 `airflow/odbc`에 제공한 뒤 `/usr/local/odbc`로 mount한다.
- Airflow 단독 실행은 `airflow/docker-compose.yaml` 하나로 관리한다.

## 실행 단계
- [x] code-server 참조 위치를 확인한다.
- [x] Dockerfile에서 code-server 설치를 제거한다.
- [x] Compose에서 `airflow-code` service와 image 이름을 정리한다.
- [x] 보조 스크립트/문서에서 code-server vendor 흐름을 제거한다.
- [x] `airflow/online/`, `airflow/scripts/`, 빈 `airflow/vendor/`를 제거한다.
- [x] compose config 검증을 실행한다.

## 검증
- `bash scripts/agent/check_compose_configs.sh`
- `docker compose -f docker-compose.dev.yml config --images | rg -n "apache/airflow|codeserver|code-server|airflow-runtime"`
- `docker compose -f docker-compose.oidc.yml config --images | rg -n "apache/airflow|codeserver|code-server|airflow-runtime"`
- `docker compose -f docker-compose.yml config --images | rg -n "apache/airflow|codeserver|code-server|airflow-runtime"`
- `AIRFLOW_WEBSERVER_SECRET_KEY=test AIRFLOW_FERNET_KEY=test AIRFLOW_UID=50000 docker compose -f airflow/docker-compose.yaml config --images | rg -n "apache/airflow|codeserver|code-server|airflow-runtime"`
- `AIRFLOW_WEBSERVER_SECRET_KEY=test AIRFLOW_FERNET_KEY=test AIRFLOW_UID=50000 docker compose -f airflow/docker-compose.yaml config --services | rg -n "airflow|code"`

## 위험과 대응
- 위험: 사내망에서 mirror registry에 접근하지 못하면 Airflow image pull이 실패한다.
- 대응: OIDC/prod Airflow image는 `repository.samsungds.net/proxy-docker-registry-1.docker.io/apache/airflow:2.11.0`로 고정한다.
- 위험: code-server 포트를 기대하던 사용자는 접속 경로가 사라진다.
- 대응: Airflow Web UI와 DAG volume mount는 유지한다.
- 위험: ODBC DSN 파일에 운영 연결 정보가 포함될 수 있다.
- 대응: repo에는 폴더만 유지하고 운영 파일은 배포 시 mount한다.

## 진행 기록
- 2026-07-08: Airflow code-server 제거 범위와 검증 방법을 정리했다.
- 2026-07-08: Dockerfile, Compose, 오프라인 준비 스크립트, README에서 code-server 실행/설치 흐름을 제거했다.
- 2026-07-08: dev/OIDC/prod 및 Airflow 단독 compose config에서 `airflow-code` 제거를 확인했다.
- 2026-07-08: 루트 dev/OIDC/prod compose는 Airflow 커스텀 빌드 대신 public/mirror `apache/airflow:2.11.0` 이미지를 직접 사용하도록 바꿨다.
- 2026-07-08: Airflow 단독 Compose도 `AIRFLOW_IMAGE` env 기반 registry image 직접 사용으로 바꿨다.
- 2026-07-08: OIDC/prod 사내망 설정을 위해 code-server 없는 최소 Airflow Dockerfile을 다시 두고 내부 apt/pip mirror build arg를 연결했다.
- 2026-07-08: OIDC/prod Airflow Dockerfile에 BigDataQuery ODBC 드라이버 설치 옵션을 추가하고 ODBC 설정 파일은 운영 mount로 분리했다.
- 2026-07-08: 중복된 `airflow/online/`과 오프라인 준비용 `airflow/scripts/`를 제거하고 단일 Airflow Compose 구조로 정리했다.
- 2026-07-08: 더 이상 참조되지 않는 빈 `airflow/vendor/`도 제거했다.
