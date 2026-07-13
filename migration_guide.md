# Migration Guide

## 목적

서버 적용 시 DB migration 이후 현재 활성 사용자에게 Portal과 활성 앱 접근 권한을 수동으로 1회 부여한다.

이 절차는 Django migration 안에서 자동 실행하지 않는다. 운영자가 migration 완료 후 명시적으로 실행한다.

## 적용 순서

### 1. DB migration 실행

```bash
docker compose -f docker-compose.yml exec -T api python manage.py migrate --noinput
```

개발 환경에서 확인할 때는 다음 명령을 사용한다.

```bash
docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate --noinput
```

### 2. 초기 권한 부여 예정 건수 확인

먼저 dry-run으로 대상 사용자 수, scope 수, 생성/수정 예정 건수를 확인한다.

```bash
docker compose -f docker-compose.yml exec -T api python manage.py grant_initial_access --dry-run
```

출력 예시는 다음과 같다.

```text
초기 접근 권한 부여 계획: users=2, scopes=14, create=27, update=0, dryRun=True
```

확인할 항목:

- `users`: 활성 사용자 수
- `scopes`: `portal`과 활성 앱 scope 수
- `create`: 새로 생성될 권한 수
- `update`: 기존 `pending/denied`를 변경할 수

기본 실행에서는 기존 `pending/denied`를 덮어쓰지 않으므로 일반적으로 `update=0`이어야 한다.

### 3. 초기 권한 부여 실행

dry-run 결과가 예상과 맞으면 실제 실행한다.

```bash
docker compose -f docker-compose.yml exec -T api python manage.py grant_initial_access
```

성공 시 다음 메시지가 출력된다.

```text
초기 접근 권한 부여를 완료했습니다.
```

## 실행 정책

`grant_initial_access`는 DB의 완료 marker 기준으로 실제 권한 부여를 최초 1회만 수행한다.

두 번째로 실행하면 다음처럼 건너뛴다.

```text
초기 접근 권한 부여가 이미 완료되어 건너뜁니다.
```

## 기존 권한 보존 정책

기본 실행은 누락된 권한만 생성한다.

- 생성 대상: 활성 사용자
- 생성 scope: `portal` + 활성 앱 전체
- 생성 상태: `allowed`
- 생성 role: `viewer`
- 보존 대상: 기존 `pending`, `denied`

즉, 기존에 수동으로 제한한 사용자의 권한은 기본 실행에서 풀리지 않는다.

## 강제 재실행

완료 marker 이후 다시 실행해야 하는 특별한 경우에만 `--force`를 사용한다.

```bash
docker compose -f docker-compose.yml exec -T api python manage.py grant_initial_access --force
```

기존 `pending/denied`까지 `allowed/viewer`로 바꿔야 하는 경우에만 `--overwrite-existing`을 함께 사용한다.

```bash
docker compose -f docker-compose.yml exec -T api python manage.py grant_initial_access --force --overwrite-existing
```

`--overwrite-existing`는 기존 제한을 해제할 수 있으므로 운영 승인 후 사용한다.

## Line Dashboard 알림 설정 권한

이번 변경 후 Line Dashboard 알림 설정은 operator 전용이 아니다.

- Line Dashboard 접근 권한이 있는 로그인 사용자는 알림 설정을 변경할 수 있다.
- `isOperator` 값은 화면 표시용으로 유지된다.
- 실제 변경 가능 여부는 `canManageRecipients` 기준으로 판단된다.

## 적용 후 확인

권한 부여 후 무결성 점검을 실행한다.

```bash
docker compose -f docker-compose.yml exec -T api python manage.py check_access_permission_integrity
```

필요하면 Django admin 또는 권한 관리 화면에서 사용자별 `portal`, 앱 scope 권한이 `allowed/viewer`로 생성됐는지 확인한다.
