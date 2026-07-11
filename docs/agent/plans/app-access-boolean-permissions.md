# ExecPlan: 앱 권한 allowed/denied 단순화

## 목표
- 앱 단위 접근 권한을 역할 선택 없이 허용/차단으로 관리한다.
- 포털 scope의 기존 역할 기반 승인 계약은 유지한다.

## 현재 상태
- `AccessScope`, `UserAccess`, `AccessPolicyRule`은 portal/app scope가 공용으로 사용하는 `role` 필드를 가진다.
- 앱 권한 매트릭스는 viewer/member/manager/admin을 선택할 수 있지만 실제 API enforcement는 `allowed`만 검사한다.
- 기존 앱 권한 데이터와 기존 사용자 backfill에는 호환용 앱별 role 값이 저장되어 있다.

## 범위
- 수정: account 접근 판정/변경 서비스, 앱 권한 데이터 migration, account/auth 회귀 테스트, 앱 권한 매트릭스 UI.
- 유지: portal role 승인, feature 내부 세부 권한, 접근 관리자 분리, 부서 식별자 변경, route/API registry 통합.

## 설계
- 공용 DB role 필드는 portal 호환성을 위해 유지한다.
- app scope의 저장 role과 default role은 호환 기본값인 `viewer`로 정규화하되 API 의미에서는 사용하지 않는다.
- app scope payload와 matrix scope 응답에서는 role/defaultRole을 노출하지 않는다.
- app scope 변경 API는 role 입력과 `change_role` action을 거부하고 grant/revoke/reset만 허용한다.
- 앱 매트릭스는 자동/미지정, 허용, 차단 상태만 제공한다.

## 실행 단계
- [x] 앱 role 데이터 정규화 migration 추가
- [x] 앱 payload/변경 서비스 계약 단순화
- [x] backend 회귀 테스트 갱신
- [x] 앱 권한 매트릭스 역할 선택 제거
- [x] migration/test/lint/build/boundary audit 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test --keepdb api.account api.auth`
- 변경 frontend 파일 ESLint
- `npm --prefix apps/web run build`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `git diff --check`

## 위험과 대응
- 위험: 기존 클라이언트가 앱 role을 전송하면 동작이 바뀔 수 있다.
- 대응: 앱 role 입력은 명시적인 400 오류로 반환하고 portal role 입력은 유지한다.
- 위험: 공용 role 필드를 즉시 제거하면 portal 승인 계약이 깨질 수 있다.
- 대응: DB 필드는 유지하고 app scope에서만 의미를 제거한다.

## 진행 기록
- 2026-07-11: 앱 권한을 allowed/denied로 우선 단순화하고 portal role은 유지하기로 결정했다.
- 2026-07-11: 앱 payload와 matrix scope에서 role/defaultRole을 제거하고 앱 role 입력을 거부하도록 변경했다.
- 2026-07-11: 순방향 권한 migration에서 앱 role을 viewer로 정규화하고 account/auth 146개 테스트와 production build를 통과했다.
