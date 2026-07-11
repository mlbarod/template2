# ExecPlan: 앱 접근 권한 강제

## 목표
- 앱별 수동 권한이 프론트엔드 route와 백엔드 API에서 실제 접근 차단으로 동작하게 한다.
- 기존 활성 사용자는 모든 앱에 계속 접근할 수 있게 보존한다.

## 현재 상태
- 앱 scope 12개와 사용자별 권한 매트릭스 관리 UI가 존재한다.
- auth 응답에는 portal 권한만 포함되며 앱 route/API는 app scope를 검사하지 않는다.
- 공통 middleware와 DRF permission은 portal scope만 검사한다.

## 범위
- 기존 활성 사용자의 누락된 앱 권한을 viewer/allowed로 backfill한다.
- auth/me 응답에 앱별 최종 권한 맵을 추가한다.
- 앱 API 경로에 공통 app scope 검사를 적용한다.
- 앱 메뉴, route, Assistant widget, Emails mailbox 조회를 앱 권한에 따라 숨기거나 차단한다.
- 앱 역할은 노출하지 않고 앱 진입 권한을 allowed/denied로만 강제한다.

## 설계
- 기존 명시 권한은 유지하고 누락된 사용자×앱 조합만 허용한다.
- 신규 사용자 또는 backfill 이후 누락 상태는 기본 차단한다.
- 백엔드는 portal 권한을 먼저 확인한 뒤 API 경로에 대응하는 app scope를 확인한다.
- 전역 앱 접속 기록 API는 portal 검사만 유지하고 access-stats 조회/관리 API만 별도 보호한다.
- 프론트 route gate는 auth/me의 `app_access`를 사용하고 백엔드를 최종 보안 경계로 둔다.
- Assistant와 Emails는 각 scope가 허용된 경우에만 전역 UI와 선행 query를 활성화한다.

## 실행 단계
- [x] 기존 사용자 앱 권한 backfill migration 추가
- [x] 앱 권한 payload와 공통 API 경로 검사 구현
- [x] auth/me 계약과 테스트 확장
- [x] 프론트 route gate 및 메뉴 필터 구현
- [x] Assistant/Emails 전역 기능 숨김 처리
- [x] backend/frontend 검증 및 로컬 migration 적용

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test --keepdb api.account api.auth`
- 앱 API 허용/차단 집중 테스트
- `npm --prefix apps/web run build`
- 변경 파일 ESLint
- backend/frontend/UI 경계 감사

## 위험과 대응
- 위험: API prefix가 여러 앱에서 공유될 수 있다.
- 대응: 실제 frontend 호출을 기준으로 앱 전용 경로만 매핑하고 전역 activity event는 제외한다.
- 위험: 기존 사용자 lockout이 발생할 수 있다.
- 대응: enforcement 배포 전에 같은 migration에서 누락 권한을 backfill한다.
- 위험: 프론트 메뉴 숨김만으로 보안을 오인할 수 있다.
- 대응: middleware와 DRF permission 양쪽에서 동일한 app scope를 검사한다.

## 진행 기록
- 2026-07-10: 기존 사용자 전체 허용, Assistant/Emails UI 숨김 및 API 차단 규칙을 확정했다.
- 2026-07-10: 순방향 권한 migration의 활성 사용자 backfill, auth app_access payload, 공통 API scope 검사, 메뉴/route gate를 구현했다.
- 2026-07-10: 로컬 활성 사용자 2명에 앱 권한 24건을 backfill하고 12개 scope 전체 허용을 확인했다.
- 2026-07-10: account+auth 테스트 143건, 변경 frontend ESLint, production build, migration check, backend boundary audit를 통과했다. 기존 dashboard-template 및 l3-spider 감사 후보는 범위 밖으로 유지했다.
- 2026-07-11: 앱 role을 외부 계약에서 제거하고 기존 role 데이터는 viewer 호환값으로 정규화했다.
