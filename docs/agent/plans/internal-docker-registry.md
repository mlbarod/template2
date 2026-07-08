# ExecPlan: internal Docker registry

## 목표
- OIDC 개발과 운영 Docker Compose 실행 시 외부 registry가 아니라 `repository.samsungds.net` 사내 registry 이미지를 사용한다.
- 외부 dev 실행은 기존 Docker Hub image 이름과 base image 기본값을 유지한다.
- OIDC 개발과 운영 Docker build 시 apt/pip/npm/Alpine package mirror도 사내 proxy를 사용한다.

## 현재 상태
- 실행 진입점은 `docker-compose.dev.yml`, `docker-compose.oidc.yml`, `docker-compose.yml`이다.
- `compose/dev.infra.yml`, `compose/oidc.infra.yml`, `compose/prod.infra.yml` 모두 공통 `compose/airflow.yml`을 include한다.
- `compose/prod.infra.yml`과 `compose/oidc.infra.yml`의 FTP image는 기존 사내 registry host를 사용한다.
- `compose/oidc.app.yml`, `compose/prod.app.yml`의 MinIO/Nginx image는 Docker Hub 이름이다.
- `apps/api/Dockerfile`, `apps/web/Dockerfile`의 base image는 public image 이름으로 고정되어 있다.
- Airflow는 code-server 제거 후 dev에서는 공식 `apache/airflow:2.11.0` 이미지를 직접 사용하고, OIDC/prod에서는 공식 이미지를 base로 하는 최소 Dockerfile로 내부 apt/pip mirror 설정을 주입한다.

## 범위
- 수정할 영역: OIDC/prod compose image 이름, OIDC/prod build args, Dockerfile base image args, registry 문서, Airflow image 참조.
- 수정하지 않을 영역: dev compose image 이름, 앱 런타임 env contract, DB schema, auth/OIDC/RAG/Mail contract.

## 설계
- Docker Hub image는 사내 환경에서 `repository.samsungds.net/proxy-docker-registry-1.docker.io/<image>` 형식으로 명시한다.
- `gcr.io` image는 사내 환경에서 `repository.samsungds.net/proxy-docker-gcr.io/<image>` 형식으로 명시한다.
- dev도 include하는 `compose/airflow.yml`은 그대로 두고, OIDC/prod용 `compose/airflow.internal.yml`을 별도로 둔다.
- `api`, `web` Dockerfile은 base image `ARG` 기본값을 public image로 유지하고, OIDC/prod compose에서만 사내 image 값을 넘긴다.
- Airflow는 dev에서 `apache/airflow:2.11.0`를 직접 사용한다.
- Airflow는 OIDC/prod에서 `repository.samsungds.net/proxy-docker-registry-1.docker.io/apache/airflow:2.11.0`를 base image로 빌드하고, 빌드 결과는 `airflow:2.11.0-internal`로 사용한다.
- Airflow OIDC/prod 빌드에서는 BigDataQuery용 Cloudera Impala ODBC 드라이버를 선택 설치한다.
- Airflow ODBC DSN 파일은 repo에 저장하지 않고 `airflow/odbc` 디렉터리에 운영 파일을 배치해 `/usr/local/odbc`로 read-only mount한다.
- Airflow 단독 Compose는 `AIRFLOW_IMAGE` env로 public/mirror image를 선택하고 기본값은 `apache/airflow:2.11.0`이다.
- `api`, `web` Dockerfile의 apt/pip/npm/Alpine mirror 설정은 optional build arg로만 받는다.
- OIDC/prod compose에서만 사내 mirror build arg를 넘기고, dev compose는 public package source 기본값을 유지한다.
- Debian apt mirror는 `deb [arch=amd64] http://repository.samsungds.net/repository/proxy-apt-mirror.kakao.com-debian bullseye main` 형식으로 설정한다.
- Airflow 공식 `apache/airflow:2.11.0`는 Debian bookworm 기반이므로 Airflow Dockerfile은 `bookworm main` 형식으로 설정한다.
- 일반 pip mirror는 `http://repository.samsungds.net/repository/proxy-pypi-files.pythonhosted.org/simple`과 trusted host `repository.samsungds.net`를 사용한다.
- BigDataQuery ODBC 설치 시에도 apt/pip mirror는 repo 표준 값을 그대로 사용하고, 승인된 사내 드라이버 `.deb` URL은 OIDC/prod 전용 `BIGDATAQUERY_ODBC_DEB_URL` build arg에 고정한다.
- npm registry는 `http://repository.samsungds.net/repository/proxy-npm-registry.npmjs.org`, `strict-ssl=false`를 사용한다.
- Alpine mirror는 `http://repository.samsungds.net/repository/proxy-raw-dl-cdn.alpinelinux.org-alpine`를 사용한다.
- torch 전용 wheel index가 필요한 Docker build가 생기면 `http://repository.samsungds.net/repository/proxy-pypi-download.pytorch.org-whl/simple`을 별도 pip 설정으로 사용한다.
- 현재 repo에서 사용하는 mirror mapping은 `docs/configuration.md`의 표로 제한해 추적한다.
- public API, DB migration, auth contract 영향은 없다.

