# ExecPlan: Scope 기반 접근 권한

## 목표
- 전체 포털 접근을 사용자 department와 사용자별 access 상태로 제한한다.
- 나중에 앱별 scope를 추가해 사용자별 앱 승인/차단/role 확장이 가능하게 한다.
- 사용자는 승인 요청 버튼을 통해 접근 승인을 신청하고, 승인 전에는 대기 상태를 본다.
- 관리자는 account API로 allowed/denied 상태를 결정할 수 있다.

## 현재 상태
- `api.auth`는 `/api/v1/auth/me`에서 현재 사용자와 department를 반환한다.
- `api.account`에는 `UserProfile.role`과 `UserSdwtProdAccess` 기반 권한 모델이 있다.
- 프론트는 `RequireAuth`와 `AuthAutoLoginGate`로 로그인 여부만 제어한다.

## 범위
- 수정할 영역: `apps/api/api/account`, `apps/api/api/auth`, `apps/web/src/features/auth`, `apps/web/src/routes`.
- 수정하지 않을 영역: OIDC callback 계약, 외부 ADFS dummy endpoint, 기존 앱별 API 권한.
- 기존 사용자에 대한 사용자별 승인 레코드 소급 생성/backfill은 하지 않는다.

## 설계
- account 도메인에 `AccessScope`, `AccessPolicyRule`, `UserAccess` 모델을 추가한다.
- 기본 scope는 `portal`이고, 기본 department allow policy는 `메모리Etch기술팀(글로벌 제조&인프라총괄)`로 둔다.
- 사용자는 department와 무관하게 승인 요청을 생성할 수 있다.
- 포털 접근 허용은 `UserAccess.status == allowed`, policy rule 매칭, 또는 관리자 사용자에게 부여한다.
- 허용 department 사용자라도 `UserAccess.status == denied`이면 수동 차단으로 보고 접근을 막는다.
- 관리자 판단은 `UserProfile.role == admin` 또는 `is_superuser`로 한다. `is_staff`는 승인 권한으로 쓰지 않는다.
- `/api/v1/auth/me`에 `portal_access` 상태를 추가한다.
- 프론트는 로그인 후 포털 shell 아래에서 `portal_access.allowed`가 false인 경우 승인 요청 UI를 보여준다.
- API 직접 호출 우회를 막기 위해 `/api/v1/*`에 포털 접근 middleware를 적용한다.
- auth, 포털 승인 요청, 소속 온보딩, 외부 소속 동기화 경로는 middleware 예외로 둔다.

## 실행 단계
- [x] 모델/migration 추가
- [x] selector/service/API 추가
- [x] auth 응답 상태 연결
- [x] 프론트 승인 요청 UI/게이트 추가
- [x] API 레벨 포털 접근 middleware 추가
- [x] 테스트 추가 및 검증 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check` 통과
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.auth --keepdb` 통과
- `npm --prefix apps/web run build` 통과
- `npm run agent:audit:web-boundary` 통과
- `npm run agent:audit:ui` 통과
- `npm run agent:audit:api-boundary` 통과

## 위험과 대응
- 위험: 포털 전체를 막으면서 로그인/승인 요청 API까지 막을 수 있다.
- 대응: auth/account 승인 요청 API는 로그인만 요구하고 포털 게이트는 프론트 shell에서 처리한다.
- 위험: `is_staff`를 승인 권한으로 쓰면 Django admin 접근자에게 과도한 권한이 부여된다.
- 대응: 비즈니스 관리자는 `UserProfile admin`, 비상 우회는 `is_superuser`만 사용한다.

## 진행 기록
- 2026-07-09: 사용자 답변을 바탕으로 사용자별 포털 승인 모델과 department 허용 목록 설계를 확정했다.
- 2026-07-09: 기존 사용자 access row backfill은 제외하고, 필요 시 `denied` 행으로 수동 차단하는 것으로 범위를 고정했다.
- 2026-07-09: 프론트 우회 호출 방지를 위해 API middleware를 추가하고, 온보딩에 필요한 account affiliation 경로는 예외 처리했다.
- 2026-07-09: 앱별 확장을 위해 `PortalAccess*` 설계를 폐기하고 `AccessScope`/`AccessPolicyRule`/`UserAccess`로 일반화했다.
