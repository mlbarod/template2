# ExecPlan: 접근 권한 관리자 capability 분리

## 목표
- 접근 권한 관리 권한을 `UserProfile.ADMIN`에서 분리한다.
- 권한 관리 capability와 portal/app 접근 우회를 서로 독립적으로 판정한다.

## 변경 전 상태
- `is_access_admin`은 superuser 또는 `UserProfile.ADMIN`을 관리자로 판정했다.
- 같은 판정 결과가 권한 관리 API 허용과 portal/app 접근 우회에 함께 사용됐다.
- `UserProfile.ADMIN`은 VOC 관리자와 Drone 운영자 판정에도 사용된다.

## 범위
- 수정: account User custom permission, capability backfill migration, 접근 판정 서비스/selector, account 회귀 테스트, 관리자 상태 UI 문구.
- 유지: 앱 allowed/denied 계약, portal role, VOC/Drone의 기존 `UserProfile.ADMIN` 의미, superuser의 전체 우회.

## 설계
- Django custom permission `account.manage_access`를 단일 관리 capability로 사용한다.
- `can_manage_access`는 superuser 또는 `account.manage_access` 보유자를 반환한다.
- `has_access_bypass`는 superuser만 반환한다.
- 모든 접근 관리 진입점은 `can_manage_access`를 직접 호출한다.
- 기존 `UserProfile.ADMIN` 사용자에게 migration에서 `account.manage_access`를 부여한다.
- 표준 운영 경로는 Django `Access Managers` 그룹이며 기존 직접 permission 부여는 그룹으로 이전한다.
- capability 보유자의 명시적 denied/pending과 비활성 scope는 일반 사용자와 동일하게 적용한다.
- superuser 우회 source는 `superuser_bypass`를 사용하고 구 `admin` 필터 입력만 호환한다.

## 실행 단계
- [x] User custom permission과 backfill migration 추가
- [x] 관리 capability와 접근 우회 서비스 분리
- [x] selector의 admin source 필터를 superuser 기준으로 변경
- [x] 테스트 helper와 관리자/우회 회귀 테스트 갱신
- [x] 프론트 관리자 상태 문구 정리
- [x] migration/test/lint/build/boundary audit 실행

## 후속 개선
- [x] superuser 우회 source를 `superuser_bypass`로 명확화
- [x] 구 `source=admin` 필터 입력과 이전 프론트 응답 호환 유지
- [x] `Access Managers` 그룹 생성 및 기존 직접 permission 이전
- [x] capability 차단 우회 방지와 pending 우선순위 회귀 테스트 추가
- [x] 접근 관리 코드와 UI의 관리자 용어 구분

## 운영 보안 강화
- [x] 일반 staff의 `is_staff`, `is_superuser`, `groups`, `user_permissions` 변경 차단
- [x] 일반 staff의 superuser 및 권한 관리자 계정 변경/삭제 차단
- [x] `Access Managers` 그룹의 이름과 permission 구성 보호
- [x] 권한 관리자 capability 부여/회수 감사 로그 추가
- [x] 모든 `/api/v1` 루트 경로의 접근 정책 분류를 backend audit에서 강제
- [x] 접근 상태/source 상수와 DB/model 불변조건 보강
- [x] migration/test/admin security/boundary audit 검증

## 최종 정합성 개선
- [x] 감사 로그 기본 조회를 전체 scope로 변경하고 capability 변경을 표시
- [x] API 접근 정책 registry를 middleware 런타임 판정의 단일 기준으로 사용
- [x] 앱 scope의 self-service 요청을 비활성화해 실제 UI/API 계약과 일치
- [x] 시스템 portal/app scope의 key, scope_type, 삭제를 보호
- [x] 부서 정책 값을 정규화하고 대소문자 비구분 중복을 차단
- [x] 배포 후 권한 데이터 무결성 점검 command 추가
- [x] migration/test/lint/build/audit 전체 검증

## Migration 배포 이력 압축
- [x] 사내 서버 적용 기준점 `0001_initial` 확인
- [x] 권한 스키마와 데이터 승계를 단일 `0002_access_permissions`로 통합
- [x] migration 직접 참조 테스트를 통합 seed/backfill 계약으로 정렬
- [x] 로컬 migration 기록을 통합 `0002`에 맞게 정렬
- [x] 빈 테스트 DB migration, 회귀 테스트, drift, 무결성 점검 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate --noinput`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test --keepdb api.account api.auth`
- 변경 frontend 파일 ESLint
- `npm --prefix apps/web run build`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `git diff --check`

