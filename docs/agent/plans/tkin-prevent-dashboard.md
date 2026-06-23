# ExecPlan: tkin prevent dashboard

## 목표
- `m_tkin_prevent` 데이터를 observer와 유사한 drilldown 조건으로 조회하는 대시보드를 추가한다.
- 라인, SDWT, PRC group, process_id, step_seq 선택 후 `ppid` 행과 `eqp_id-tkin_prevent_chamber_id` 컬럼으로 matrix를 표시한다.

## 현재 상태
- `api.observer`는 `mes_line_mapping_info`와 `station_master` 기준의 라인/SDWT/PRC dropdown API를 이미 제공한다.
- `api.data_movement.m_tkin_prevent`는 적재 모델과 최근 load-job selector만 있고 화면 조회용 selector는 없다.
- `apps/web/src/features/observer`는 route, API client, React Query hook, observer page 구조를 갖고 있다.

## 범위
- 수정할 영역: `api.observer` selector/view/url/test, `apps/web/src/features/observer` API/hook/page/route.
- 수정하지 않을 영역: DB schema, data movement loader, env/compose mount, 기존 observer timeline 동작.

## 설계
- 기존 observer 라인/SDWT/PRC endpoint를 재사용한다.
- 신규 API:
  - `GET /api/v1/observer/tkin-prevent/processes?prcGroup=...`
  - `GET /api/v1/observer/tkin-prevent/step-seqs?prcGroup=...&processId=...`
  - `GET /api/v1/observer/tkin-prevent/matrix?prcGroup=...&processId=...&stepSeq=...`
- PRC group은 `station_master.prc_group_lookup`으로 필터링하고, 해당 row들의 `ch_main`을 `m_tkin_prevent.eqp_id`와 매칭한다.
- cell 값은 `DOING`이면 `DOING`, `PREVENT`이면 `registration_level(tkin_restrc_lot_count/tkin_lot_count)`, `LEVEL2/LEVEL3`이면 `registration_level(level2_restrc_lot_count/tkin_restrc_lot_count/tkin_lot_count)`로 변환한다.
- Migration/env/auth 변경은 없다.

## 실행 단계
- [x] API selector와 endpoint 추가
- [x] selector/view 테스트 추가
- [x] React API/hook/page/route 추가
- [x] 검증 명령 실행 및 결과 기록

## 검증
- [x] `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer --keepdb`
- [x] `npm run web:build`
- [x] `npm run agent:audit`

## 위험과 대응
- 위험: 실제 데이터에서 동일 cell에 다중 row가 있을 수 있다.
- 대응: API에서 중복 제거 후 배열로 내려주고 UI에서 줄 단위로 표시한다.
- 위험: `tkin_restc_lot_count` 명칭과 모델 필드 `tkin_restrc_lot_count` 철자가 다르다.
- 대응: 현재 모델 필드명 `tkin_restrc_lot_count`를 사용한다.

## 진행 기록
- 2026-06-23: observer 기준정보 API 재사용과 `m_tkin_prevent` matrix 신규 endpoint 추가 방향으로 계획을 작성했다.
- 2026-06-23: observer API에 `tkin-prevent` process/step/matrix endpoint를 추가하고 React dashboard route를 연결했다.
- 2026-06-23: `api` 컨테이너와 test DB의 `pg_trgm` extension을 보정한 뒤 observer 테스트, web build, agent audit을 통과했다.
