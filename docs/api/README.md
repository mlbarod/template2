# API 공통 호출 규칙

이 문서는 모든 API에 공통으로 적용되는 호출 규칙입니다. 모듈별 상세 endpoint는 같은 폴더의 `*.md` 문서를 봅니다.

## Base URL

로컬 개발 기본값:

```text
http://localhost:8000
```

업무 API prefix:

```text
/api/v1
```

예외:

```text
/auth/google/callback/
```

OIDC provider가 `form_post`로 호출하는 callback입니다.

## 인증 방식

| 방식 | 사용처 | 설명 |
| --- | --- | --- |
| Django session | 일반 웹 API | OIDC 로그인 후 브라우저 쿠키 기반 |
| Airflow Bearer token | 수집/동기화 trigger | `Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>` |
| Internal token | OCR worker | `X-Internal-Token: <EMAIL_OCR_INTERNAL_TOKEN>` |
| 공개 | health, 일부 조회 | 인증 없이 접근 가능 |

## API 문서 작성 단위

각 endpoint는 다음 항목을 확인할 수 있어야 합니다.

| 항목 | 설명 |
| --- | --- |
| Method/Path | 실제 `apps/api/api/<feature>/urls.py` 기준 경로 |
| Auth | Session, Bearer token, Internal token, 공개 여부 |
| Query/Body | 필수/선택 입력, `snake_case`/`camelCase` 호환 여부 |
| Response | 주요 field와 collection envelope |
| Error | 400/401/403/404/409/5xx 조건 |
| Side effect | DB write, 외부 호출, ActivityLog, RAG Outbox 같은 부작용 |

실제 endpoint 색인은 `docs/inventory.md`를 기준으로 확인합니다.

## 요청 형식

대부분의 write API는 JSON body를 사용합니다.

```http
Content-Type: application/json
```

프론트 호환을 위해 일부 API는 `snake_case`와 `camelCase`를 함께 허용합니다. 모듈별 문서에 별도 표기합니다.

## 응답 형식

기본 응답은 JSON입니다.

```json
{
  "results": []
}
```

파일/이미지 endpoint는 바이너리 또는 redirect를 반환할 수 있습니다.

목록 응답은 모듈별로 다음 중 하나를 사용합니다.

| 형태 | 예 |
| --- | --- |
| 단순 목록 | `{ "results": [] }` |
| 페이지 목록 | `{ "results": [], "page": 1, "page_size": 20, "count": 100 }` |
| 요약 포함 | `{ "results": [], "summary": {} }` |
| 단건 객체 | `{ "id": 1, ... }` |
| 파일/HTML | binary, redirect, HTML response |

## 공통 오류

| Status | 의미 |
| --- | --- |
| 400 | 잘못된 요청 body/query |
| 401 | 인증 필요 |
| 403 | 권한 없음 |
| 404 | 대상 없음 |
| 409 | 현재 상태와 맞지 않는 요청 |
| 500 | 서버 처리 실패 |
| 502 | 외부 연동 실패 |
| 503 | 필수 외부 연동 설정 누락 |

## Side effect 분류

| 분류 | 해당 모듈 |
| --- | --- |
| DB write | Account, Emails, Drone, AppStore, VOC |
| 외부 read/search | Assistant, Timeline, Drone |
| 외부 write/send | Emails RAG, Drone Jira/Mail/Messenger, Assistant LLM |
| 파일/asset | Emails, AppStore |
| ActivityLog | Account 일부 작업, Emails 이동/삭제, Drone table update, VOC |

## 모듈별 API 문서

- `docs/api/auth.md`
- `docs/api/account.md`
- `docs/api/emails.md`
- `docs/api/assistant.md`
- `docs/api/line-dashboard.md`
- `docs/api/l3-spider.md`
- `docs/api/timeline.md`
- `docs/api/appstore.md`
- `docs/api/voc.md`
- `docs/api/activity-health.md`
