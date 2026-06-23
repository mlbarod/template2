# ExecPlan: PM Spider Feature Rename

## 목표
- PM SPIDER 프론트 feature 폴더와 사용자-facing 주소를 `pm-spider` / `/pm_spider` 기준으로 정리한다.

## 현재 상태
- 프론트 feature는 `apps/web/src/features/pm-spider`로 이동했다.
- 사용자-facing route는 `/pm_spider`로 등록하고, 기존 `/pm-comparison`은 호환 redirect로 유지한다.
- 백엔드 API prefix `/api/v1/pm-comparison/`와 Django app `api.pm_comparison`은 서버 계약이므로 이번 요청 범위가 아니다.

## 범위
- 수정: PM SPIDER 프론트 feature 폴더명, route facade, router import, query key, app access id, branding key, 파일 경로 주석, docs inventory.
- 제외: Django API prefix, Django app/module name, env group, 데이터 mount/env.

## 설계
- 신규 라우트는 `pm_spider`로 등록한다.
- 기존 `/pm-comparison` 진입은 `/pm_spider`로 redirect해 기존 북마크와 로그인 `next` 값을 흡수한다.
- public facade는 `@/features/pm-spider`에서 `pmSpiderRoutes`를 export한다.
- React Query key와 프론트 app/branding id는 `pm-spider`를 사용한다.

## 실행 단계
- [x] ExecPlan 작성
- [x] 프론트 라우트와 링크/prefix 수정
- [x] feature 폴더와 프론트 식별자 rename
- [x] 문서 inventory의 화면 주소 수정
- [x] 검색과 frontend boundary audit으로 확인

## 검증
- `rg -n "PmComparison|pmComparison|@/features/pm-comparison|src/features/pm-comparison" apps/web docs/inventory.md`
- `scripts/agent/check_frontend_boundaries.sh`
- `npm run agent:audit:ui`
- `docker compose -f docker-compose.dev.yml exec -T web npm run build`
- `npm run agent:audit:docs`

## 위험과 대응
- 위험: 기존 `/pm-comparison` 북마크 또는 로그인 `next` 값이 깨질 수 있다.
- 대응: 기존 route를 redirect로 유지한다.

## 진행 기록
- 2026-06-22: PM SPIDER 화면 주소 변경 요청을 받고 route/link/prefix 변경 범위를 정리했다.
- 2026-06-22: `/pm_spider` 라우트를 추가하고 기존 `/pm-comparison`은 redirect로 유지했다.
- 2026-06-22: 메뉴, 접근 로그 prefix, 브랜딩 prefix, inventory 문서를 `/pm_spider` 기준으로 갱신했다.
- 2026-06-22: frontend boundary audit, web container build, docs inventory audit가 통과했다.
- 2026-06-22: 추가 요청에 따라 프론트 feature 폴더를 `pm-spider`로 이동하고 facade/import/query key/app id/branding key를 `pm-spider` 기준으로 갱신했다.
- 2026-06-22: feature rename 이후 frontend boundary audit, UI consistency audit, web container build, docs inventory audit가 통과했다.