## 위험과 대응
- 위험: 기존 프로필 관리자가 권한 관리 화면을 잃을 수 있다.
- 대응: migration에서 기존 `UserProfile.ADMIN` 사용자에게 새 permission을 부여한다.
- 위험: capability 보유자가 기존처럼 자신의 접근 제한을 우회할 것으로 기대할 수 있다.
- 대응: capability와 bypass를 응답 source와 테스트에서 명확히 분리한다.
- 위험: `change_user` 또는 `change_group`을 가진 일반 staff가 권한을 스스로 상승시킬 수 있다.
- 대응: 민감 사용자 필드와 privileged target, Django Group 변경을 superuser 전용으로 제한한다.
- 위험: 신규 API prefix가 앱 scope 매핑에서 누락되면 포털 권한만으로 통과할 수 있다.
- 대응: 루트 API prefix별 `public/token/portal/app:<scope>` 분류를 정적 audit로 강제한다.
- 위험: application validation을 우회한 값이 status/role/source 계약을 훼손할 수 있다.
- 대응: DB CheckConstraint와 model clean, 계약 회귀 테스트를 함께 둔다.
- 위험: 기존 사용자 전체 앱 허용을 자동 정리하면 수동 부여와 backfill을 구분하지 못해 lockout이 발생할 수 있다.
- 대응: 순방향 권한 migration 적용 시점의 기존 사용자에게 활성 앱 누락 권한을 보충하고, 이후 신규 가입자부터 기본 권한 판정을 적용한다.

## 진행 기록
- 2026-07-11: Django permission 하나로 관리 capability를 분리하고 superuser만 접근을 우회하도록 결정했다.
- 2026-07-11: 기존 `UserProfile.ADMIN` 사용자에게 permission을 승계하는 데이터 이관을 구현했다.
- 2026-07-11: account/auth 테스트 148개, migration drift 검사, 변경 프론트 ESLint, Vite build, backend boundary audit를 통과했다.
- 2026-07-11: frontend boundary audit는 기존 `dashboard-template`의 facade 누락, UI audit는 기존 `l3-spider`의 raw color/inline style만 보고했다.
- 2026-07-11: `Access Managers` 그룹을 생성하고 직접 capability 부여를 그룹 멤버십으로 이전했다.
- 2026-07-11: superuser 우회 source를 `superuser_bypass`로 변경하고 구 `admin` 필터 입력을 호환 처리했다.
- 2026-07-11: capability 우회 방지와 pending 우선순위를 포함한 account/auth 테스트 150개를 통과했다.
- 2026-07-11: 변경 프론트 ESLint, Vite build, backend boundary audit를 다시 통과했으며 기존 frontend/UI audit 후보는 동일했다.
- 2026-07-11: Django Admin의 민감 사용자 필드와 접근 권한 모델 쓰기를 superuser 전용으로 제한했다.
- 2026-07-11: capability 부여/회수 action과 DB 제약을 추가했다.
- 2026-07-11: 루트 API 접근 정책 registry와 backend 정적 audit를 추가했다.
- 2026-07-11: account/auth/common 테스트 167개, migration drift, frontend ESLint/build, backend/docs audit를 통과했다.
- 2026-07-11: 기존 활성 사용자의 전체 앱 허용은 유지하고 신규 가입자부터 명시 권한/부서 정책을 적용하기로 확정했다.
- 2026-07-11: 권한 migration 적용 시점의 기존 사용자에게 활성 앱 누락 권한을 보충하고 이후 신규 가입자는 자동 허용하지 않도록 배포 경계를 확정했다.
- 2026-07-11: 서버와 공유 DB가 `0001`까지만 적용됐음을 확인하고 권한 스키마와 데이터 승계를 `0002_access_permissions`로 통합했다.
- 2026-07-11: 빈 테스트 DB에서 account/auth/common 테스트 170개, migration drift/plan, 권한 무결성, backend/docs audit를 통과했다.
- 2026-07-11: 감사 로그 전체 scope 조회, runtime API registry, 앱 self-service 비활성화, 시스템 scope 보호, 정책 중복 제약, 무결성 점검 command를 완료했다.
- 2026-07-11: account/auth/common 테스트 173개, migration drift, Django check, 변경 frontend ESLint, Vite build, backend/docs audit를 통과했다. 전체 frontend/UI audit는 기존 범위 밖 항목만 보고했다.
