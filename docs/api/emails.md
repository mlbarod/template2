# Emails API

Emails API는 메일함 조회, 메일 처리, POP3 수집, OCR, RAG Outbox 처리를 제공합니다.

## 호출자

- 브라우저 SPA
- Airflow 또는 scheduler
- OCR worker

## 인증

| API | 인증 |
| --- | --- |
| 일반 메일 조회/이동/삭제 | Django session |
| POP3 수집/Outbox 처리 | Airflow Bearer token |
| OCR claim/update | `X-Internal-Token` |

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/emails/inbox/` | 받은 메일 목록 |
| GET | `/api/v1/emails/sent/` | 보낸 메일 목록 |
| GET | `/api/v1/emails/mailboxes/` | 접근 가능한 메일함 |
| GET | `/api/v1/emails/mailboxes/summary/` | 메일함 접근 요약 |
| GET | `/api/v1/emails/mailboxes/members/` | 메일함 멤버 |
| GET | `/api/v1/emails/unassigned/` | 내 미분류 메일 수 |
| POST | `/api/v1/emails/unassigned/claim/` | 미분류 메일 가져오기 |
| POST | `/api/v1/emails/move/` | 메일 이동 |
| POST | `/api/v1/emails/bulk-delete/` | 메일 여러 건 삭제 |
| GET/DELETE | `/api/v1/emails/<email_id>/` | 메일 상세/삭제 |
| GET | `/api/v1/emails/<email_id>/html/` | HTML 본문 |
| GET | `/api/v1/emails/<email_id>/assets/<sequence>/` | 첨부/이미지 asset |
| POST | `/api/v1/emails/ingest/` | POP3 수집 |
| POST | `/api/v1/emails/outbox/process/` | RAG Outbox 처리 |
| POST | `/api/v1/emails/assets/ocr/claim/` | OCR 작업 claim |
| POST | `/api/v1/emails/assets/ocr/update/` | OCR 결과 update |

## 메일 목록 쿼리

```http
GET /api/v1/emails/inbox/?userSdwtProd=G-A&q=report&page=1&page_size=20
```

| Query | 설명 |
| --- | --- |
| `user_sdwt_prod`, `userSdwtProd` | 메일함 필터 |
| `q` | 검색어 |
| `sender` | 발신자 필터 |
| `recipient` | 수신자 필터 |
| `date_from`, `date_to` | 날짜/시간 필터 |
| `page`, `page_size` | 페이지네이션 |

## 메일 이동

```json
{
  "emailIds": [1, 2, 3],
  "targetUserSdwtProd": "G-B"
}
```

동작:

1. 원본 메일 접근 권한을 확인합니다.
2. 대상 소속 접근 권한을 확인합니다.
3. 메일 소속을 변경합니다.
4. RAG 재인덱싱 작업을 Outbox에 쌓습니다.

## POP3 수집

```http
POST /api/v1/emails/ingest/
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
```

동작:

1. POP3 mailbox에서 메일을 읽습니다.
2. 발신자 기준으로 소속을 분류합니다.
3. `Email`에 저장합니다.
4. 필요한 RAG 작업을 Outbox에 쌓습니다.

## OCR 작업

```http
POST /api/v1/emails/assets/ocr/claim/
X-Internal-Token: <EMAIL_OCR_INTERNAL_TOKEN>
```

```http
POST /api/v1/emails/assets/ocr/update/
X-Internal-Token: <EMAIL_OCR_INTERNAL_TOKEN>
```

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 query/body |
| 401 | 인증 필요 또는 token 오류 |
| 403 | 메일함/메일 접근 권한 없음 |
| 404 | 메일 또는 asset 없음 |
| 500 | 수집/저장 실패 |
| 502 | RAG/Mail 외부 호출 실패 |

## 관련 모듈 문서

- `docs/modules/emails.md`
