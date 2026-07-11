# ExecPlan: 권한 변경 통합 리뷰

## 목표
- 현재 브랜치의 포털 및 앱 접근 권한 변경을 백엔드와 프론트엔드에서 함께 검토한다.
- 권한 우회, 데이터 무결성, API 계약, 관리 UI 상태와 접근성 문제를 수정한다.

## 현재 상태
- 기준 커밋은 `main`과 현재 브랜치의 merge-base인 `9dc434b3`이다.
- 권한 관련 변경은 `account`, `auth`, 공통 permission/middleware, 계정 관리 UI, 라우트 gate에 걸쳐 있다.
- 작업 트리는 리뷰 시작 시점에 깨끗하며 변경은 현재 브랜치 커밋에 포함되어 있다.

## 범위
- 포털 승인, 앱 접근 권한, 관리 가능 조직 범위, 인증 응답과 프론트엔드 접근 제어를 검토한다.
- 계정 권한 관리 화면의 loading, empty, error, disabled, pending 상태와 접근성을 검토한다.
- Spider 기능 이름 변경 자체와 권한에 무관한 화면 재설계는 수정하지 않는다.

## 설계
- 서버를 권한 판정의 최종 권위로 유지하고 프론트엔드 gate는 탐색 및 안내 용도로만 사용한다.
- 권한 변경은 기존 account service facade와 selector를 통해 처리하며 view의 ORM 접근을 추가하지 않는다.
- 공개 API 필드와 라우트는 유지하고, 잘못된 상태 전이나 범위 누락만 보완한다.
- DB schema, migration, env contract는 결함 재현 결과가 요구하지 않는 한 변경하지 않는다.

## 실행 단계
- [x] 권한 모델, selector, service, permission, middleware, API와 UI 데이터 흐름을 매핑한다.
- [x] 정적 경계 및 UI 일관성 감사를 실행하고 변경 범위의 후보를 분류한다.
- [x] 백엔드 결함을 테스트로 재현하고 최소 범위로 수정한다.
- [x] 프론트엔드 gate 및 관리 UI 결함을 수정하고 필요한 테스트를 보강한다.
- [x] Docker Compose `api` 테스트와 프론트엔드 lint/build/audit를 실행한다.
- [x] 최종 diff와 보안 경계를 재검토하고 잔여 위험을 기록한다.
- [x] 2차 검토에서 인증 경로, migration 상태별 적용 결과, 상태 전이와 관리 UI의 지연 응답 상태를 독립적으로 재검증한다.
- [x] 2차 검토에서 재현한 앱 활동 추적과 stale row 조작 문제를 수정하고 회귀 검증한다.

## 검증
- `npm run agent:audit:api-boundary`
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.auth`
- 프론트엔드 package script를 확인한 뒤 변경 범위에 맞는 lint/test/build 명령을 실행한다.

## 위험과 대응
- 위험: 현재 브랜치와 `main`이 서로 다른 커밋을 포함해 전체 diff에 권한과 무관한 변경이 섞일 수 있다.
- 대응: merge-base 이후의 권한 관련 파일과 해당 호출 경로만 수정한다.
- 위험: 프론트엔드 gate만 고치면 직접 API 호출로 우회할 수 있다.
- 대응: 모든 접근 결정을 서버 permission과 endpoint 테스트에서 먼저 확인한다.
- 위험: 대규모 기존 테스트에서 환경 의존 실패가 섞일 수 있다.
- 대응: 권한 도메인 집중 테스트를 먼저 실행하고, 실패 원인과 전체 회귀 범위를 분리해 기록한다.

## 진행 기록
- 2026-07-11: 현재 브랜치의 4개 커밋과 merge-base를 확인하고 통합 리뷰를 시작했다.
- 2026-07-11: 적용된 `0002` 편집으로 L0/L1 scope가 누락되는 문제를 확인하고 결정을 보존하는 `0003` migration으로 분리했다.
- 2026-07-11: 기본 활성화된 개발 fixture와 앱 매트릭스의 상속 결과 오표시를 수정했다.
- 2026-07-11: account/auth 161개와 전체 backend 758개 테스트, migration drift, 무결성 검사, 변경 frontend lint, production build, 경계/문서 감사를 통과했다.
- 2026-07-11: 1440x960 및 390x844 브라우저 검증에서 가로 넘침 없이 실제 빈 상태와 13개 앱 scope가 표시됨을 확인했다.
- 2026-07-11: 전체 web lint의 기존 L3 Spider 미사용 상수 1건과 UI 감사의 기존 L3 차트 색상 후보 6건은 요청 범위 밖 잔여 항목으로 기록했다.
- 2026-07-11: 2차 검토에서 비활성 앱 gate가 표시되어도 성공 방문 추적 요청이 발생하고, 필터 응답 대기 중 이전 권한 행의 변경 컨트롤이 활성 상태인 문제를 브라우저에서 재현했다.
- 2026-07-11: 포털 미승인 사용자가 홈 gate에 차단된 상태에서도 성공 방문 추적 요청이 발생하는 문제를 별도 계정으로 재현했다.
- 2026-07-11: `line-dashboard`만 허용된 사용자가 TIP의 Observer gate에 차단되어도 ESOP 성공 방문으로 기록되는 중첩 scope 문제를 재현했다.
- 2026-07-11: 활동 추적을 포털 승인 및 단일·중첩 앱 scope와 일치시켰고, 앱 경로를 URL segment 기준으로 정규화했다.
- 2026-07-11: 필터 재조회 중 stale row의 앱 셀과 사용자 작업을 비활성화하고 동일한 지연 응답 브라우저 시나리오로 수정 결과를 확인했다.
- 2026-07-11: account/auth 161개 테스트, migration drift·무결성·plan, 변경 frontend lint, production build, frontend/backend 경계 및 문서 감사를 최종 통과했다.
