# ExecPlan: 권한 migration 통합과 인증 상태 즉시 갱신

## 목표
- 서버의 account migration이 `0001`까지만 적용된 배포 전제에서 현재 권한 스키마를 단일 `0002`로 적용한다.
- 권한 변경 성공 직후 `auth/me` 사용자 상태를 갱신해 메뉴와 route gate에 반영한다.

## 현재 상태
- 서버 DB에는 `0001_initial`만 적용되어 있고, 기존 `0002` 이후 이력을 적용한 공유 DB는 없다.
- 로컬 DB에는 기존 개발 migration 이력이 적용되어 있지만 현재 모델의 최종 스키마와 데이터는 이미 반영되어 있다.
- 접근 권한 mutation 성공 시 account React Query cache와 AuthProvider 상태를 함께 갱신한다.

## 범위
- 수정: account migration chain, 권한 migration 테스트, account mutation hook, 관련 계획 문서.
- 유지: 현재 모델/API 계약, 권한 판정 우선순위, 권한 관리 UI 동작.
- 제외: TTTM/Grafana 프록시 권한, 권한 매트릭스 확인 UX, 기타 리뷰 항목.

## 설계
- `0001_initial` 이후의 권한 변경을 `0002_access_permissions` 하나로 통합한다.
- 통합 migration은 최종 스키마를 직접 생성하고 포털/앱 scope, 앱 boolean 계약, 관리 capability, 기존 사용자 앱 권한을 초기화한다.
- backfill 동작은 기존 권한 구현의 사용자·활성 앱 범위를 그대로 보존한다.
- `useAccessUserDecision` 성공 처리에서 AuthProvider `refresh()`와 관련 query invalidation을 함께 실행한다.

## 실행 단계
- [x] 단일 `0002_access_permissions` 생성
- [x] migration 회귀 테스트를 통합 seed/backfill 계약에 맞게 수정
- [x] 권한 mutation 후 인증 상태 갱신 연결
- [x] 로컬 migration recorder를 새 `0002` 기준으로 정렬
- [x] migration/test/lint/build/boundary audit 검증
- [x] 앱 권한 적용으로 실패한 도메인 endpoint 테스트의 권한 경계를 명시적으로 격리
- [x] 전체 backend 757개 테스트와 frontend lint를 통과하도록 회귀 정리
- [x] 통합 migration의 Git index 상태 정렬

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- 빈 테스트 DB에서 account migration 집중 테스트
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.auth api.common`
- 변경 frontend 파일 ESLint 및 production build
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `git diff --check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test --noinput`
- `npm run web:lint`

## 위험과 대응
- 위험: 기존 `0002` 이후 migration을 적용한 공유 DB에는 통합 migration을 바로 적용할 수 없다.
- 대응: 서버와 공유 DB가 `0001`까지만 적용됐다는 배포 전제를 명시하고, 로컬은 스키마를 변경하지 않은 채 recorder만 정렬한다.
- 위험: 권한 mutation마다 `auth/me` 요청이 한 번 추가된다.
- 대응: mutation 성공 시에만 실행하고 기존 백그라운드 refresh 경로를 재사용한다.

## 진행 기록
- 2026-07-11: 커밋된 migration 보존과 mutation 후 AuthProvider refresh 방식으로 수정 범위를 확정했다.
- 2026-07-11: `0002`~`0004`를 복구하고 `0005`~`0007` 순방향 chain과 기존 사용자 backfill을 검증했다.
- 2026-07-11: 권한 mutation 성공 시 account query와 AuthProvider 사용자 상태를 함께 갱신하도록 연결했다.
- 2026-07-11: 빈 DB 집중 테스트와 account/auth/common 170개 테스트, migration drift/plan, 무결성 command, ESLint, production build, backend boundary audit를 통과했다.
- 2026-07-11: frontend boundary audit는 기존 `dashboard-template`의 facade 누락만 보고했다.
- 2026-07-11: 서버가 `0001`까지만 적용됐다는 확인에 따라 권한 migration을 단일 `0002_access_permissions`로 통합하기로 결정했다.
- 2026-07-11: fresh DB에서 account/auth/common 170개 테스트를 통과하고 로컬 recorder를 `0001_initial`, `0002_access_permissions`로 정렬했다.
- 2026-07-11: migration drift/plan, Django check, 권한 무결성, 변경 hook ESLint, production build, backend/docs audit를 통과했다. frontend boundary audit는 기존 `dashboard-template` 누락만 보고했다.
- 2026-07-11: 전체 backend 757개 테스트에서 신규 사용자 기본 차단 계약 때문에 120개 도메인 endpoint 테스트가 실패함을 확인했다.
- 2026-07-11: domain endpoint 테스트에서 account 권한 응답을 격리해 운영 권한 정책을 유지하면서 전체 backend 757개 테스트를 통과했다.
- 2026-07-11: frontend lint/build, migration drift/plan, 권한 무결성, Django check, repository 전체 agent audit를 통과했다.
- 2026-07-11: 기존 권한 migration 삭제와 통합 `0002_access_permissions` 추가가 하나의 Git 변경으로 반영되도록 index를 정렬했다.
