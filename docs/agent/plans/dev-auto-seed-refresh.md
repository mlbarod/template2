# ExecPlan: dev auto seed refresh

## 목표
- `docker-compose.dev.yml` 실행 시 dev 환경에서만 더미 데이터를 결정적으로 refresh한다.
- refresh 시작 전에 `dummy.user`를 staff 슈퍼유저로 보장한다.
- OIDC/prod 환경에서는 새 seed 경로가 절대 실행되지 않도록 env guard를 둔다.

## 현재 상태
- dev API entrypoint는 `ensure_dev_database`, `migrate`, `runserver`만 실행한다.
- `seed_dummy_emails`는 `ENVIRONMENT=development`가 필요하다.
- `seed_drone_dummy_data`는 `ENVIRONMENT=development`와 `DRONE_SEED_ALLOWED=1`이 필요하다.
- `dummy.user` 슈퍼유저 보정은 account `post_migrate` 로직에 있다.

## 범위
- 수정할 영역: account dev user 보장 함수 분리, 통합 dev seed command, dev env/compose entrypoint, 문서와 테스트.
- 수정하지 않을 영역: prod/oidc compose, DB schema/migration, 실제 OIDC callback contract, dummy FastAPI endpoint.

## 설계
- `api.account.services.ensure_dev_dummy_superuser`를 공통 함수로 제공하고 `ENVIRONMENT=development`를 요구한다.
- `seed_dev_data` management command를 추가하고 `ENVIRONMENT=development`를 요구한다.
- command는 dummy user 보장 후 기존 seed command들을 prefix 기반 `--reset`으로 호출한다.
- dev entrypoint는 `DEV_AUTO_SEED=1`일 때만 `seed_dev_data --reset`을 실행한다.
- `env/api.dev.env`에만 `DEV_AUTO_SEED`, `DEV_SEED_PREFIX`를 둔다.

## 실행 단계
- [x] account dev user 보장 로직을 service 함수로 분리한다.
- [x] `seed_dev_data` command와 테스트를 추가한다.
- [x] `env/api.dev.env`, `compose/dev.app.yml`, docs를 동기화한다.
- [x] 컨테이너 기준 테스트와 backend boundary audit를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python -m py_compile ...`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account.tests.AccountConfigDefaultUserTests api.management.tests --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_dev_data --reset --skip-rag --prefix DEV`
- `npm run agent:audit:api-boundary`

## 위험과 대응
- 위험: prod/oidc에서 seed가 실행되어 데이터가 오염될 수 있다.
- 대응: dev compose/env에만 자동 호출을 추가하고 command 내부에서 `ENVIRONMENT=development`를 검증한다. 서버에서는 dev compose 실행 경로를 제거한다.
- 위험: refresh가 사용자가 직접 만든 데이터를 삭제할 수 있다.
- 대응: 기존 seed command의 prefix 기반 reset만 호출한다.

## 진행 기록
- 2026-07-13: dev-only 자동 seed refresh 설계를 확정하고 구현 시작.
- 2026-07-13: account dev user 보장 service, `seed_dev_data` command, dev entrypoint/env/docs를 추가.
- 2026-07-13: management/account 테스트, 실제 `seed_dev_data` smoke test, backend/docs audit, compose config 검증 통과.
- 2026-07-13: 사용자 요청에 따라 `DEV_DUMMY_SUPERUSER_ALLOWED`, `DEV_SEED_ALLOWED`를 제거하고 `DEV_AUTO_SEED`, `DEV_SEED_PREFIX` 중심으로 단순화.
