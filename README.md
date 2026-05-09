# Tailwind 프로젝트 안내

이 저장소는 React 웹앱과 Django API를 함께 관리하는 업무용 모듈형 모놀리스입니다. 화면은 `apps/web`, 서버 API는 `apps/api`, 로컬 개발용 더미 외부 시스템은 `apps/adfs_dummy`에 있습니다.

## 한눈에 보기

| 영역 | 경로 | 역할 |
| --- | --- | --- |
| Web | `apps/web` | React 19 + Vite SPA |
| API | `apps/api` | Django 5.1 API 서버 |
| Dummy 외부계 | `apps/adfs_dummy` | 로컬 ADFS/RAG/LLM/메일/Jira 대체 서버 |
| Docs | `docs` | 앱 전체 기능/API/운영/연동 문서 |
| Env | `env` | Docker Compose 환경 변수 |
| Proxy | `deploy/nginx` | 로컬 통합 진입점 |

## 로컬에서 실행하기

개발 환경은 Docker Compose 기준입니다.

```bash
docker compose -f docker-compose.dev.yml up -d
```

실행 후 주로 보는 주소는 다음과 같습니다.

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- 통합 진입점: `http://localhost`
- 더미 ADFS/RAG/LLM/메일/Jira: `http://localhost:9102`
- MinIO: `http://localhost:9000`, `http://localhost:9001`

## 자주 쓰는 명령

```bash
npm run web:dev
npm run web:build
npm run web:lint
docker compose -f docker-compose.dev.yml exec -T api python manage.py check
docker compose -f docker-compose.dev.yml exec -T api python manage.py test
docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run
```

## 주요 API 영역

모든 업무 API는 `/api/v1/` 아래에 있습니다. 예외적으로 OIDC 콜백만 `/auth/google/callback/`을 사용합니다.

| Prefix | 설명 |
| --- | --- |
| `/api/v1/auth/` | 로그인, 로그아웃, 현재 사용자 |
| `/api/v1/account/` | 소속, 접근 권한, 사용자 검색 |
| `/api/v1/emails/` | 메일함, 메일 조회/이동/삭제, OCR, RAG Outbox |
| `/api/v1/assistant/` | RAG 기반 채팅 |
| `/api/v1/line-dashboard/` | Drone SOP, 라인 대시보드, 알림 |
| `/api/v1/timeline/` | 라인/설비/로그 조회 |
| `/api/v1/appstore/` | 내부 앱 등록/댓글/좋아요 |
| `/api/v1/activity/` | 활동 로그 조회 |
| `/api/v1/voc/` | VOC 게시글/답변 |
| `/api/v1/health/` | 서버 상태 확인 |

## 문서 읽는 순서

1. 전체 구조는 이 파일을 봅니다.
2. 백엔드 실행/설정은 `apps/api/README.md`를 봅니다.
3. 프론트엔드 실행/구조는 `apps/web/README.md`를 봅니다.
4. API 공통 규칙은 `docs/api/README.md`, 모듈별 호출 방식은 `docs/api/*.md`를 봅니다.
5. 소속/권한 정책은 `docs/modules/account.md`를 봅니다.

## 작업할 때 지켜야 할 큰 원칙

- 프론트엔드는 feature 외부에서 `apps/web/src/features/<feature>/index.js`만 import합니다.
- 백엔드는 다른 feature를 직접 파고들지 않고 selector 또는 service facade를 통해 의존합니다.
- 서버 데이터는 React Query가 기준이고, Zustand에는 UI 상태만 둡니다.
- 인증/RAG/assistant/mail 계약을 바꾸면 `docker-compose.dev.yml`, `env/api.dev.env`, `apps/adfs_dummy`도 함께 맞춥니다.
