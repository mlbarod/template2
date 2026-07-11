# ExecPlan: 부서 전용 자동 접근 정책

## 목표
- 자동 접근 규칙의 적용 기준을 `부서 일치` 하나로 제한한다.
- API와 DB에서 비부서 정책 유형을 거부하고 기존 비부서 정책 레코드를 제거한다.
- 권한 관리 화면에서 불필요한 적용 기준 선택 UI를 제거한다.

## 현재 상태
- `AccessPolicyRule.RuleTypes`는 부서, 프로필 역할, 소속 권한, 로그인 사용자 전체를 지원한다.
- 정책 평가 서비스는 활성 규칙 중 하나가 일치하면 자동 접근을 허용한다.
- 권한 관리 화면은 네 가지 적용 기준을 선택할 수 있다.
- 현재 작업 트리의 `PermissionsPage.jsx`에는 이번 요청과 무관한 사용자 레이아웃 변경이 있다.

## 범위
- 수정할 영역: `apps/api/api/account`, `apps/web/src/features/account/pages/PermissionsPage.jsx`, `docs/agent/plans`.
- 수정하지 않을 영역: 개별 사용자 권한, 관리자 우회 권한, 기존 감사 로그 스냅샷, 다른 account 화면의 작업 트리 변경.

## 설계
- 모델 선택값과 API 입력 선택값은 `department`만 허용한다.
- DB check constraint를 추가해 ORM 검증을 우회한 비부서 정책 저장도 차단한다.
- 데이터 마이그레이션은 기존 비부서 `AccessPolicyRule` 레코드를 삭제하고 과거 감사 로그 스냅샷은 유지한다.
- 정책 평가는 사용자 부서와 활성 부서 규칙만 비교한다.
- 프론트는 적용 기준 선택기를 제거하고 생성 요청에 `ruleType: "department"`를 고정한다.

## 실행 단계
- [x] 모델과 정책 평가 로직을 부서 전용으로 축소한다.
- [x] 기존 비부서 정책 정리와 DB 제약을 포함한 migration을 추가한다.
- [x] API, 모델, DB 제약 회귀 테스트를 갱신한다.
- [x] 권한 관리 화면을 부서 전용 입력과 목록으로 단순화한다.
- [x] migration, backend 테스트, frontend lint/build, boundary/UI audit를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account --keepdb`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- 변경된 프론트 파일 대상 ESLint
- `npm run web:build`
- `git diff --check`

## 위험과 대응
- 위험: 비부서 정책 삭제로 해당 규칙에만 의존하던 사용자의 접근이 즉시 해제될 수 있다.
- 대응: 사용자 결정에 따라 비부서 규칙만 명시적으로 삭제하고, 개별 권한과 부서 규칙은 유지한다.
- 위험: 기존 감사 이력을 삭제하면 과거 변경 추적이 불가능해진다.
- 대응: 정책 레코드만 삭제하고 JSON 감사 스냅샷은 수정하지 않는다.
- 위험: 같은 프론트 파일의 기존 작업이 손실될 수 있다.
- 대응: 현재 작업 트리 버전을 기준으로 필요한 정책 UI 블록만 수정한다.

## 진행 기록
- 2026-07-10: 사용자 확인에 따라 UI뿐 아니라 API와 DB에서도 비부서 정책 유형을 제거하기로 결정했다.
- 2026-07-10: 모델 choices와 정책 평가 분기를 부서 전용으로 축소하고, 비부서 레코드 삭제 및 DB check constraint migration을 추가했다.
- 2026-07-10: 권한 관리 화면에서 적용 기준 선택기와 비부서 전용 입력·확인 흐름을 제거했다.
- 2026-07-10: migration drift와 Django system check, 변경 파일 ESLint, API boundary, web build, `api.account` 110개 및 `api.auth` 24개 테스트, `git diff --check`를 통과했다.
- 2026-07-10: frontend boundary와 UI audit는 이번 변경과 무관한 기존 `dashboard-template` facade 누락 및 `l3-spider` raw color/inline style만 보고했다.
