# 백엔드 상세 구조

`apps/api`는 Django API 서버입니다. 업무 API는 `api.<feature>` app 단위로 나뉘며, global URLConf는 `apps/api/api/urls.py`입니다.

## 실행 단위

| 항목 | 값 |
| --- | --- |
| Framework | Django 5.1, Django REST Framework |
| 기본 API prefix | `/api/v1/` |
| Auth callback 예외 | `/auth/google/callback/` |
| 기본 DB | `DJANGO_DB_*` PostgreSQL |
| Timeline DB | `TIMELINE_DB_*` PostgreSQL |
| 로컬 실행 | `docker compose -f docker-compose.dev.yml up -d api` |

## App 구조

| App | 책임 | 주요 파일 |
| --- | --- | --- |
| `api.auth` | OIDC 인증, 로그인/로그아웃, 현재 사용자 | `views.py`, `callback_urls.py`, `services/oidc*.py` |
| `api.account` | 사용자, 소속, 접근 권한, 외부 소속 동기화 | `models.py`, `selectors.py`, `services/*.py`, `views.py` |
| `api.emails` | 메일함, 메일 수집, asset, OCR, RAG Outbox | `models.py`, `permissions.py`, `services/*.py`, `management/commands/*.py` |
| `api.assistant` | RAG 검색, LLM 호출, 답변 조립 | `services/chat.py`, `services/rag.py`, `services/llm.py` |
| `api.rag` | RAG 공통 client와 설정 | `services/client.py`, `services/config.py` |
| `api.drone` | Drone SOP 수집, 알림 대상, dispatch/delivery, 라인 대시보드 | `models.py`, `selectors.py`, `services/*.py`, `management/commands/*.py` |
| `api.timeline` | timeline 전용 DB 기준 정보/로그 조회 | `selectors.py`, `views.py` |
| `api.appstore` | 내부 앱, 댓글, 좋아요, cover | `models.py`, `services/*.py`, `views.py` |
| `api.voc` | VOC 게시글과 답변 | `models.py`, `services/posts.py`, `views.py` |
| `api.activity` | 사용자 활동 로그 조회 | `models.py`, `selectors.py`, `services/activity_logs.py` |
| `api.health` | health check | `services/health_status.py`, `views.py` |
| `api.common` | 공통 DB, storage, mail, messenger, request helper | `services/*.py` |

## 책임 분리

| 계층 | 책임 | 금지/주의 |
| --- | --- | --- |
| `urls.py` | 상대 route 선언 | 비즈니스 로직 금지 |
| `views.py` | 인증 확인, request 파싱, serializer/selector/service 호출, response 변환 | 복잡한 ORM 읽기/쓰기 직접 구현 금지 |
| `serializers.py` | 입력 검증, 출력 schema | 외부 호출/DB write 금지 |
| `selectors.py` | read-only ORM query, 외부 read-only DB 조회 | side effect 금지 |
| `services/` | 쓰기, transaction, 외부 호출, orchestration | HTTP request/response 객체 의존 최소화 |
| `models.py` | schema, 제약, 순수 domain helper | 외부 시스템 호출 금지 |
| `management/commands/` | 운영/개발 command entry | 다른 feature 내부 module 직접 우회 금지 |

## URL prefix

| Prefix | App | 문서 |
| --- | --- | --- |
| `/api/v1/auth/` | `api.auth` | `docs/api/auth.md` |
| `/api/v1/account/` | `api.account` | `docs/api/account.md` |
| `/api/v1/emails/` | `api.emails` | `docs/api/emails.md` |
| `/api/v1/assistant/` | `api.assistant` | `docs/api/assistant.md` |
| `/api/v1/line-dashboard/` | `api.drone` | `docs/api/line-dashboard.md` |
| `/api/v1/l3_spider/` | `api.l3_spider` | `docs/api/l3-spider.md` |
| `/api/v1/timeline/` | `api.timeline` | `docs/api/timeline.md` |
| `/api/v1/appstore/` | `api.appstore` | `docs/api/appstore.md` |
| `/api/v1/voc/` | `api.voc` | `docs/api/voc.md` |
| `/api/v1/activity/` | `api.activity` | `docs/api/activity-health.md` |
| `/api/v1/health/` | `api.health` | `docs/api/activity-health.md` |

## 인증과 권한 기준

| 방식 | 사용 위치 | 확인 값 |
| --- | --- | --- |
| Django session | 일반 브라우저 API | 로그인 session cookie |
| OIDC callback | `/auth/google/callback/` | provider `form_post` payload |
| Airflow Bearer token | 수집/동기화 trigger | `Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>` |
| Internal OCR token | OCR worker | `X-Internal-Token: <EMAIL_OCR_INTERNAL_TOKEN>` |
| 공개/조건부 공개 | health, 일부 조회성 API | endpoint별 문서 확인 |

## Management command

| Command | App | 실행 예 |
| --- | --- | --- |
| `seed_dummy_emails` | `api.emails` | `python manage.py seed_dummy_emails` |
| `process_email_outbox` | `api.emails` | `python manage.py process_email_outbox` |
| `seed_drone_dummy_data` | `api.drone` | `python manage.py seed_drone_dummy_data` |
| `seed_drone_affiliation_notifications` | `api.drone` | `python manage.py seed_drone_affiliation_notifications` |
| `prune_drone_sop` | `api.drone` | `python manage.py prune_drone_sop` |
| `purge_drone_sop` | `api.drone` | `python manage.py purge_drone_sop --dry-run` |

모든 backend command와 test는 Docker Compose `api` 컨테이너 기준으로 실행합니다.

## 변경 시 갱신해야 하는 문서

- route 추가/변경: `docs/inventory.md`, `docs/api/*.md`, `docs/modules/*.md`
- model/schema 변경: `docs/data-model.md`, 해당 `docs/modules/*.md`
- env contract 변경: `docs/configuration.md`, `docs/integrations.md`, 필요 시 `apps/adfs_dummy`
- command 추가/변경: `docs/inventory.md`, `docs/operations.md`
