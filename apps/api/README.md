# Django API 안내

`apps/api`는 웹앱이 사용하는 Django API 서버입니다. 인증, 소속/권한, 메일, RAG/Assistant, Drone SOP, AppStore, VOC 같은 업무 API가 이 안에 있습니다.

## 실행하기

로컬 개발과 테스트는 Docker Compose의 `api` 컨테이너에서 실행하는 것을 기준으로 합니다.

```bash
docker compose -f docker-compose.dev.yml up -d api
docker compose -f docker-compose.dev.yml exec -T api python manage.py check
docker compose -f docker-compose.dev.yml exec -T api python manage.py test
```

마이그레이션 변경이 없어야 하는지 확인할 때:

```bash
docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run
```

컨테이너 없이 직접 실행해야 한다면:

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

## 설정 파일

| 파일 | 설명 |
| --- | --- |
| `env/api.common.env` | 공통 기본값 |
| `env/api.dev.env` | 로컬 개발 오버라이드 |
| `minio.env` | MinIO 접근 정보 |
| `docker-compose.dev.yml` | 개발용 API/Web/Dummy/MinIO/Nginx 조합 |

기본 데이터베이스는 PostgreSQL입니다. Django 기본 DB는 `DJANGO_DB_*`, 타임라인 전용 DB는 `TIMELINE_DB_*` 환경 변수를 사용합니다.

## 앱별 역할

| Django app | 역할 |
| --- | --- |
| `api.auth` | OIDC 로그인/로그아웃/현재 사용자 |
| `api.account` | 사용자 소속, 접근 권한, 사용자 pool |
| `api.emails` | 메일 수집/조회/이동/삭제/OCR/RAG Outbox |
| `api.assistant` | RAG 검색과 LLM 답변 생성 |
| `api.rag` | RAG 서버 호출 공통 client |
| `api.drone` | Line Dashboard와 Drone SOP 알림 파이프라인 |
| `api.timeline` | 별도 timeline DB 조회 |
| `api.appstore` | 내부 앱 등록, 댓글, 좋아요 |
| `api.activity` | ActivityLog 조회 |
| `api.voc` | VOC 게시글/답변 |
| `api.common` | 공통 middleware, DB, storage, mail, messenger helper |
| `api.health` | health check |

## 자주 쓰는 관리 명령

```bash
python manage.py seed_dummy_emails
python manage.py process_email_outbox
python manage.py seed_drone_dummy_data
```

## 더 읽을 문서

- 전체 구조: `docs/architecture.md`
- API 공통 규칙: `docs/api/README.md`
- 모듈별 API 계약: `docs/api/*.md`
- 모듈별 기능/동작: `docs/modules/*.md`
- 운영/외부 연동: `docs/operations.md`, `docs/integrations.md`
