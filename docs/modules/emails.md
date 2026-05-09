# Emails 모듈

Emails는 메일 수집부터 조회, 이동/삭제, OCR, RAG 인덱싱까지 담당합니다.

## 기능 요약

- POP3 메일 수집
- 메일함 목록/요약/멤버 조회
- 받은 메일/보낸 메일 조회
- 메일 상세/HTML/asset 조회
- 미분류 메일 claim
- 메일 이동/삭제
- OCR 작업 처리
- RAG Outbox 처리

## 권한 기준

메일 접근은 Account가 계산한 `user_sdwt_prod` 접근 범위와 사용자의 `knox_id`를 사용합니다.

- 일반 사용자: 접근 가능한 소속 메일 또는 본인이 보낸 메일
- staff/superuser: 전체 접근
- `UNASSIGNED`: 기본적으로 privileged 사용자만 조회

## 메일 수집 흐름

1. Airflow 또는 scheduler가 수집 endpoint를 호출합니다.
2. POP3에서 메일을 가져옵니다.
3. 제목 제외 규칙을 적용합니다.
4. 발신자 기준으로 소속을 판단합니다.
5. `Email`을 저장합니다.
6. RAG 작업이 필요하면 `EmailOutbox`에 쌓습니다.

## RAG Outbox 흐름

메일 저장/이동/삭제는 RAG 서버를 즉시 호출하지 않고 Outbox에 작업을 쌓습니다.

- `INDEX`: RAG 문서 등록/갱신
- `DELETE`: RAG 문서 삭제
- `RECLASSIFY`: 재분류
- `RECLASSIFY_ALL`: 전체 재분류

## OCR 흐름

1. OCR worker가 claim endpoint로 작업을 가져갑니다.
2. OCR 처리 후 update endpoint로 결과를 저장합니다.
3. asset별 OCR 상태와 텍스트가 갱신됩니다.

## 부작용

- Email/EmailOutbox DB write
- MinIO asset read/write
- RAG insert/delete
- ActivityLog 기록

## 관련 API

- `docs/api/emails.md`

## 관련 코드

- `apps/api/api/emails/views.py`
- `apps/api/api/emails/models.py`
- `apps/api/api/emails/permissions.py`
- `apps/api/api/emails/selectors.py`
- `apps/api/api/emails/services/ingest.py`
- `apps/api/api/emails/services/mutations.py`
- `apps/api/api/emails/services/mailbox.py`
- `apps/api/api/emails/services/ocr.py`
- `apps/api/api/emails/services/rag.py`
- `apps/api/api/emails/services/storage.py`
- `apps/web/src/features/emails`