- [x] Dockerfile base image를 build arg로 분리한다.
- [x] OIDC/prod app compose image와 build args를 사내 registry 기준으로 바꾼다.
- [x] OIDC/prod infra compose가 사내 Airflow compose를 include하도록 바꾼다.
- [x] 사내 Airflow compose와 monitoring image를 사내 registry 기준으로 추가/수정한다.
- [x] 관련 문서를 `repository.samsungds.net` 기준으로 갱신한다.
- [x] compose config 검증을 실행한다.
- [x] apt/pip/npm/Alpine mirror build args를 Dockerfile에 추가한다.
- [x] OIDC/prod compose에 사내 package mirror build args를 연결한다.
- [x] package mirror 문서와 compose config 검증을 갱신한다.
- [x] Airflow code-server 커스텀 빌드를 제거한다.
- [x] OIDC/prod Airflow에 code-server 없는 최소 Dockerfile로 사내 apt/pip mirror 설정을 주입한다.
- [x] OIDC/prod Airflow에 BigDataQuery ODBC 드라이버 설치 옵션과 운영 제공 ODBC 설정 mount를 추가한다.

## 검증
- 통과: `bash scripts/agent/check_compose_configs.sh`
- 통과: `docker compose -f docker-compose.dev.yml config --images`
- 통과: `docker compose -f docker-compose.oidc.yml config --images`
- 통과: `docker compose -f docker-compose.yml config --images`
- 통과: `docker compose -f docker-compose.dev.yml config | rg -n "PYTHON_BASE_IMAGE|NODE_BASE_IMAGE|AIRFLOW_BASE_IMAGE|image:"`
- 통과: `docker compose -f docker-compose.oidc.yml config | rg -n "PYTHON_BASE_IMAGE|NODE_BASE_IMAGE|AIRFLOW_BASE_IMAGE|image:"`
- 통과: `docker compose -f docker-compose.yml config | rg -n "PYTHON_BASE_IMAGE|NODE_BASE_IMAGE|AIRFLOW_BASE_IMAGE|image:"`
- 통과: `docker compose -f docker-compose.dev.yml config | rg -n "APT_DEBIAN|PIP_INDEX_URL|PIP_TRUSTED_HOST|ALPINE_REPOSITORY_MIRROR|NPM_REGISTRY|NPM_STRICT_SSL|proxy-pypi|proxy-npm|proxy-raw|proxy-apt"` 결과 없음
- 통과: `docker compose -f docker-compose.oidc.yml config | rg -n "APT_DEBIAN|PIP_INDEX_URL|PIP_TRUSTED_HOST|ALPINE_REPOSITORY_MIRROR|NPM_REGISTRY|NPM_STRICT_SSL|proxy-pypi|proxy-npm|proxy-raw|proxy-apt"`
- 통과: `docker compose -f docker-compose.yml config | rg -n "APT_DEBIAN|PIP_INDEX_URL|PIP_TRUSTED_HOST|ALPINE_REPOSITORY_MIRROR|NPM_REGISTRY|NPM_STRICT_SSL|proxy-pypi|proxy-npm|proxy-raw|proxy-apt"`
- 확인: `docker compose -f docker-compose.oidc.yml config --format json`에서 Airflow build arg가 내부 base image, `APT_DEBIAN_CODENAME=bookworm`, 내부 pip mirror로 표시된다.
- 확인: `docker compose -f docker-compose.oidc.yml config --format json`에서 Airflow build arg가 `INSTALL_BIGDATAQUERY_ODBC=true`, 승인된 `BIGDATAQUERY_ODBC_DEB_URL` 고정 URL로 표시된다.

