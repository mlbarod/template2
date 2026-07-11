# ExecPlan: 포털 권한 기능 보완

## 목표
- 세션, Basic 인증, 익명 요청에서 포털 접근 게이트가 일관되게 적용되도록 한다.
- 권한/정책 변경과 감사 로그의 원자성 및 변경 이력의 불변성을 보장한다.
- 운영자가 권한 관리 UI에서 변경 결과와 실패를 명확히 확인하고 작은 화면에서도 주요 작업을 수행할 수 있게 한다.
- 미승인 사용자가 허용된 계정 소속 화면에서 온보딩을 완료할 수 있게 한다.

## 현재 상태
- `AccessScope`, `AccessPolicyRule`, `UserAccess`, `AccessAuditLog`와 관리 API/UI가 워크트리에 구현되어 있다.
- Django middleware보다 늦게 수행되는 DRF Basic 인증과 익명 읽기 요청은 포털 판정을 우회할 수 있다.
- 일부 서비스 쓰기와 감사 로그 생성이 하나의 transaction으로 묶이지 않았다.
- 권한 관리 UI는 mutation 실패, 위험 정책 확인, 관리자 메뉴 필터, 작은 화면 스크롤 처리가 부족하다.

## 범위
- 수정할 영역: `apps/api/api/account`, `apps/api/api/auth`, `apps/api/api/common`, `apps/api/config/settings.py`, `apps/web/src/features/account`, `apps/web/src/features/auth`, `apps/web/src/lib/account`, `apps/web/src/lib/config`.
- 수정하지 않을 영역: OIDC callback 계약, 외부 동기화 token 계약, 앱별 세부 권한, 여러 정책이 동시에 일치할 때의 role 병합 규칙.
- 기존 사용자 변경과 공개 facade를 보존한다.

## 설계
- DRF 기본 permission에서 보호 API의 익명 요청과 인증 사용자 접근 상태를 확인한다.
- Basic 인증은 인증 직후 동일한 포털 접근 판정을 수행해 명시 permission을 사용하는 API도 우회하지 못하게 한다.
- 포털 예외 경로 판정과 요청별 접근 payload를 공통화해 middleware/DRF의 정책 드리프트와 중복 조회를 줄인다.
- 권한 결정과 정책 CRUD는 row lock 및 `transaction.atomic()` 안에서 감사 로그까지 저장한다.
- 감사 로그 Django Admin은 조회 전용으로 제한하고 API에는 당시 snapshot을 표시한다.
- UI mutation은 명시적 성공/실패 피드백과 중복 제출 방지를 제공하고, 광범위한 인증 사용자 정책은 확인 후 반영한다.
- 미승인 계정 화면은 포털 보호 overview query를 실행하지 않고 예외 처리된 affiliation 흐름만 렌더링한다.

## 실행 단계
- [x] 인증/permission 우회 차단과 회귀 테스트 추가
- [x] 권한/정책 write와 감사 로그 원자성 보완
- [x] 감사 로그/필터/입력 검증 보완
- [x] 권한 관리 및 승인 게이트 UI 보완
- [x] 미승인 계정 온보딩 경로 보완
- [x] migration/test/build/audit/화면 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.auth --keepdb`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- 변경된 프론트 파일 대상 ESLint
- `npm run web:build`
- Playwright 또는 사용 가능한 브라우저 자동화로 desktop/mobile 화면 확인

## 위험과 대응
- 위험: 전역 permission 적용이 auth/health/온보딩/system endpoint를 막을 수 있다.
- 대응: 기존 middleware 예외 경로를 공통화하고 Basic/익명/예외 경로 테스트를 추가한다.
- 위험: 감사 로그 보완 중 기존 운영 API 응답이 달라질 수 있다.
- 대응: 기존 field를 유지하고 snapshot 선택 및 새 action만 추가한다.
- 위험: UI 고정 높이 안에서 작은 화면 내용이 잘릴 수 있다.
- 대응: page scroll과 table scroll의 소유권을 viewport 크기에 따라 분리하고 screenshot으로 확인한다.

## 진행 기록
- 2026-07-10: 현재 staged/unstaged 변경과 기존 두 ExecPlan을 검토하고 보안, 정합성, UI 회귀 항목을 확정했다.
- 2026-07-10: 다중 정책 role 병합 규칙은 별도 권한 정책 결정이 필요해 이번 범위에서 제외했다.
- 2026-07-10: middleware, DRF permission, Basic 인증이 공통 포털 판정을 사용하도록 보완하고 익명 요청은 401, 미승인 인증 요청은 403으로 일관되게 처리했다.
- 2026-07-10: 권한 요청/결정과 정책 CRUD를 transaction 및 row lock으로 보호하고 감사 snapshot, scope action, Django Admin 변경 감사를 추가했다.
- 2026-07-10: 권한 관리 화면의 실패 피드백, 위험 정책 확인, 검색 적용/초기화, 반응형 스크롤, 감사 변경값을 보완하고 권한 없는 메뉴와 화면을 fail-closed 처리했다.
- 2026-07-10: account/auth 133개 테스트, migration drift, API boundary, 변경 파일 ESLint, web build, `git diff --check`를 통과했다.
- 2026-07-10: 1440x960 및 390x844 Playwright 확인에서 문서 가로 넘침과 console error가 없었고 권한 화면의 전역 채팅 위젯 겹침을 제거했다.
- 2026-07-10: 전체 web lint와 frontend boundary/UI audit는 이번 변경과 무관한 기존 `l3-spider` 미사용 상수·raw color/inline style 및 `dashboard-template` facade 누락만 보고했다.
- 2026-07-10: 로컬 Compose DB에 account migration 0002~0004를 적용하고 portal scope와 기본 정책 생성을 확인했다.
