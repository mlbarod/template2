# 앱 문서 홈

이 `docs` 폴더는 코드를 열지 않아도 앱의 기능, 외부 요청 방식, 권한 정책, 운영 방법을 이해할 수 있게 정리한 문서입니다.

## 문서 지도

| 문서 | 설명 |
| --- | --- |
| `docs/architecture.md` | 전체 구조와 모듈 경계 |
| `docs/api/README.md` | API 공통 호출 규칙 |
| `docs/api/*.md` | 모듈별 외부 요청 계약 |
| `docs/modules/*.md` | 모듈별 기능, 권한, 동작 흐름 |
| `docs/operations.md` | 로컬 실행, 테스트, management command |
| `docs/integrations.md` | ADFS, RAG, LLM, Mail, Jira, MinIO 연동 |

## 먼저 읽을 순서

1. 전체 앱 구조를 보려면 `docs/architecture.md`
2. API 호출 규칙을 보려면 `docs/api/README.md`
3. 계정/소속/권한 정책을 보려면 `docs/modules/account.md`
4. 외부 시스템 연동을 보려면 `docs/integrations.md`
5. 실행과 운영 명령을 보려면 `docs/operations.md`

## 모듈 목록

| 모듈 | 기능 문서 | API 문서 |
| --- | --- | --- |
| Auth | `docs/modules/auth.md` | `docs/api/auth.md` |
| Account | `docs/modules/account.md` | `docs/api/account.md` |
| Emails | `docs/modules/emails.md` | `docs/api/emails.md` |
| Assistant/RAG | `docs/modules/assistant.md` | `docs/api/assistant.md` |
| Line Dashboard/Drone | `docs/modules/line-dashboard.md` | `docs/api/line-dashboard.md` |
| Timeline | `docs/modules/timeline.md` | `docs/api/timeline.md` |
| AppStore | `docs/modules/appstore.md` | `docs/api/appstore.md` |
| VOC | `docs/modules/voc.md` | `docs/api/voc.md` |
| Activity/Health | `docs/modules/activity-health.md` | `docs/api/activity-health.md` |

## 문서 작성 원칙

- API 문서는 외부 호출자가 알아야 할 method, path, auth, body, response, error를 우선합니다.
- 모듈 문서는 기능 목적, 권한, 상태, 동작 흐름, 부작용을 우선합니다.
- 내부 파일 경로는 마지막 “관련 코드”에만 둡니다.
- 코드 동작과 다른 내용을 문서에 쓰지 않습니다.