## 위험과 대응
- 위험: 공통 `compose/airflow.yml`을 직접 바꾸면 dev가 사내 registry에 의존한다.
- 대응: OIDC/prod 전용 `compose/airflow.internal.yml`을 사용한다.
- 위험: Dockerfile base image를 사내 값으로 고정하면 dev build가 외부망에서 실패한다.
- 대응: Dockerfile 기본값은 public image로 두고 compose build args만 환경별로 지정한다.
- 위험: ODBC DSN 파일을 repo에 두면 host, 계정, 인증 방식 같은 운영 연결 정보가 노출될 수 있다.
- 대응: repo에는 `airflow/odbc` 디렉터리만 유지하고 운영에서 `odbc.ini`, `odbcinst.ini`를 주입한다.

## 진행 기록
- 2026-07-07: 사내 registry host를 `repository.samsungds.net`로 확정하고 변경 계획을 작성했다.
- 2026-07-07: OIDC/prod app/infra image와 Dockerfile base image args, 관련 문서를 갱신했다.
- 2026-07-07: dev/OIDC/prod compose config와 image/base image arg 검증을 통과했다.
- 2026-07-07: OIDC/prod Airflow build 산출물이 pull 대상이 되지 않도록 `pull_policy: never`를 추가했다.
- 2026-07-07: OIDC/prod Airflow compose 조각 이름을 `airflow.internal.yml`로 정리했다.
- 2026-07-08: Docker Hub 사내 proxy 경로를 `repository.samsungds.net/proxy-docker-registry-1.docker.io/<image>` 형식으로 통일했다.
- 2026-07-08: apt/pip/npm/Alpine package mirror도 OIDC/prod build arg로 분리해 적용하기로 했다.
- 2026-07-08: OIDC/prod compose에 apt/pip/npm/Alpine package mirror build arg를 연결하고, dev compose는 public 기본값을 유지했다.
- 2026-07-08: `gcr.io` 사내 proxy 경로를 `repository.samsungds.net/proxy-docker-gcr.io/<image>` 형식으로 통일했다.
- 2026-07-08: 제공된 mirror mapping 중 현재 repo가 사용하는 항목만 `docs/configuration.md`에 표로 정리했다.
- 2026-07-08: Airflow code-server 커스텀 빌드를 제거했다.
- 2026-07-08: Airflow 단독 Compose도 `AIRFLOW_IMAGE` env 기반 registry image 직접 사용으로 바꿨다.
- 2026-07-08: OIDC/prod Airflow는 공식 이미지를 base로 하는 최소 Dockerfile을 다시 두고 내부 apt/pip mirror 설정을 주입하도록 정리했다.
- 2026-07-08: OIDC/prod Airflow에 BigDataQuery ODBC 드라이버 설치 옵션과 운영 제공 ODBC 설정 mount를 추가했다.
