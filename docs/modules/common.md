# Common 모듈

Common은 여러 백엔드 모듈에서 공유하는 helper, middleware, 외부 client facade를 제공합니다.

## 기능 요약

- JSON 요청 파싱
- Airflow Bearer token 검증
- ActivityLog metadata helper
- KnoxIdRequired middleware
- 안전한 raw SQL helper
- schema/table helper
- MinIO storage helper
- Knox Mail/Messenger client

## 사용 원칙

다른 모듈은 공통 기능을 직접 구현하지 않고 `api.common.services` facade를 통해 사용합니다.

## 대표 기능

| 기능 | 설명 |
| --- | --- |
| `parse_json_body` | JSON body 파싱 |
| `ensure_airflow_token` | Airflow trigger token 검증 |
| `set_activity_summary` | ActivityLog summary 주입 |
| `run_query`, `execute` | raw SQL 실행 |
| `sanitize_identifier` | 안전한 SQL 식별자 검증 |
| `upload_bytes`, `download_bytes` | MinIO 객체 처리 |
| `send_knox_mail_api` | Knox Mail API 호출 |
| `send_chat_message` | Knox Messenger 메시지 전송 |

## 관련 문서

- `docs/integrations.md`
- `docs/operations.md`

## 관련 코드

- `apps/api/api/common/services/__init__.py`
- `apps/api/api/common/services/request_helpers.py`
- `apps/api/api/common/services/activity_logging.py`
- `apps/api/api/common/services/middleware.py`
- `apps/api/api/common/services/db.py`
- `apps/api/api/common/services/schema.py`
- `apps/api/api/common/services/storage.py`
- `apps/api/api/common/services/mail_api.py`
- `apps/api/api/common/services/messenger.py`
