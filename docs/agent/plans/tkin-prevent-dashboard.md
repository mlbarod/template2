# ExecPlan: tkin prevent dashboard

## 목표
- `m_tkin_prevent` 데이터를 observer와 유사한 drilldown 조건으로 조회하는 대시보드를 추가한다.
- ESOP Dashboard line 선택, user_sdwt_prod, PRC group, process_id, step_seq 선택 후 `ppid` 컬럼과 `eqp_id-tkin_prevent_chamber_id` 행으로 matrix를 표시한다.

## 현재 상태
- `api.observer`는 `mes_line_mapping_info`와 `station_master` 기준의 라인/SDWT/PRC dropdown API를 이미 제공한다.
- `api.account`는 `account_affiliation.line/user_sdwt_prod` 기반 `/api/v1/account/line-sdwt-options`를 이미 제공한다.
- `api.data_movement.m_tkin_prevent`는 적재 모델과 최근 load-job selector만 있고 화면 조회용 selector는 없다.
- `apps/web/src/features/observer`는 route, API client, React Query hook, observer page 구조를 갖고 있다.

## 범위
- 수정할 영역: `api.observer` selector/view/url/test, `apps/web/src/features/observer` API/hook/page/route.
- 수정하지 않을 영역: DB schema, data movement loader, env/compose mount, 기존 observer timeline 동작.

## 설계
- ESOP Dashboard line selector와 account affiliation 기반 user_sdwt_prod 후보를 사용한다.
- 신규 API:
  - `GET /api/v1/observer/tkin-prevent/prc-groups?userSdwtProd=...`
  - `GET /api/v1/observer/tkin-prevent/processes?userSdwtProd=...&prcGroup=...`
  - `GET /api/v1/observer/tkin-prevent/step-seqs?userSdwtProd=...&prcGroup=...&processId=...`
  - `GET /api/v1/observer/tkin-prevent/matrix?userSdwtProd=...&prcGroup=...&processId=...&stepSeq=...`
- Line은 user_sdwt_prod 선택까지만 사용하고, 이후 조회는 `station_master.sdwt_prod_lookup`과 `station_master.prc_group_lookup`으로 필터링한다.
- 필터링된 `station_master.ch_main`을 `m_tkin_prevent.eqp_id`와 매칭한다.
- cell 값은 `DOING`이면 `DOING`, `PREVENT`이면 `registration_level(tkin_restrc_lot_count/tkin_lot_count)`, `LEVEL2/LEVEL3`이면 `registration_level(level2_restrc_lot_count/tkin_restrc_lot_count/tkin_lot_count)`로 변환한다.
- ESOP Dashboard 내부 `TIP현황`은 ESOP line selector의 `ActiveLineProvider` 값을 사용한다.
- `TIP현황`의 user_sdwt_prod 후보는 `/api/v1/account/line-sdwt-options`의 `account_affiliation.line -> user_sdwt_prod` 매핑에서 가져온다.
- T/K Prevent PRC 후보는 `GET /api/v1/observer/tkin-prevent/prc-groups?userSdwtProd=...`로 조회하고, 이후 process/step/matrix 조회는 `userSdwtProd + prcGroup` scope를 사용한다.
- `TIP현황` route는 `/ESOP_Dashboard/tip-status/:lineId`로 line-scoped 처리한다.
- Migration/env/auth 변경은 없다.

## 실행 단계
- [x] API selector와 endpoint 추가
- [x] selector/view 테스트 추가
- [x] React API/hook/page/route 추가
- [x] 검증 명령 실행 및 결과 기록
- [x] ESOP line selector 기반 TIP현황 route로 전환
- [x] account affiliation 기반 user_sdwt_prod 드릴다운 적용
- [x] T/K Prevent 전용 PRC group endpoint 추가 및 테스트 보강
- [x] matrix cell hover comment 표시 추가

## 검증
- [x] `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer --keepdb`
- [x] `npm run web:build`
- [x] `npm run agent:audit`
- [x] `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer --keepdb`
- [x] `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- [x] `npm run agent:audit:api-boundary`
- [x] `npm run agent:audit:web-boundary`
- [x] `npm run agent:audit:ui`
- [x] `npm run web:lint -- --quiet`
- [x] `npm run web:build`
- [x] `git diff --check`
- [x] `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer --keepdb`
- [x] `npm run agent:audit:api-boundary`
- [x] `npm run agent:audit:web-boundary`
- [x] `npm run agent:audit:ui`
- [x] `npm run web:lint -- --quiet`
- [x] `npm run web:build`
- [x] `git diff --check`

## 위험과 대응
- 위험: 실제 데이터에서 동일 cell에 다중 row가 있을 수 있다.
- 대응: API에서 중복 제거 후 배열로 내려주고 UI에서 줄 단위로 표시한다.
- 위험: `tkin_restc_lot_count` 명칭과 모델 필드 `tkin_restrc_lot_count` 철자가 다르다.
- 대응: 현재 모델 필드명 `tkin_restrc_lot_count`를 사용한다.

## 진행 기록
- 2026-06-23: observer 기준정보 API 재사용과 `m_tkin_prevent` matrix 신규 endpoint 추가 방향으로 계획을 작성했다.
- 2026-06-23: observer API에 `tkin-prevent` process/step/matrix endpoint를 추가하고 React dashboard route를 연결했다.
- 2026-06-23: `api` 컨테이너와 test DB의 `pg_trgm` extension을 보정한 뒤 observer 테스트, web build, agent audit을 통과했다.
- 2026-06-23: 사용자 확인에 따라 Line은 SDWT 선택까지만 사용하고 T/K-IN Prevent process/step/matrix 조회 scope에서 제거했다.
- 2026-06-23: `TIP현황`을 ESOP Dashboard 내부 route로 이동하고 `/observer/tkin-prevent` 호환 route를 제거했다.
- 2026-06-23: 사용자 확인에 따라 matrix 표시 방향을 `ppid = 컬럼`, `eqp_id-chamber_id = 행`으로 전치했다.
- 2026-06-23: ESOP line selector와 `account_affiliation.line/user_sdwt_prod` 기반 드릴다운으로 전환하는 작업을 시작했다.
- 2026-06-23: T/K Prevent 전용 PRC endpoint와 frontend account affiliation drilldown 전환을 완료하고 backend/frontend/docs 검증을 통과했다.
- 2026-06-23: T/K Prevent query 계약을 `userSdwtProd`로 명확히 하고 PRC 후보 기준을 `station_master.prc_group_lookup`으로 정정했다.
- 2026-06-29: matrix cell hover 시 `tkin_prevent_comment`를 표시하도록 matrix 응답과 frontend cell tooltip을 확장했다.
