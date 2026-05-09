# 전체 아키텍처

이 앱은 React SPA와 Django API가 한 저장소에 있는 모듈형 모놀리스입니다.

## 구성 요소

| 영역 | 경로 | 역할 |
| --- | --- | --- |
| Web | `apps/web` | React SPA |
| API | `apps/api` | Django API 서버 |
| Dummy 외부계 | `apps/adfs_dummy` | 로컬 ADFS/RAG/LLM/Mail/Jira 대체 서버 |
| Env | `env` | 개발/공통 환경 변수 |
| Proxy | `deploy/nginx` | 로컬 통합 진입점 |

## 백엔드 모듈

| Django app | 역할 |
| --- | --- |
| `api.auth` | OIDC 로그인/로그아웃/현재 사용자 |
| `api.account` | 소속, 권한, 사용자 pool |
| `api.emails` | 메일 수집/조회/이동/삭제/OCR/RAG Outbox |
| `api.assistant` | RAG 기반 채팅 |
| `api.rag` | 외부 RAG 서버 공통 client |
| `api.drone` | Line Dashboard와 Drone SOP 알림 |
| `api.timeline` | 별도 timeline DB 조회 |
| `api.appstore` | 내부 앱 등록/댓글/좋아요 |
| `api.voc` | VOC 게시판 |
| `api.activity` | ActivityLog 조회 |
| `api.health` | 헬스 체크 |
| `api.common` | 공통 middleware/helper/client |

## 프론트엔드 모듈

프론트엔드는 `apps/web/src/features/<feature>` 단위로 구성됩니다.

| Feature | 역할 |
| --- | --- |
| `auth` | 로그인, 온보딩, 소속 재확인 |
| `account` | 계정, 소속, 멤버/권한 |
| `emails` | 메일함과 메일 처리 |
| `assistant` | RAG 기반 채팅 |
| `line-dashboard` | Drone SOP/라인 대시보드 |
| `timeline` | 설비/로그 타임라인 |
| `appstore` | 내부 앱 공유 |
| `voc` | VOC 게시판 |
| `home`, `errors`, `teamstaff` | 공통/보조 화면 |

## 핵심 데이터 흐름

### 인증과 소속

1. 사용자가 OIDC로 로그인합니다.
2. `auth`가 `User`를 만들거나 갱신합니다.
3. `account`가 현재 소속과 접근 가능한 `user_sdwt_prod`를 계산합니다.
4. Emails, Assistant, Drone은 이 접근 범위를 재사용합니다.

### 메일과 RAG

1. Emails가 POP3에서 메일을 수집합니다.
2. 발신자와 소속을 기준으로 메일함을 분류합니다.
3. RAG 등록/삭제가 필요하면 `EmailOutbox`에 작업을 쌓습니다.
4. Outbox 처리기가 외부 RAG 서버를 호출합니다.
5. Assistant는 RAG 검색 결과를 LLM에 전달해 답변합니다.

### Drone SOP 알림

1. Drone이 SOP 메일을 수집합니다.
2. 대상 소속과 전송 필요 여부를 계산합니다.
3. Jira, Messenger, Mail 채널별로 전송합니다.
4. 채널별 성공/실패 상태를 저장합니다.

## 경계 규칙

- 프론트 feature 외부 공개는 `features/<feature>/index.js`를 통합니다.
- 백엔드 view는 HTTP 처리만 맡고, 비즈니스 로직은 service/selector에 둡니다.
- 다른 백엔드 feature를 직접 파고드는 import는 피하고 selector 또는 service facade를 사용합니다.
- 외부 시스템 URL과 인증값은 환경 변수로 관리합니다.
