# 환경 설정

환경 변수는 `env/` 아래에 모여 있습니다. 외부 시스템 URL, token, credential은 코드에 하드코딩하지 않고 env로 주입합니다.

## 파일별 역할

| 파일 | 사용처 | 역할 |
| --- | --- | --- |
| `env/api.common.env` | API 공통 | DB, 보안, auth, POP3, Drone, RAG, LLM, Mail API 기본값 |
| `env/api.dev.env` | 로컬 API | dummy ADFS/RAG/LLM/Mail/Jira 연결 |
| `env/api.oidc.dev.env` | OIDC 개발 API | 실제 OIDC/RAG 개발 연결용 override |
| `env/api.prod.env` | 운영 API | 운영 배포 템플릿 |
| `env/web.common.env` | Web 공통 | 모든 Web 환경에서 공유하는 브라우저 노출 설정 |
| `env/web.dev.env` | 로컬 Web | local browser/backend URL |
| `env/web.oidc.dev.env` | OIDC 개발 Web | nginx 경유 OIDC 개발 URL |
| `env/web.prod.env` | 운영 Web | 운영 site/backend URL |
| `env/minio.env` | MinIO | local MinIO 계정과 endpoint |
| `env/grafana.env` | Grafana | 모니터링 콘솔 관리자 계정과 기본 보안 설정 |

## 환경별 dependency source 정책

이 repo의 실행 환경은 dependency source 기준으로 아래처럼 나눕니다.

| 환경 | 실행 명령 | 용도 | Docker image | package manager |
| --- | --- | --- | --- | --- |
| `dev` | `make dev` | 로컬 개발 전용 | public registry | public source |
| `oidc` | `make oidc` | 사내 OIDC 검증/스테이징 | internal mirror | internal mirror |
| `prod` | `make prod` | 운영 compose 조립 | internal mirror | internal mirror |

`dev`는 로컬 PC에서만 사용하는 개발 환경입니다.
내부 mirror 주소인 `repository.samsungds.net`에 의존하지 않습니다.
`oidc`와 `prod`는 외부 public 저장소를 직접 사용하지 않고 내부 mirror를 사용합니다.

## Env / Compose 관리 원칙

