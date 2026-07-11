# ExecPlan: L0 Spider scope rename

## 목표
- `fdc-trend`로 남아 있는 L0 Spider 소유권을 `l0-spider` / `l0_spider`로 정리한다.
- L1 Spider는 현재 외부주소를 쓰지만 별도 app scope와 feature route로 분리한다.
- 서버 배포 기준은 account `0001`이지만 로컬 적용 이력도 보존할 수 있도록 scope 이름 변경을 별도 순방향 migration으로 처리한다.

## 현재 상태
- 변경 전 backend 앱은 `api.fdc_trend`였고 전역 API prefix는 `/api/v1/fdc-trend/`였다.
- 변경 전 권한 seed와 system scope key에는 `fdc-trend`가 있었다.
- 변경 전 frontend feature 폴더는 `features/fdc-trend`였고 Spider 허브의 L0/L1 appScope도 `fdc-trend`였다.
- L0/L1/TTTM은 현재 외부주소 또는 proxy 기반 화면이지만 향후 프로젝트 내부로 병합될 수 있다.

## 범위
- 수정: backend app rename, API include/permission mapping, account scope seed/test, frontend feature folder/import/scope, 문서 inventory.
- 유지: `/api/v1/fdc-trend/` path 호환 alias, 기존 legacy `/fdc_trend` page route.
- 제외: L1/TTTM backend 빈 Django app 생성, 외부 URL env 계약 재설계, DB schema 추가.

## 설계
- Backend Python module은 `api.l0_spider`로 둔다.
- 신규 API prefix는 `/api/v1/l0_spider/`로 추가하고, 기존 `/api/v1/fdc-trend/`는 같은 urls를 include하는 alias로 둔다.
- 권한 scope는 `l0-spider`, `l1-spider`, `l3-spider`, `pm-spider`, `tttm-spider`를 사용한다.
- 기존 `0002`의 `fdc-trend` scope seed는 적용 이력 보존을 위해 유지한다.
- `0003_spider_access_scopes`에서 기존 scope의 PK와 사용자 결정을 보존한 채 `l0-spider`로 이름을 바꾸고 `l1-spider`를 추가한다.
- Frontend feature 폴더는 `features/l0-spider`로 rename하고, route export는 `l0SpiderRoutes`로 바꾼다.

## 실행 단계
- [x] `api.fdc_trend`를 `api.l0_spider`로 rename한다.
- [x] 별도 migration에서 `fdc-trend`를 `l0-spider`로 이전하고 `l1-spider`를 추가한다.
- [x] API route access policy와 auth tests를 새 scope 기준으로 갱신한다.
- [x] `features/fdc-trend`를 `features/l0-spider`로 rename하고 frontend imports를 갱신한다.
- [x] Spider 허브와 navigation/branding/activity mapping을 새 scope 기준으로 갱신한다.
- [x] 문서 inventory와 plan 기록을 갱신한다.

## 검증
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- 변경 frontend 파일 targeted ESLint
- `npm run web:build`
- Docker Compose `api` 컨테이너에서 관련 backend 테스트 실행

## 위험과 대응
- 위험: 기존 `/api/v1/fdc-trend/` 호출이 바로 깨질 수 있다.
- 대응: 같은 `api.l0_spider.urls`를 include하는 호환 alias를 유지한다.
- 위험: 적용된 `0002`를 다시 편집하면 로컬/공유 DB에 구 scope가 남아 코드와 불일치할 수 있다.
- 대응: `0002`는 원래 이력으로 복원하고 `0003`에서 기존 결정을 보존하는 순방향 이전을 수행한다.
- 위험: frontend feature rename 중 facade import가 깨질 수 있다.
- 대응: route orchestration layer만 `@/features/l0-spider` facade를 import하게 유지하고 boundary audit를 실행한다.

## 진행 기록
- 2026-07-11: 사용자가 `l0_spider`, L1/TTTM 향후 내부 병합 준비 방향을 승인했다.
- 2026-07-11: backend app을 `api.l0_spider`로 옮기고 `/api/v1/l0_spider/`를 신규 prefix로 추가했다.
- 2026-07-11: `l0-spider`, `l1-spider` app scope를 `0002_access_permissions.py` seed와 frontend 허브에 반영했다.
- 2026-07-11: frontend `features/l0-spider`, `features/l1-spider` facade/route를 구성했다.
- 2026-07-11: targeted ESLint, frontend/backend boundary audit, docs audit, `git diff --check`, `npm run web:build`, Docker `api` 컨테이너 backend 테스트 162개 통과를 확인했다.
- 2026-07-11: 전체 web lint와 UI audit는 기존 L3 Spider 파일의 별도 후보/오류가 남아 있음을 확인했다.
- 2026-07-11: 통합 리뷰에서 적용된 `0002` 편집으로 로컬 scope가 누락되는 문제를 재현하고 별도 `0003` 데이터 migration으로 교정했다.
