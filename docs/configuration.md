# 환경 설정

환경 변수는 `env/`와 `minio.env`에 나뉘어 있습니다. 외부 시스템 URL, token, credential은 코드에 하드코딩하지 않고 env로 주입합니다.

## 파일별 역할

| 파일 | 사용처 | 역할 |
| --- | --- | --- |
| `env/api.common.env` | API 공통 | DB, 보안, auth, POP3, Drone, RAG, LLM, Mail API 기본값 |
| `env/api.dev.env` | 로컬 API | dummy ADFS/RAG/LLM/Mail/Jira 연결 |
| `env/api.oidc.dev.env` | OIDC 개발 API | 실제 OIDC/RAG 개발 연결용 override |
| `env/api.prod.env` | 운영 API | 운영 배포 템플릿 |
| `env/web.dev.env` | 로컬 Web | local browser/backend URL |
| `env/web.oidc.dev.env` | OIDC 개발 Web | nginx 경유 OIDC 개발 URL |
| `env/web.prod.env` | 운영 Web | 운영 site/backend URL |
| `minio.env` | MinIO | local MinIO 계정과 endpoint |

## 주요 설정 그룹

| 그룹 | 대표 변수 | 설명 |
| --- | --- | --- |
| `DJANGO_*` / Django runtime | `ENVIRONMENT`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_TIME_ZONE` | API 실행 모드와 기본 Django 설정 |
| 보안/proxy | `DJANGO_SECURE`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `USE_X_FORWARDED_HOST` | HTTPS, cookie, reverse proxy 설정 |
| `DJANGO_DB_*` / 기본 DB | `DJANGO_DB_ENGINE`, `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT` | Django 기본 PostgreSQL |
| `TIMELINE_DB_*` / Timeline DB | `TIMELINE_DB_ENGINE`, `TIMELINE_DB_NAME`, `TIMELINE_DB_USER`, `TIMELINE_DB_PASSWORD`, `TIMELINE_DB_HOST`, `TIMELINE_DB_PORT`, `TIMELINE_QUERY_DAYS` | Timeline 전용 PostgreSQL과 기본 조회 기간 |
| `L3_SPIDER_*` / L3 Spider 파일 데이터 | `L3_SPIDER_DATA_ROOT`, `L3_SPIDER_MAX_CHART_POINTS_PER_PANEL` | read-only mount된 `daily_anomaly` Parquet 데이터 경로와 차트 sampling 제한 |
| `OIDC_*` / `ADFS_*` / Auth/OIDC | `OIDC_CLIENT_ID`, `OIDC_ISSUER`, `ADFS_AUTH_URL`, `ADFS_LOGOUT_URL`, `OIDC_REDIRECT_URI`, `ADFS_CER_PATH`, `ALLOWED_REDIRECT_HOSTS` | ADFS/OIDC 로그인 |
| Airflow trigger | `AIRFLOW_TRIGGER_TOKEN` | 수집/동기화 trigger 보호용 Bearer token |
| Emails POP3/OCR | `EMAIL_POP3_*`, `EMAIL_OCR_INTERNAL_TOKEN`, `EMAIL_EXCLUDED_SUBJECT_PREFIXES` | 메일 수집과 OCR worker |
| Drone POP3/Jira/Mail/Messenger | `DRONE_*`, `KNOX_MESSENGER_*` | Drone SOP 수집과 채널별 전송 |
| Assistant/RAG/LLM | `ASSISTANT_*`, `RAG_*` | RAG 검색, RAG 문서 등록/삭제, LLM 답변 |
| `MAIL_API_*` / Mail API | `MAIL_API_URL`, `MAIL_API_KEY`, `MAIL_API_SYSTEM_ID`, `MAIL_API_KNOX_ID` | 외부 Mail API 전송 |
| MinIO | `MINIO_*` | 메일 asset storage |
| `VITE_*` / Web | `VITE_BACKEND_URL`, `BACKEND_API_URL`, `VITE_ASSISTANT_API_URL`, `VITE_AIRFLOW_BASE_URL`, `VITE_SITE_URL` | 브라우저와 container 내부 API URL |

## 로컬 개발 기본 흐름

1. `docker-compose.dev.yml`이 API, Web, dummy 외부계, MinIO, Nginx를 함께 띄웁니다.
2. API는 `env/api.common.env`와 `env/api.dev.env`를 사용합니다.
3. Web은 `env/web.dev.env`를 사용합니다.
4. ADFS/RAG/LLM/Mail/Jira 호출은 `apps/adfs_dummy`의 `http://adfs:9000` 또는 host 기준 `http://localhost:9102`로 연결됩니다.

## 운영/실제 연동 흐름

1. `env/api.prod.env` 또는 `env/api.oidc.dev.env`에서 실제 OIDC/RAG/Mail/Jira endpoint를 지정합니다.
2. `DJANGO_SECURE`, cookie secure, CSRF trusted origin, allowed host를 배포 도메인에 맞춥니다.
3. Web의 `VITE_BACKEND_URL`은 reverse proxy 구조에 맞춰 `/` 또는 API origin을 사용합니다.
4. 민감 값은 배포 secret manager나 별도 env injection으로 주입하고 문서/커밋에 반복 기재하지 않습니다.

## 변경 시 동기화 대상

- Auth 계약 변경: `env/api*.env`, `env/web*.env`, `apps/adfs_dummy`, `docs/integrations.md`, `docs/api/auth.md`
- RAG/LLM 계약 변경: `env/api*.env`, `apps/adfs_dummy`, `docs/integrations.md`, `docs/modules/assistant.md`, `docs/api/assistant.md`
- Mail/Email 계약 변경: `env/api*.env`, `apps/adfs_dummy`, `docs/modules/emails.md`, `docs/api/emails.md`
- Drone/Jira/Messenger 계약 변경: `env/api*.env`, `apps/adfs_dummy`, `docs/modules/line-dashboard.md`, `docs/api/line-dashboard.md`
- Timeline DB 계약 변경: `env/api*.env`, `docs/modules/timeline.md`, `docs/api/timeline.md`, `docs/data-model.md`
- L3 Spider 데이터 경로 변경: `env/api*.env`, `docker-compose*.yml`, `docs/api/l3-spider.md`, `docs/inventory.md`
