# ExecPlan: Dev Login Affiliation

> 2026-07-13 업데이트: 더미 데이터 refresh 요구사항이 다시 생겨 `dev-auto-seed-refresh.md` 계획으로 dev-only seed 흐름을 복구했다. 이 문서는 dev 자동 소속 분리 작업의 과거 결정 기록으로 유지한다.

## 목표
- 로컬 dev에서 로그인 후 소속 선택 없이 앱을 테스트할 수 있게 한다.
- dev 시작 시 더미데이터 seed/reset 흐름은 제거한다.
- OIDC 개발/운영 환경에서는 자동 소속 변경이 일어나지 않게 한다.

## 현재 상태
- 프론트는 `/auth/me`의 `user_sdwt_prod`가 비어 있으면 소속 선택 dialog를 표시한다.
- 로컬 dev는 `env/api.dev.env`를 사용하고, OIDC 개발/운영은 별도 env 파일을 사용한다.

## 범위
- 수정: auth/account service, dev compose entrypoint, dev env, 관련 문서와 tests.
- 수정하지 않음: DB schema/migration, frontend UI, 기존 개별 관리 command.

## 설계
- `/auth/me` 응답 직전에 dev 자동 소속 helper를 호출한다.
- helper는 `ENVIRONMENT=development`와 `DEV_AUTO_AFFILIATION_ALLOWED=1`일 때만 동작한다.
- 기본 소속 prefix는 `DEV_AUTO_AFFILIATION_PREFIX`로 제어한다.
- `seed_dev_data` 통합 command와 도메인별 dev seed service는 제거한다.
- `make dev`의 API entrypoint는 DB bootstrap, migrate, runserver만 수행한다.

## 실행 단계
- [x] dev 자동 소속 helper를 seed 코드에서 분리
- [x] 통합 dev seed command와 도메인별 dev seed service 제거
- [x] dev compose startup seed 호출 제거
- [x] env/docs/tests를 seed 없는 구조로 정리
- [x] Docker Compose `api` 컨테이너 기준 검증

## 검증
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint "" api python manage.py test api.auth --keepdb`
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint "" api python manage.py test api.management`
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint "" api python manage.py check`
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint "" api python -m compileall -q api/auth api/account api/management`

## 위험과 대응
- 위험: OIDC 개발/운영 사용자의 소속이 자동 변경됨
- 대응: `env/api.dev.env`에만 `DEV_AUTO_AFFILIATION_ALLOWED=1`을 둔다.
- 위험: seed 제거 후 dev 화면에 샘플 데이터가 없음
- 대응: 로그인/권한 진입만 자동 소속으로 보장하고, 업무 데이터는 실제 적재/개별 기능 흐름으로 확인한다.

## 진행 기록
- 2026-06-14: 통합 dev seed/reset 흐름을 제거하고 dev 자동 소속 보장만 유지하기로 정리했다.
