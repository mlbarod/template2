# ExecPlan: internal Docker registry

## 목표
- OIDC 개발과 운영 Docker Compose 실행 시 외부 registry가 아니라 `repository.samsungds.net` 사내 registry 이미지를 사용한다.
- 외부 dev 실행은 기존 Docker Hub image 이름과 base image 기본값을 유지한다.

## 현재 상태
- 실행 진입점은 `docker-compose.dev.yml`, `docker-compose.oidc.yml`, `docker-compose.yml`이다.
- `compose/dev.infra.yml`, `compose/oidc.infra.yml`, `compose/prod.infra.yml` 모두 공통 `compose/airflow.yml`을 include한다.
- `compose/prod.infra.yml`과 `compose/oidc.infra.yml`의 FTP image는 기존 사내 registry host를 사용한다.
- `compose/oidc.app.yml`, `compose/prod.app.yml`의 MinIO/Nginx image는 Docker Hub 이름이다.
- `apps/api/Dockerfile`, `apps/web/Dockerfile`, `airflow/Dockerfile`의 base image는 public image 이름으로 고정되어 있다.

## 범위
- 수정할 영역: OIDC/prod compose image 이름, OIDC/prod build args, Dockerfile base image args, registry 문서.
- 수정하지 않을 영역: dev compose image 이름, 앱 런타임 env contract, DB schema, auth/OIDC/RAG/Mail contract.

## 설계
- Docker Hub image는 사내 환경에서 `repository.samsungds.net/docker.io/<image>` 형식으로 명시한다.
- `gcr.io` image는 원 registry namespace를 보존해 `repository.samsungds.net/gcr.io/<image>` 형식으로 명시한다.
- dev도 include하는 `compose/airflow.yml`은 그대로 두고, OIDC/prod용 `compose/airflow.internal.yml`을 별도로 둔다.
- `api`, `web`, `airflow` Dockerfile은 base image `ARG` 기본값을 public image로 유지하고, OIDC/prod compose에서만 사내 image 값을 넘긴다.
- OIDC/prod Airflow build 산출물인 `airflow-with-codeserver`는 외부에서 pull하지 않도록 `pull_policy: never`를 둔다.
- public API, DB migration, auth contract 영향은 없다.

- [x] Dockerfile base image를 build arg로 분리한다.
- [x] OIDC/prod app compose image와 build args를 사내 registry 기준으로 바꾼다.
- [x] OIDC/prod infra compose가 사내 Airflow compose를 include하도록 바꾼다.
- [x] 사내 Airflow compose와 monitoring image를 사내 registry 기준으로 추가/수정한다.
- [x] 관련 문서를 `repository.samsungds.net` 기준으로 갱신한다.
- [x] compose config 검증을 실행한다.

## 검증
- 통과: `bash scripts/agent/check_compose_configs.sh`
- 통과: `docker compose -f docker-compose.dev.yml config --images`
- 통과: `docker compose -f docker-compose.oidc.yml config --images`
- 통과: `docker compose -f docker-compose.yml config --images`
- 통과: `docker compose -f docker-compose.dev.yml config | rg -n "PYTHON_BASE_IMAGE|NODE_BASE_IMAGE|AIRFLOW_BASE_IMAGE|image:"`
- 통과: `docker compose -f docker-compose.oidc.yml config | rg -n "PYTHON_BASE_IMAGE|NODE_BASE_IMAGE|AIRFLOW_BASE_IMAGE|image:"`
- 통과: `docker compose -f docker-compose.yml config | rg -n "PYTHON_BASE_IMAGE|NODE_BASE_IMAGE|AIRFLOW_BASE_IMAGE|image:"`
- 확인: `docker compose -f docker-compose.oidc.yml --dry-run pull`에서 Airflow build 산출물은 skip되며, 사내 registry DNS 미해결로 실제 registry image lookup은 실패한다.

## 위험과 대응
- 위험: 공통 `compose/airflow.yml`을 직접 바꾸면 dev가 사내 registry에 의존한다.
- 대응: OIDC/prod 전용 `compose/airflow.internal.yml`을 사용한다.
- 위험: Dockerfile base image를 사내 값으로 고정하면 dev build가 외부망에서 실패한다.
- 대응: Dockerfile 기본값은 public image로 두고 compose build args만 환경별로 지정한다.

## 진행 기록
- 2026-07-07: 사내 registry host를 `repository.samsungds.net`로 확정하고 변경 계획을 작성했다.
- 2026-07-07: OIDC/prod app/infra image와 Dockerfile base image args, 관련 문서를 갱신했다.
- 2026-07-07: dev/OIDC/prod compose config와 image/base image arg 검증을 통과했다.
- 2026-07-07: OIDC/prod Airflow build 산출물이 pull 대상이 되지 않도록 `pull_policy: never`를 추가했다.
- 2026-07-07: OIDC/prod Airflow compose 조각 이름을 `airflow.internal.yml`로 정리했다.