- 공통 기본값은 `*.common.env`에 두고, dev/OIDC/prod 차이는 환경별 env 파일에만 둡니다.
- `VITE_*` 값은 브라우저 번들에 포함될 수 있으므로 secret을 넣지 않습니다.
- 운영 Web의 `VITE_*` build arg는 빌드 시점 값입니다. `env_file` 변경만으로 이미 빌드된 정적 번들이 바뀌지 않습니다.
- 서비스 고유 infra 설정은 `env/minio.env`, `env/grafana.env`처럼 서비스별 env 파일에 둡니다.
- Compose 계층은 app과 infra를 분리합니다. 앱 컨테이너는 `compose/*.app.yml`, 운영 보조 서비스는 `compose/*.infra.yml` 또는 infra에서 include하는 파일에 둡니다.
- Airflow Compose 공통 env에는 Airflow runtime과 DAG 공통 연결/인증 값만 둡니다. DAG별 schedule/timeout/limit/dry-run 기본값은 각 DAG 코드에 둡니다.
- OIDC 개발과 운영 Compose에서 외부 registry image를 pull할 때는 `repository.samsungds.net` 사내 registry를 사용합니다. Docker Hub image는 `repository.samsungds.net/proxy-docker-registry-1.docker.io/<image>` 형식으로 적습니다.
- OIDC 개발과 운영 Compose의 Docker build는 사내 package mirror build args를 사용합니다. Debian apt는 `http://repository.samsungds.net/repository/proxy-apt-mirror.kakao.com-debian`의 `bullseye main`, 일반 pip는 `http://repository.samsungds.net/repository/proxy-pypi-files.pythonhosted.org/simple`, npm은 `http://repository.samsungds.net/repository/proxy-npm-registry.npmjs.org`, Alpine은 `http://repository.samsungds.net/repository/proxy-raw-dl-cdn.alpinelinux.org-alpine`을 사용합니다.
- OIDC/prod Airflow 이미지는 `bigdataquery` Python 패키지를 빌드 시 설치합니다. 신규 PyPI mirror 적재 전까지 `PIP_EXTRA_INDEX_URL`에 기존 `repo.samsungds.net` PyPI simple URL을 임시로 고정해 함께 참조합니다.
- Airflow 공식 `apache/airflow:2.11.0` 이미지는 Debian bookworm 기반이므로 OIDC/prod Airflow Dockerfile은 같은 Debian mirror의 `bookworm main`을 사용합니다.
- OIDC/prod Airflow 이미지는 BigDataQuery용 Cloudera Impala ODBC 드라이버를 빌드 시 설치합니다. apt/pip source는 위 repo 표준 mirror를 사용하고, ODBC 드라이버 `.deb`는 승인된 사내 artifact URL을 `BIGDATAQUERY_ODBC_DEB_URL` build arg에 고정합니다. 이 예외는 dev Compose에서 사용하지 않는 versioned driver artifact에만 허용합니다.
- Airflow ODBC 설정 파일은 repo에 저장하지 않습니다. 운영에서 `airflow/odbc/odbc.ini`, `airflow/odbc/odbcinst.ini`를 제공하면 Compose가 `/usr/local/odbc`에 read-only로 mount합니다.
- dev Compose는 Dockerfile의 public 기본값과 public package source를 유지합니다.
- torch 전용 wheel index가 필요한 Docker build를 추가할 때는 `http://repository.samsungds.net/repository/proxy-pypi-download.pytorch.org-whl/simple`과 trusted host `repository.samsungds.net`를 별도 pip 설정으로 사용합니다.
- password/token/key/secret 값은 실제 운영에서는 배포 secret manager나 외부 env injection으로 관리합니다. repo env 파일에는 로컬/템플릿 값만 둡니다.
- env/Compose 변경 후 `bash scripts/agent/check_compose_configs.sh`로 dev/OIDC/prod Compose 병합 결과를 확인합니다.

현재 Compose와 Docker build에서 사용하는 사내 mirror 매핑은 아래 항목으로 제한합니다.
전체 proxy mirror catalog는 `docs/integrations/proxy-mirrors.md`를 봅니다.

| type | public | mirror | repo 적용 형식 |
| --- | --- | --- | --- |
| `docker` | `https://registry-1.docker.io/` | `proxy-docker-registry-1.docker.io` | `repository.samsungds.net/proxy-docker-registry-1.docker.io/<image>` |
| `docker` | `https://gcr.io` | `proxy-docker-gcr.io` | `repository.samsungds.net/proxy-docker-gcr.io/<image>` |
| `apt` | `http://mirror.kakao.com/debian/` | `proxy-apt-mirror.kakao.com-debian` | `http://repository.samsungds.net/repository/proxy-apt-mirror.kakao.com-debian` |
| `raw` | `https://dl-cdn.alpinelinux.org/alpine` | `proxy-raw-dl-cdn.alpinelinux.org-alpine` | `http://repository.samsungds.net/repository/proxy-raw-dl-cdn.alpinelinux.org-alpine` |
| `npm` | `https://registry.npmjs.org` | `proxy-npm-registry.npmjs.org` | `http://repository.samsungds.net/repository/proxy-npm-registry.npmjs.org` |
| `pypi` | `https://files.pythonhosted.org` | `proxy-pypi-files.pythonhosted.org` | `http://repository.samsungds.net/repository/proxy-pypi-files.pythonhosted.org/simple` |
| `pypi` | `https://download.pytorch.org/whl/` | `proxy-pypi-download.pytorch.org-whl` | `http://repository.samsungds.net/repository/proxy-pypi-download.pytorch.org-whl/simple` |

## 주요 설정 그룹

