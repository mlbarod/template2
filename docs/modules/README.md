# 모듈 문서 색인

모듈 문서는 업무 관점에서 “무엇을 하는 기능인지”와 “어떤 코드/API/데이터와 연결되는지”를 설명합니다. 실제 route와 model 색인은 `docs/inventory.md`를 봅니다.

## 모듈별 추적표

| 모듈 | Frontend feature | Backend app | API 문서 | 주요 데이터/외부 연동 |
| --- | --- | --- | --- | --- |
| Auth | `apps/web/src/features/auth` | `api.auth`, `api.account` | `docs/api/auth.md` | OIDC/ADFS, Django session |
| Account | `apps/web/src/features/account` | `api.account` | `docs/api/account.md` | `User`, `Affiliation`, `UserSdwtProdAccess`, 외부 소속 snapshot |
| Emails | `apps/web/src/features/emails` | `api.emails` | `docs/api/emails.md` | `Email`, `EmailAsset`, `EmailOutbox`, POP3, RAG, MinIO |
| Assistant/RAG | `apps/web/src/features/assistant` | `api.assistant`, `api.rag` | `docs/api/assistant.md` | RAG, LLM, Account permission group |
| Line Dashboard/Drone | `apps/web/src/features/line-dashboard` | `api.drone` | `docs/api/line-dashboard.md` | `DroneSOP`, target/channel/recipient/delivery, Jira/Mail/Messenger |
| Observer | `apps/web/src/features/observer` | `api.observer` | `docs/api/observer.md` | 기본 DB 기준정보와 로그 |
| PM SPIDER | `apps/web/src/features/pm-spider` | `api.pm_comparison` | `docs/modules/pm-comparison-dashboard-spec.md` | PM SPIDER raw/result Parquet |
| AppStore | `apps/web/src/features/appstore` | `api.appstore` | `docs/api/appstore.md` | `AppStoreApp`, 댓글, 좋아요, cover image |
| VOC | `apps/web/src/features/voc` | `api.voc` | `docs/api/voc.md` | `VocPost`, `VocReply`, ActivityLog |
| Activity/Health | API only | `api.activity`, `api.health` | `docs/api/activity-health.md` | `ActivityLog`, runtime health |
| Common | shared | `api.common` | 공통 문서 | request helper, storage, mail, messenger, middleware |

## 각 모듈 문서의 필수 항목

- 기능 목적과 사용자가 보는 화면
- 주요 route와 endpoint
- 인증/권한 기준
- 핵심 데이터 모델 또는 외부 데이터 소스
- 주요 흐름과 side effect
- 운영/장애 확인 포인트
- 관련 코드 경로
