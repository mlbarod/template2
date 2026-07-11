# ExecPlan: Portal 우선 권한 계층 강화

## 목표
- 인증 상태를 확인하기 전에는 보호된 프론트 라우트가 렌더링되지 않게 한다.
- Portal 접근이 차단되면 저장된 앱 권한과 관계없이 모든 앱의 최종 접근을 차단한다.
- Portal 접근 역할과 `account.manage_access` 관리 capability의 차이를 운영자가 오해하지 않게 한다.
- 30초 권한 상태 갱신이 운영 DB에 주는 부하를 측정하고 적용 기준을 기록한다.

## 현재 상태
- 서버 API는 Portal 검사 후 앱 scope를 검사하지만 `/api/v1/auth/me`와 관리 매트릭스의 앱 payload는 Portal 차단을 반영하지 않는다.
- `AuthAutoLoginGate`, `PortalAccessGate`, `AppAccessGate`는 `user`가 없을 때 하위 화면을 렌더링한다.
- Portal 역할은 접근 payload에 저장되지만 권한 관리 capability는 Django permission으로 별도 관리된다.
- `AuthProvider`는 화면이 보이는 인증 세션에서 30초마다 `/api/v1/auth/me`를 호출한다.

## 범위
- 수정: `api.account` 접근 판정 서비스와 테스트, auth payload 조립, 공통 permission 캐시 연결, 프론트 auth gate와 권한 매트릭스 문구, account API/모듈 문서.
- 유지: 기존 사용자 전체 앱 허용 backfill, 앱 접속 로그 API, `account.manage_access` capability 분리, migration/env 계약.
- 제외: 최신 `main` 병합과 기존 L3 Spider lint/UI 후보.

## 설계
- 앱별 원래 판정은 그대로 계산하고 Portal이 차단된 경우 최종 `allowed=false`, `effectiveStatus=denied`, `source=portal_access_required`로 덮는다.
- 차단된 앱 payload에는 `blockedByPortal=true`와 원래 `allowed`, `reason`, `effectiveStatus`, `source`를 `underlyingAccess`로 보존한다.
- auth 응답과 요청 middleware는 이미 계산한 Portal payload를 앱 판정에 재사용해 중복 조회를 피한다.
- 관리 매트릭스도 사용자별 Portal 판정을 먼저 계산해 모든 앱의 최종 상태에 적용한다.
- 프론트 gate는 인증 로딩/비인증 상태에서 보호 children을 렌더링하지 않는다.
- 역할 선택지는 `Portal 접근 역할`로 표시하고 권한 관리 capability와 별도라는 안내를 제공한다.
- 실제 `/auth/me` SQL 수를 측정하고, 일반 권한 상태 갱신 주기를 30초에서 1시간으로 늘려 DB 부하를 낮춘다.

## 실행 단계
- [x] Portal 우선 앱 판정 helper와 응답 계약 테스트를 추가한다.
- [x] auth payload, middleware, 관리 매트릭스가 Portal payload를 재사용하게 한다.
- [x] 프론트 auth/app gate를 fail-closed로 변경한다.
- [x] Portal 역할과 권한 관리자 capability 문구를 분리한다.
- [x] SQL query 수와 동시 사용자별 예상 부하를 측정한다.
- [x] backend/frontend 회귀와 경계 감사를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.auth api.common --keepdb --noinput`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test --keepdb --noinput`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- 변경 frontend 파일 대상 ESLint
- `npm run web:build`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:docs`
- `git diff --check`

## 위험과 대응
- 위험: Portal 차단이 앱의 기존 수동 허용 정보를 숨길 수 있다.
- 대응: 최종 판정과 `underlyingAccess`를 함께 반환하고 매트릭스는 명시 상태를 계속 편집할 수 있게 한다.
- 위험: 앱 판정마다 Portal을 다시 조회하면 `/auth/me`와 관리 매트릭스 query 수가 증가한다.
- 대응: 상위 호출자가 계산한 Portal payload를 전달하고 사용자 목록은 일괄 조회한다.
- 위험: 역할 문구 개선 중 capability가 역할에 다시 결합될 수 있다.
- 대응: `can_manage_access` 구현은 변경하지 않고 UI/문서에서 별도 capability임을 명시한다.

## 진행 기록
- 2026-07-11: 사용자 결정에 따라 frontend fail-closed, Portal 우선 앱 차단, 역할/capability 문구 개선, 30초 polling 부하 검증을 시작했다.
- 2026-07-11: production 유사 설정의 `/api/v1/auth/me` 30회 측정에서 요청당 SQL 13건(쓰기 1건), 평균 9.75ms, p95 10.72ms를 확인했다. 30초 주기 기준 활성 탭 100/500/1,000개는 각각 약 43/217/433 SQL QPS이며, write QPS는 약 3.3/16.7/33.3이다.
- 2026-07-11: 일반 권한 상태 polling을 30초에서 5분으로 늘렸다. 활성 탭 100/500/1,000개 기준 예상 부하는 약 4.3/21.7/43.3 SQL QPS와 0.3/1.7/3.3 write QPS로 감소한다. Portal 승인 대기의 15초 polling과 탭 포커스 갱신은 유지한다.
- 2026-07-11: 후속 결정에 따라 일반 권한 상태 polling을 1시간으로 늘렸다. 활성 탭 100/500/1,000개 기준 예상 부하는 약 0.36/1.81/3.61 SQL QPS와 0.03/0.14/0.28 write QPS로 감소한다.
- 2026-07-11: 별도 임시 PostgreSQL DB에서 `account.0001_initial`까지 적용한 뒤 기존 사용자 4명을 구성하고 `0002`, `0003`을 적용했다. 사용자당 앱 권한 13건 backfill, 기존 관리자 그룹 승계, FDC→L0 및 L1 scope 생성, 권한 무결성 검사를 확인하고 임시 DB를 삭제했다.
- 2026-07-11: 권한 관련 175개와 전체 backend 762개 테스트, migration drift 검사, frontend production build, backend/frontend boundary 및 문서 감사를 통과했다. 전체 web lint와 UI 감사는 요청 범위 밖의 기존 L3 Spider 후보 때문에 실패했으며 변경 파일 대상 ESLint는 통과했다.