| 그룹 | 대표 변수 | 설명 |
| --- | --- | --- |
| `DJANGO_*` / Django runtime | `ENVIRONMENT`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_TIME_ZONE` | API 실행 모드와 기본 Django 설정 |
| 보안/proxy | `DJANGO_SECURE`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `USE_X_FORWARDED_HOST` | HTTPS, cookie, reverse proxy 설정 |
| `DJANGO_DB_*` / 기본 DB | `DJANGO_DB_ENGINE`, `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT` | Django 기본 PostgreSQL |
| Dev auto affiliation | `DEV_AUTO_AFFILIATION_ALLOWED`, `DEV_AUTO_AFFILIATION_PREFIX` | 소속 없는 로컬 dev 로그인 사용자의 기본 개발 소속 보장 |
| Observer 설정 | `OBSERVER_QUERY_DAYS` | Observer 로그 기본 조회 기간 |
| RACB report URL | `RACB_REPORT_BASE_URL` | RACB 로그 상세 팝업 URL 생성 기준 |
| `L3_SPIDER_*` / L3 Spider 파일 데이터/메일 | `L3_SPIDER_DATA_ROOT`, `L3_SPIDER_MAX_CHART_POINTS_PER_PANEL`, `L3_SPIDER_MAIL_SENDER`, `L3_SPIDER_MAIL_TARGET_URL` | read-only mount된 `daily_anomaly` Parquet 데이터 경로, 차트 sampling 제한, L3 Spider 알림 메일 발신자와 메일 본문 이동 링크 |
| `FDC_HARD_SPEC_*` / FDC Trend 추천 데이터 | `FDC_HARD_SPEC_DATA_ROOT`, `FDC_HARD_SPEC_PRIORITY_PATH`, `FDC_HARD_SPEC_UNIT_MODEL_PATH`, `FDC_HARD_SPEC_HARD_LIMIT_PATH` | FDC Hard Limit 추천 Parquet 데이터 경로 |
| `PM_COMPARISON_*` / PM SPIDER 파일 데이터 | `PM_COMPARISON_DATA_ROOT`, `PM_COMPARISON_DATA_HOST_PATH`, `PM_COMPARISON_MAX_FILES`, `PM_COMPARISON_MAX_META_DIRS` | PM SPIDER raw/score Parquet 데이터의 host mount와 컨테이너 내부 경로, scan 제한 |
| 외부 앱 사용량 API | `EXTERNAL_APP_USAGE_API_URLS`, `EXTERNAL_APP_USAGE_API_TIMEOUT_SECONDS` | 앱별 접속현황에서 저장 없이 조회 시점에 합산하는 외부 사용량 API source 목록(JSON)과 timeout |
| `DATA_MOVEMENT_*` / 파일 적재 데이터 | `DATA_MOVEMENT_HOST_PATH`, `DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS`, `DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS`, `DATA_MOVEMENT_M_TKIN_PREVENT_DIR`, `DATA_MOVEMENT_CTTTM_WORKORDER_LIST_DIR`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_DIR`, `DATA_MOVEMENT_EQP_STATUS_CHG_DIR`, `DATA_MOVEMENT_MI_TIP_UPDATE_HIST_DIR`, `DATA_MOVEMENT_RACB_LIST_DIR`, `DATA_MOVEMENT_MES_LINE_MAPPING_INFO_DIR`, `DATA_MOVEMENT_STATION_MASTER_DIR` | FTP 등으로 수신한 파일의 host mount와 테이블별 root 경로. 하위 `incoming/processing` 사용. 최근 수정 파일과 stat 값이 변하는 파일은 이번 적재에서 제외 |
| `FTP_*` / Data Movement FTP | `FTP_USER`, `FTP_PASS`, `FTP_PORT`, `FTP_PASV_ADDRESS`, `FTP_PASV_MIN_PORT`, `FTP_PASV_MAX_PORT` | `data_movement` 업로드용 FTP 계정, 접속 port, passive mode address/port |
| `OIDC_*` / `ADFS_*` / Auth/OIDC | `OIDC_CLIENT_ID`, `OIDC_ISSUER`, `ADFS_AUTH_URL`, `ADFS_LOGOUT_URL`, `OIDC_REDIRECT_URI`, `ADFS_CER_PATH`, `ALLOWED_REDIRECT_HOSTS` | ADFS/OIDC 로그인 |
| Airflow trigger | `AIRFLOW_TRIGGER_TOKEN` | 수집/동기화 trigger 보호용 Bearer token |
| Airflow DAG overrides | `L3_SPIDER_MAIL_TRIGGER_*`, `DATA_MOVEMENT_LOAD_*`, `DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_*` | 필요할 때만 외부 env injection으로 덮어쓰는 DAG별 schedule/timeout/limit/dry-run 옵션. 기본값은 각 DAG 코드에 둠 |
| Emails POP3/OCR | `EMAIL_POP3_*`, `EMAIL_OCR_INTERNAL_TOKEN`, `EMAIL_EXCLUDED_SUBJECT_PREFIXES` | 메일 수집과 OCR worker |
| Drone POP3/Jira/Mail/Messenger | `DRONE_*`, `KNOX_MESSENGER_*` | Drone SOP 수집과 채널별 전송 |
| Assistant/RAG/LLM | `ASSISTANT_*`, `RAG_*` | RAG 검색, RAG 문서 등록/삭제, LLM 답변 |
| OpenWebUI 요약 배치 | `OPENWEBUI_*` | `ct_process_comment` contents 요약 생성 |
| `MAIL_API_*` / Mail API | `MAIL_API_URL`, `MAIL_API_KEY`, `MAIL_API_SYSTEM_ID`, `MAIL_API_KNOX_ID` | 외부 Mail API 전송 |
| MinIO | `MINIO_*` | 메일 asset storage |
| `VITE_*` / Web | `VITE_BACKEND_URL`, `BACKEND_API_URL`, `VITE_ASSISTANT_API_URL`, `VITE_AIRFLOW_BASE_URL`, `VITE_SITE_URL` | 브라우저와 container 내부 API URL |
| `VITE_PORTAL_*` / Web | `VITE_PORTAL_PMX_URL`, `VITE_PORTAL_MOSAIC_URL`, `VITE_PORTAL_CONFLUENCE_URL` | Portal 전역 네비게이션 외부 링크. 비어 있으면 메뉴 또는 화면에서 숨김/안내 |
| Monitoring | `PROMETHEUS_RETENTION_TIME`, `GF_SECURITY_ADMIN_USER`, `GF_SECURITY_ADMIN_PASSWORD`, `GF_SERVER_ROOT_URL`, `GF_SERVER_SERVE_FROM_SUB_PATH` | Prometheus 보관 기간, Grafana 관리자 계정, nginx subpath 프록시 설정 |
| TTTM Spider | `TTTM_SPIDER_UPSTREAM` | nginx `/tttm-spider/` HTTPS 프록시가 전달할 내부 TTTM Spider host:port |

