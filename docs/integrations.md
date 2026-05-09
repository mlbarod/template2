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
