# ExecPlan: PM Spider Feature Rename

## 목표
- PM SPIDER 프론트 feature 폴더, 사용자-facing 주소, 서버 API URL 계약을 `pm-spider` / `/pm_spider` 기준으로 정리한다.

## 현재 상태
- 프론트 feature는 `apps/web/src/features/pm-spider`로 이동했다.
- 사용자-facing route는 `/pm_spider`로 등록하고, 기존 `/pm-comparison` route alias는 제거했다.
- 백엔드 API prefix는 `/api/v1/pm_spider/`로 변경한다.
- Django app `api.pm_comparison`과 `PM_COMPARISON_*` env는 내부 모듈/데이터 설정 이름이므로 이번 요청 범위가 아니다.

## 범위
- 수정: PM SPIDER 프론트 feature 폴더명, route facade, router import, query key, app access id, branding key, API prefix, API client base path, 파일 경로 주석, docs inventory.
- 제외: Django app/module name, env group, 데이터 mount/env.

## 설계
- 신규 라우트는 `pm_spider`로 등록한다.
- 기존 `/pm-comparison` route alias는 제거한다.
- 서버 API prefix는 `/api/v1/pm_spider/`로 등록한다.
- public facade는 `@/features/pm-spider`에서 `pmSpiderRoutes`를 export한다.
- React Query key와 프론트 app/branding id는 `pm-spider`를 사용한다.

## 실행 단계
- [x] ExecPlan 작성
- [x] 프론트 라우트와 링크/prefix 수정
- [x] feature 폴더와 프론트 식별자 rename
- [x] 문서 inventory의 화면 주소 수정
- [x] 검색과 frontend boundary audit으로 확인

## 검증
- `rg -n "pm_spider|pm-spider|api/v1/pm_spider" apps/web apps/api docs/inventory.md`
- `scripts/agent/check_frontend_boundaries.sh`
- `npm run agent:audit:api-boundary`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.pm_comparison`
- `npm run agent:audit:ui`
- `docker compose -f docker-compose.dev.yml exec -T web npm run build`
- `npm run agent:audit:docs`

## 위험과 대응
- 위험: 기존 `/pm-comparison` 북마크 또는 로그인 `next` 값이 깨질 수 있다.
- 대응: 사용자-facing 주소를 `/pm_spider`로 단일화한다는 최신 요청을 우선한다.

## 진행 기록
- 2026-06-22: PM SPIDER 화면 주소 변경 요청을 받고 route/link/prefix 변경 범위를 정리했다.
- 2026-06-22: `/pm_spider` 라우트를 추가하고 기존 `/pm-comparison`은 redirect로 유지했다.
- 2026-06-22: 메뉴, 접근 로그 prefix, 브랜딩 prefix, inventory 문서를 `/pm_spider` 기준으로 갱신했다.
- 2026-06-22: frontend boundary audit, web container build, docs inventory audit가 통과했다.
- 2026-06-22: 추가 요청에 따라 프론트 feature 폴더를 `pm-spider`로 이동하고 facade/import/query key/app id/branding key를 `pm-spider` 기준으로 갱신했다.
- 2026-06-22: feature rename 이후 frontend boundary audit, UI consistency audit, web container build, docs inventory audit가 통과했다.
- 2026-06-23: 추가 요청에 따라 기존 `/pm-comparison` route alias를 제거하고 사용자-facing 주소를 `/pm_spider`로 단일화했다.
- 2026-06-23: 추가 요청에 따라 서버 API prefix와 프론트 API client를 `/api/v1/pm_spider/` 기준으로 정렬한다.
- 2026-06-23: `api.pm_comparison` 테스트, backend/frontend boundary audit, docs inventory audit가 통과했다. 기본 web build는 기존 `apps/web/dist` 권한 문제로 실패했지만 임시 outDir build는 통과했다.