### Web 공통 환경 변수

- `env/web.common.env`는 dev/OIDC dev/prod Web 서비스가 공통으로 읽는 브라우저 노출 설정입니다.
- Vite의 `VITE_*` 값은 운영 정적 빌드 시점에 번들에 포함됩니다.

### 모니터링 스택

- 사내 OIDC/운영 인프라 Compose인 `compose/oidc.infra.yml`, `compose/prod.infra.yml`은 `compose/monitoring.yml`을 함께 include합니다.
- 포함 서비스는 `prometheus`, `node-exporter`, `cadvisor`, `grafana`입니다.
- Grafana는 host port를 직접 열지 않고 nginx의 `/grafana/` 경로 뒤에서만 접근합니다.
- nginx는 `/grafana/` 요청 전에 `/api/v1/auth/me`로 Django 세션 로그인 여부를 확인합니다. 미로그인 사용자는 `/api/v1/auth/login`으로 이동합니다.
- Prometheus는 외부 포트를 열지 않고 `shared-net` 내부에서 Grafana datasource로만 사용합니다.
- Prometheus 보관 기간은 `PROMETHEUS_RETENTION_TIME`으로 조정합니다. 기본값은 `15d`입니다.
- Grafana 기본 관리자 값은 `env/grafana.env`에 있습니다. 운영 보안 정책에 맞게 `GF_SECURITY_ADMIN_PASSWORD`를 관리합니다.
- 기본 dashboard `App Load Overview`는 host CPU/메모리/파일시스템/네트워크와 container별 CPU/메모리 추세를 표시합니다.
- endpoint별 API latency, HTTP status, Django DB query 추세는 아직 앱 내부 metric이 없으므로 별도 instrumentation을 추가해야 합니다.

