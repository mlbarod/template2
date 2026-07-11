# ExecPlan: 포털 권한 관리 운영 UI

## 목표
- 운영자가 전체 인원의 포털 접근 최종 상태를 보고 권한을 승인, 거절, 부여, 회수, 정책 기준으로 복귀할 수 있게 한다.
- 운영자가 기본 허용 정책을 UI/API로 관리할 수 있게 한다.
- 권한 변경 이력을 조회할 수 있게 해 운영 감사 가능성을 확보한다.

## 현재 상태
- `AccessScope`, `AccessPolicyRule`, `UserAccess` 모델과 포털 접근 게이트가 있다.
- `portal-access/approvals` API는 pending/기존 `UserAccess` row 중심 승인/거절만 처리한다.
- 제품 프론트에는 사용자 승인 요청 UI만 있고 운영자 관리 UI는 없다.
- 정책 허용 사용자는 `UserAccess` row가 없을 수 있어 기존 approval 목록만으로는 권한 회수를 처리하기 어렵다.

## 범위
- 수정할 영역: `apps/api/api/account`, `apps/web/src/lib/account`, `apps/web/src/features/account`, `docs/agent/plans`.
- 수정하지 않을 영역: 기존 Airflow DAG 변경, 포털 접근 middleware 예외 정책, OIDC/auth callback 계약.
- 이번 UI/API는 기존 `portal` scope를 기본 대상으로 하되 `scope` 파라미터를 유지한다.

## 설계
- 백엔드는 사용자별 effective access read model을 제공한다.
- effective access는 명시 상태(`UserAccess`), 정책 판정(`AccessPolicyRule`), 관리자 우회를 함께 계산해 `source`로 구분한다.
- 정책 허용 사용자의 회수는 `UserAccess(status=denied)`를 생성/갱신해 정책보다 우선 차단한다.
- `reset_to_policy`는 명시 `UserAccess` row를 삭제하고 감사 로그를 남긴다.
- 정책 rule CRUD는 account access admin만 허용하며 모델 `full_clean()` 검증을 사용한다.
- 감사 로그 모델을 추가해 사용자 권한 결정과 정책 변경을 기록하고 API로 조회한다.
- 프론트는 계정 설정 하위에 `settings/permissions` 라우트를 추가하고 사용자 권한, 승인 대기, 기본 정책, 변경 이력 탭을 제공한다.

## 실행 단계
- [x] 감사 로그 모델/migration/admin 추가
- [x] selector/service/serializer/view/url API 추가
- [x] backend 테스트 추가
- [x] account API client/query hook 추가
- [x] 권한 관리 페이지와 라우트 추가
- [x] 검증 실행 및 결과 기록

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.auth --keepdb`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `npm run web:lint`
- `npm run web:build`

## 위험과 대응
- 위험: 정책 허용과 명시 차단이 섞여 운영자가 실제 접근 상태를 오해할 수 있다.
- 대응: 응답과 UI에서 `allowed`, `effectiveStatus`, `explicitStatus`, `policyMatched`, `source`를 함께 표시한다.
- 위험: 정책 rule 삭제가 즉시 다수 사용자 접근에 영향을 줄 수 있다.
- 대응: 정책 탭은 비활성화 토글을 제공하고 삭제는 확인 dialog를 거친다.
- 위험: 감사 로그가 누락되면 권한 회수 추적이 어렵다.
- 대응: service write 경로에서 사용자 권한과 정책 변경 로그를 함께 기록한다.

## 진행 기록
- 2026-07-09: 사용자 요청에 따라 전체 인원 권한 관리, 기본 정책 관리, 회수, 감사 로그까지 포함하는 구현 계획을 분리 작성했다.
- 2026-07-09: `AccessAuditLog`와 운영자용 access users/policy-rules/audit-logs API를 추가했다.
- 2026-07-09: `/settings/permissions` 프론트 페이지를 추가하고 사용자 권한, 승인 대기, 기본 정책, 변경 이력 탭을 연결했다.
- 2026-07-09: migration check, backend account/auth tests, frontend lint/build, boundary/UI/docs audit를 실행해 통과를 확인했다.
- 2026-07-09: 리뷰 보완으로 사용자 목록 기본 조회 선페이지네이션, Django Admin 감사 로그, legacy 승인 API decision 필수화, 정책 삭제 확인 dialog, 삭제 정책 이력 fallback을 추가했다.
- 2026-07-09: 보완 후 py_compile, migration check, backend account/auth tests, frontend lint/build, boundary/UI/docs audit를 다시 실행해 통과를 확인했다.
