# 외부 연동 계약

이 문서는 앱이 외부 시스템과 통신하는 방식을 정리합니다. 로컬 개발에서는 대부분 `apps/adfs_dummy`가 외부 시스템을 대체합니다.

## 연동 목록

| 연동 | 사용 모듈 | 로컬 대체 |
| --- | --- | --- |
| ADFS/OIDC | Auth | `apps/adfs_dummy` |
| RAG | Emails, Assistant | `apps/adfs_dummy` |
| LLM | Assistant | `apps/adfs_dummy` |
| Mail API | Emails, Drone | `apps/adfs_dummy` |
| Jira | Drone | `apps/adfs_dummy` |
| Knox Messenger | Drone/Common | 설정 기반 |
| MinIO | Emails/Common | `minio` service |
| Airflow | Account/Emails/Drone trigger | Bearer token |

## 참고 문서

| 문서 | 용도 |
| --- | --- |
| `docs/integrations/proxy-mirrors.md` | 외부 package repository public URL과 내부 proxy mirror 이름 매핑 |

## 로컬 dummy 외부계

`apps/adfs_dummy`는 로컬 개발에서 다음 역할을 대체합니다.

| 파일 | 역할 |
| --- | --- |
| `apps/adfs_dummy/adfs_oidc.py` | OIDC authorize/logout/callback 보조 |
| `apps/adfs_dummy/adfs_rag.py` | RAG search/insert/delete/index-info |
| `apps/adfs_dummy/adfs_llm.py` | LLM chat completions |
| `apps/adfs_dummy/adfs_mail.py` | Mail send와 dummy mail messages |
| `apps/adfs_dummy/adfs_jira.py` | Jira issue 대체 |
| `apps/adfs_dummy/adfs_stores.py` | dummy 저장소 |

## ADFS/OIDC

주요 설정:

- `OIDC_CLIENT_ID`
- `OIDC_ISSUER`
- `ADFS_AUTH_URL`
- `ADFS_LOGOUT_URL`
- `OIDC_REDIRECT_URI`
- `ADFS_CER_PATH`
- `ALLOWED_REDIRECT_HOSTS`

로컬 개발에서는 `http://localhost:9102`의 dummy ADFS를 사용합니다.

## RAG

사용 위치:

- Emails: 메일 문서 insert/delete
- Assistant: 질문 검색

주요 설정:

- `ASSISTANT_RAG_URL`, `RAG_SEARCH_URL`
- `ASSISTANT_RAG_INSERT_URL`, `RAG_INSERT_URL`
- `ASSISTANT_RAG_DELETE_URL`, `RAG_DELETE_URL`
- `RAG_INDEX_DEFAULT`, `RAG_INDEX_EMAILS`, `RAG_INDEX_LIST`
- `ASSISTANT_RAG_PERMISSION_GROUPS`, `RAG_PERMISSION_GROUPS`

## LLM

Assistant가 RAG 검색 결과를 LLM에 전달해 답변을 생성합니다.

주요 설정:

- `ASSISTANT_LLM_URL`
- `ASSISTANT_LLM_CREDENTIAL`
- `ASSISTANT_LLM_MODEL`
- `ASSISTANT_LLM_TEMPERATURE`
- `ASSISTANT_LLM_COMMON_HEADERS`
- `ASSISTANT_REQUEST_TIMEOUT`

## OpenWebUI 요약

`ct_process_comment` 요약 배치는 OpenWebUI의 OpenAI 호환 chat completions API를 호출해 `contents_text`를 요약합니다.

주요 설정:

- `OPENWEBUI_URL`
- `OPENWEBUI_API_TOKEN`
- `OPENWEBUI_MODEL`
- `OPENWEBUI_COMMON_HEADERS`
- `OPENWEBUI_TIMEOUT_SECONDS`
- `OPENWEBUI_SUMMARY_BATCH_SIZE`

## Mail API

Emails와 Drone이 Knox Mail API를 호출할 수 있습니다.

주요 설정:

- `MAIL_API_URL`
- `MAIL_API_KEY`
- `MAIL_API_SYSTEM_ID`
- `MAIL_API_KNOX_ID`
- `DRONE_MAIL_*`

## Jira

Drone SOP 알림에서 Jira issue 생성 또는 업데이트에 사용합니다.

주요 설정:

- `DRONE_JIRA_BASE_URL`
- `DRONE_JIRA_TOKEN`
- `DRONE_JIRA_ISSUE_TYPE`
- `DRONE_JIRA_USE_BULK_API`
- `DRONE_JIRA_BULK_SIZE`

## MinIO

메일 asset 저장/조회에 사용합니다.

주요 설정:

- `MINIO_ENDPOINT`
- `MINIO_BUCKET`
- `MINIO_REGION`
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`

## Airflow trigger

외부 scheduler가 호출하는 endpoint는 Bearer token으로 보호합니다.

```http
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
```

사용 예:

- 외부 소속 동기화
- Emails POP3 수집
- Emails Outbox 처리
- Drone SOP 수집/파이프라인

## 연동 변경 체크리스트

| 변경 | 함께 확인할 문서/파일 |
| --- | --- |
| OIDC provider 변경 | `env/api*.env`, `env/web*.env`, `apps/adfs_dummy/adfs_oidc.py`, `docs/api/auth.md` |
| RAG endpoint/schema 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_rag.py`, `docs/api/assistant.md`, `docs/modules/emails.md` |
| LLM request/response 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_llm.py`, `docs/modules/assistant.md` |
| OpenWebUI 요약 request/response 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_llm.py`, `docs/modules/observer.md`, `docs/api/observer.md` |
| Mail API 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_mail.py`, `docs/modules/emails.md`, `docs/modules/line-dashboard.md` |
| Jira 변경 | `env/api*.env`, `apps/adfs_dummy/adfs_jira.py`, `docs/modules/line-dashboard.md` |
| MinIO 변경 | `env/minio.env`, `docs/data-model.md`, `docs/modules/emails.md` |
| Airflow token/trigger 변경 | `env/api*.env`, 관련 `docs/api/*.md`, `docs/operations.md` |