### TTTM Spider 프록시

- 운영 nginx는 `/tttm-spider/` 경로를 `TTTM_SPIDER_UPSTREAM`으로 프록시합니다.
- 브라우저 iframe은 HTTP 원본 URL 대신 same-origin HTTPS 경로인 `/tttm-spider/`를 사용합니다.
- `TTTM_SPIDER_UPSTREAM` 값은 scheme 없이 `host:port` 형식으로 설정합니다. 기본값은 운영 compose의 nginx environment에 있습니다.
- TTTM Spider 원본 페이지가 내부 asset을 절대 HTTP URL로 렌더링하면 브라우저 mixed content가 남을 수 있으므로, 이 경우 원본 서비스 base URL 또는 nginx rewrite를 추가 조정해야 합니다.

### 외부 앱 사용량 API

- 여러 외부 사용량 API를 사용할 때는 `EXTERNAL_APP_USAGE_API_URLS`에 명시적 source 목록을 JSON 배열로 설정합니다.
- 예: `[{"sourceName":"m-etch-dx","url":"https://example.test/get/usage"},{"sourceName":"other-system","url":"https://other.example.test/get/usage"}]`
- 각 응답 row는 `date`, `appName`, `accessCount`를 사용하며, `appName`은 앞뒤 공백 제거 후 대문자로 정규화되어 앱 키와 표시명에 사용됩니다.
- `EXTERNAL_APP_USAGE_API_URLS=[]`이면 외부 API 조회를 비활성화합니다.

### L3 Spider 메일 링크 배포 체크

- 운영 서버 배포 또는 PR 리뷰 전 `env/api.common.env`의 `L3_SPIDER_MAIL_TARGET_URL`을 반드시 확인합니다.
- `L3_SPIDER_MAIL_TARGET_URL`은 메일 본문의 `L3 Spider에서 확인` 버튼과 이벤트별 `열기` deep link의 base URL입니다.
- 값은 `/l3_spider`까지 포함한 Web URL로 설정합니다. 예: `https://<운영-host>/l3_spider`
- 비워두면 backend는 `FRONTEND_BASE_URL + /l3_spider`를 사용합니다. 운영에서 `FRONTEND_BASE_URL`이 기대한 Web host인지 함께 확인합니다.

## 파일 데이터 마운트 규칙

API가 직접 읽는 업무 파일 데이터는 신규/변경 시 아래 규칙을 따릅니다.

