# ExecPlan: 초기 접근 권한 부여와 Line Dashboard 알림 권한 완화

## 목표
- 서버 적용 직후 현재 활성 사용자가 Portal과 활성 앱 접근에서 막히지 않게 한다.
- Line Dashboard 알림 설정 수정 권한을 operator 전용에서 Line Dashboard 접근 사용자 전체로 완화한다.
- 이후 권한 관리 화면에서 필요한 사용자/scope만 회수할 수 있게 유지한다.

## 현재 상태
- `api.common.permissions`는 `/api/v1/line-dashboard/...` 요청에 `app:line-dashboard` 접근 정책을 적용한다.
- `api.drone.selectors.user_can_manage_drone_sop_recipients()`는 현재 operator 사용자만 알림 설정 변경 가능으로 판단한다.
- `apps/web/src/features/line-dashboard/components/LineSettingsPage.jsx`는 `isGlobalOperator` 상태로 수신인/Jira/Target 설정 버튼을 제어한다.
- `apps/api/api/account/management/commands`에는 접근 권한 무결성 점검 command만 있고 초기 권한 부여 command는 없다.

## 범위
- 수정할 영역:
  - `apps/api/api/account/management/commands/grant_initial_access.py`
  - `apps/api/api/account/tests.py`
  - `apps/api/api/drone/selectors.py`
  - `apps/api/api/drone/tests.py`
  - `apps/web/src/features/line-dashboard/api/notificationRecipients.js`
  - `apps/web/src/features/line-dashboard/components/LineSettingsPage.jsx`
  - `apps/web/src/features/line-dashboard/components/cards/NotificationTargetCard.jsx`
  - `docs/operations.md`
- 수정하지 않을 영역:
  - DB schema와 migration
  - 공통 route access policy
  - Line Dashboard 외 도메인 권한 정책

## 설계
- 초기 권한 부여:
  - 대상 사용자: 기본 `is_active=True` 사용자
  - 대상 scope: `portal` + `scope_type=app`, `is_active=True`인 app scope
  - 기본 실행은 누락된 `UserAccess`만 `allowed/viewer`로 생성한다.
  - `--overwrite-existing` 옵션을 둬 기존 `pending/denied`를 명시적으로 `allowed/viewer`로 바꿀 수 있게 한다.
  - `--force` 옵션을 둬 완료 marker 이후에도 운영자가 명시적으로 재실행할 수 있게 한다.
  - `--dry-run`으로 생성/변경 예정 건수를 먼저 확인한다.
  - 변경 내역은 `AccessAuditLog(action=grant)`로 남긴다.
  - 완료 여부는 `AccessAuditLog` marker로 남겨 DB 기준 1회만 실제 실행한다.
  - API 컨테이너 시작 흐름에는 연결하지 않고 운영자가 `migrate` 이후 수동 실행한다.
- Line Dashboard 알림 설정:
  - 백엔드는 기존 `user_can_manage_drone_sop_recipients()`를 인증 사용자 기준으로 완화한다.
  - `/api/v1/line-dashboard/...`는 이미 Portal/App 접근 검사를 통과해야 하므로 익명/앱 미승인 사용자는 계속 차단된다.
  - 권한 context 응답은 기존 `isOperator`를 유지하고 새 `canManageRecipients`를 추가한다.
  - 프론트는 `isOperator` 대신 `canManageRecipients`로 설정 변경 가능 여부를 계산한다.

## 실행 단계
- [x] 초기 권한 부여 management command 추가
- [x] account command 테스트 추가
- [x] Drone selector 권한 완화
- [x] Line Dashboard API wrapper와 설정 화면 권한 상태 변경
- [x] Drone 권한 테스트 갱신
- [x] 수동 post-migrate 실행 방식으로 운영 문서 정리
- [x] 정적 감사와 가능한 런타임 검증 실행

## 검증
- `python3 -m py_compile apps/api/api/account/management/commands/grant_initial_access.py apps/api/api/account/tests.py`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py grant_initial_access --dry-run`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `git diff --check`
- 가능하면:
  - `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account.tests.AccountEndpointTests.test_grant_initial_access_command_grants_portal_and_active_apps api.account.tests.AccountEndpointTests.test_grant_initial_access_command_preserves_existing_decisions_by_default api.account.tests.AccountEndpointTests.test_grant_initial_access_command_can_overwrite_existing_decisions --keepdb`
  - `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone.tests.DroneSopTargetRecipientTests api.drone.tests.DroneJiraKeyEndpointTests --keepdb`

## 위험과 대응
- 위험: 테스트 DB에 `pg_trgm` 확장이 없어 `gin_trgm_ops` migration 단계에서 테스트가 중단될 수 있다.
- 대응: 정적 감사와 command dry-run은 실행하고, Django test 실패가 test DB 확장 문제인지 변경 실패인지 분리해 보고한다.
- 위험: 백엔드와 프론트 배포 순서가 어긋나면 `canManageRecipients`가 없는 응답을 받을 수 있다.
- 대응: 프론트 파서에서 `canManageRecipients ?? isOperator` fallback을 유지한다.

## 진행 기록
- 2026-07-13: 현재 코드 기준 적용 지점 확인 후 구현 계획 작성.
- 2026-07-13: 초기 권한 부여 command와 Line Dashboard 알림 설정 권한 완화를 구현하고 관련 테스트를 갱신.
- 2026-07-13: `py_compile`, `git diff --check`, API/Web boundary audit, command dry-run, 대상 Django 테스트 9개 통과. UI audit은 기존 `apps/web/src/features/l3-spider/components/L3SpiderChart.jsx` raw color/inline style 후보로 실패.
- 2026-07-13: `grant_initial_access`를 완료 marker 기준 DB당 1회 실행으로 변경하고 `--force` 명시 재실행 옵션을 추가.
- 2026-07-13: 사용자 결정에 따라 API entrypoint/Compose 자동 실행 연결은 제거하고 수동 실행 방식으로 확정.