| 항목 | 규칙 | 예시 |
| --- | --- | --- |
| 컨테이너 경로 | `api` 컨테이너 내부에서는 `/data/<domain>`을 사용합니다. `<domain>`은 lowercase snake_case로 작성합니다. | `/data/pm_spider`, `/data/l3_spider/daily_anomaly` |
| 호스트 경로 env | Compose bind mount의 host 경로는 `${<DOMAIN>_DATA_HOST_PATH:-../data/<domain>}` 형식으로 둡니다. | `${PM_COMPARISON_DATA_HOST_PATH:-../data/pm_spider}` |
| Django data root | Django 설정은 컨테이너 내부 경로를 `<DOMAIN>_DATA_ROOT`로 노출합니다. | `PM_COMPARISON_DATA_ROOT=/data/pm_spider` |
| 권한 | 원본/참조 데이터는 `:ro`로 read-only mount합니다. 앱이 생성/업로드/처리하는 큐성 데이터만 read-write를 허용합니다. | `:/data/pm_spider:ro` |
| 동기화 파일 | API 파일 마운트 변경 시 `compose/dev.app.yml`, `compose/oidc.app.yml`, `compose/prod.app.yml`, `env/api.common.env`, 이 문서를 함께 갱신합니다. | PM SPIDER 마운트 변경 |
| 예외 | DB data dir, `node_modules`, staticfiles, MinIO bucket 등 서비스 내부 상태는 named volume 또는 서비스 고유 경로를 유지할 수 있습니다. | `api_data:/data`, `web_node_modules:/app/node_modules` |

새 마운트에는 `/appdata` 컨테이너 경로를 추가하지 않습니다. 기존 `/appdata` 기반 경로는 해당 데이터 계약을 수정할 때 `/data/<domain>`으로 이동합니다.

PM SPIDER는 단일 `/data/pm_spider` mount 아래에서 `/data/pm_spider/data`와 `/data/pm_spider/result` 구조만 지원합니다.

## 로컬 개발 기본 흐름

1. `make dev`가 API, Web, dummy 외부계, MinIO, Nginx를 함께 띄웁니다.
2. API는 `env/api.common.env`와 `env/api.dev.env`를 사용합니다.
3. Web은 `env/web.dev.env`를 사용합니다.
4. ADFS/RAG/LLM/Mail/Jira 호출은 `apps/adfs_dummy`의 `http://adfs:9000` 또는 host 기준 `http://localhost:9102`로 연결됩니다.
5. `DEV_AUTO_AFFILIATION_ALLOWED=1`이면 소속 없는 로그인 사용자에게 `DEV_AUTO_AFFILIATION_PREFIX` 기반 기본 소속을 부여해 소속 선택 없이 다른 앱을 테스트할 수 있습니다.

## 운영/실제 연동 흐름

1. `env/api.prod.env` 또는 `env/api.oidc.dev.env`에서 실제 OIDC/RAG/Mail/Jira endpoint를 지정합니다.
2. `DJANGO_SECURE`, cookie secure, CSRF trusted origin, allowed host를 배포 도메인에 맞춥니다.
3. Web의 `VITE_BACKEND_URL`은 reverse proxy 구조에 맞춰 `/` 또는 API origin을 사용합니다.
4. 민감 값은 배포 secret manager나 별도 env injection으로 주입하고 문서/커밋에 반복 기재하지 않습니다.

## 변경 시 동기화 대상

- Auth 계약 변경: `env/api*.env`, `env/web*.env`, `apps/adfs_dummy`, `docs/integrations.md`, `docs/api/auth.md`
- RAG/LLM 계약 변경: `env/api*.env`, `apps/adfs_dummy`, `docs/integrations.md`, `docs/modules/assistant.md`, `docs/api/assistant.md`
- OpenWebUI 요약 계약 변경: `env/api*.env`, `apps/adfs_dummy`, `docs/integrations.md`, `docs/modules/observer.md`, `docs/api/observer.md`
- Mail/Email 계약 변경: `env/api*.env`, `apps/adfs_dummy`, `docs/modules/emails.md`, `docs/api/emails.md`
- Drone/Jira/Messenger 계약 변경: `env/api*.env`, `apps/adfs_dummy`, `docs/modules/line-dashboard.md`, `docs/api/line-dashboard.md`
- Observer 기준정보/로그 계약 변경: `env/api*.env`, `docs/modules/observer.md`, `docs/api/observer.md`, `docs/data-model.md`
- L3 Spider 데이터 경로 변경: `env/api*.env`, `docker-compose*.yml`, `compose/*.yml`, `docs/api/l3-spider.md`, `docs/inventory.md`
